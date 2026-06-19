#!/usr/bin/env python3
"""Probe body-control grammar families for remaining rejected large .tex segments."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import struct
from collections import Counter, defaultdict
from pathlib import Path

from trace_te_stream import trace_payload


DEFAULT_OUTPUT = Path("output/tex_large_body_control_grammar_probe")
DEFAULT_SEGMENTS = Path("output/tex_large_rejected_decoder_profile/segments.csv")
DEFAULT_REVIEW_CANDIDATES = Path("output/tex_large_unresolved_probe_review/candidates.csv")
DEFAULT_MIX_ENTRY_INDEX = 2
DEFAULT_MAX_EVENTS = 2048

DEFAULT_MODES = [
    "filter",
    "low_skip",
    "zero_skip",
    "cmd20_skip4_markerknown",
    "cmd20_sig_skip4_markerknown",
    "op4_skip2",
    "op4_cmd20_skip4_markerknown",
    "op4_cmd20_sig_skip4_markerknown",
]

SUMMARY_FIELDNAMES = [
    "scope",
    "segment_rows",
    "control_path_groups",
    "shared_2700302b_rows",
    "llse_signature_rows",
    "shifted_2930_rows",
    "trace_candidate_rows",
    "header_offset_rows",
    "terminal_marker_rows",
    "issue_rows",
    "top_control_path",
    "top_trace_fingerprint",
    "next_action",
]

SEGMENT_FIELDNAMES = [
    "segment_id",
    "archive",
    "archive_tag",
    "pcx_name",
    "control_path",
    "body_size",
    "segment_size",
    "body_first_word",
    "head16_hex",
    "tail16_hex",
    "le16_head8",
    "marker_offsets",
    "marker_pairs",
    "candidate_offsets",
    "visual_widths",
    "visual_heights",
    "visual_skips",
    "terminal_marker_offset",
    "terminal_tail_bytes",
    "zero_ratio",
    "low_byte_ratio",
    "op4_candidate_ratio",
    "cmd20_count_64k",
    "issues",
]

FAMILY_FIELDNAMES = [
    "control_path",
    "rows",
    "pcx_names",
    "body_first_words",
    "candidate_offsets",
    "marker_pairs",
    "terminal_marker_rows",
    "best_trace_fingerprint",
    "best_trace_rows",
    "next_probe",
]

TRACE_FIELDNAMES = [
    "segment_id",
    "archive_tag",
    "pcx_name",
    "control_path",
    "offset",
    "offset_reason",
    "mode",
    "width",
    "height",
    "trace_bytes",
    "events",
    "pixels",
    "fill_ratio",
    "cmd20",
    "op4",
    "control",
    "ignored_low",
    "ignored_high",
    "pixel",
    "taken_commands",
    "command_density",
    "final_x",
    "final_y",
    "dominant_actions",
    "fingerprint",
    "issues",
]

KNOWN_MARKER_PAIRS = {
    (0x27, 0x30),
    (0x28, 0x30),
    (0x29, 0x30),
    (0x2A, 0x30),
    (0x2B, 0x30),
    (0x2B, 0x31),
}
TERMINAL_MARKER = b"\x00\x11\x00\x00\x00\x00\x00\x00"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, str], field: str, default: int = 0) -> int:
    raw = row.get(field, "")
    try:
        return int(raw, 0) if raw else default
    except ValueError:
        return default


def ratio(count: int, total: int) -> str:
    return f"{count / max(1, total):.6f}"


def read_mix_entry(path: Path, index: int) -> bytes:
    data = path.read_bytes()
    if len(data) < 6:
        raise ValueError(f"{path}: too small to be a MIX archive")
    count, body_size = struct.unpack_from("<HI", data, 0)
    table_end = 6 + count * 12
    if index < 0 or index >= count or table_end > len(data):
        raise ValueError(f"{path}: invalid MIX entry index {index}")
    _file_id, offset, size = struct.unpack_from("<III", data, 6 + index * 12)
    if offset + size > body_size:
        raise ValueError(f"{path}: entry {index} exceeds declared body size")
    return data[table_end + offset : table_end + offset + size]


def unique_join(values: list[str]) -> str:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            output.append(value)
    return "|".join(output)


def segment_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        row.get("archive", ""),
        row.get("pcx_name", "").lower(),
        row.get("segment_index", ""),
        row.get("body_offset_hex", "") or row.get("body_offset", ""),
    )


def review_candidates_by_segment(rows: list[dict[str, str]]) -> dict[tuple[str, str, str, str], list[dict[str, str]]]:
    output: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        output[segment_key(row)].append(row)
    return output


def marker_pairs(body: bytes, limit: int = 96) -> list[tuple[int, str]]:
    pairs: list[tuple[int, str]] = []
    scan = body[: min(len(body), limit)]
    for offset in range(max(0, len(scan) - 1)):
        pair = (scan[offset], scan[offset + 1])
        if pair in KNOWN_MARKER_PAIRS:
            pairs.append((offset, f"{pair[0]:02x}{pair[1]:02x}"))
    return pairs


def candidate_offsets(body: bytes, control_path: str, pairs: list[tuple[int, str]]) -> list[tuple[int, str]]:
    candidates: dict[int, list[str]] = defaultdict(list)
    for offset, reason in [
        (0, "body_start"),
        (4, "after_head4"),
        (8, "after_head8"),
        (12, "after_head12"),
        (16, "after_head16"),
    ]:
        if 0 <= offset < len(body):
            candidates[offset].append(reason)
    if control_path == "llse_signature" and len(body) > 4:
        candidates[4].append("after_llse")
    for offset, pair in pairs:
        candidates[offset].append(f"marker_{pair}")
        if offset + 2 < len(body):
            candidates[offset + 2].append(f"after_marker_{pair}")
        if offset + 4 < len(body):
            candidates[offset + 4].append(f"after_marker4_{pair}")
    return [(offset, "+".join(reasons)) for offset, reasons in sorted(candidates.items()) if offset < 64]


def le16_head_words(body: bytes, count: int = 8) -> str:
    words = []
    for offset in range(0, min(len(body), count * 2), 2):
        if offset + 1 >= len(body):
            break
        words.append(f"0x{struct.unpack_from('<H', body, offset)[0]:04x}")
    return "|".join(words)


def op4_candidate_count(data: bytes) -> int:
    return sum(1 for value in data if 0x40 <= value <= 0x68 and value % 4 == 0)


def action_fingerprint(action_counts: Counter[tuple[str, str]], kind_counts: Counter[str], taken: int) -> str:
    events = max(1, sum(kind_counts.values()))
    if kind_counts.get("op4", 0) / events >= 0.02:
        return "op4_heavy"
    if action_counts.get(("cmd20", "sig_skip"), 0) or action_counts.get(("cmd20", "sig_noop"), 0):
        return "cmd20_signature"
    if kind_counts.get("cmd20", 0):
        return "cmd20_control"
    if kind_counts.get("control", 0) and taken:
        return "low_control"
    if kind_counts.get("pixel", 0) / events >= 0.8:
        return "pixel_dense"
    return "filter_like"


def dominant_actions(action_counts: Counter[tuple[str, str]], limit: int = 5) -> str:
    return "|".join(f"{kind}:{action}:{count}" for (kind, action), count in action_counts.most_common(limit))


def load_segment_body(row: dict[str, str], payload_cache: dict[Path, bytes], mix_entry_index: int) -> tuple[bytes, list[str]]:
    issues: list[str] = []
    archive = Path(row.get("archive", ""))
    offset = int_value(row, "body_offset")
    size = int_value(row, "body_size")
    try:
        if archive not in payload_cache:
            payload_cache[archive] = read_mix_entry(archive, mix_entry_index)
        payload = payload_cache[archive]
        body = payload[offset : offset + size]
        if len(body) != size:
            issues.append("short_body_read")
        return body, issues
    except Exception as exc:
        return b"", [f"read_failed:{exc}"]


def build_segment_row(
    source: dict[str, str],
    body: bytes,
    body_issues: list[str],
    review_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[tuple[int, str]], list[tuple[int, str]]]:
    pairs = marker_pairs(body)
    offsets = candidate_offsets(body, source.get("control_path", ""), pairs)
    terminal_offset = body.rfind(TERMINAL_MARKER)
    sample = body[: min(len(body), 65536)]
    widths = unique_join([row.get("width", "") for row in sorted(review_rows, key=lambda row: int_value(row, "rank"))])
    heights = unique_join([row.get("height", "") for row in sorted(review_rows, key=lambda row: int_value(row, "rank"))])
    skips = unique_join([row.get("skip", "") for row in sorted(review_rows, key=lambda row: int_value(row, "rank"))])
    issues = list(body_issues)
    if not body:
        issues.append("empty_body")
    if not review_rows:
        issues.append("missing_review_candidates")
    return (
        {
            "segment_id": source.get("segment_id", ""),
            "archive": source.get("archive", ""),
            "archive_tag": source.get("archive_tag", ""),
            "pcx_name": source.get("pcx_name", ""),
            "control_path": source.get("control_path", ""),
            "body_size": str(len(body)),
            "segment_size": source.get("segment_size", ""),
            "body_first_word": source.get("body_first_word", ""),
            "head16_hex": body[:16].hex(),
            "tail16_hex": body[-16:].hex() if body else "",
            "le16_head8": le16_head_words(body),
            "marker_offsets": "|".join(str(offset) for offset, _pair in pairs),
            "marker_pairs": "|".join(f"{offset}:{pair}" for offset, pair in pairs),
            "candidate_offsets": "|".join(f"{offset}:{reason}" for offset, reason in offsets),
            "visual_widths": widths,
            "visual_heights": heights,
            "visual_skips": skips,
            "terminal_marker_offset": str(terminal_offset) if terminal_offset >= 0 else "",
            "terminal_tail_bytes": body[terminal_offset : terminal_offset + len(TERMINAL_MARKER)].hex()
            if terminal_offset >= 0
            else "",
            "zero_ratio": ratio(sample.count(0), len(sample)),
            "low_byte_ratio": ratio(sum(1 for value in sample if value < 0x30), len(sample)),
            "op4_candidate_ratio": ratio(op4_candidate_count(sample), len(sample)),
            "cmd20_count_64k": str(sample.count(0x20)),
            "issues": ";".join(sorted(set(issues))),
        },
        pairs,
        offsets,
    )


def trace_candidate(
    source: dict[str, str],
    body: bytes,
    offset: int,
    offset_reason: str,
    mode: str,
    width: int,
    height: int,
    low: int,
    high: int,
    max_events: int,
) -> dict[str, str]:
    issues: list[str] = []
    if not body:
        issues.append("empty_body")
    if offset < 0 or offset >= len(body):
        issues.append("offset_out_of_body")
        payload = b""
    else:
        payload = body[offset:]
    if width <= 0 or height <= 0:
        issues.append("invalid_dimensions")
    events = list(trace_payload(payload, max(1, width), max(1, height), mode, low, high, max_events)) if not issues else []
    kind_counts: Counter[str] = Counter(str(event["kind"]) for event in events)
    action_counts: Counter[tuple[str, str]] = Counter(
        (str(event["kind"]), str(event["action"])) for event in events
    )
    pixels = sum(int(event.get("emit") or 0) for event in events)
    taken = sum(
        1
        for event in events
        if event.get("kind") in {"cmd20", "op4", "control"}
        and (int(event.get("skip") or 0) > 0 or str(event.get("action", "")).endswith("advance"))
    )
    last = events[-1] if events else {}
    return {
        "segment_id": source.get("segment_id", ""),
        "archive_tag": source.get("archive_tag", ""),
        "pcx_name": source.get("pcx_name", ""),
        "control_path": source.get("control_path", ""),
        "offset": str(offset),
        "offset_reason": offset_reason,
        "mode": mode,
        "width": str(width),
        "height": str(height),
        "trace_bytes": str(len(payload)),
        "events": str(len(events)),
        "pixels": str(pixels),
        "fill_ratio": ratio(pixels, width * height),
        "cmd20": str(kind_counts.get("cmd20", 0)),
        "op4": str(kind_counts.get("op4", 0)),
        "control": str(kind_counts.get("control", 0)),
        "ignored_low": str(kind_counts.get("ignored_low", 0)),
        "ignored_high": str(kind_counts.get("ignored_high", 0)),
        "pixel": str(kind_counts.get("pixel", 0)),
        "taken_commands": str(taken),
        "command_density": ratio(taken, len(events)),
        "final_x": str(last.get("x_after", "")),
        "final_y": str(last.get("y_after", "")),
        "dominant_actions": dominant_actions(action_counts),
        "fingerprint": action_fingerprint(action_counts, kind_counts, taken) if events else "",
        "issues": ";".join(issues),
    }


def trace_rows_for_segment(
    source: dict[str, str],
    body: bytes,
    offsets: list[tuple[int, str]],
    review_rows: list[dict[str, str]],
    modes: list[str],
    low: int,
    high: int,
    max_events: int,
) -> list[dict[str, str]]:
    dimensions: list[tuple[int, int]] = []
    for row in sorted(review_rows, key=lambda item: int_value(item, "rank")):
        width = int_value(row, "width")
        height = int_value(row, "height")
        if width > 0 and height > 0 and (width, height) not in dimensions:
            dimensions.append((width, height))
    if not dimensions:
        dimensions.append((64, 512))
    selected_offsets = offsets[:8]
    rows: list[dict[str, str]] = []
    for offset, reason in selected_offsets:
        for width, height in dimensions[:2]:
            for mode in modes:
                rows.append(trace_candidate(source, body, offset, reason, mode, width, height, low, high, max_events))
    return rows


def build_family_rows(segment_rows: list[dict[str, str]], trace_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_family: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in segment_rows:
        by_family[row.get("control_path", "")].append(row)
    traces_by_family: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in trace_rows:
        if not row.get("issues"):
            traces_by_family[row.get("control_path", "")].append(row)
    output: list[dict[str, str]] = []
    for control_path, rows in sorted(by_family.items(), key=lambda item: (-len(item[1]), item[0])):
        family_traces = traces_by_family.get(control_path, [])
        fingerprint_counts = Counter(row.get("fingerprint", "") for row in family_traces if row.get("fingerprint"))
        best_fingerprint, best_count = ("", 0)
        if fingerprint_counts:
            best_fingerprint, best_count = fingerprint_counts.most_common(1)[0]
        if control_path == "shared_2700302b_header":
            next_probe = "derive shared 0x2700302b header field semantics across 2 large rejected .tex segments"
        elif control_path == "llse_signature":
            next_probe = "decode LLSE signature large .tex body control path"
        elif control_path == "shifted_2930_header":
            next_probe = "probe shifted 0x2930 large .tex body-control header"
        else:
            next_probe = f"probe {control_path or 'unknown'} body-control grammar"
        output.append(
            {
                "control_path": control_path,
                "rows": str(len(rows)),
                "pcx_names": "|".join(sorted(row.get("pcx_name", "") for row in rows if row.get("pcx_name"))),
                "body_first_words": "|".join(
                    sorted(set(row.get("body_first_word", "") for row in rows if row.get("body_first_word")))
                ),
                "candidate_offsets": "|".join(
                    sorted(set(row.get("candidate_offsets", "") for row in rows if row.get("candidate_offsets")))
                ),
                "marker_pairs": "|".join(sorted(set(row.get("marker_pairs", "") for row in rows if row.get("marker_pairs")))),
                "terminal_marker_rows": str(sum(1 for row in rows if row.get("terminal_marker_offset"))),
                "best_trace_fingerprint": best_fingerprint,
                "best_trace_rows": str(best_count),
                "next_probe": next_probe,
            }
        )
    return output


def build_summary(
    segment_rows: list[dict[str, str]],
    family_rows: list[dict[str, str]],
    trace_rows: list[dict[str, str]],
) -> dict[str, str]:
    control_counts = Counter(row.get("control_path", "") for row in segment_rows)
    trace_fingerprints = Counter(row.get("fingerprint", "") for row in trace_rows if row.get("fingerprint") and not row.get("issues"))
    issue_rows = sum(1 for row in segment_rows if row.get("issues")) + sum(1 for row in trace_rows if row.get("issues"))
    top_control_path = control_counts.most_common(1)[0][0] if control_counts else ""
    top_trace = trace_fingerprints.most_common(1)[0][0] if trace_fingerprints else ""
    if issue_rows:
        next_action = "fix large body-control grammar probe issues"
    elif control_counts.get("shared_2700302b_header", 0) >= 2:
        next_action = "derive shared 0x2700302b header field semantics across 2 large rejected .tex segments"
    elif family_rows:
        next_action = family_rows[0].get("next_probe", "review large body-control grammar families")
    else:
        next_action = "no large body-control grammar rows to probe"
    return {
        "scope": "total",
        "segment_rows": str(len(segment_rows)),
        "control_path_groups": str(len(family_rows)),
        "shared_2700302b_rows": str(control_counts.get("shared_2700302b_header", 0)),
        "llse_signature_rows": str(control_counts.get("llse_signature", 0)),
        "shifted_2930_rows": str(control_counts.get("shifted_2930_header", 0)),
        "trace_candidate_rows": str(len(trace_rows)),
        "header_offset_rows": str(sum(1 for row in segment_rows if row.get("candidate_offsets"))),
        "terminal_marker_rows": str(sum(1 for row in segment_rows if row.get("terminal_marker_offset"))),
        "issue_rows": str(issue_rows),
        "top_control_path": top_control_path,
        "top_trace_fingerprint": top_trace,
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


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    try:
        return os.path.relpath(Path(path_text), base_dir)
    except ValueError:
        return str(path_text)


def build_html(
    summary: dict[str, str],
    segment_rows: list[dict[str, str]],
    family_rows: list[dict[str, str]],
    trace_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "segments": segment_rows,
        "families": family_rows,
        "trace_candidates": trace_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f"<a href=\"{html.escape(relative_href(path, output_dir))}\">{html.escape(name)}</a>"
        for name, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("segments.csv", output_dir / "segments.csv"),
            ("families.csv", output_dir / "families.csv"),
            ("trace_candidates.csv", output_dir / "trace_candidates.csv"),
        )
    )
    shared_rows = html.escape(summary["shared_2700302b_rows"])
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
:root {{
  color-scheme: dark; --bg: #101317; --panel: #181d23; --text: #e8edf2; --muted: #98a4b3;
  --accent: #74b8ff; --warn: #f0b35a; --ok: #6fd08c;
}}
body {{ margin: 0; font-family: system-ui, sans-serif; background: var(--bg); color: var(--text); }}
header, main {{ max-width: 1500px; margin: 0 auto; padding: 24px; }}
h1 {{ margin: 0 0 8px; font-size: 26px; }}
h2 {{ margin: 0 0 12px; font-size: 18px; }}
.muted {{ color: var(--muted); }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 20px 0; }}
.stat, .panel {{ background: var(--panel); border: 1px solid #29313b; border-radius: 8px; padding: 14px; }}
.label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
.value {{ font-size: 24px; font-weight: 700; }}
.ok {{ color: var(--ok); }}
.warn {{ color: var(--warn); }}
a {{ color: var(--accent); text-decoration: none; margin-right: 10px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
th, td {{ border-bottom: 1px solid #29313b; padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); position: sticky; top: 0; background: var(--panel); }}
td {{ max-width: 520px; overflow-wrap: anywhere; }}
section {{ margin-bottom: 20px; }}
</style>
</head>
<body>
<header>
  <h1>{html.escape(title)}</h1>
  <div class="muted">Traces candidate control grammars for remaining rejected large .tex bodies.</div>
  <p>{links}</p>
</header>
<main>
  <section class="grid">
    <div class="stat"><div class="label">Segments</div><div class="value">{html.escape(summary['segment_rows'])}</div></div>
    <div class="stat"><div class="label">Control paths</div><div class="value">{html.escape(summary['control_path_groups'])}</div></div>
    <div class="stat"><div class="label">Shared 2700302b</div><div class="value warn">{shared_rows}</div></div>
    <div class="stat"><div class="label">Trace rows</div><div class="value">{html.escape(summary['trace_candidate_rows'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel">
    <h2>Summary</h2>
    {render_table([summary], SUMMARY_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Families</h2>
    {render_table(family_rows, FAMILY_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Segments</h2>
    {render_table(segment_rows, SEGMENT_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Trace candidates</h2>
    {render_table(trace_rows[:400], TRACE_FIELDNAMES)}
  </section>
</main>
<script type="application/json" id="probe-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    segments_path: Path,
    review_candidates_path: Path,
    mix_entry_index: int,
    modes: list[str],
    low: int,
    high: int,
    max_events: int,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    source_rows = read_csv(segments_path)
    review_lookup = review_candidates_by_segment(read_csv(review_candidates_path))
    payload_cache: dict[Path, bytes] = {}
    segment_rows: list[dict[str, str]] = []
    trace_rows: list[dict[str, str]] = []
    for source in source_rows:
        body, issues = load_segment_body(source, payload_cache, mix_entry_index)
        review_rows = review_lookup.get(segment_key(source), [])
        segment_row, _pairs, offsets = build_segment_row(source, body, issues, review_rows)
        segment_rows.append(segment_row)
        trace_rows.extend(trace_rows_for_segment(source, body, offsets, review_rows, modes, low, high, max_events))
    family_rows = build_family_rows(segment_rows, trace_rows)
    summary = build_summary(segment_rows, family_rows, trace_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "segments.csv", SEGMENT_FIELDNAMES, segment_rows)
    write_csv(output_dir / "families.csv", FAMILY_FIELDNAMES, family_rows)
    write_csv(output_dir / "trace_candidates.csv", TRACE_FIELDNAMES, trace_rows)
    (output_dir / "index.html").write_text(build_html(summary, segment_rows, family_rows, trace_rows, output_dir, title))
    return summary, segment_rows, family_rows, trace_rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe body-control grammar families for remaining rejected large .tex segments."
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--segments", type=Path, default=DEFAULT_SEGMENTS)
    parser.add_argument("--review-candidates", type=Path, default=DEFAULT_REVIEW_CANDIDATES)
    parser.add_argument("--mix-entry-index", type=int, default=DEFAULT_MIX_ENTRY_INDEX)
    parser.add_argument("--mode", action="append", dest="modes", default=None)
    parser.add_argument("--low", type=lambda value: int(value, 0), default=0x30)
    parser.add_argument("--high", type=lambda value: int(value, 0), default=0xBF)
    parser.add_argument("--max-events", type=int, default=DEFAULT_MAX_EVENTS)
    parser.add_argument("--title", default="Lands of Lore II .tex Large Body Control Grammar Probe")
    args = parser.parse_args()

    summary, _segments, _families, _trace = write_report(
        args.output,
        args.segments,
        args.review_candidates,
        args.mix_entry_index,
        args.modes or DEFAULT_MODES,
        args.low,
        args.high,
        args.max_events,
        args.title,
    )
    print(f"Segments: {summary['segment_rows']}")
    print(f"Control paths: {summary['control_path_groups']}")
    print(f"Trace candidates: {summary['trace_candidate_rows']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
