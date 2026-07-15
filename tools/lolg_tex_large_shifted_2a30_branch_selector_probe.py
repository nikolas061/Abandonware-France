#!/usr/bin/env python3
"""Probe pre-render selector evidence for the shifted 0x2a30 branch target."""

from __future__ import annotations

import argparse
import html
import json
import os
from collections import Counter, defaultdict
from pathlib import Path

try:
    from analyze_te_pcx_payloads import bounded_payload, load_rows
    from trace_te_stream import trace_payload
except ModuleNotFoundError as exc:
    OPTIONAL_IMPORT_ERROR = exc
    bounded_payload = None
    load_rows = None
    trace_payload = None
else:
    OPTIONAL_IMPORT_ERROR = None
from lolg_tex_large_shifted_2a30_branch_trace_probe import (
    classify_fingerprint,
    fmt_ratio,
)
from lolg_tex_large_shifted_2a30_branch_bounded_family_probe import (
    float_text,
    int_text,
    key_for,
    read_csv,
    write_csv,
)

DEFAULT_OUTPUT = Path("output/tex_large_shifted_2a30_branch_selector_probe")
DEFAULT_RENDERER_CANDIDATES = Path("output/tex_large_shifted_2a30_branch_renderer_probe/candidates.csv")
DEFAULT_RENDERER_SUMMARY = Path("output/tex_large_shifted_2a30_branch_renderer_probe/summary.csv")
DEFAULT_TRACE_SUMMARY = Path("output/tex_large_shifted_2a30_branch_trace_probe/summary.csv")
DEFAULT_TRACE_CANDIDATES = Path("output/tex_large_shifted_2a30_branch_trace_probe/candidates.csv")
DEFAULT_BOUNDED_FAMILY = Path("output/tex_large_shifted_2a30_branch_bounded_family_probe/family.csv")
DEFAULT_CATALOG = Path("reports/te_resources.tsv")
DEFAULT_FEATURES = Path("reports/te_decoder_features.tsv")

SUMMARY_FIELDNAMES = [
    "scope",
    "renderer_candidate_rows",
    "renderer_best_score",
    "renderer_best_mode",
    "renderer_best_extra",
    "trace_support_rank1_fingerprints",
    "trace_support_any_fingerprints",
    "target_best_rank",
    "target_best_score",
    "target_best_mode",
    "target_best_extra",
    "target_best_fingerprint",
    "target_rank1_supported_rows",
    "target_any_supported_rows",
    "target_near_any_supported_rows",
    "target_near_rank1_supported_rows",
    "target_supported_command_rows",
    "best_rank1_supported_fingerprint",
    "best_rank1_supported_rank",
    "best_rank1_supported_score",
    "best_rank1_supported_delta",
    "best_any_supported_fingerprint",
    "best_any_supported_rank",
    "best_any_supported_score",
    "best_any_supported_delta",
    "best_supported_command_fingerprint",
    "best_supported_command_rank",
    "best_supported_command_score",
    "best_supported_command_delta",
    "cmd20_sig_sparse_target_rows",
    "filter_like_target_rows",
    "op4_heavy_target_rows",
    "family_prefix_occurrences",
    "exact_prefix_occurrences",
    "target_subprefix_occurrences",
    "target_subprefix_cross_pcx_support",
    "issue_rows",
    "visual_status",
    "next_action",
]

TRACE_FIELDNAMES = [
    "rank",
    "archive_tag",
    "pcx_name",
    "branch_key",
    "mode",
    "extra",
    "width",
    "height",
    "score",
    "score_delta_vs_best",
    "fingerprint",
    "support_rank1_fingerprint",
    "support_any_fingerprint",
    "command_bearing",
    "near_score",
    "events",
    "pixels",
    "trace_fill_ratio",
    "cmd20",
    "op4",
    "control",
    "ignored_low",
    "ignored_high",
    "taken_commands",
    "command_density",
    "cmd20_sig_skip",
    "cmd20_sig_noop",
    "op4_small_skip",
    "markerknown_skip",
    "first_cmd20_pos",
    "first_op4_pos",
    "first_control_pos",
    "final_x",
    "final_y",
]

FINGERPRINT_FIELDNAMES = [
    "fingerprint",
    "target_rows",
    "best_rank",
    "best_score",
    "best_delta",
    "best_mode",
    "best_extra",
    "support_rank1",
    "support_any",
    "command_bearing",
]

PREFIX_FIELDNAMES = [
    "archive_tag",
    "pcx_name",
    "offset",
    "is_family_row",
    "is_target",
    "known_mode",
    "known_width",
    "known_score",
    "pre4_hex",
    "prefix5_hex",
    "post5_10_hex",
    "post10_14_hex",
    "post14_18_hex",
    "head32_hex",
]


def catalog_payloads(catalog: Path) -> dict[tuple[str, str], bytes]:
    payloads: dict[tuple[str, str], bytes] = {}
    for row in load_rows(catalog):
        if row.get("ext") != ".pcx" or row.get("name", "").lower() == "palette.pcx":
            continue
        key = key_for(row["source_path"].parent.name, row.get("name", ""))
        payloads[key] = bounded_payload(row)
    return payloads


def feature_lookup(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    rows = {}
    for row in read_csv(path, delimiter="\t"):
        rows[key_for(row.get("level", ""), row.get("name", ""))] = row
    return rows


def sorted_unique(values: list[str]) -> str:
    return "|".join(sorted({value for value in values if value}))


def first_pos(events: list[dict[str, object]], kind: str) -> str:
    for event in events:
        if event.get("kind") == kind:
            return str(event.get("stream_pos", ""))
    return ""


def is_command_bearing(fingerprint: str) -> bool:
    return fingerprint not in {"filter_like"}


def trace_renderer_candidates(
    renderer_rows: list[dict[str, str]],
    payload: bytes,
    marker_pos: int,
    support_rank1: set[str],
    support_any: set[str],
    low: int,
    high: int,
    max_events: int,
    near_delta: float,
) -> list[dict[str, str]]:
    best_score = min((float_text(row.get("score")) for row in renderer_rows), default=0.0)
    output = []
    for row in renderer_rows:
        extra = int_text(row.get("extra"), 0)
        start = marker_pos + extra
        width = int_text(row.get("width"))
        height = int_text(row.get("height"))
        mode = row.get("mode", "")
        events = list(trace_payload(payload[start:], width, height, mode, low, high, max_events))
        kind_counts: Counter[str] = Counter(str(event["kind"]) for event in events)
        action_counts: Counter[tuple[str, str]] = Counter(
            (str(event["kind"]), str(event["action"])) for event in events
        )
        taken = sum(
            1
            for event in events
            if event["kind"] in {"cmd20", "op4", "control"}
            and (int(event.get("skip") or 0) > 0 or str(event.get("action", "")).endswith("advance"))
        )
        pixels = sum(int(event["emit"]) for event in events)
        fingerprint = classify_fingerprint(action_counts, kind_counts, taken)
        score = float_text(row.get("score"))
        delta = score - best_score
        last = events[-1] if events else {}
        output.append(
            {
                "rank": row.get("rank", ""),
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "branch_key": row.get("branch_key", ""),
                "mode": mode,
                "extra": row.get("extra", ""),
                "width": row.get("width", ""),
                "height": row.get("height", ""),
                "score": row.get("score", ""),
                "score_delta_vs_best": f"{delta:.4f}",
                "fingerprint": fingerprint,
                "support_rank1_fingerprint": "yes" if fingerprint in support_rank1 else "no",
                "support_any_fingerprint": "yes" if fingerprint in support_any else "no",
                "command_bearing": "yes" if is_command_bearing(fingerprint) else "no",
                "near_score": "yes" if delta <= near_delta else "no",
                "events": str(len(events)),
                "pixels": str(pixels),
                "trace_fill_ratio": fmt_ratio(pixels, width * height),
                "cmd20": str(kind_counts.get("cmd20", 0)),
                "op4": str(kind_counts.get("op4", 0)),
                "control": str(kind_counts.get("control", 0)),
                "ignored_low": str(kind_counts.get("ignored_low", 0)),
                "ignored_high": str(kind_counts.get("ignored_high", 0)),
                "taken_commands": str(taken),
                "command_density": fmt_ratio(taken, len(events)),
                "cmd20_sig_skip": str(action_counts.get(("cmd20", "sig_skip"), 0)),
                "cmd20_sig_noop": str(action_counts.get(("cmd20", "sig_noop"), 0)),
                "op4_small_skip": str(action_counts.get(("op4", "small_skip"), 0)),
                "markerknown_skip": str(action_counts.get(("control", "markerknown_skip"), 0)),
                "first_cmd20_pos": first_pos(events, "cmd20"),
                "first_op4_pos": first_pos(events, "op4"),
                "first_control_pos": first_pos(events, "control"),
                "final_x": str(last.get("x_after", "")),
                "final_y": str(last.get("y_after", "")),
            }
        )
    return output


def best_row(rows: list[dict[str, str]]) -> dict[str, str]:
    return min(rows, key=lambda row: (float_text(row.get("score")), int_text(row.get("rank"))), default={})


def fingerprint_rows(trace_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in trace_rows:
        grouped[row.get("fingerprint", "")].append(row)
    rows = []
    for fingerprint in sorted(grouped):
        best = best_row(grouped[fingerprint])
        rows.append(
            {
                "fingerprint": fingerprint,
                "target_rows": str(len(grouped[fingerprint])),
                "best_rank": best.get("rank", ""),
                "best_score": best.get("score", ""),
                "best_delta": best.get("score_delta_vs_best", ""),
                "best_mode": best.get("mode", ""),
                "best_extra": best.get("extra", ""),
                "support_rank1": best.get("support_rank1_fingerprint", ""),
                "support_any": best.get("support_any_fingerprint", ""),
                "command_bearing": best.get("command_bearing", ""),
            }
        )
    return rows


def scan_prefixes(
    payloads: dict[tuple[str, str], bytes],
    family_rows: list[dict[str, str]],
    features: dict[tuple[str, str], dict[str, str]],
    family_prefix: bytes,
) -> list[dict[str, str]]:
    family_keys = {key_for(row.get("archive_tag", ""), row.get("pcx_name", "")) for row in family_rows}
    target_keys = {
        key_for(row.get("archive_tag", ""), row.get("pcx_name", ""))
        for row in family_rows
        if row.get("is_target") == "yes"
    }
    rows = []
    for key, payload in sorted(payloads.items()):
        start = 0
        while True:
            pos = payload.find(family_prefix, start)
            if pos < 0:
                break
            feature = features.get(key, {})
            head = payload[pos : pos + 32]
            rows.append(
                {
                    "archive_tag": key[0],
                    "pcx_name": key[1],
                    "offset": str(pos),
                    "is_family_row": "yes" if key in family_keys else "no",
                    "is_target": "yes" if key in target_keys else "no",
                    "known_mode": feature.get("mode", ""),
                    "known_width": feature.get("width", ""),
                    "known_score": feature.get("score", ""),
                    "pre4_hex": payload[max(0, pos - 4) : pos].hex(" "),
                    "prefix5_hex": payload[pos : pos + 5].hex(" "),
                    "post5_10_hex": payload[pos + 5 : pos + 10].hex(" "),
                    "post10_14_hex": payload[pos + 10 : pos + 14].hex(" "),
                    "post14_18_hex": payload[pos + 14 : pos + 18].hex(" "),
                    "head32_hex": head.hex(" "),
                }
            )
            start = pos + 1
    return rows


def build_summary(
    renderer_summary: dict[str, str],
    trace_summary: dict[str, str],
    trace_rows: list[dict[str, str]],
    prefix_rows: list[dict[str, str]],
    support_any: set[str],
    target_payload: bytes,
    target_marker: int,
    near_delta: float,
    issues: list[str],
) -> dict[str, str]:
    best = best_row(trace_rows)
    support_rank1 = set(trace_summary.get("support_rank1_fingerprints", "").split("|")) - {""}
    rank1_supported = [row for row in trace_rows if row.get("fingerprint") in support_rank1]
    any_supported = [row for row in trace_rows if row.get("fingerprint") in support_any]
    near_any_supported = [row for row in any_supported if float_text(row.get("score_delta_vs_best")) <= near_delta]
    near_rank1_supported = [
        row for row in rank1_supported if float_text(row.get("score_delta_vs_best")) <= near_delta
    ]
    supported_command = [
        row for row in rank1_supported if row.get("command_bearing") == "yes"
    ]
    any_supported_command = [
        row for row in any_supported if row.get("command_bearing") == "yes"
    ]
    best_rank1_supported = best_row(rank1_supported)
    best_any_supported = best_row(any_supported)
    best_supported_command = best_row(supported_command or any_supported_command)
    family_prefix = target_payload[target_marker : target_marker + 5].hex(" ")
    exact_prefix = target_payload[target_marker : target_marker + 10].hex(" ")
    target_subprefix = target_payload[target_marker : target_marker + 14].hex(" ")
    exact_prefix_occurrences = sum(
        1
        for row in prefix_rows
        if row.get("prefix5_hex") + " " + row.get("post5_10_hex") == exact_prefix
    )
    target_subprefix_occurrences = sum(
        1
        for row in prefix_rows
        if (
            row.get("prefix5_hex")
            + " "
            + row.get("post5_10_hex")
            + " "
            + row.get("post10_14_hex")
        )
        == target_subprefix
    )
    target_subprefix_cross_support = sum(
        1
        for row in prefix_rows
        if row.get("is_target") != "yes"
        and (
            row.get("prefix5_hex")
            + " "
            + row.get("post5_10_hex")
            + " "
            + row.get("post10_14_hex")
        )
        == target_subprefix
    )
    if issues:
        visual_status = "blocked_selector_probe_issues"
        next_action = "fix shifted 0x2a30 branch selector probe inputs"
    elif not rank1_supported:
        visual_status = "blocked_no_rank1_supported_target_renderer"
        next_action = "derive new renderer candidates for shifted 0x2a30 branch before selector promotion"
    elif not near_rank1_supported and best_supported_command:
        visual_status = "blocked_supported_command_renderer_too_noisy"
        next_action = (
            "derive singleton header semantics for shifted 0x2a30 branch "
            f"{family_prefix}; best rank1-supported command renderer is "
            f"{best_supported_command.get('fingerprint', '')} rank{best_supported_command.get('rank', '')} "
            f"delta {best_supported_command.get('score_delta_vs_best', '')}, while target subprefix "
            f"{target_subprefix} has cross-PCX support {target_subprefix_cross_support}"
        )
    else:
        visual_status = "blocked_selector_needs_visual_review"
        next_action = "review near-score supported shifted 0x2a30 branch renderer before promotion"
    return {
        "scope": "total",
        "renderer_candidate_rows": str(len(trace_rows)),
        "renderer_best_score": renderer_summary.get("best_score", ""),
        "renderer_best_mode": renderer_summary.get("best_mode", ""),
        "renderer_best_extra": renderer_summary.get("best_extra", ""),
        "trace_support_rank1_fingerprints": trace_summary.get("support_rank1_fingerprints", ""),
        "trace_support_any_fingerprints": sorted_unique(list(support_any)),
        "target_best_rank": best.get("rank", ""),
        "target_best_score": best.get("score", ""),
        "target_best_mode": best.get("mode", ""),
        "target_best_extra": best.get("extra", ""),
        "target_best_fingerprint": best.get("fingerprint", ""),
        "target_rank1_supported_rows": str(len(rank1_supported)),
        "target_any_supported_rows": str(len(any_supported)),
        "target_near_any_supported_rows": str(len(near_any_supported)),
        "target_near_rank1_supported_rows": str(len(near_rank1_supported)),
        "target_supported_command_rows": str(len(supported_command)),
        "best_rank1_supported_fingerprint": best_rank1_supported.get("fingerprint", ""),
        "best_rank1_supported_rank": best_rank1_supported.get("rank", ""),
        "best_rank1_supported_score": best_rank1_supported.get("score", ""),
        "best_rank1_supported_delta": best_rank1_supported.get("score_delta_vs_best", ""),
        "best_any_supported_fingerprint": best_any_supported.get("fingerprint", ""),
        "best_any_supported_rank": best_any_supported.get("rank", ""),
        "best_any_supported_score": best_any_supported.get("score", ""),
        "best_any_supported_delta": best_any_supported.get("score_delta_vs_best", ""),
        "best_supported_command_fingerprint": best_supported_command.get("fingerprint", ""),
        "best_supported_command_rank": best_supported_command.get("rank", ""),
        "best_supported_command_score": best_supported_command.get("score", ""),
        "best_supported_command_delta": best_supported_command.get("score_delta_vs_best", ""),
        "cmd20_sig_sparse_target_rows": str(sum(1 for row in trace_rows if row.get("fingerprint") == "cmd20_sig_sparse")),
        "filter_like_target_rows": str(sum(1 for row in trace_rows if row.get("fingerprint") == "filter_like")),
        "op4_heavy_target_rows": str(sum(1 for row in trace_rows if row.get("fingerprint") == "op4_heavy")),
        "family_prefix_occurrences": str(len(prefix_rows)),
        "exact_prefix_occurrences": str(exact_prefix_occurrences),
        "target_subprefix_occurrences": str(target_subprefix_occurrences),
        "target_subprefix_cross_pcx_support": str(target_subprefix_cross_support),
        "issue_rows": str(len(issues)),
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
    fingerprints: list[dict[str, str]],
    trace_rows: list[dict[str, str]],
    prefix_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "fingerprints": fingerprints, "prefixes": prefix_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("renderer_trace.csv", output_dir / "renderer_trace.csv"),
            ("fingerprints.csv", output_dir / "fingerprints.csv"),
            ("prefixes.csv", output_dir / "prefixes.csv"),
        )
    )
    top_trace = sorted(trace_rows, key=lambda row: int_text(row.get("rank")))[:40]
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
<p class="muted">Pre-render selector evidence for the shifted 0x2a30 branch target. No renderer is promoted here.</p>
<p>{links}</p>
<h2>Summary</h2>
{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Fingerprints</h2>
{render_table(fingerprints, FINGERPRINT_FIELDNAMES)}
<h2>Top Renderer Trace Rows</h2>
{render_table(top_trace, TRACE_FIELDNAMES)}
<h2>Prefix Occurrences</h2>
{render_table(prefix_rows, PREFIX_FIELDNAMES)}
</main>
<script>const TEX_LARGE_SHIFTED_2A30_BRANCH_SELECTOR_PROBE = {data_json};</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[str]]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    renderer_rows = read_csv(args.renderer_candidates)
    renderer_summary = (read_csv(args.renderer_summary) or [{}])[0]
    trace_summary = (read_csv(args.trace_summary) or [{}])[0]
    trace_candidates = read_csv(args.trace_candidates)
    family_rows = read_csv(args.bounded_family)
    if not renderer_rows and renderer_summary.get("candidate_rows") not in ("", "0"):
        issues.append("missing_renderer_candidates")
    if not trace_summary:
        issues.append("missing_trace_summary")
    if not trace_candidates and trace_summary.get("trace_candidate_rows") not in ("", "0"):
        issues.append("missing_trace_candidates")
    if not family_rows and trace_summary.get("bounded_family_rows") not in ("", "0"):
        issues.append("missing_family_rows")
    if not renderer_rows and not trace_candidates and not family_rows:
        trace_rows: list[dict[str, str]] = []
        prefix_rows: list[dict[str, str]] = []
        support_any: set[str] = set()
        target_payload = b""
        marker_pos = -1
        fingerprints = fingerprint_rows(trace_rows)
        summary = build_summary(
            renderer_summary,
            trace_summary,
            trace_rows,
            prefix_rows,
            support_any,
            target_payload,
            marker_pos,
            args.near_delta,
            issues,
        )
        write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
        write_csv(args.output / "renderer_trace.csv", TRACE_FIELDNAMES, trace_rows)
        write_csv(args.output / "fingerprints.csv", FINGERPRINT_FIELDNAMES, fingerprints)
        write_csv(args.output / "prefixes.csv", PREFIX_FIELDNAMES, prefix_rows)
        (args.output / "index.html").write_text(
            build_html(summary, fingerprints, trace_rows, prefix_rows, args.output, args.title),
            encoding="utf-8",
        )
        return summary, issues
    if OPTIONAL_IMPORT_ERROR is not None:
        raise OPTIONAL_IMPORT_ERROR
    target_key = key_for(trace_summary.get("target_archive_tag", ""), trace_summary.get("target_pcx_name", ""))
    payloads = catalog_payloads(args.catalog)
    target_payload = payloads.get(target_key, b"")
    if not target_payload:
        issues.append(f"missing_target_payload:{target_key[0]}/{target_key[1]}")
    marker_pos = target_payload.find(bytes.fromhex("2a30")) if target_payload else -1
    if marker_pos < 0:
        issues.append("missing_target_marker_2a30")

    support_rank1 = set(trace_summary.get("support_rank1_fingerprints", "").split("|")) - {""}
    support_any = {
        row.get("fingerprint", "")
        for row in trace_candidates
        if row.get("is_target") != "yes" and row.get("fingerprint")
    }
    trace_rows = []
    prefix_rows = []
    if not issues:
        trace_rows = trace_renderer_candidates(
            renderer_rows,
            target_payload,
            marker_pos,
            support_rank1,
            support_any,
            args.low,
            args.high,
            args.max_events,
            args.near_delta,
        )
        features = feature_lookup(args.features)
        prefix_rows = scan_prefixes(
            payloads,
            family_rows,
            features,
            target_payload[marker_pos : marker_pos + 5],
        )
    fingerprints = fingerprint_rows(trace_rows)
    summary = build_summary(
        renderer_summary,
        trace_summary,
        trace_rows,
        prefix_rows,
        support_any,
        target_payload,
        marker_pos,
        args.near_delta,
        issues,
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "renderer_trace.csv", TRACE_FIELDNAMES, trace_rows)
    write_csv(args.output / "fingerprints.csv", FINGERPRINT_FIELDNAMES, fingerprints)
    write_csv(args.output / "prefixes.csv", PREFIX_FIELDNAMES, prefix_rows)
    (args.output / "index.html").write_text(
        build_html(summary, fingerprints, trace_rows, prefix_rows, args.output, args.title),
        encoding="utf-8",
    )
    return summary, issues


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe selector evidence for shifted 0x2a30 branch candidates.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--renderer-candidates", type=Path, default=DEFAULT_RENDERER_CANDIDATES)
    parser.add_argument("--renderer-summary", type=Path, default=DEFAULT_RENDERER_SUMMARY)
    parser.add_argument("--trace-summary", type=Path, default=DEFAULT_TRACE_SUMMARY)
    parser.add_argument("--trace-candidates", type=Path, default=DEFAULT_TRACE_CANDIDATES)
    parser.add_argument("--bounded-family", type=Path, default=DEFAULT_BOUNDED_FAMILY)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES)
    parser.add_argument("--low", type=lambda value: int(value, 0), default=0x30)
    parser.add_argument("--high", type=lambda value: int(value, 0), default=0xBF)
    parser.add_argument("--max-events", type=int, default=20000)
    parser.add_argument("--near-delta", type=float, default=0.5)
    parser.add_argument("--title", default="Lands of Lore II .tex Large Shifted 2a30 Branch Selector Probe")
    args = parser.parse_args()

    summary, issues = write_report(args)
    print(f"Renderer candidates: {summary['renderer_candidate_rows']}")
    print(f"Target best fingerprint: {summary['target_best_fingerprint']}")
    print(f"Rank1-supported rows: {summary['target_rank1_supported_rows']}")
    print(f"Best rank1-supported: {summary['best_rank1_supported_fingerprint']} delta {summary['best_rank1_supported_delta']}")
    print(f"Target subprefix cross support: {summary['target_subprefix_cross_pcx_support']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Visual status: {summary['visual_status']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")
    if issues:
        print("Issues: " + "; ".join(issues))


if __name__ == "__main__":
    main()
