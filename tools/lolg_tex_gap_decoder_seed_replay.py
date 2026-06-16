#!/usr/bin/env python3
"""Replay a selected .tex zero/literal decoder seed over gap fixtures."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path

from PIL import Image

from lolg_tex_gap_decoder_risk_adjusted_probe import (
    DEFAULT_LITERALS,
    DEFAULT_OPERATIONS,
    enrich_literal_rows,
    fixture_key,
    length,
    op_key,
    select_literal,
    select_zero,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_seed_replay")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_FRONTIERS = Path("output/tex_gap_frontier_report/frontiers.csv")
DEFAULT_RISK_SUMMARY = Path("output/tex_gap_decoder_risk_adjusted_probe/summary.csv")
TARGET_SIZE = (1920, 1080)

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate",
    "priority",
    "zero_rule",
    "literal_rule",
    "fixture_rows",
    "operation_rows",
    "selected_ops",
    "trusted_ops",
    "false_ops",
    "selected_bytes",
    "trusted_bytes",
    "false_bytes",
    "unselected_bytes",
    "output_exact_bytes",
    "native_previews",
    "fullhd_previews",
    "issue_rows",
]

FIXTURE_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "fixture_bytes",
    "operations",
    "selected_ops",
    "trusted_ops",
    "false_ops",
    "selected_bytes",
    "trusted_bytes",
    "false_bytes",
    "unselected_bytes",
    "output_exact_bytes",
    "selected_exact_ratio",
    "decoded_path",
    "known_mask_path",
    "risk_mask_path",
    "native_preview_path",
    "fullhd_preview_path",
    "fullhd_width",
    "fullhd_height",
    "issues",
]

DECISION_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "op_index",
    "op_kind",
    "expected_start",
    "expected_end",
    "length",
    "zero_selected",
    "literal_selected",
    "decision",
    "risk_class",
    "selected_bytes",
    "trusted_bytes",
    "false_bytes",
    "output_exact_bytes",
    "source_offset",
    "source_end",
    "token_value",
    "token_plus3_match",
    "pre4_hex",
    "next2_hex",
    "issues",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def safe_stem(*parts: str) -> str:
    raw = "_".join(part for part in parts if part)
    return "".join(char if char.isalnum() or char in "-_." else "_" for char in raw).strip("_")


def fixture_sort_key(key: tuple[str, str, str]) -> tuple[int, str, str]:
    rank, pcx_name, frontier_id = key
    return int(rank) if rank.isdigit() else 999999, pcx_name, frontier_id


def parse_candidate(candidate: str) -> tuple[str, str, str]:
    parts = {}
    for item in candidate.split("|"):
        if "=" in item:
            key, value = item.split("=", 1)
            parts[key] = value
    priority = parts.get("priority", "")
    zero_rule = parts.get("zero", "")
    literal_rule = parts.get("literal", "")
    if not priority or not zero_rule or not literal_rule:
        raise ValueError(f"invalid candidate: {candidate}")
    return priority, zero_rule, literal_rule


def choose_candidate(summary_path: Path, mode: str, explicit: str) -> str:
    if explicit:
        return explicit
    rows = read_csv(summary_path)
    if len(rows) != 1:
        raise ValueError(f"{summary_path}: expected one summary row")
    row = rows[0]
    field = {
        "best_correct": "best_nonoracle_by_correct",
        "best_net": "best_nonoracle_by_net",
        "low_false": "best_low_false_candidate",
    }[mode]
    candidate = row.get(field, "")
    if not candidate:
        raise ValueError(f"{summary_path}: missing {field}")
    return candidate


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    path = Path(path_text)
    try:
        return path.read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def exact_byte_count(left: bytes, right: bytes) -> int:
    return sum(1 for index in range(min(len(left), len(right))) if left[index] == right[index])


def frontier_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], dict[str, str]]:
    output = {}
    for row in rows:
        key = (row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", ""))
        if key[0] and key[1] and key[2]:
            output[key] = row
    return output


def infer_gap_shape(frontier: dict[str, str], byte_count: int) -> tuple[int, int, int]:
    if byte_count <= 0:
        return 1, 1, 0
    gap_start = int_value(frontier, "gap_start")
    gap_start_x = int_value(frontier, "gap_start_x")
    gap_start_y = int_value(frontier, "gap_start_y")
    gap_end = int_value(frontier, "gap_end")
    gap_end_x = int_value(frontier, "gap_end_x")
    gap_end_y = int_value(frontier, "gap_end_y")
    width_candidates = []
    if gap_start_y > 0:
        width_candidates.append((gap_start - gap_start_x) // gap_start_y)
    if gap_end_y > 0:
        width_candidates.append((gap_end - gap_end_x) // gap_end_y)
    width_candidates = [value for value in width_candidates if value > 0]
    width = width_candidates[0] if width_candidates else min(256, byte_count)
    if width <= 0:
        width = max(1, min(256, byte_count))
    if gap_end_y >= gap_start_y and gap_end_y > 0:
        height = gap_end_y - gap_start_y + 1
    else:
        height = (byte_count + width - 1) // width
    return width, max(1, height), gap_start


def render_preview(
    *,
    expected: bytes,
    decoded: bytes,
    known_mask: bytes,
    risk_mask: bytes,
    frontier: dict[str, str],
    native_path: Path,
    fullhd_path: Path,
) -> tuple[int, int]:
    width, height, gap_start = infer_gap_shape(frontier, len(expected))
    gutter = 4
    panel_width = width
    image = Image.new("RGB", (panel_width * 3 + gutter * 2, height), (10, 12, 14))
    expected_pixels = image.load()

    for index, value in enumerate(expected):
        offset = gap_start + index if frontier else index
        x = offset % width if width else 0
        y = offset // width if width else 0
        if frontier:
            y -= int_value(frontier, "gap_start_y")
        if x < 0 or x >= width or y < 0 or y >= height:
            continue
        gray = int(value)
        expected_pixels[x, y] = (gray, gray, gray)

        decoded_x = x + panel_width + gutter
        if index < len(known_mask) and known_mask[index]:
            decoded_value = decoded[index] if index < len(decoded) else 0
            expected_pixels[decoded_x, y] = (decoded_value, decoded_value, decoded_value)
        else:
            expected_pixels[decoded_x, y] = (22, 26, 29)

        mask_x = x + panel_width * 2 + gutter * 2
        if index < len(known_mask) and known_mask[index]:
            if index < len(risk_mask) and risk_mask[index] >= 200:
                expected_pixels[mask_x, y] = (75, 190, 122)
            else:
                expected_pixels[mask_x, y] = (214, 118, 72)
        else:
            expected_pixels[mask_x, y] = (22, 26, 29)

    native_path.parent.mkdir(parents=True, exist_ok=True)
    fullhd_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(native_path)
    image.resize(TARGET_SIZE, Image.Resampling.NEAREST).save(fullhd_path)
    return TARGET_SIZE


def operation_literal_lookup(
    literal_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
) -> dict[tuple[str, str, str, str], dict[str, str]]:
    return {op_key(row): row for row in enrich_literal_rows(literal_rows, operation_rows)}


def decision_for(
    operation: dict[str, str],
    literal: dict[str, str] | None,
    *,
    priority: str,
    zero_rule: str,
    literal_rule: str,
) -> tuple[bool, bool, str]:
    zero_selected = select_zero(zero_rule, operation)
    literal_selected = select_literal(literal_rule, literal)
    if priority == "zero_first":
        if zero_selected:
            return zero_selected, literal_selected, "zero"
        if literal_selected:
            return zero_selected, literal_selected, "literal"
    elif priority == "literal_first":
        if literal_selected:
            return zero_selected, literal_selected, "literal"
        if zero_selected:
            return zero_selected, literal_selected, "zero"
    else:
        raise ValueError(f"unknown priority: {priority}")
    return zero_selected, literal_selected, ""


def selected_output(
    operation: dict[str, str],
    segment: bytes,
    decision: str,
    row_length: int,
    issues: list[str],
) -> bytes:
    if decision == "zero":
        return b"\x00" * row_length
    if decision != "literal":
        return b""
    source_offset = int_value(operation, "source_offset")
    source_end = int_value(operation, "source_end")
    if source_end <= source_offset:
        issues.append("invalid_literal_source_range")
        return b""
    output = segment[source_offset:source_end]
    if len(output) != row_length:
        issues.append("literal_source_length_mismatch")
    return output[:row_length]


def risk_class(operation: dict[str, str], literal: dict[str, str] | None, decision: str) -> str:
    if decision == "zero":
        return "true_zero" if operation.get("op_kind") == "zero" else "false_zero"
    if decision == "literal":
        return "true_literal" if literal and literal.get("token_plus3_match") == "1" else "false_literal"
    return "unselected"


def build_rows(
    *,
    output_dir: Path,
    fixture_rows: list[dict[str, str]],
    frontier_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    literal_rows: list[dict[str, str]],
    candidate: str,
    priority: str,
    zero_rule: str,
    literal_rule: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    fixtures = {fixture_key(row): row for row in fixture_rows}
    frontiers = frontier_lookup(frontier_rows)
    operations_by_fixture: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for operation in operation_rows:
        operations_by_fixture[fixture_key(operation)].append(operation)
    literal_by_op = operation_literal_lookup(literal_rows, operation_rows)

    fixture_output_dir = output_dir / "fixtures"
    native_preview_dir = output_dir / "native"
    fullhd_preview_dir = output_dir / "fullhd"
    fixture_output_dir.mkdir(parents=True, exist_ok=True)
    native_preview_dir.mkdir(parents=True, exist_ok=True)
    fullhd_preview_dir.mkdir(parents=True, exist_ok=True)

    all_fixture_rows: list[dict[str, str]] = []
    all_decision_rows: list[dict[str, str]] = []
    issue_rows = 0

    for key in sorted(operations_by_fixture, key=fixture_sort_key):
        fixture = fixtures.get(key, {})
        fixture_issues = ["missing_fixture_manifest_row"] if not fixture else []
        expected = load_bytes(fixture.get("expected_gap_path", ""), fixture_issues, "expected")
        segment = load_bytes(fixture.get("segment_gap_path", ""), fixture_issues, "segment")
        decoded = bytearray(len(expected))
        known_mask = bytearray(len(expected))
        risk_mask = bytearray(len(expected))
        stats = {
            "operations": 0,
            "selected_ops": 0,
            "trusted_ops": 0,
            "false_ops": 0,
            "selected_bytes": 0,
            "trusted_bytes": 0,
            "false_bytes": 0,
            "output_exact_bytes": 0,
        }

        for operation in sorted(operations_by_fixture[key], key=lambda row: int_value(row, "op_index")):
            op_issues: list[str] = []
            row_length = length(operation)
            expected_start = int_value(operation, "expected_start")
            expected_end = int_value(operation, "expected_end")
            if expected_end - expected_start != row_length:
                op_issues.append("expected_range_length_mismatch")
            expected_slice = expected[expected_start:expected_end]
            if len(expected_slice) != row_length:
                op_issues.append("expected_slice_length_mismatch")

            literal = literal_by_op.get(op_key(operation))
            zero_selected, literal_selected, decision = decision_for(
                operation,
                literal,
                priority=priority,
                zero_rule=zero_rule,
                literal_rule=literal_rule,
            )
            output = selected_output(operation, segment, decision, row_length, op_issues)
            if decision and len(output) != row_length:
                output = output + (b"\x00" * max(0, row_length - len(output)))
            risk = risk_class(operation, literal, decision)
            selected_bytes = row_length if decision else 0
            trusted_bytes = row_length if risk.startswith("true_") else 0
            false_bytes = row_length if risk.startswith("false_") else 0
            output_exact = exact_byte_count(output, expected_slice) if decision else 0

            if decision and expected_start < len(decoded):
                end = min(expected_end, len(decoded))
                write_size = max(0, end - expected_start)
                decoded[expected_start:end] = output[:write_size]
                known_mask[expected_start:end] = b"\xff" * write_size
                risk_mask[expected_start:end] = bytes(
                    [255 if risk.startswith("true_") else 96]
                ) * write_size

            stats["operations"] += 1
            if decision:
                stats["selected_ops"] += 1
            if risk.startswith("true_"):
                stats["trusted_ops"] += 1
            if risk.startswith("false_"):
                stats["false_ops"] += 1
            stats["selected_bytes"] += selected_bytes
            stats["trusted_bytes"] += trusted_bytes
            stats["false_bytes"] += false_bytes
            stats["output_exact_bytes"] += output_exact

            if op_issues:
                issue_rows += 1
            all_decision_rows.append(
                {
                    "rank": key[0],
                    "archive": operation.get("archive", ""),
                    "archive_tag": operation.get("archive_tag", ""),
                    "pcx_name": key[1],
                    "frontier_id": key[2],
                    "op_index": operation.get("op_index", ""),
                    "op_kind": operation.get("op_kind", ""),
                    "expected_start": operation.get("expected_start", ""),
                    "expected_end": operation.get("expected_end", ""),
                    "length": str(row_length),
                    "zero_selected": "1" if zero_selected else "0",
                    "literal_selected": "1" if literal_selected else "0",
                    "decision": decision,
                    "risk_class": risk,
                    "selected_bytes": str(selected_bytes),
                    "trusted_bytes": str(trusted_bytes),
                    "false_bytes": str(false_bytes),
                    "output_exact_bytes": str(output_exact),
                    "source_offset": operation.get("source_offset", ""),
                    "source_end": operation.get("source_end", ""),
                    "token_value": literal.get("token_value", "") if literal else "",
                    "token_plus3_match": literal.get("token_plus3_match", "") if literal else "",
                    "pre4_hex": operation.get("pre4_hex", ""),
                    "next2_hex": operation.get("next2_hex", ""),
                    "issues": ";".join(op_issues),
                }
            )

        if fixture_issues:
            issue_rows += 1
        stem = safe_stem(f"rank{int(key[0]):03d}" if key[0].isdigit() else f"rank{key[0]}", key[1], f"frontier{key[2]}")
        decoded_path = fixture_output_dir / f"{stem}_decoded_seed.bin"
        known_mask_path = fixture_output_dir / f"{stem}_known_mask.bin"
        risk_mask_path = fixture_output_dir / f"{stem}_risk_mask.bin"
        decoded_path.write_bytes(decoded)
        known_mask_path.write_bytes(known_mask)
        risk_mask_path.write_bytes(risk_mask)
        native_preview_path = native_preview_dir / f"{stem}_seed_replay.png"
        fullhd_preview_path = fullhd_preview_dir / f"{stem}_seed_replay_fullhd.png"
        fullhd_width, fullhd_height = render_preview(
            expected=expected,
            decoded=bytes(decoded),
            known_mask=bytes(known_mask),
            risk_mask=bytes(risk_mask),
            frontier=frontiers.get((fixture.get("archive", ""), key[1], key[2]), {}),
            native_path=native_preview_path,
            fullhd_path=fullhd_preview_path,
        )

        fixture_bytes = len(expected)
        selected_exact_ratio = (
            stats["output_exact_bytes"] / stats["selected_bytes"] if stats["selected_bytes"] else 0.0
        )
        all_fixture_rows.append(
            {
                "rank": key[0],
                "archive": fixture.get("archive", ""),
                "archive_tag": fixture.get("archive_tag", ""),
                "pcx_name": key[1],
                "frontier_id": key[2],
                "fixture_bytes": str(fixture_bytes),
                "operations": str(stats["operations"]),
                "selected_ops": str(stats["selected_ops"]),
                "trusted_ops": str(stats["trusted_ops"]),
                "false_ops": str(stats["false_ops"]),
                "selected_bytes": str(stats["selected_bytes"]),
                "trusted_bytes": str(stats["trusted_bytes"]),
                "false_bytes": str(stats["false_bytes"]),
                "unselected_bytes": str(max(0, fixture_bytes - stats["selected_bytes"])),
                "output_exact_bytes": str(stats["output_exact_bytes"]),
                "selected_exact_ratio": f"{selected_exact_ratio:.6f}",
                "decoded_path": decoded_path.as_posix(),
                "known_mask_path": known_mask_path.as_posix(),
                "risk_mask_path": risk_mask_path.as_posix(),
                "native_preview_path": native_preview_path.as_posix(),
                "fullhd_preview_path": fullhd_preview_path.as_posix(),
                "fullhd_width": str(fullhd_width),
                "fullhd_height": str(fullhd_height),
                "issues": ";".join(fixture_issues),
            }
        )

    summary = {
        "scope": "total",
        "candidate": candidate,
        "priority": priority,
        "zero_rule": zero_rule,
        "literal_rule": literal_rule,
        "fixture_rows": str(len(all_fixture_rows)),
        "operation_rows": str(len(all_decision_rows)),
        "selected_ops": str(sum(int_value(row, "selected_ops") for row in all_fixture_rows)),
        "trusted_ops": str(sum(int_value(row, "trusted_ops") for row in all_fixture_rows)),
        "false_ops": str(sum(int_value(row, "false_ops") for row in all_fixture_rows)),
        "selected_bytes": str(sum(int_value(row, "selected_bytes") for row in all_fixture_rows)),
        "trusted_bytes": str(sum(int_value(row, "trusted_bytes") for row in all_fixture_rows)),
        "false_bytes": str(sum(int_value(row, "false_bytes") for row in all_fixture_rows)),
        "unselected_bytes": str(sum(int_value(row, "unselected_bytes") for row in all_fixture_rows)),
        "output_exact_bytes": str(sum(int_value(row, "output_exact_bytes") for row in all_fixture_rows)),
        "native_previews": str(sum(1 for row in all_fixture_rows if row.get("native_preview_path"))),
        "fullhd_previews": str(
            sum(
                1
                for row in all_fixture_rows
                if (row.get("fullhd_width"), row.get("fullhd_height"))
                == (str(TARGET_SIZE[0]), str(TARGET_SIZE[1]))
            )
        ),
        "issue_rows": str(issue_rows),
    }
    return summary, all_fixture_rows, all_decision_rows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 160) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def render_preview_card(row: dict[str, str], output_dir: Path) -> str:
    image = html.escape(relative_href(row.get("fullhd_preview_path", ""), output_dir))
    return f"""
<article class="card">
  <a class="preview" href="{image}"><img src="{image}" loading="lazy" decoding="async" alt=""></a>
  <div class="card-body">
    <div class="card-title">#{html.escape(row.get('rank', ''))} {html.escape(row.get('pcx_name', ''))}</div>
    <div class="muted">{html.escape(row.get('selected_bytes', ''))} selected - {html.escape(row.get('trusted_bytes', ''))} trusted - {html.escape(row.get('false_bytes', ''))} risk</div>
    <a href="{image}">Full HD</a>
  </div>
</article>"""


def build_html(
    summary: dict[str, str],
    fixture_rows: list[dict[str, str]],
    decision_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "fixtures": fixture_rows, "decisions": decision_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("fixtures.csv", output_dir / "fixtures.csv"),
            ("decisions.csv", output_dir / "decisions.csv"),
        )
    )
    top_decisions = sorted(
        [row for row in decision_rows if row.get("decision")],
        key=lambda row: (
            int_value(row, "false_bytes"),
            -int_value(row, "trusted_bytes"),
            int_value(row, "rank"),
            int_value(row, "op_index"),
        ),
        reverse=True,
    )
    cards = "\n".join(render_preview_card(row, output_dir) for row in fixture_rows)
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
  --panel: #171f22;
  --line: #31424a;
  --text: #edf5f4;
  --muted: #9dafb5;
  --accent: #77d3b1;
  --ok: #80df94;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.wrap {{ width: min(1680px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12191b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 720; letter-spacing: 0; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 10px; }}
.stat, .panel, .card {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); }}
.stat, .panel {{ padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 22px; font-weight: 760; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.panel {{ overflow-x: auto; }}
.preview {{ display: block; aspect-ratio: 16 / 9; background: #07090a; border-bottom: 1px solid var(--line); overflow: hidden; }}
.preview img {{ width: 100%; height: 100%; object-fit: contain; image-rendering: pixelated; }}
.card-body {{ padding: 10px; display: grid; gap: 6px; }}
.card-title {{ font-weight: 700; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1380px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
code {{ color: var(--accent); }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub"><code>{html.escape(summary['candidate'])}</code></div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Trusted bytes</div><div class="value ok">{html.escape(summary['trusted_bytes'])}</div></div>
    <div class="stat"><div class="label">False-risk bytes</div><div class="value">{html.escape(summary['false_bytes'])}</div></div>
    <div class="stat"><div class="label">Selected bytes</div><div class="value">{html.escape(summary['selected_bytes'])}</div></div>
    <div class="stat"><div class="label">Fixtures</div><div class="value">{html.escape(summary['fixture_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="cards">{cards}</section>
  <section class="panel"><h2>Fixtures</h2>{render_table(fixture_rows, FIXTURE_FIELDNAMES)}</section>
  <section class="panel"><h2>Selected decisions</h2>{render_table(top_decisions, DECISION_FIELDNAMES)}</section>
</main>
<script>
const TEX_GAP_DECODER_SEED_REPLAY = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    fixtures_path: Path,
    frontiers_path: Path,
    operations_path: Path,
    literals_path: Path,
    risk_summary_path: Path,
    *,
    candidate_mode: str,
    candidate: str,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate_name = choose_candidate(risk_summary_path, candidate_mode, candidate)
    priority, zero_rule, literal_rule = parse_candidate(candidate_name)
    summary, fixture_rows, decision_rows = build_rows(
        output_dir=output_dir,
        fixture_rows=read_csv(fixtures_path),
        frontier_rows=read_csv(frontiers_path),
        operation_rows=read_csv(operations_path),
        literal_rows=read_csv(literals_path),
        candidate=candidate_name,
        priority=priority,
        zero_rule=zero_rule,
        literal_rule=literal_rule,
    )
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "fixtures.csv", FIXTURE_FIELDNAMES, fixture_rows)
    write_csv(output_dir / "decisions.csv", DECISION_FIELDNAMES, decision_rows)
    (output_dir / "index.html").write_text(build_html(summary, fixture_rows, decision_rows, output_dir, title))
    return summary, fixture_rows, decision_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay a selected .tex zero/literal decoder seed.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--frontiers", type=Path, default=DEFAULT_FRONTIERS)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--literals", type=Path, default=DEFAULT_LITERALS)
    parser.add_argument("--risk-summary", type=Path, default=DEFAULT_RISK_SUMMARY)
    parser.add_argument(
        "--candidate-mode",
        choices=("low_false", "best_net", "best_correct"),
        default="low_false",
    )
    parser.add_argument("--candidate", default="")
    parser.add_argument("--title", default="Lands of Lore II .tex Decoder Seed Replay")
    args = parser.parse_args()

    summary, _fixtures, _decisions = write_report(
        args.output,
        args.fixtures,
        args.frontiers,
        args.operations,
        args.literals,
        args.risk_summary,
        candidate_mode=args.candidate_mode,
        candidate=args.candidate,
        title=args.title,
    )
    print(f"Candidate: {summary['candidate']}")
    print(f"Fixtures: {summary['fixture_rows']}")
    print(f"Selected bytes: {summary['selected_bytes']}")
    print(f"Trusted bytes: {summary['trusted_bytes']}")
    print(f"False-risk bytes: {summary['false_bytes']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
