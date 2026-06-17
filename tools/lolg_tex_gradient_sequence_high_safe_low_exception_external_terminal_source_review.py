#!/usr/bin/env python3
"""Review external source bytes that block residual high-safe dependency terminals."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
from collections import defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_clean_gap_queue import classify_span, clean_distance, mask_spans
from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value


DEFAULT_SLOTS = Path("output/tex_gradient_sequence_high_safe_low_exception_source_dependency_second_promoted_replay/slots.csv")
DEFAULT_TERMINALS = Path("output/tex_gradient_sequence_high_safe_low_exception_source_dependency_residual_core/terminals.csv")
DEFAULT_FIXTURES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_second_promoted_replay/fixtures.csv"
)
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_high_safe_low_exception_external_terminal_source")

EDGE_RE = re.compile(r"\d+\|\d+->\d+\|\d+")

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "external_terminal_slots",
    "external_terminal_root_chains",
    "external_terminal_edges",
    "blocked_fixtures",
    "blocker_source_bytes",
    "blocker_span_rows",
    "blocker_span_bytes",
    "small_nonzero_blocker_spans",
    "top_blocker_span",
    "top_blocker_span_chains",
    "top_blocker_span_source_bytes",
    "top_blocker_span_expected_hex",
    "dominant_blocker",
    "next_probe",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

BYTE_FIELDNAMES = [
    "rank",
    "terminal_slot_rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "source_offset",
    "terminal_target_offset",
    "terminal_target_low",
    "terminal_low_bucket",
    "source_expected_byte",
    "source_decoded_byte",
    "root_chains",
    "incoming_edges",
    "span_key",
    "span_class",
    "span_start",
    "span_end",
    "span_length",
    "span_expected_hex",
    "span_decoded_hex",
    "span_known_mask_hex",
    "position_in_span",
    "left_clean_distance",
    "right_clean_distance",
    "left_clean_byte",
    "right_clean_byte",
    "window_expected_hex",
    "window_decoded_hex",
    "window_known_mask_hex",
    "control_prefix_hex",
    "fragment_hex",
    "segment_head_hex",
    "next_probe",
]

SPAN_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_key",
    "span_class",
    "start",
    "end",
    "length",
    "zero_bytes",
    "nonzero_bytes",
    "blocker_source_bytes",
    "blocker_terminal_slots",
    "blocker_root_chains",
    "blocker_edges",
    "expected_hex",
    "decoded_hex",
    "known_mask_hex",
    "left_clean_distance",
    "right_clean_distance",
    "left_clean_byte",
    "right_clean_byte",
    "control_prefix_hex",
    "fragment_hex",
    "segment_head_hex",
    "next_probe",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def asset_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def byte_hex(buffer: bytes, offset: int) -> str:
    if 0 <= offset < len(buffer):
        return f"{buffer[offset]:02x}"
    return ""


def window_bytes(buffer: bytes, offset: int, radius: int = 6) -> str:
    if not buffer:
        return ""
    start = max(0, offset - radius)
    end = min(len(buffer), offset + radius + 1)
    return buffer[start:end].hex()


def edge_keys(text: str) -> list[str]:
    return EDGE_RE.findall(text or "")


def build_spans(expected: bytes, decoded: bytes, known_mask: bytes) -> list[dict[str, str]]:
    unknown_mask = bytearray(len(expected))
    for index in range(len(expected)):
        if index >= len(known_mask) or not known_mask[index]:
            unknown_mask[index] = 255

    rows: list[dict[str, str]] = []
    for span_index, (start, end) in enumerate(mask_spans(bytes(unknown_mask), 255), start=1):
        span_class, zero_bytes, nonzero_bytes = classify_span(expected, start, end, "unresolved")
        left_distance, right_distance = clean_distance(known_mask, start, end)
        rows.append(
            {
                "span_index": str(span_index),
                "span_class": span_class,
                "start": str(start),
                "end": str(end),
                "length": str(max(0, end - start)),
                "zero_bytes": str(zero_bytes),
                "nonzero_bytes": str(nonzero_bytes),
                "expected_hex": expected[start:end].hex(),
                "decoded_hex": decoded[start:end].hex(),
                "known_mask_hex": known_mask[start:end].hex(),
                "left_clean_distance": left_distance,
                "right_clean_distance": right_distance,
                "left_clean_byte": byte_hex(decoded, start - 1) if start > 0 and known_mask[start - 1] else "",
                "right_clean_byte": byte_hex(decoded, end) if end < len(known_mask) and known_mask[end] else "",
            }
        )
    return rows


def span_for_offset(spans: list[dict[str, str]], offset: int) -> dict[str, str]:
    for span in spans:
        if int_value(span, "start") <= offset < int_value(span, "end"):
            return span
    return {}


def source_buffers(
    fixture: dict[str, str],
    manifest: dict[str, str],
    issues: list[str],
) -> dict[str, bytes]:
    expected = load_bytes(manifest.get("expected_gap_path", ""), issues, "expected")
    decoded = load_bytes(fixture.get("decoded_path", ""), issues, "decoded")
    known_mask = load_bytes(fixture.get("known_mask_path", ""), issues, "known_mask")
    if len(decoded) != len(expected):
        issues.append("decoded_size_mismatch")
        decoded = decoded[: len(expected)] + (b"\x00" * max(0, len(expected) - len(decoded)))
    if len(known_mask) != len(expected):
        issues.append("known_mask_size_mismatch")
        known_mask = known_mask[: len(expected)] + (b"\x00" * max(0, len(expected) - len(known_mask)))
    return {
        "expected": expected,
        "decoded": decoded,
        "known_mask": known_mask,
        "segment": load_bytes(manifest.get("segment_gap_path", ""), issues, "segment"),
        "control_prefix": load_bytes(manifest.get("control_prefix_path", ""), issues, "control_prefix"),
        "fragment": load_bytes(manifest.get("fragment_path", ""), issues, "fragment"),
    }


def next_probe_for_span(row: dict[str, str]) -> str:
    if row.get("span_class") == "unresolved_nonzero" and int_value(row, "length") <= 5:
        return "probe small unresolved nonzero span selector"
    if row.get("span_class") == "unresolved_nonzero":
        return "probe nonzero span source selector"
    return "split mixed external terminal source span"


def build(
    slot_rows: list[dict[str, str]],
    terminal_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    slots_by_rank = {row["rank"]: row for row in slot_rows}
    fixtures_by_key = {asset_key(row): row for row in fixture_rows}
    manifest_by_key = {asset_key(row): row for row in manifest_rows}
    fixture_cache: dict[tuple[str, str, str], dict[str, object]] = {}
    issue_rows = 0

    external_terms = [
        row
        for row in terminal_rows
        if row.get("terminal_source_availability") == "unknown_source"
        and row.get("terminal_source_location") == "outside_highsafe"
    ]

    byte_rows: list[dict[str, str]] = []
    span_groups: dict[tuple[str, str, str, int, int], dict[str, object]] = {}

    for terminal in external_terms:
        slot = slots_by_rank.get(terminal.get("terminal_slot_rank", ""), {})
        if not slot:
            issue_rows += 1
            continue
        key = asset_key(slot)
        if key not in fixture_cache:
            fixture = fixtures_by_key.get(key, {})
            manifest = manifest_by_key.get(key, {})
            issues: list[str] = []
            buffers = source_buffers(fixture, manifest, issues)
            expected = buffers["expected"]
            decoded = buffers["decoded"]
            known_mask = buffers["known_mask"]
            spans = build_spans(expected, decoded, known_mask)
            if issues:
                issue_rows += 1
            fixture_cache[key] = {
                "fixture": fixture,
                "manifest": manifest,
                "buffers": buffers,
                "spans": spans,
                "issues": issues,
            }

        cache = fixture_cache[key]
        fixture = cache["fixture"] if isinstance(cache["fixture"], dict) else {}
        manifest = cache["manifest"] if isinstance(cache["manifest"], dict) else {}
        buffers = cache["buffers"] if isinstance(cache["buffers"], dict) else {}
        spans = cache["spans"] if isinstance(cache["spans"], list) else []
        expected = buffers.get("expected", b"")
        decoded = buffers.get("decoded", b"")
        known_mask = buffers.get("known_mask", b"")
        control_prefix = buffers.get("control_prefix", b"")
        fragment = buffers.get("fragment", b"")
        segment = buffers.get("segment", b"")
        offset = int_value(slot, "source_actual_offset", -1)
        span = span_for_offset(spans, offset)
        if not span:
            issue_rows += 1
        start = int_value(span, "start", offset)
        end = int_value(span, "end", offset + 1)
        span_key = f"{slot.get('frontier_id', '')}:{start}-{end}"
        edges = edge_keys(terminal.get("incoming_edges", ""))
        group_key = (key[0], key[1], key[2], start, end)
        group = span_groups.setdefault(
            group_key,
            {
                "slot": slot,
                "fixture": fixture,
                "manifest": manifest,
                "span": span,
                "buffers": buffers,
                "source_offsets": set(),
                "terminal_slots": [],
                "root_chains": 0,
                "edges": set(),
            },
        )
        group["source_offsets"].add(offset)
        group["terminal_slots"].append(terminal.get("terminal_slot_rank", ""))
        group["root_chains"] += int_value(terminal, "root_chains")
        group["edges"].update(edges)

        byte_rows.append(
            {
                "rank": str(len(byte_rows) + 1),
                "terminal_slot_rank": terminal.get("terminal_slot_rank", ""),
                "archive": key[0],
                "archive_tag": fixture.get("archive_tag", manifest.get("archive_tag", "")),
                "pcx_name": key[1],
                "frontier_id": key[2],
                "source_offset": str(offset),
                "terminal_target_offset": terminal.get("terminal_target_offset", ""),
                "terminal_target_low": terminal.get("terminal_target_low", ""),
                "terminal_low_bucket": terminal.get("terminal_low_bucket", ""),
                "source_expected_byte": byte_hex(expected, offset),
                "source_decoded_byte": byte_hex(decoded, offset),
                "root_chains": terminal.get("root_chains", ""),
                "incoming_edges": ";".join(edges),
                "span_key": span_key,
                "span_class": span.get("span_class", ""),
                "span_start": span.get("start", ""),
                "span_end": span.get("end", ""),
                "span_length": span.get("length", ""),
                "span_expected_hex": span.get("expected_hex", ""),
                "span_decoded_hex": span.get("decoded_hex", ""),
                "span_known_mask_hex": span.get("known_mask_hex", ""),
                "position_in_span": str(offset - start) if offset >= 0 else "",
                "left_clean_distance": span.get("left_clean_distance", ""),
                "right_clean_distance": span.get("right_clean_distance", ""),
                "left_clean_byte": span.get("left_clean_byte", ""),
                "right_clean_byte": span.get("right_clean_byte", ""),
                "window_expected_hex": window_bytes(expected, offset),
                "window_decoded_hex": window_bytes(decoded, offset),
                "window_known_mask_hex": window_bytes(known_mask, offset),
                "control_prefix_hex": control_prefix[:16].hex(),
                "fragment_hex": fragment[:16].hex(),
                "segment_head_hex": segment[:24].hex(),
                "next_probe": next_probe_for_span(span),
            }
        )

    span_rows: list[dict[str, str]] = []
    for group in span_groups.values():
        slot = group["slot"]
        fixture = group["fixture"]
        manifest = group["manifest"]
        span = group["span"]
        buffers = group["buffers"]
        offsets = sorted(group["source_offsets"])
        edges = sorted(group["edges"])
        span_rows.append(
            {
                "rank": str(len(span_rows) + 1),
                "archive": slot.get("archive", ""),
                "archive_tag": fixture.get("archive_tag", manifest.get("archive_tag", "")),
                "pcx_name": slot.get("pcx_name", ""),
                "frontier_id": slot.get("frontier_id", ""),
                "span_key": f"{slot.get('frontier_id', '')}:{span.get('start', '')}-{span.get('end', '')}",
                "span_class": span.get("span_class", ""),
                "start": span.get("start", ""),
                "end": span.get("end", ""),
                "length": span.get("length", ""),
                "zero_bytes": span.get("zero_bytes", ""),
                "nonzero_bytes": span.get("nonzero_bytes", ""),
                "blocker_source_bytes": str(len(offsets)),
                "blocker_terminal_slots": ";".join(group["terminal_slots"]),
                "blocker_root_chains": str(group["root_chains"]),
                "blocker_edges": ";".join(edges),
                "expected_hex": span.get("expected_hex", ""),
                "decoded_hex": span.get("decoded_hex", ""),
                "known_mask_hex": span.get("known_mask_hex", ""),
                "left_clean_distance": span.get("left_clean_distance", ""),
                "right_clean_distance": span.get("right_clean_distance", ""),
                "left_clean_byte": span.get("left_clean_byte", ""),
                "right_clean_byte": span.get("right_clean_byte", ""),
                "control_prefix_hex": buffers.get("control_prefix", b"")[:16].hex(),
                "fragment_hex": buffers.get("fragment", b"")[:16].hex(),
                "segment_head_hex": buffers.get("segment", b"")[:24].hex(),
                "next_probe": next_probe_for_span(span),
            }
        )
    span_rows.sort(
        key=lambda row: (
            -int_value(row, "blocker_root_chains"),
            -int_value(row, "blocker_source_bytes"),
            int_value(row, "frontier_id"),
            int_value(row, "start"),
        )
    )
    for index, row in enumerate(span_rows, start=1):
        row["rank"] = str(index)

    unique_edges = sorted({edge for row in byte_rows for edge in row.get("incoming_edges", "").split(";") if edge})
    top_span = span_rows[0] if span_rows else {}
    next_probe = (
        "probe small unresolved nonzero span selector for external terminal sources"
        if span_rows
        and all(row.get("span_class") == "unresolved_nonzero" and int_value(row, "length") <= 5 for row in span_rows)
        else "split external terminal source spans before promotion"
    )
    summary = {
        "scope": "total",
        "candidate_mode": "high_safe_low_exception_external_terminal_source_review",
        "external_terminal_slots": str(len(byte_rows)),
        "external_terminal_root_chains": str(sum(int_value(row, "root_chains") for row in byte_rows)),
        "external_terminal_edges": str(len(unique_edges)),
        "blocked_fixtures": str(len({(row["archive"], row["pcx_name"], row["frontier_id"]) for row in byte_rows})),
        "blocker_source_bytes": str(len({(row["archive"], row["pcx_name"], row["frontier_id"], row["source_offset"]) for row in byte_rows})),
        "blocker_span_rows": str(len(span_rows)),
        "blocker_span_bytes": str(sum(int_value(row, "length") for row in span_rows)),
        "small_nonzero_blocker_spans": str(
            sum(1 for row in span_rows if row.get("span_class") == "unresolved_nonzero" and int_value(row, "length") <= 5)
        ),
        "top_blocker_span": top_span.get("span_key", ""),
        "top_blocker_span_chains": top_span.get("blocker_root_chains", "0"),
        "top_blocker_span_source_bytes": top_span.get("blocker_source_bytes", "0"),
        "top_blocker_span_expected_hex": top_span.get("expected_hex", ""),
        "dominant_blocker": "small unresolved nonzero external terminal source spans" if span_rows else "",
        "next_probe": next_probe,
        "promotion_candidate_bytes": "0",
        "promotion_ready_bytes": "0",
        "issue_rows": str(issue_rows),
    }
    return summary, byte_rows, span_rows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 200) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    byte_rows: list[dict[str, str]],
    span_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "bytes": byte_rows, "spans": span_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("bytes.csv", output_dir / "bytes.csv"),
            ("spans.csv", output_dir / "spans.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{
  color-scheme: dark;
  --bg: #101417;
  --panel: #171d20;
  --line: #2b363a;
  --text: #ecf2f0;
  --muted: #9fb0ad;
  --accent: #82c6a2;
}}
body {{ margin: 0; font: 14px/1.45 system-ui, sans-serif; background: var(--bg); color: var(--text); }}
main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
h1 {{ font-size: 22px; margin: 0 0 12px; }}
h2 {{ font-size: 17px; margin: 0 0 12px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin: 16px 0; }}
.box {{ background: var(--panel); border: 1px solid var(--line); padding: 12px; border-radius: 6px; }}
.num {{ font-size: 24px; font-weight: 700; color: var(--accent); }}
.muted {{ color: var(--muted); font-size: 12px; }}
.panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 16px; margin: 16px 0; overflow-x: auto; }}
a {{ color: var(--accent); }}
table {{ border-collapse: collapse; width: 100%; min-width: 900px; }}
th, td {{ border-bottom: 1px solid var(--line); padding: 6px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
code {{ color: var(--accent); }}
</style>
</head>
<body>
<main>
<h1>{html.escape(title)}</h1>
<p class="muted">Sorties: {links}</p>
<div class="grid">
  <div class="box"><div class="num">{summary['external_terminal_slots']}</div><div class="muted">external terminal bytes</div></div>
  <div class="box"><div class="num">{summary['external_terminal_root_chains']}</div><div class="muted">blocked root chains</div></div>
  <div class="box"><div class="num">{summary['blocker_span_rows']}</div><div class="muted">blocker spans</div></div>
  <div class="box"><div class="num">{summary['small_nonzero_blocker_spans']}</div><div class="muted">small nonzero spans</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel">
<h2>Blocage dominant</h2>
<p><code>{html.escape(summary['dominant_blocker'])}</code></p>
<p>Top span: <code>{html.escape(summary['top_blocker_span'])}</code> ({html.escape(summary['top_blocker_span_chains'])} chains, expected <code>{html.escape(summary['top_blocker_span_expected_hex'])}</code>).</p>
<p>Next probe: <code>{html.escape(summary['next_probe'])}</code></p>
</div>
<div class="panel"><h2>Spans bloquants</h2>{render_table(span_rows, SPAN_FIELDNAMES)}</div>
<div class="panel"><h2>Octets sources externes</h2>{render_table(byte_rows, BYTE_FIELDNAMES)}</div>
<script type="application/json" id="gradient-sequence-high-safe-low-exception-external-terminal-source-data">{html.escape(data_json)}</script>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Review external terminal source bytes for residual high-safe chains.")
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("--terminals", type=Path, default=DEFAULT_TERMINALS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Gradient External Terminal Source Review",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, byte_rows, span_rows = build(
        read_csv(args.slots),
        read_csv(args.terminals),
        read_csv(args.fixtures),
        read_csv(args.manifest),
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "bytes.csv", BYTE_FIELDNAMES, byte_rows)
    write_csv(args.output / "spans.csv", SPAN_FIELDNAMES, span_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, byte_rows, span_rows, args.output, args.title), encoding="utf-8")

    print(f"External terminal bytes: {summary['external_terminal_slots']}")
    print(f"Blocked root chains: {summary['external_terminal_root_chains']}")
    print(f"Blocker spans: {summary['blocker_span_rows']}")
    print(f"Top blocker span: {summary['top_blocker_span']} ({summary['top_blocker_span_chains']} chains)")
    print(f"Next probe: {summary['next_probe']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
