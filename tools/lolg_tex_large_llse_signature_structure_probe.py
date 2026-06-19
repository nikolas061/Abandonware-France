#!/usr/bin/env python3
"""Profile LLSE-signature large .tex bodies before renderer grammar work."""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import os
from collections import Counter
from pathlib import Path

from lolg_tex_large_body_control_grammar_probe import int_value, read_mix_entry, write_csv


DEFAULT_OUTPUT = Path("output/tex_large_llse_signature_structure_probe")
DEFAULT_SEGMENTS = Path("output/tex_large_rejected_decoder_profile/segments.csv")
DEFAULT_CONTROL_PROBE_SUMMARY = Path("output/tex_large_llse_signature_control_probe/summary.csv")
DEFAULT_MIX_ENTRY_INDEX = 2
TARGET_CONTROL_PATH = "llse_signature"
TERMINAL_MARKER = b"\x00\x11\x00\x00\x00\x00\x00\x00"
KNOWN_MARKER_PAIRS = {
    (0x27, 0x30),
    (0x28, 0x30),
    (0x29, 0x30),
    (0x2A, 0x30),
    (0x2B, 0x30),
    (0x2B, 0x31),
}

SUMMARY_FIELDNAMES = [
    "scope",
    "segment_rows",
    "structure_rows",
    "window_rows",
    "pair_rows",
    "terminal_marker_total",
    "terminal_marker_segments",
    "marker_pair_total_scan",
    "cmd20_total_scan",
    "op4_candidate_total_scan",
    "min_entropy_window",
    "max_low_ratio_window",
    "max_zero_ratio_window",
    "issue_rows",
    "structure_verdict",
    "next_action",
]

STRUCTURE_FIELDNAMES = [
    "segment_id",
    "archive",
    "archive_tag",
    "pcx_name",
    "body_size",
    "scan_bytes",
    "head32_hex",
    "tail32_hex",
    "signature_ascii",
    "signature_hex",
    "llse_marker_offset",
    "llse_marker_pair",
    "le16_head16",
    "terminal_marker_count",
    "terminal_marker_first_offsets",
    "terminal_marker_last_offset",
    "terminal_gap_min",
    "terminal_gap_max",
    "known_marker_pairs_scan",
    "known_marker_pair_counts_scan",
    "cmd20_count_scan",
    "op4_candidate_count_scan",
    "zero_ratio_scan",
    "low_ratio_scan",
    "printable_head_strings",
    "issues",
]

WINDOW_FIELDNAMES = [
    "rank",
    "segment_id",
    "window_offset",
    "window_size",
    "entropy",
    "zero_ratio",
    "low_ratio",
    "cmd20_count",
    "op4_candidate_count",
    "top_bytes",
    "verdict",
]

PAIR_FIELDNAMES = [
    "segment_id",
    "parity",
    "rank",
    "word_hex",
    "count",
    "ratio",
    "sample_offsets",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_summary(path: Path) -> dict[str, str]:
    rows = read_csv(path)
    return rows[0] if rows else {}


def ratio(count: int, total: int) -> str:
    return f"{count / max(1, total):.6f}"


def safe_ascii(data: bytes) -> str:
    return "".join(chr(value) if 32 <= value < 127 else "." for value in data)


def le16_words(data: bytes, count: int = 16) -> str:
    words = []
    for offset in range(0, min(len(data), count * 2), 2):
        if offset + 1 >= len(data):
            break
        words.append(f"0x{data[offset] | (data[offset + 1] << 8):04x}")
    return "|".join(words)


def op4_candidate(byte: int) -> bool:
    return 0x40 <= byte <= 0x68 and byte % 4 == 0


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    total = len(data)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def top_bytes(data: bytes, limit: int = 8) -> str:
    return "|".join(f"{byte:02x}:{count}" for byte, count in Counter(data).most_common(limit))


def find_all(data: bytes, needle: bytes) -> list[int]:
    offsets: list[int] = []
    start = 0
    while True:
        offset = data.find(needle, start)
        if offset < 0:
            break
        offsets.append(offset)
        start = offset + 1
    return offsets


def marker_pair_counts(data: bytes) -> Counter[str]:
    counts: Counter[str] = Counter()
    for index in range(max(0, len(data) - 1)):
        pair = (data[index], data[index + 1])
        if pair in KNOWN_MARKER_PAIRS:
            counts[f"{pair[0]:02x}{pair[1]:02x}"] += 1
    return counts


def printable_strings(data: bytes, min_len: int = 4, limit: int = 12) -> str:
    strings: list[str] = []
    current: list[int] = []
    for value in data:
        if 32 <= value < 127:
            current.append(value)
            continue
        if len(current) >= min_len:
            strings.append(bytes(current).decode("ascii", errors="replace"))
            if len(strings) >= limit:
                break
        current = []
    if len(strings) < limit and len(current) >= min_len:
        strings.append(bytes(current).decode("ascii", errors="replace"))
    return "|".join(strings[:limit])


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


def build_structure_row(
    source: dict[str, str],
    body: bytes,
    body_issues: list[str],
    scan_bytes: int,
) -> dict[str, str]:
    issues = list(body_issues)
    if not body:
        issues.append("empty_body")
    scan = body[: min(len(body), scan_bytes)]
    terminal_offsets = find_all(body, TERMINAL_MARKER)
    terminal_gaps = [
        later - earlier
        for earlier, later in zip(terminal_offsets, terminal_offsets[1:])
    ]
    pairs = marker_pair_counts(scan)
    marker_offset = body.find(b"\x27\x30")
    return {
        "segment_id": source.get("segment_id", ""),
        "archive": source.get("archive", ""),
        "archive_tag": source.get("archive_tag", ""),
        "pcx_name": source.get("pcx_name", ""),
        "body_size": str(len(body)),
        "scan_bytes": str(len(scan)),
        "head32_hex": body[:32].hex(),
        "tail32_hex": body[-32:].hex() if body else "",
        "signature_ascii": safe_ascii(body[:4]),
        "signature_hex": body[:4].hex(),
        "llse_marker_offset": str(marker_offset) if marker_offset >= 0 else "",
        "llse_marker_pair": body[marker_offset : marker_offset + 2].hex() if marker_offset >= 0 else "",
        "le16_head16": le16_words(body),
        "terminal_marker_count": str(len(terminal_offsets)),
        "terminal_marker_first_offsets": "|".join(str(offset) for offset in terminal_offsets[:12]),
        "terminal_marker_last_offset": str(terminal_offsets[-1]) if terminal_offsets else "",
        "terminal_gap_min": str(min(terminal_gaps)) if terminal_gaps else "",
        "terminal_gap_max": str(max(terminal_gaps)) if terminal_gaps else "",
        "known_marker_pairs_scan": str(sum(pairs.values())),
        "known_marker_pair_counts_scan": "|".join(f"{key}:{count}" for key, count in pairs.most_common()),
        "cmd20_count_scan": str(scan.count(0x20)),
        "op4_candidate_count_scan": str(sum(1 for byte in scan if op4_candidate(byte))),
        "zero_ratio_scan": ratio(scan.count(0), len(scan)),
        "low_ratio_scan": ratio(sum(1 for byte in scan if byte < 0x30), len(scan)),
        "printable_head_strings": printable_strings(scan[:65536]),
        "issues": ";".join(sorted(set(issues))),
    }


def build_window_rows(
    source: dict[str, str],
    body: bytes,
    scan_bytes: int,
    window_size: int,
    window_step: int,
    limit: int,
) -> list[dict[str, str]]:
    segment_id = source.get("segment_id", "")
    scan = body[: min(len(body), scan_bytes)]
    rows: list[dict[str, str]] = []
    if window_size <= 0 or window_step <= 0:
        return rows
    for offset in range(0, max(0, len(scan) - window_size + 1), window_step):
        window = scan[offset : offset + window_size]
        low = sum(1 for byte in window if byte < 0x30)
        zero = window.count(0)
        op4 = sum(1 for byte in window if op4_candidate(byte))
        ent = entropy(window)
        verdict = "low_entropy_window" if ent < 5.0 else "mixed_entropy_window"
        if low / max(1, len(window)) >= 0.50:
            verdict = f"{verdict}+low_control_dense"
        rows.append(
            {
                "rank": "",
                "segment_id": segment_id,
                "window_offset": str(offset),
                "window_size": str(len(window)),
                "entropy": f"{ent:.4f}",
                "zero_ratio": ratio(zero, len(window)),
                "low_ratio": ratio(low, len(window)),
                "cmd20_count": str(window.count(0x20)),
                "op4_candidate_count": str(op4),
                "top_bytes": top_bytes(window),
                "verdict": verdict,
            }
        )
    rows.sort(
        key=lambda row: (
            float(row["entropy"]),
            -float(row["low_ratio"]),
            -float(row["zero_ratio"]),
            int(row["window_offset"]),
        )
    )
    rows = rows[:limit]
    for rank, row in enumerate(rows, 1):
        row["rank"] = str(rank)
    return rows


def build_pair_rows(
    source: dict[str, str],
    body: bytes,
    scan_bytes: int,
    limit: int,
) -> list[dict[str, str]]:
    segment_id = source.get("segment_id", "")
    scan = body[: min(len(body), scan_bytes)]
    output: list[dict[str, str]] = []
    for parity in (0, 1):
        counts: Counter[int] = Counter()
        offsets: dict[int, list[int]] = {}
        for offset in range(parity, max(0, len(scan) - 1), 2):
            word = scan[offset] | (scan[offset + 1] << 8)
            counts[word] += 1
            offsets.setdefault(word, [])
            if len(offsets[word]) < 8:
                offsets[word].append(offset)
        total = sum(counts.values())
        for rank, (word, count) in enumerate(counts.most_common(limit), 1):
            output.append(
                {
                    "segment_id": segment_id,
                    "parity": str(parity),
                    "rank": str(rank),
                    "word_hex": f"0x{word:04x}",
                    "count": str(count),
                    "ratio": ratio(count, total),
                    "sample_offsets": "|".join(str(offset) for offset in offsets.get(word, [])),
                }
            )
    return output


def summary_row(
    control_summary: dict[str, str],
    structure_rows: list[dict[str, str]],
    window_rows: list[dict[str, str]],
    pair_rows: list[dict[str, str]],
) -> dict[str, str]:
    issue_rows = sum(1 for row in structure_rows if row.get("issues"))
    terminal_total = sum(int_value(row, "terminal_marker_count") for row in structure_rows)
    terminal_segments = sum(1 for row in structure_rows if int_value(row, "terminal_marker_count") > 0)
    marker_pair_total = sum(int_value(row, "known_marker_pairs_scan") for row in structure_rows)
    cmd20_total = sum(int_value(row, "cmd20_count_scan") for row in structure_rows)
    op4_total = sum(int_value(row, "op4_candidate_count_scan") for row in structure_rows)
    min_entropy = min((float(row["entropy"]) for row in window_rows), default=0.0)
    max_low = max((float(row["low_ratio"]) for row in window_rows), default=0.0)
    max_zero = max((float(row["zero_ratio"]) for row in window_rows), default=0.0)
    multi_terminal = any(int_value(row, "terminal_marker_count") > 1 for row in structure_rows)
    if issue_rows:
        verdict = "llse_structure_probe_issues"
        next_action = "fix LLSE structure probe inputs"
    elif multi_terminal:
        verdict = "llse_body_contains_multiple_terminal_markers"
        next_action = "split LLSE body by terminal markers before renderer grammar work"
    elif marker_pair_total and cmd20_total:
        verdict = "llse_single_stream_control_dense"
        next_action = "derive LLSE command record grammar from marker 2730 and cmd20/control byte fields"
    elif control_summary.get("probe_verdict") == "llse_signature_existing_modes_noisy":
        verdict = "llse_single_stream_existing_modes_noisy"
        next_action = "derive LLSE command stream fields after marker 2730 using 16-bit pair profile"
    else:
        verdict = "llse_structure_profile_ready"
        next_action = "review LLSE structure profile before next decoder probe"
    return {
        "scope": "total",
        "segment_rows": str(len(structure_rows)),
        "structure_rows": str(len(structure_rows)),
        "window_rows": str(len(window_rows)),
        "pair_rows": str(len(pair_rows)),
        "terminal_marker_total": str(terminal_total),
        "terminal_marker_segments": str(terminal_segments),
        "marker_pair_total_scan": str(marker_pair_total),
        "cmd20_total_scan": str(cmd20_total),
        "op4_candidate_total_scan": str(op4_total),
        "min_entropy_window": f"{min_entropy:.4f}",
        "max_low_ratio_window": f"{max_low:.6f}",
        "max_zero_ratio_window": f"{max_zero:.6f}",
        "issue_rows": str(issue_rows),
        "structure_verdict": verdict,
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
    structures: list[dict[str, str]],
    windows: list[dict[str, str]],
    pairs: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "structures": structures, "windows": windows, "pairs": pairs}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f"<a href=\"{html.escape(relative_href(path, output_dir))}\">{html.escape(label)}</a>"
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("structures.csv", output_dir / "structures.csv"),
            ("windows.csv", output_dir / "windows.csv"),
            ("pairs.csv", output_dir / "pairs.csv"),
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
  <div class="muted">Byte-level structure profile for LLSE-signature large .tex bodies.</div>
  <p>{links}</p>
</header>
<main>
  <section class="grid">
    <div class="stat"><div class="label">Segments</div><div class="value">{html.escape(summary['segment_rows'])}</div></div>
    <div class="stat"><div class="label">Terminal Markers</div><div class="value warn">{html.escape(summary['terminal_marker_total'])}</div></div>
    <div class="stat"><div class="label">Min Entropy</div><div class="value">{html.escape(summary['min_entropy_window'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel">
    <h2>Summary</h2>
    {render_table([summary], SUMMARY_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Structures</h2>
    {render_table(structures, STRUCTURE_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Lowest Entropy Windows</h2>
    {render_table(windows, WINDOW_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>16-bit Pairs</h2>
    {render_table(pairs, PAIR_FIELDNAMES)}
  </section>
</main>
<script type="application/json" id="llse-structure-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    control_summary = read_summary(args.control_probe_summary)
    segments = [row for row in read_csv(args.segments) if row.get("control_path") == TARGET_CONTROL_PATH]
    payload_cache: dict[Path, bytes] = {}
    structure_rows: list[dict[str, str]] = []
    window_rows: list[dict[str, str]] = []
    pair_rows: list[dict[str, str]] = []
    for source in segments:
        body, issues = load_body(source, payload_cache, args.mix_entry_index)
        structure_rows.append(build_structure_row(source, body, issues, args.scan_bytes))
        window_rows.extend(
            build_window_rows(
                source,
                body,
                args.window_scan_bytes,
                args.window_size,
                args.window_step,
                args.window_limit,
            )
        )
        pair_rows.extend(build_pair_rows(source, body, args.scan_bytes, args.pair_limit))
    summary = summary_row(control_summary, structure_rows, window_rows, pair_rows)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "structures.csv", STRUCTURE_FIELDNAMES, structure_rows)
    write_csv(args.output / "windows.csv", WINDOW_FIELDNAMES, window_rows)
    write_csv(args.output / "pairs.csv", PAIR_FIELDNAMES, pair_rows)
    (args.output / "index.html").write_text(
        build_html(summary, structure_rows, window_rows, pair_rows, args.output, args.title),
        encoding="utf-8",
    )
    return summary, structure_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile LLSE-signature large .tex byte structure.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--segments", type=Path, default=DEFAULT_SEGMENTS)
    parser.add_argument("--control-probe-summary", type=Path, default=DEFAULT_CONTROL_PROBE_SUMMARY)
    parser.add_argument("--mix-entry-index", type=int, default=DEFAULT_MIX_ENTRY_INDEX)
    parser.add_argument("--scan-bytes", type=int, default=1024 * 1024)
    parser.add_argument("--window-scan-bytes", type=int, default=4 * 1024 * 1024)
    parser.add_argument("--window-size", type=int, default=4096)
    parser.add_argument("--window-step", type=int, default=4096)
    parser.add_argument("--window-limit", type=int, default=32)
    parser.add_argument("--pair-limit", type=int, default=24)
    parser.add_argument("--title", default="Lands of Lore II .tex LLSE Signature Structure Probe")
    args = parser.parse_args()

    summary, _rows = write_report(args)
    print(f"Segments: {summary['segment_rows']}")
    print(f"Terminal markers: {summary['terminal_marker_total']}")
    print(f"Marker pairs scanned: {summary['marker_pair_total_scan']}")
    print(f"Min entropy window: {summary['min_entropy_window']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Structure verdict: {summary['structure_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
