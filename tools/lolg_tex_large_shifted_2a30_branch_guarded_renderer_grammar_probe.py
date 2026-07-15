#!/usr/bin/env python3
"""Probe command grammar for the guarded shifted 0x2a30 branch renderer."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_large_shifted_2a30_branch_bounded_family_probe import catalog_payloads, key_for
try:
    from trace_te_stream import trace_payload
except ModuleNotFoundError as exc:
    OPTIONAL_IMPORT_ERROR = exc
    trace_payload = None
else:
    OPTIONAL_IMPORT_ERROR = None


DEFAULT_OUTPUT = Path("output/tex_large_shifted_2a30_branch_guarded_renderer_grammar_probe")
DEFAULT_ROUTE_SUMMARY = Path("output/tex_large_shifted_2a30_branch_start_guard_route/summary.csv")
DEFAULT_ROUTE_ROWS = Path("output/tex_large_shifted_2a30_branch_start_guard_route/routes.csv")
DEFAULT_TRACE_CANDIDATES = Path("output/tex_large_shifted_2a30_branch_selector_probe/renderer_trace.csv")
DEFAULT_SUPPORT_TRACE_CANDIDATES = Path("output/tex_large_shifted_2a30_branch_trace_probe/candidates.csv")
DEFAULT_BOUNDED_FAMILY = Path("output/tex_large_shifted_2a30_branch_bounded_family_probe/family.csv")
DEFAULT_CATALOG = Path("reports/te_resources.tsv")

HIGH_ARG2_SIGNATURES = {0xE0, 0xFC, 0xFD, 0xFE, 0xFF}

SUMMARY_FIELDNAMES = [
    "scope",
    "route_branch_start_guard_rows",
    "route_renderer_blocked_rows",
    "trace_candidate_rows",
    "target_archive_tag",
    "target_pcx_name",
    "target_rank",
    "target_start",
    "target_mode",
    "target_score",
    "target_fingerprint",
    "target_cmd20_rows",
    "target_sig_skip_rows",
    "target_sig_high_arg2_skip_rows",
    "target_sig_zero_skip_rows",
    "target_sig_noop_rows",
    "target_sig_high_arg2_values",
    "target_sig_high_arg2_y_span",
    "target_sig_high_arg2_y_bands",
    "support_rank1_rows",
    "support_rank1_sig_high_arg2_skip_max",
    "support_rank1_sig_zero_skip_max",
    "support_any_sig_high_arg2_skip_max",
    "support_any_sig_zero_skip_max",
    "best_plain_sig_score_delta",
    "best_arg2_safe_score_delta",
    "best_op4_arg2_safe_score_delta",
    "command_window_rows",
    "class_rows",
    "grammar_candidate_rows",
    "issue_rows",
    "grammar_verdict",
    "next_action",
]

COMMAND_FIELDNAMES = [
    "role",
    "archive_tag",
    "pcx_name",
    "rank",
    "mode",
    "start",
    "event_index",
    "stream_pos",
    "x",
    "y",
    "y_band8",
    "byte_hex",
    "action",
    "cmd_class",
    "skip",
    "arg1_hex",
    "arg2_hex",
    "arg3_hex",
    "arg2_signed",
    "x_after",
    "y_after",
    "next8",
]

CLASS_FIELDNAMES = [
    "role",
    "archive_tag",
    "pcx_name",
    "rank",
    "mode",
    "cmd_class",
    "count",
    "first_y",
    "last_y",
    "y_bands",
    "arg2_values",
    "arg1_min",
    "arg1_max",
]

GRAMMAR_FIELDNAMES = [
    "candidate_id",
    "condition",
    "target_rows",
    "support_rank1_max_rows",
    "support_any_max_rows",
    "score_delta_reference",
    "verdict",
    "next_probe",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_text(value: str | int | None, default: int = 0) -> int:
    try:
        return int(str(value), 0) if value not in (None, "") else default
    except ValueError:
        return default


def float_text(value: str | float | None, default: float = 0.0) -> float:
    try:
        return float(str(value)) if value not in (None, "") else default
    except ValueError:
        return default


def hex_byte(value: object) -> str:
    if value in (None, ""):
        return ""
    return f"{int(value):02x}"


def signed_byte(value: int | None) -> str:
    if value is None:
        return ""
    signed = value - 256 if value >= 128 else value
    return str(signed)


def compact_counter(counter: Counter[str], *, limit: int = 8) -> str:
    return "|".join(f"{key}:{count}" for key, count in counter.most_common(limit))


def same_trace_candidate(row: dict[str, str], target_trace: dict[str, str]) -> bool:
    return (
        row.get("archive_tag", "") == target_trace.get("archive_tag", "")
        and row.get("pcx_name", "").lower() == target_trace.get("pcx_name", "").lower()
        and row.get("rank", "") == target_trace.get("rank", "")
        and row.get("mode", "") == target_trace.get("mode", "")
        and row.get("extra", "") == target_trace.get("extra", "")
    )


def role_for(row: dict[str, str], target_key: tuple[str, str], target_trace: dict[str, str]) -> str:
    key = key_for(row.get("archive_tag", ""), row.get("pcx_name", ""))
    if key == target_key:
        return "target" if same_trace_candidate(row, target_trace) else "target_variant"
    if int_text(row.get("rank")) == 1:
        return "support_rank1"
    return "support_any"


def classify_cmd20(event: dict[str, object]) -> str:
    action = str(event.get("action", ""))
    arg1 = event.get("arg1")
    arg2 = event.get("arg2")
    arg3 = event.get("arg3")
    if action == "sig_skip":
        if (arg1, arg2, arg3) == (0, 0, 0):
            return "sig_zero_skip"
        if isinstance(arg2, int) and arg2 in HIGH_ARG2_SIGNATURES:
            return "sig_high_arg2_skip"
        return "sig_other_skip"
    if action == "sig_noop":
        return "sig_noop_literal_20"
    if action == "skip":
        return "blind_skip"
    return action or "cmd20_other"


def target_key_from_routes(route_rows: list[dict[str, str]], route_summary: dict[str, str]) -> tuple[str, str]:
    for row in route_rows:
        if row.get("branch_guard_id") == "tail0_half_start_guard":
            return key_for(row.get("archive_tag", ""), row.get("pcx_name", ""))
    return key_for(route_summary.get("target_archive_tag", ""), route_summary.get("target_pcx_name", ""))


def best_target_trace_row(trace_rows: list[dict[str, str]], target_key: tuple[str, str]) -> dict[str, str]:
    candidates = [
        row for row in trace_rows if key_for(row.get("archive_tag", ""), row.get("pcx_name", "")) == target_key
    ]
    return min(candidates, key=lambda row: (float_text(row.get("score")), int_text(row.get("rank"))), default={})


def trace_identity(row: dict[str, str]) -> tuple[str, str, str, str, str, str]:
    return (
        row.get("archive_tag", ""),
        row.get("pcx_name", "").lower(),
        row.get("rank", ""),
        row.get("mode", ""),
        row.get("extra", ""),
        row.get("start", ""),
    )


def unique_trace_rows(*row_groups: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str, str, str, str]] = set()
    output: list[dict[str, str]] = []
    for rows in row_groups:
        for row in rows:
            identity = trace_identity(row)
            if identity in seen:
                continue
            seen.add(identity)
            output.append(row)
    return output


def load_payloads(family_rows: list[dict[str, str]], catalog: Path) -> dict[tuple[str, str], bytes]:
    return catalog_payloads(
        catalog,
        [{"level": row.get("archive_tag", ""), "name": row.get("pcx_name", "")} for row in family_rows],
    )


def marker_lookup(family_rows: list[dict[str, str]]) -> dict[tuple[str, str], int]:
    return {
        key_for(row.get("archive_tag", ""), row.get("pcx_name", "")): int_text(row.get("marker_pos"), -1)
        for row in family_rows
    }


def trace_start(row: dict[str, str], markers: dict[tuple[str, str], int]) -> int:
    start = int_text(row.get("start"), -1)
    if start >= 0:
        return start
    key = key_for(row.get("archive_tag", ""), row.get("pcx_name", ""))
    marker = markers.get(key, -1)
    if marker >= 0 and row.get("extra", "") != "":
        return marker + int_text(row.get("extra"))
    return -1


def trace_command_rows(
    trace_rows: list[dict[str, str]],
    payloads: dict[tuple[str, str], bytes],
    markers: dict[tuple[str, str], int],
    target_key: tuple[str, str],
    target_trace: dict[str, str],
    low: int,
    high: int,
    max_events: int,
) -> tuple[list[dict[str, str]], list[str]]:
    command_rows: list[dict[str, str]] = []
    issues: list[str] = []
    for row in trace_rows:
        key = key_for(row.get("archive_tag", ""), row.get("pcx_name", ""))
        payload = payloads.get(key, b"")
        start = trace_start(row, markers)
        width = int_text(row.get("width"))
        height = int_text(row.get("height"))
        mode = row.get("mode", "")
        if not payload:
            issues.append(f"missing_payload:{key[0]}/{key[1]}")
            continue
        if start < 0 or start >= len(payload) or width <= 0 or height <= 0 or not mode:
            issues.append(f"invalid_trace_row:{key[0]}/{key[1]}:{row.get('rank', '')}")
            continue
        role = role_for(row, target_key, target_trace)
        events = trace_payload(payload[start:], width, height, mode, low, high, max_events)
        for event in events:
            if event.get("kind") not in {"cmd20", "control"}:
                continue
            cmd_class = classify_cmd20(event) if event.get("kind") == "cmd20" else str(event.get("action", ""))
            command_rows.append(
                {
                    "role": role,
                    "archive_tag": row.get("archive_tag", ""),
                    "pcx_name": row.get("pcx_name", ""),
                    "rank": row.get("rank", ""),
                    "mode": mode,
                    "start": str(start),
                    "event_index": str(event.get("event_index", "")),
                    "stream_pos": str(event.get("stream_pos", "")),
                    "x": str(event.get("x", "")),
                    "y": str(event.get("y", "")),
                    "y_band8": str(int(event.get("y") or 0) // 8),
                    "byte_hex": hex_byte(event.get("byte")),
                    "action": str(event.get("action", "")),
                    "cmd_class": cmd_class,
                    "skip": str(event.get("skip", "")),
                    "arg1_hex": hex_byte(event.get("arg1")),
                    "arg2_hex": hex_byte(event.get("arg2")),
                    "arg3_hex": hex_byte(event.get("arg3")),
                    "arg2_signed": signed_byte(event.get("arg2") if isinstance(event.get("arg2"), int) else None),
                    "x_after": str(event.get("x_after", "")),
                    "y_after": str(event.get("y_after", "")),
                    "next8": str(event.get("next8", "")),
                }
            )
    return command_rows, issues


def class_rows(command_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: defaultdict[tuple[str, str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in command_rows:
        if row.get("byte_hex") != "20" and not row.get("cmd_class", "").startswith("marker"):
            continue
        key = (
            row.get("role", ""),
            row.get("archive_tag", ""),
            row.get("pcx_name", ""),
            row.get("rank", ""),
            row.get("mode", ""),
            row.get("cmd_class", ""),
        )
        grouped[key].append(row)
    output = []
    for key, rows in sorted(grouped.items()):
        role, archive, name, rank, mode, cmd_class = key
        ys = [int_text(row.get("y")) for row in rows]
        arg1s = [int_text(row.get("arg1_hex"), -1) for row in rows if row.get("arg1_hex")]
        output.append(
            {
                "role": role,
                "archive_tag": archive,
                "pcx_name": name,
                "rank": rank,
                "mode": mode,
                "cmd_class": cmd_class,
                "count": str(len(rows)),
                "first_y": str(min(ys, default=0)),
                "last_y": str(max(ys, default=0)),
                "y_bands": compact_counter(Counter(row.get("y_band8", "") for row in rows)),
                "arg2_values": compact_counter(Counter(row.get("arg2_hex", "") for row in rows if row.get("arg2_hex"))),
                "arg1_min": "" if not arg1s else f"{min(arg1s):02x}",
                "arg1_max": "" if not arg1s else f"{max(arg1s):02x}",
            }
        )
    return output


def best_delta(rows: list[dict[str, str]], predicate) -> str:
    values = [float_text(row.get("score_delta_vs_best")) for row in rows if predicate(row)]
    if not values:
        return ""
    return f"{min(values):.4f}"


def count_class(rows: list[dict[str, str]], role: str, cmd_class: str, rank1_only: bool = False) -> int:
    counts = []
    grouped: defaultdict[tuple[str, str, str], int] = defaultdict(int)
    for row in rows:
        role_match = row.get("role") == role
        if role == "support_any":
            role_match = row.get("role") in {"support_rank1", "support_any"}
        if not role_match or row.get("cmd_class") != cmd_class:
            continue
        if rank1_only and int_text(row.get("rank")) != 1:
            continue
        grouped[(row.get("archive_tag", ""), row.get("pcx_name", ""), row.get("rank", ""))] += 1
    counts = list(grouped.values())
    return max(counts, default=0)


def grammar_rows(
    command_rows: list[dict[str, str]],
    target_trace: dict[str, str],
    trace_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    target_high = count_class(command_rows, "target", "sig_high_arg2_skip")
    target_zero = count_class(command_rows, "target", "sig_zero_skip")
    support_rank1_high = count_class(command_rows, "support_rank1", "sig_high_arg2_skip", rank1_only=True)
    support_any_high = count_class(command_rows, "support_any", "sig_high_arg2_skip")
    support_rank1_zero = count_class(command_rows, "support_rank1", "sig_zero_skip", rank1_only=True)
    plain_delta = best_delta(trace_rows, lambda row: row.get("mode", "").startswith("cmd20_sig_skip"))
    arg2_delta = best_delta(
        trace_rows,
        lambda row: row.get("mode", "").startswith("cmd20_arg2_") and "safe_dy" in row.get("mode", ""),
    )
    if target_high and not support_rank1_high and float_text(arg2_delta, 99.0) > 5.0:
        verdict = "target_only_high_arg2_skip_cluster_needs_guarded_validation"
        next_probe = "validate skip-only high-arg2 cmd20 cluster for guarded 0x2a30 extra64 renderer"
    else:
        verdict = "renderer_grammar_still_ambiguous"
        next_probe = "broaden guarded 0x2a30 renderer command grammar evidence"
    return [
        {
            "candidate_id": "cmd20_sig_high_arg2_skip_only",
            "condition": "byte20 with arg2 in e0/fc/fd/fe/ff is skipped only, no cursor move",
            "target_rows": str(target_high),
            "support_rank1_max_rows": str(support_rank1_high),
            "support_any_max_rows": str(support_any_high),
            "score_delta_reference": f"plain_sig={plain_delta};arg2_safe={arg2_delta};target_rank={target_trace.get('rank', '')}",
            "verdict": verdict,
            "next_probe": next_probe,
        },
        {
            "candidate_id": "cmd20_sig_zero_skip",
            "condition": "byte20 followed by 00 00 00 is skipped only",
            "target_rows": str(target_zero),
            "support_rank1_max_rows": str(support_rank1_zero),
            "support_any_max_rows": str(count_class(command_rows, "support_any", "sig_zero_skip")),
            "score_delta_reference": f"plain_sig={plain_delta}",
            "verdict": "support_pattern_not_target_driver" if not target_zero else "zero_signature_present",
            "next_probe": "keep zero-signature skip as support evidence, not target grammar",
        },
    ]


def build_summary(
    route_summary: dict[str, str],
    trace_rows: list[dict[str, str]],
    target_trace: dict[str, str],
    markers: dict[tuple[str, str], int],
    command_rows: list[dict[str, str]],
    class_rows_out: list[dict[str, str]],
    grammar_rows_out: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    target_commands = [row for row in command_rows if row.get("role") == "target"]
    target_cmd20 = [row for row in target_commands if row.get("byte_hex") == "20"]
    target_high = [row for row in target_cmd20 if row.get("cmd_class") == "sig_high_arg2_skip"]
    target_zero = [row for row in target_cmd20 if row.get("cmd_class") == "sig_zero_skip"]
    target_noop = [row for row in target_cmd20 if row.get("cmd_class") == "sig_noop_literal_20"]
    high_ys = [int_text(row.get("y")) for row in target_high]
    support_rank1_rows = {
        (row.get("archive_tag", ""), row.get("pcx_name", ""))
        for row in trace_rows
        if key_for(row.get("archive_tag", ""), row.get("pcx_name", ""))
        != key_for(target_trace.get("archive_tag", ""), target_trace.get("pcx_name", ""))
        and int_text(row.get("rank")) == 1
    }
    high_arg2_values = compact_counter(Counter(row.get("arg2_hex", "") for row in target_high if row.get("arg2_hex")))
    verdict = grammar_rows_out[0].get("verdict", "renderer_grammar_still_ambiguous") if grammar_rows_out else "renderer_grammar_still_ambiguous"
    next_action = (
        grammar_rows_out[0].get("next_probe", "broaden guarded 0x2a30 renderer command grammar evidence")
        if grammar_rows_out
        else "broaden guarded 0x2a30 renderer command grammar evidence"
    )
    if issues:
        verdict = "guarded_renderer_grammar_probe_issues"
        next_action = "fix guarded 0x2a30 renderer grammar probe inputs"
    return {
        "scope": "total",
        "route_branch_start_guard_rows": route_summary.get("branch_start_guard_rows", "0"),
        "route_renderer_blocked_rows": route_summary.get("branch_renderer_blocked_rows", "0"),
        "trace_candidate_rows": str(len(trace_rows)),
        "target_archive_tag": target_trace.get("archive_tag", ""),
        "target_pcx_name": target_trace.get("pcx_name", ""),
        "target_rank": target_trace.get("rank", ""),
        "target_start": str(trace_start(target_trace, markers)) if target_trace else "",
        "target_mode": target_trace.get("mode", ""),
        "target_score": target_trace.get("score", ""),
        "target_fingerprint": target_trace.get("fingerprint", ""),
        "target_cmd20_rows": str(len(target_cmd20)),
        "target_sig_skip_rows": str(len(target_high) + len(target_zero)),
        "target_sig_high_arg2_skip_rows": str(len(target_high)),
        "target_sig_zero_skip_rows": str(len(target_zero)),
        "target_sig_noop_rows": str(len(target_noop)),
        "target_sig_high_arg2_values": high_arg2_values,
        "target_sig_high_arg2_y_span": "" if not high_ys else f"{min(high_ys)}-{max(high_ys)}",
        "target_sig_high_arg2_y_bands": compact_counter(Counter(row.get("y_band8", "") for row in target_high)),
        "support_rank1_rows": str(len(support_rank1_rows)),
        "support_rank1_sig_high_arg2_skip_max": str(
            count_class(command_rows, "support_rank1", "sig_high_arg2_skip", rank1_only=True)
        ),
        "support_rank1_sig_zero_skip_max": str(
            count_class(command_rows, "support_rank1", "sig_zero_skip", rank1_only=True)
        ),
        "support_any_sig_high_arg2_skip_max": str(count_class(command_rows, "support_any", "sig_high_arg2_skip")),
        "support_any_sig_zero_skip_max": str(count_class(command_rows, "support_any", "sig_zero_skip")),
        "best_plain_sig_score_delta": best_delta(
            trace_rows,
            lambda row: row.get("mode", "").startswith("cmd20_sig_skip"),
        ),
        "best_arg2_safe_score_delta": best_delta(
            trace_rows,
            lambda row: row.get("mode", "").startswith("cmd20_arg2_") and "safe_dy" in row.get("mode", ""),
        ),
        "best_op4_arg2_safe_score_delta": best_delta(
            trace_rows,
            lambda row: row.get("mode", "").startswith("op4_cmd20_arg2_") and "safe_dy" in row.get("mode", ""),
        ),
        "command_window_rows": str(len(command_rows)),
        "class_rows": str(len(class_rows_out)),
        "grammar_candidate_rows": str(len(grammar_rows_out)),
        "issue_rows": str(len(issues)),
        "grammar_verdict": verdict,
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
    class_rows_out: list[dict[str, str]],
    grammar_rows_out: list[dict[str, str]],
    command_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "classes": class_rows_out,
        "grammar": grammar_rows_out,
        "commands": command_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("command_classes.csv", output_dir / "command_classes.csv"),
            ("grammar_candidates.csv", output_dir / "grammar_candidates.csv"),
            ("command_windows.csv", output_dir / "command_windows.csv"),
        )
    )
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
<p class="muted">Command grammar evidence for the tail0/2 guarded extra64 branch renderer. Evidence only.</p>
<p>{links}</p>
<h2>Summary</h2>
{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Grammar Candidates</h2>
{render_table(grammar_rows_out, GRAMMAR_FIELDNAMES)}
<h2>Command Classes</h2>
{render_table(class_rows_out, CLASS_FIELDNAMES)}
<h2>Command Windows</h2>
{render_table(command_rows, COMMAND_FIELDNAMES)}
</main>
<script>const TEX_LARGE_SHIFTED_2A30_BRANCH_GUARDED_RENDERER_GRAMMAR_PROBE = {data_json};</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[str]]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    route_summary = (read_csv(args.route_summary) or [{}])[0]
    route_rows = read_csv(args.route_rows)
    renderer_trace_rows = read_csv(args.trace_candidates)
    support_trace_rows = read_csv(args.support_trace_candidates)
    trace_rows = unique_trace_rows(renderer_trace_rows, support_trace_rows)
    family_rows = read_csv(args.bounded_family)
    if not route_summary:
        issues.append("missing_route_summary")
    if not route_rows and route_summary.get("branch_start_guard_rows") not in ("", "0"):
        issues.append("missing_route_rows")
    if not renderer_trace_rows and route_summary.get("branch_renderer_blocked_rows") not in ("", "0"):
        issues.append("missing_trace_candidates")
    if not support_trace_rows and route_summary.get("branch_renderer_blocked_rows") not in ("", "0"):
        issues.append("missing_support_trace_candidates")
    if not family_rows and route_summary.get("branch_start_guard_rows") not in ("", "0"):
        issues.append("missing_bounded_family")
    if (
        route_summary.get("branch_start_guard_rows") in ("", "0")
        and not renderer_trace_rows
        and not support_trace_rows
        and not family_rows
    ):
        target_trace: dict[str, str] = {}
        markers: dict[tuple[str, str], int] = {}
        command_rows: list[dict[str, str]] = []
        class_rows_out: list[dict[str, str]] = []
        grammar_rows_out: list[dict[str, str]] = []
        summary = build_summary(
            route_summary,
            trace_rows,
            target_trace,
            markers,
            command_rows,
            class_rows_out,
            grammar_rows_out,
            issues,
        )
        write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
        write_csv(args.output / "command_windows.csv", COMMAND_FIELDNAMES, command_rows)
        write_csv(args.output / "command_classes.csv", CLASS_FIELDNAMES, class_rows_out)
        write_csv(args.output / "grammar_candidates.csv", GRAMMAR_FIELDNAMES, grammar_rows_out)
        (args.output / "index.html").write_text(
            build_html(summary, class_rows_out, grammar_rows_out, command_rows, args.output, args.title),
            encoding="utf-8",
        )
        return summary, issues
    if OPTIONAL_IMPORT_ERROR is not None:
        raise OPTIONAL_IMPORT_ERROR
    target_key = target_key_from_routes(route_rows, route_summary)
    target_trace = best_target_trace_row(renderer_trace_rows or trace_rows, target_key)
    if not target_trace:
        issues.append(f"missing_target_trace:{target_key[0]}/{target_key[1]}")
    payloads = load_payloads(family_rows, args.catalog)
    markers = marker_lookup(family_rows)
    command_rows, trace_issues = trace_command_rows(
        trace_rows,
        payloads,
        markers,
        target_key,
        target_trace,
        args.low,
        args.high,
        args.max_events,
    )
    issues.extend(trace_issues)
    class_rows_out = class_rows(command_rows)
    grammar_rows_out = grammar_rows(command_rows, target_trace, renderer_trace_rows or trace_rows)
    summary = build_summary(
        route_summary,
        trace_rows,
        target_trace,
        markers,
        command_rows,
        class_rows_out,
        grammar_rows_out,
        issues,
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "command_windows.csv", COMMAND_FIELDNAMES, command_rows)
    write_csv(args.output / "command_classes.csv", CLASS_FIELDNAMES, class_rows_out)
    write_csv(args.output / "grammar_candidates.csv", GRAMMAR_FIELDNAMES, grammar_rows_out)
    (args.output / "index.html").write_text(
        build_html(summary, class_rows_out, grammar_rows_out, command_rows, args.output, args.title),
        encoding="utf-8",
    )
    return summary, issues


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe command grammar for guarded shifted 0x2a30 branch renderer candidates."
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--route-summary", type=Path, default=DEFAULT_ROUTE_SUMMARY)
    parser.add_argument("--route-rows", type=Path, default=DEFAULT_ROUTE_ROWS)
    parser.add_argument("--trace-candidates", type=Path, default=DEFAULT_TRACE_CANDIDATES)
    parser.add_argument("--support-trace-candidates", type=Path, default=DEFAULT_SUPPORT_TRACE_CANDIDATES)
    parser.add_argument("--bounded-family", type=Path, default=DEFAULT_BOUNDED_FAMILY)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--low", type=lambda value: int(value, 0), default=0x30)
    parser.add_argument("--high", type=lambda value: int(value, 0), default=0xBF)
    parser.add_argument("--max-events", type=int, default=20000)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Large Shifted 2a30 Branch Guarded Renderer Grammar Probe",
    )
    args = parser.parse_args()

    summary, issues = write_report(args)
    print(f"Target high-arg2 sig skips: {summary['target_sig_high_arg2_skip_rows']}")
    print(f"Support rank1 high-arg2 sig skip max: {summary['support_rank1_sig_high_arg2_skip_max']}")
    print(f"Best arg2 safe score delta: {summary['best_arg2_safe_score_delta']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Grammar verdict: {summary['grammar_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")
    if issues:
        print("Issues: " + "; ".join(issues))


if __name__ == "__main__":
    main()
