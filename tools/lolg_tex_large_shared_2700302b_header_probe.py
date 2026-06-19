#!/usr/bin/env python3
"""Derive shared 0x2700302b header field evidence for large rejected .tex bodies."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import struct
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_large_body_control_grammar_probe import int_value, read_mix_entry, ratio, write_csv


DEFAULT_OUTPUT = Path("output/tex_large_shared_2700302b_header_probe")
DEFAULT_SEGMENTS = Path("output/tex_large_rejected_decoder_profile/segments.csv")
DEFAULT_BODY_CONTROL_TRACES = Path("output/tex_large_body_control_grammar_probe/trace_candidates.csv")
DEFAULT_MIX_ENTRY_INDEX = 2
TARGET_CONTROL_PATH = "shared_2700302b_header"

SUMMARY_FIELDNAMES = [
    "scope",
    "shared_rows",
    "field_rows",
    "constant_field_rows",
    "varying_field_rows",
    "trace_support_rows",
    "best_offset",
    "best_offset_reason",
    "best_mode",
    "best_fingerprint",
    "terminal_marker_rows",
    "issue_rows",
    "next_action",
]

SEGMENT_FIELDNAMES = [
    "segment_id",
    "archive",
    "archive_tag",
    "pcx_name",
    "body_size",
    "segment_size",
    "head64_hex",
    "le16_head16",
    "le32_head8",
    "terminal_marker_offset",
    "tail16_hex",
    "issues",
]

FIELD_FIELDNAMES = [
    "offset",
    "width",
    "values",
    "distinct_values",
    "constant",
    "semantic_hint",
]

TRACE_SUPPORT_FIELDNAMES = [
    "offset",
    "offset_reason",
    "mode",
    "rows",
    "pcx_names",
    "fingerprints",
    "avg_command_density",
    "min_pixels",
    "max_pixels",
    "max_final_y",
    "score",
    "recommended",
]

TERMINAL_MARKER = b"\x00\x11\x00\x00\x00\x00\x00\x00"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    try:
        return os.path.relpath(Path(path_text), base_dir)
    except ValueError:
        return str(path_text)


def load_body(row: dict[str, str], payload_cache: dict[Path, bytes], mix_entry_index: int) -> tuple[bytes, list[str]]:
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


def hex_words(body: bytes, width: int, count: int) -> str:
    values: list[str] = []
    for offset in range(0, min(len(body), width * count), width):
        if offset + width > len(body):
            break
        if width == 2:
            values.append(f"0x{struct.unpack_from('<H', body, offset)[0]:04x}")
        elif width == 4:
            values.append(f"0x{struct.unpack_from('<I', body, offset)[0]:08x}")
    return "|".join(values)


def build_segment_rows(rows: list[dict[str, str]], mix_entry_index: int) -> tuple[list[dict[str, str]], dict[str, bytes]]:
    payload_cache: dict[Path, bytes] = {}
    bodies: dict[str, bytes] = {}
    output: list[dict[str, str]] = []
    for row in rows:
        if row.get("control_path") != TARGET_CONTROL_PATH:
            continue
        body, issues = load_body(row, payload_cache, mix_entry_index)
        segment_id = row.get("segment_id", "")
        bodies[segment_id] = body
        terminal_offset = body.rfind(TERMINAL_MARKER)
        if not body:
            issues.append("empty_body")
        output.append(
            {
                "segment_id": segment_id,
                "archive": row.get("archive", ""),
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "body_size": str(len(body)),
                "segment_size": row.get("segment_size", ""),
                "head64_hex": body[:64].hex(),
                "le16_head16": hex_words(body, 2, 16),
                "le32_head8": hex_words(body, 4, 8),
                "terminal_marker_offset": str(terminal_offset) if terminal_offset >= 0 else "",
                "tail16_hex": body[-16:].hex() if body else "",
                "issues": ";".join(sorted(set(issues))),
            }
        )
    return output, bodies


def field_hint(offset: int, width: int, values: set[str]) -> str:
    if width == 2 and offset == 0 and values == {"0x302b"}:
        return "marker_pair_le"
    if width == 2 and offset == 2 and values == {"0x2700"}:
        return "shared_family_word"
    if width == 4 and offset == 0 and values == {"0x2700302b"}:
        return "shared_header_dword"
    if len(values) == 1:
        return "constant_header_field"
    return "varying_candidate_field"


def build_field_rows(bodies: dict[str, bytes]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for width, limit in ((2, 32), (4, 32)):
        for offset in range(0, limit, width):
            values: list[str] = []
            for body in bodies.values():
                if offset + width > len(body):
                    continue
                if width == 2:
                    values.append(f"0x{struct.unpack_from('<H', body, offset)[0]:04x}")
                else:
                    values.append(f"0x{struct.unpack_from('<I', body, offset)[0]:08x}")
            distinct = set(values)
            if not values:
                continue
            rows.append(
                {
                    "offset": str(offset),
                    "width": str(width),
                    "values": "|".join(values),
                    "distinct_values": str(len(distinct)),
                    "constant": "yes" if len(distinct) == 1 else "no",
                    "semantic_hint": field_hint(offset, width, distinct),
                }
            )
    return rows


def float_value(row: dict[str, str], field: str) -> float:
    try:
        return float(row.get(field, "0") or 0)
    except ValueError:
        return 0.0


def mode_score(mode: str, offset: int) -> int:
    score = 0
    if "op4_cmd20_sig" in mode:
        score += 50
    elif "op4_cmd20" in mode:
        score += 45
    elif mode.startswith("op4"):
        score += 35
    elif "cmd20_sig" in mode:
        score += 25
    elif "cmd20" in mode:
        score += 20
    if offset == 4:
        score += 20
    elif offset in {2, 8}:
        score += 10
    return score


def build_trace_support_rows(trace_rows: list[dict[str, str]], expected_rows: int) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in trace_rows:
        if row.get("control_path") != TARGET_CONTROL_PATH or row.get("issues"):
            continue
        grouped[(row.get("offset", ""), row.get("offset_reason", ""), row.get("mode", ""))].append(row)

    rows: list[dict[str, str]] = []
    for (offset_text, reason, mode), group in sorted(grouped.items(), key=lambda item: (int(item[0][0]), item[0][2])):
        pcx_names = sorted({row.get("pcx_name", "") for row in group if row.get("pcx_name")})
        if len(pcx_names) < expected_rows:
            continue
        offset = int(offset_text)
        densities = [float_value(row, "command_density") for row in group]
        pixels = [int_value(row, "pixels") for row in group]
        final_y = [int_value(row, "final_y") for row in group]
        fingerprints = Counter(row.get("fingerprint", "") for row in group if row.get("fingerprint"))
        dominant_fingerprint = fingerprints.most_common(1)[0][0] if fingerprints else ""
        score = mode_score(mode, offset) + int(200 * (sum(densities) / max(1, len(densities))))
        rows.append(
            {
                "offset": offset_text,
                "offset_reason": reason,
                "mode": mode,
                "rows": str(len(group)),
                "pcx_names": "|".join(pcx_names),
                "fingerprints": "|".join(f"{key}:{count}" for key, count in fingerprints.most_common()),
                "avg_command_density": f"{sum(densities) / max(1, len(densities)):.6f}",
                "min_pixels": str(min(pixels) if pixels else 0),
                "max_pixels": str(max(pixels) if pixels else 0),
                "max_final_y": str(max(final_y) if final_y else 0),
                "score": str(score),
                "recommended": "no",
            }
        )
    rows.sort(key=lambda row: (-int_value(row, "score"), int_value(row, "offset"), row.get("mode", "")))
    if rows:
        rows[0]["recommended"] = "yes"
    return rows


def build_summary(
    segment_rows: list[dict[str, str]],
    field_rows: list[dict[str, str]],
    trace_support_rows: list[dict[str, str]],
) -> dict[str, str]:
    best = trace_support_rows[0] if trace_support_rows else {}
    issue_rows = sum(1 for row in segment_rows if row.get("issues"))
    if issue_rows:
        next_action = "fix shared 0x2700302b header probe issues"
    elif best:
        next_action = (
            "probe shared 0x2700302b payload start "
            f"offset {best.get('offset', '')} with {best.get('mode', '')}"
        )
    else:
        next_action = "expand shared 0x2700302b header field comparison"
    return {
        "scope": "total",
        "shared_rows": str(len(segment_rows)),
        "field_rows": str(len(field_rows)),
        "constant_field_rows": str(sum(1 for row in field_rows if row.get("constant") == "yes")),
        "varying_field_rows": str(sum(1 for row in field_rows if row.get("constant") != "yes")),
        "trace_support_rows": str(len(trace_support_rows)),
        "best_offset": best.get("offset", ""),
        "best_offset_reason": best.get("offset_reason", ""),
        "best_mode": best.get("mode", ""),
        "best_fingerprint": best.get("fingerprints", "").split("|", 1)[0].split(":", 1)[0] if best else "",
        "terminal_marker_rows": str(sum(1 for row in segment_rows if row.get("terminal_marker_offset"))),
        "issue_rows": str(issue_rows),
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
    segment_rows: list[dict[str, str]],
    field_rows: list[dict[str, str]],
    trace_support_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "segments": segment_rows,
        "fields": field_rows,
        "trace_support": trace_support_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f"<a href=\"{html.escape(relative_href(path, output_dir))}\">{html.escape(name)}</a>"
        for name, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("segments.csv", output_dir / "segments.csv"),
            ("fields.csv", output_dir / "fields.csv"),
            ("trace_support.csv", output_dir / "trace_support.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme: dark; --bg: #101317; --panel: #181d23; --text: #e8edf2; --muted: #98a4b3; --accent: #74b8ff; --warn: #f0b35a; --ok: #6fd08c; }}
body {{ margin: 0; font-family: system-ui, sans-serif; background: var(--bg); color: var(--text); }}
header, main {{ max-width: 1450px; margin: 0 auto; padding: 24px; }}
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
td {{ max-width: 620px; overflow-wrap: anywhere; }}
section {{ margin-bottom: 20px; }}
</style>
</head>
<body>
<header>
  <h1>{html.escape(title)}</h1>
  <div class="muted">Compares the two remaining large shared 0x2700302b bodies and ranks common trace starts.</div>
  <p>{links}</p>
</header>
<main>
  <section class="grid">
    <div class="stat"><div class="label">Shared rows</div><div class="value">{html.escape(summary['shared_rows'])}</div></div>
    <div class="stat"><div class="label">Constant fields</div><div class="value warn">{html.escape(summary['constant_field_rows'])}</div></div>
    <div class="stat"><div class="label">Trace support</div><div class="value">{html.escape(summary['trace_support_rows'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel">
    <h2>Summary</h2>
    {render_table([summary], SUMMARY_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Trace support</h2>
    {render_table(trace_support_rows[:80], TRACE_SUPPORT_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Fields</h2>
    {render_table(field_rows, FIELD_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Segments</h2>
    {render_table(segment_rows, SEGMENT_FIELDNAMES)}
  </section>
</main>
<script type="application/json" id="probe-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    segments_path: Path,
    trace_candidates_path: Path,
    mix_entry_index: int,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    segment_rows, bodies = build_segment_rows(read_csv(segments_path), mix_entry_index)
    field_rows = build_field_rows(bodies)
    trace_support_rows = build_trace_support_rows(read_csv(trace_candidates_path), len(segment_rows))
    summary = build_summary(segment_rows, field_rows, trace_support_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "segments.csv", SEGMENT_FIELDNAMES, segment_rows)
    write_csv(output_dir / "fields.csv", FIELD_FIELDNAMES, field_rows)
    write_csv(output_dir / "trace_support.csv", TRACE_SUPPORT_FIELDNAMES, trace_support_rows)
    (output_dir / "index.html").write_text(
        build_html(summary, segment_rows, field_rows, trace_support_rows, output_dir, title)
    )
    return summary, segment_rows, field_rows, trace_support_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Derive shared 0x2700302b header field evidence.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--segments", type=Path, default=DEFAULT_SEGMENTS)
    parser.add_argument("--trace-candidates", type=Path, default=DEFAULT_BODY_CONTROL_TRACES)
    parser.add_argument("--mix-entry-index", type=int, default=DEFAULT_MIX_ENTRY_INDEX)
    parser.add_argument("--title", default="Lands of Lore II .tex Shared 0x2700302b Header Probe")
    args = parser.parse_args()

    summary, _segments, _fields, _traces = write_report(
        args.output,
        args.segments,
        args.trace_candidates,
        args.mix_entry_index,
        args.title,
    )
    print(f"Shared rows: {summary['shared_rows']}")
    print(f"Constant fields: {summary['constant_field_rows']}")
    print(f"Trace support rows: {summary['trace_support_rows']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
