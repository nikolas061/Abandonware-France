#!/usr/bin/env python3
"""Probe external source support for normalized Frontier80 palette-walk runs."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path

from lolg_tex_gap_decoder_frontier80_clean_nonzero_palette_walk_producer_probe import (
    fixture_key,
    key_text,
    normalize_bytes,
    read_csv,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_clean_nonzero_palette_walk_external_source_probe")
DEFAULT_CANDIDATES = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_producer_probe/candidates.csv"
)
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CLEAN_FIXTURES = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_fixture_replay/fixtures.csv"
)
DEFAULT_RAW_ROOT = Path("C/LOLG")

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_runs",
    "palette_bytes",
    "fixture_sources",
    "fixture_best_any_exact_min",
    "fixture_best_any_exact_max",
    "fixture_best_known_exact_min",
    "fixture_best_known_exact_max",
    "raw_source_files",
    "raw_source_bytes",
    "raw_palette_exact_hits",
    "raw_palette_head_hits",
    "raw_best_head_exact",
    "terminal_sequences",
    "terminal_sequence_hits",
    "terminal_sequence_hit_files",
    "terminal_sequence_hit_bytes",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

CANDIDATE_FIELDNAMES = [
    "target_id",
    "rank",
    "pcx_name",
    "frontier_id",
    "start",
    "end",
    "length",
    "palette_bytes",
    "terminal_bytes",
    "fixture_best_any_exact",
    "fixture_best_any_ratio",
    "fixture_best_any_source_key",
    "fixture_best_any_source_start",
    "fixture_best_known_exact",
    "fixture_best_known_ratio",
    "fixture_best_known_source_key",
    "fixture_best_known_source_start",
    "raw_palette_exact_hits",
    "raw_palette_head_hits",
    "raw_best_head_exact",
    "raw_best_head_ratio",
    "raw_best_head_source",
    "raw_best_head_start",
    "terminal_sequence_hits",
    "terminal_sequence_hit_files",
    "verdict",
    "next_probe",
]

FIXTURE_FIELDNAMES = [
    "target_id",
    "source_key",
    "source_start",
    "source_known",
    "source_known_bytes",
    "normalized_exact_bytes",
    "normalized_exact_ratio",
    "raw_exact_bytes",
    "raw_exact_ratio",
    "source_head_hex",
    "normalized_source_head_hex",
]

RAW_HIT_FIELDNAMES = [
    "target_id",
    "hit_kind",
    "source_path",
    "source_start",
    "source_bytes",
    "exact_bytes",
    "exact_ratio",
    "source_head_hex",
    "target_head_hex",
]

TERMINAL_FIELDNAMES = [
    "target_id",
    "terminal_index",
    "terminal_hex",
    "length",
    "raw_sequence_hits",
    "raw_sequence_hit_files",
    "raw_byte_hit_files",
    "sample_source_path",
    "sample_source_start",
]


def manifest_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def load_bytes(path_text: str, issues: list[str], label: str, row_id: str) -> bytes:
    if not path_text:
        issues.append(f"{row_id}:missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"{row_id}:read_{label}_failed:{exc}")
        return b""


def known_window(mask: bytes, start: int, length: int) -> tuple[bool, int]:
    if start < 0 or length <= 0 or start + length > len(mask):
        return False, 0
    known = sum(1 for value in mask[start : start + length] if value)
    return known == length, known


def exact_count(left: bytes, right: bytes) -> int:
    return sum(1 for left_value, right_value in zip(left, right) if left_value == right_value)


def target_palette_and_terminals(data: bytes) -> tuple[bytes, list[bytes]]:
    normalized, _modes, palette_hits = normalize_bytes(data)
    palette = bytes(value for value, hit in zip(normalized, palette_hits) if hit)
    terminals: list[bytes] = []
    start: int | None = None
    for index, hit in enumerate(palette_hits):
        if hit:
            if start is not None:
                terminals.append(data[start:index])
                start = None
        elif start is None:
            start = index
    if start is not None:
        terminals.append(data[start:])
    return palette, terminals


def overlap_same_target(
    source_key: tuple[str, str, str],
    target_key: tuple[str, str, str],
    source_start: int,
    source_end: int,
    target_start: int,
    target_end: int,
) -> bool:
    return source_key == target_key and max(source_start, target_start) < min(source_end, target_end)


def build_fixture_data(
    manifest_rows: list[dict[str, str]],
    clean_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[tuple[str, str, str], dict[str, object]]:
    clean_by_key = {fixture_key(row): row for row in clean_rows}
    output: dict[tuple[str, str, str], dict[str, object]] = {}
    for manifest in manifest_rows:
        key = manifest_key(manifest)
        clean = clean_by_key.get(key, {})
        expected = load_bytes(manifest.get("expected_gap_path", ""), issues, "expected", key_text(key))
        known_mask = load_bytes(clean.get("known_mask_path", ""), issues, "known_mask", key_text(key)) if clean else b""
        output[key] = {
            "manifest": manifest,
            "clean": clean,
            "expected": expected,
            "known_mask": known_mask,
            "normalized": normalize_bytes(expected)[0],
        }
    return output


def score_fixture_sources(
    candidate: dict[str, str],
    target_palette: bytes,
    fixtures: dict[tuple[str, str, str], dict[str, object]],
    *,
    output_limit: int,
) -> tuple[list[dict[str, str]], dict[str, str], dict[str, str]]:
    target_key = fixture_key(candidate)
    target_start = int_value(candidate, "start")
    target_end = int_value(candidate, "end")
    length = len(target_palette)
    rows: list[dict[str, str]] = []
    best_any: dict[str, str] = {}
    best_known: dict[str, str] = {}

    if not target_palette:
        return rows, best_any, best_known

    for source_key, fixture in fixtures.items():
        expected = fixture.get("expected", b"")
        normalized = fixture.get("normalized", b"")
        known_mask = fixture.get("known_mask", b"")
        if not isinstance(expected, bytes) or not isinstance(normalized, bytes) or not isinstance(known_mask, bytes):
            continue
        if len(normalized) < length:
            continue
        for source_start in range(0, len(normalized) - length + 1):
            source_end = source_start + length
            if overlap_same_target(source_key, target_key, source_start, source_end, target_start, target_end):
                continue
            source = expected[source_start:source_end]
            source_normalized = normalized[source_start:source_end]
            normalized_exact = exact_count(source_normalized, target_palette)
            raw_exact = exact_count(source, target_palette)
            known_full, known_bytes = known_window(known_mask, source_start, length)
            row = {
                "target_id": candidate.get("target_id", ""),
                "source_key": key_text(source_key),
                "source_start": str(source_start),
                "source_known": "1" if known_full else "0",
                "source_known_bytes": str(known_bytes),
                "normalized_exact_bytes": str(normalized_exact),
                "normalized_exact_ratio": f"{normalized_exact / length:.6f}",
                "raw_exact_bytes": str(raw_exact),
                "raw_exact_ratio": f"{raw_exact / length:.6f}",
                "source_head_hex": source[:16].hex(),
                "normalized_source_head_hex": source_normalized[:16].hex(),
            }
            if not best_any or normalized_exact > int_value(best_any, "normalized_exact_bytes"):
                best_any = row
            if known_full and (
                not best_known or normalized_exact > int_value(best_known, "normalized_exact_bytes")
            ):
                best_known = row
            rows.append(row)

    rows.sort(
        key=lambda row: (
            -int_value(row, "normalized_exact_bytes"),
            -int_value(row, "source_known"),
            -int_value(row, "source_known_bytes"),
            row.get("source_key", ""),
            int_value(row, "source_start"),
        )
    )
    return rows[:output_limit], best_any, best_known


def raw_source_paths(raw_root: Path, suffixes: set[str], issues: list[str]) -> list[Path]:
    if not raw_root.exists():
        issues.append(f"missing_raw_root:{raw_root}")
        return []
    paths = []
    for path in raw_root.iterdir():
        if not path.is_file():
            continue
        if suffixes and path.suffix.lower() not in suffixes:
            continue
        paths.append(path)
    paths.sort(key=lambda path: str(path).lower())
    return paths


def find_all(data: bytes, needle: bytes, limit: int) -> list[int]:
    if not needle:
        return []
    hits: list[int] = []
    start = data.find(needle)
    while start >= 0:
        hits.append(start)
        if len(hits) >= limit:
            break
        start = data.find(needle, start + 1)
    return hits


def scan_raw_sources(
    candidate: dict[str, str],
    target_palette: bytes,
    raw_payloads: list[tuple[Path, bytes]],
    *,
    hit_limit: int,
) -> tuple[list[dict[str, str]], int, int, dict[str, str]]:
    rows: list[dict[str, str]] = []
    exact_hits = 0
    head_hits = 0
    best_head: dict[str, str] = {}
    if not target_palette:
        return rows, exact_hits, head_hits, best_head
    head = target_palette[: min(16, len(target_palette))]
    for path, data in raw_payloads:
        for pos in find_all(data, target_palette, hit_limit):
            exact_hits += 1
            rows.append(raw_hit_row(candidate, "full", path, data, target_palette, pos, len(target_palette)))
        for pos in find_all(data, head, hit_limit):
            head_hits += 1
            exact = exact_count(data[pos : pos + len(target_palette)], target_palette)
            row = raw_hit_row(candidate, "head", path, data, target_palette, pos, exact)
            if not best_head or exact > int_value(best_head, "exact_bytes"):
                best_head = row
            if len(rows) < hit_limit:
                rows.append(row)
    rows.sort(
        key=lambda row: (
            row.get("target_id", ""),
            0 if row.get("hit_kind") == "full" else 1,
            -int_value(row, "exact_bytes"),
            row.get("source_path", ""),
            int_value(row, "source_start"),
        )
    )
    return rows[:hit_limit], exact_hits, head_hits, best_head


def raw_hit_row(
    candidate: dict[str, str],
    hit_kind: str,
    path: Path,
    data: bytes,
    target: bytes,
    pos: int,
    exact: int,
) -> dict[str, str]:
    return {
        "target_id": candidate.get("target_id", ""),
        "hit_kind": hit_kind,
        "source_path": str(path),
        "source_start": str(pos),
        "source_bytes": str(len(data)),
        "exact_bytes": str(exact),
        "exact_ratio": f"{exact / len(target):.6f}" if target else "0.000000",
        "source_head_hex": data[pos : pos + 16].hex(),
        "target_head_hex": target[:16].hex(),
    }


def scan_terminals(
    candidate: dict[str, str],
    terminals: list[bytes],
    raw_payloads: list[tuple[Path, bytes]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, terminal in enumerate(terminals):
        sequence_hits = 0
        sequence_files: set[str] = set()
        byte_files: set[str] = set()
        sample_path = ""
        sample_start = ""
        for path, data in raw_payloads:
            hits = find_all(data, terminal, 1000000)
            if hits:
                sequence_hits += len(hits)
                sequence_files.add(str(path))
                if not sample_path:
                    sample_path = str(path)
                    sample_start = str(hits[0])
            if any(bytes([value]) in data for value in terminal):
                byte_files.add(str(path))
        rows.append(
            {
                "target_id": candidate.get("target_id", ""),
                "terminal_index": str(index),
                "terminal_hex": terminal.hex(),
                "length": str(len(terminal)),
                "raw_sequence_hits": str(sequence_hits),
                "raw_sequence_hit_files": str(len(sequence_files)),
                "raw_byte_hit_files": str(len(byte_files)),
                "sample_source_path": sample_path,
                "sample_source_start": sample_start,
            }
        )
    return rows


def build_candidate_record(
    candidate: dict[str, str],
    palette: bytes,
    terminals: list[bytes],
    fixture_best_any: dict[str, str],
    fixture_best_known: dict[str, str],
    raw_exact_hits: int,
    raw_head_hits: int,
    raw_best_head: dict[str, str],
    terminal_rows: list[dict[str, str]],
) -> dict[str, str]:
    fixture_any = int_value(fixture_best_any, "normalized_exact_bytes")
    fixture_known = int_value(fixture_best_known, "normalized_exact_bytes")
    raw_best = int_value(raw_best_head, "exact_bytes")
    terminal_sequence_hits = sum(int_value(row, "raw_sequence_hits") for row in terminal_rows)
    terminal_sequence_hit_files = sum(int_value(row, "raw_sequence_hit_files") for row in terminal_rows)
    palette_ready = raw_exact_hits > 0 or fixture_known >= len(palette)
    terminal_specific = all(int_value(row, "raw_sequence_hit_files") <= 1 for row in terminal_rows) if terminal_rows else True
    if palette_ready and terminal_specific:
        verdict = "palette_walk_external_source_ready"
        next_probe = "promote external-source palette-walk producer with terminal marker guard"
    elif raw_exact_hits == 0 and raw_best == 0 and fixture_any < max(1, len(palette) // 2):
        verdict = "palette_walk_external_source_absent"
        next_probe = "derive generated normalized palette-walk sequence and contextual terminal marker guard"
    else:
        verdict = "palette_walk_external_source_partial"
        next_probe = "profile partial external palette-walk anchors before generator fallback"
    return {
        "target_id": candidate.get("target_id", ""),
        "rank": candidate.get("rank", ""),
        "pcx_name": candidate.get("pcx_name", ""),
        "frontier_id": candidate.get("frontier_id", ""),
        "start": candidate.get("start", ""),
        "end": candidate.get("end", ""),
        "length": candidate.get("length", ""),
        "palette_bytes": str(len(palette)),
        "terminal_bytes": str(sum(len(terminal) for terminal in terminals)),
        "fixture_best_any_exact": str(fixture_any),
        "fixture_best_any_ratio": f"{fixture_any / len(palette):.6f}" if palette else "0.000000",
        "fixture_best_any_source_key": fixture_best_any.get("source_key", ""),
        "fixture_best_any_source_start": fixture_best_any.get("source_start", ""),
        "fixture_best_known_exact": str(fixture_known),
        "fixture_best_known_ratio": f"{fixture_known / len(palette):.6f}" if palette else "0.000000",
        "fixture_best_known_source_key": fixture_best_known.get("source_key", ""),
        "fixture_best_known_source_start": fixture_best_known.get("source_start", ""),
        "raw_palette_exact_hits": str(raw_exact_hits),
        "raw_palette_head_hits": str(raw_head_hits),
        "raw_best_head_exact": str(raw_best),
        "raw_best_head_ratio": f"{raw_best / len(palette):.6f}" if palette else "0.000000",
        "raw_best_head_source": raw_best_head.get("source_path", ""),
        "raw_best_head_start": raw_best_head.get("source_start", ""),
        "terminal_sequence_hits": str(terminal_sequence_hits),
        "terminal_sequence_hit_files": str(terminal_sequence_hit_files),
        "verdict": verdict,
        "next_probe": next_probe,
    }


def build_summary(
    candidate_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    raw_rows: list[dict[str, str]],
    terminal_rows: list[dict[str, str]],
    *,
    raw_file_count: int,
    raw_byte_count: int,
    issue_count: int,
) -> dict[str, str]:
    palette_bytes = sum(int_value(row, "palette_bytes") for row in candidate_rows)
    fixture_any_values = [int_value(row, "fixture_best_any_exact") for row in candidate_rows]
    fixture_known_values = [int_value(row, "fixture_best_known_exact") for row in candidate_rows]
    raw_exact_hits = sum(int_value(row, "raw_palette_exact_hits") for row in candidate_rows)
    raw_head_hits = sum(int_value(row, "raw_palette_head_hits") for row in candidate_rows)
    raw_best_head = max([int_value(row, "raw_best_head_exact") for row in candidate_rows] or [0])
    terminal_sequence_hits = sum(int_value(row, "raw_sequence_hits") for row in terminal_rows)
    terminal_sequence_hit_files = sum(int_value(row, "raw_sequence_hit_files") for row in terminal_rows)
    terminal_sequence_hit_bytes = sum(
        int_value(row, "length") for row in terminal_rows if int_value(row, "raw_sequence_hits") > 0
    )
    if candidate_rows and all(row.get("verdict") == "palette_walk_external_source_ready" for row in candidate_rows):
        verdict = "frontier80_clean_nonzero_palette_walk_external_source_ready"
        next_probe = "promote external-source palette-walk producer with terminal marker guard"
    elif raw_exact_hits == 0 and raw_best_head == 0:
        verdict = "frontier80_clean_nonzero_palette_walk_external_source_absent"
        next_probe = "derive generated normalized palette-walk sequence and contextual terminal marker guard"
    else:
        verdict = "frontier80_clean_nonzero_palette_walk_external_source_partial"
        next_probe = "profile partial external palette-walk anchors before generator fallback"
    return {
        "scope": "total",
        "candidate_runs": str(len(candidate_rows)),
        "palette_bytes": str(palette_bytes),
        "fixture_sources": str(len(fixture_rows)),
        "fixture_best_any_exact_min": str(min(fixture_any_values) if fixture_any_values else 0),
        "fixture_best_any_exact_max": str(max(fixture_any_values) if fixture_any_values else 0),
        "fixture_best_known_exact_min": str(min(fixture_known_values) if fixture_known_values else 0),
        "fixture_best_known_exact_max": str(max(fixture_known_values) if fixture_known_values else 0),
        "raw_source_files": str(raw_file_count),
        "raw_source_bytes": str(raw_byte_count),
        "raw_palette_exact_hits": str(raw_exact_hits),
        "raw_palette_head_hits": str(raw_head_hits),
        "raw_best_head_exact": str(raw_best_head),
        "terminal_sequences": str(len(terminal_rows)),
        "terminal_sequence_hits": str(terminal_sequence_hits),
        "terminal_sequence_hit_files": str(terminal_sequence_hit_files),
        "terminal_sequence_hit_bytes": str(terminal_sequence_hit_bytes),
        "issue_rows": str(issue_count),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 120) -> str:
    if not rows:
        return "<p>No rows.</p>"
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    candidate_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    raw_rows: list[dict[str, str]],
    terminal_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "candidates": candidate_rows,
        "fixture_sources": fixture_rows,
        "raw_hits": raw_rows,
        "terminals": terminal_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
            ("fixture_sources.csv", output_dir / "fixture_sources.csv"),
            ("raw_hits.csv", output_dir / "raw_hits.csv"),
            ("terminal_hits.csv", output_dir / "terminal_hits.csv"),
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
  --panel: #171f22;
  --line: #31424a;
  --text: #edf5f4;
  --muted: #9dafb5;
  --accent: #77d3b1;
  --warn: #f0c36a;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; min-height: 100vh; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
.wrap {{ width: min(1680px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12191b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 720; letter-spacing: 0; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 22px; font-weight: 760; line-height: 1.05; margin-top: 4px; }}
.warn {{ color: var(--warn); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1320px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Searches fixture-normalized sources and raw MIX files for contiguous palette-walk evidence.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Palette bytes</div><div class="value">{html.escape(summary['palette_bytes'])}</div></div>
    <div class="stat"><div class="label">Fixture best max</div><div class="value">{html.escape(summary['fixture_best_any_exact_max'])}</div></div>
    <div class="stat"><div class="label">Raw exact hits</div><div class="value warn">{html.escape(summary['raw_palette_exact_hits'])}</div></div>
    <div class="stat"><div class="label">Terminal hits</div><div class="value">{html.escape(summary['terminal_sequence_hits'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="sub">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</div></section>
  <section class="panel"><h2>Candidates</h2>{render_table(candidate_rows, CANDIDATE_FIELDNAMES)}</section>
  <section class="panel"><h2>Fixture sources</h2>{render_table(fixture_rows, FIXTURE_FIELDNAMES)}</section>
  <section class="panel"><h2>Raw hits</h2>{render_table(raw_rows, RAW_HIT_FIELDNAMES)}</section>
  <section class="panel"><h2>Terminal hits</h2>{render_table(terminal_rows, TERMINAL_FIELDNAMES)}</section>
</main>
<script type="application/json" id="palette-walk-external-source-data">{data_json}</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    candidates_path: Path,
    manifest_path: Path,
    clean_fixtures_path: Path,
    raw_root: Path,
    *,
    raw_suffixes: set[str],
    fixture_limit: int,
    raw_hit_limit: int,
    title: str,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    manifest_rows = read_csv(manifest_path)
    fixtures = build_fixture_data(manifest_rows, read_csv(clean_fixtures_path), issues)
    raw_paths = raw_source_paths(raw_root, raw_suffixes, issues)
    raw_payloads: list[tuple[Path, bytes]] = []
    for path in raw_paths:
        try:
            raw_payloads.append((path, path.read_bytes()))
        except OSError as exc:
            issues.append(f"read_raw_failed:{path}:{exc}")

    manifest_by_key = {manifest_key(row): row for row in manifest_rows}
    candidate_rows: list[dict[str, str]] = []
    fixture_rows: list[dict[str, str]] = []
    raw_rows: list[dict[str, str]] = []
    terminal_rows: list[dict[str, str]] = []
    for candidate in read_csv(candidates_path):
        key = fixture_key(candidate)
        manifest = manifest_by_key.get(key)
        if not manifest:
            issues.append(f"{candidate.get('target_id', key_text(key))}:missing_manifest")
            continue
        expected = load_bytes(manifest.get("expected_gap_path", ""), issues, "expected", candidate.get("target_id", ""))
        data = expected[int_value(candidate, "start") : int_value(candidate, "end")]
        palette, terminals = target_palette_and_terminals(data)
        local_fixture_rows, best_any, best_known = score_fixture_sources(
            candidate,
            palette,
            fixtures,
            output_limit=fixture_limit,
        )
        local_raw_rows, raw_exact_hits, raw_head_hits, best_head = scan_raw_sources(
            candidate,
            palette,
            raw_payloads,
            hit_limit=raw_hit_limit,
        )
        local_terminal_rows = scan_terminals(candidate, terminals, raw_payloads)
        candidate_rows.append(
            build_candidate_record(
                candidate,
                palette,
                terminals,
                best_any,
                best_known,
                raw_exact_hits,
                raw_head_hits,
                best_head,
                local_terminal_rows,
            )
        )
        fixture_rows.extend(local_fixture_rows)
        raw_rows.extend(local_raw_rows)
        terminal_rows.extend(local_terminal_rows)

    summary = build_summary(
        candidate_rows,
        fixture_rows,
        raw_rows,
        terminal_rows,
        raw_file_count=len(raw_payloads),
        raw_byte_count=sum(len(data) for _path, data in raw_payloads),
        issue_count=len(issues),
    )
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "candidates.csv", CANDIDATE_FIELDNAMES, candidate_rows)
    write_csv(output_dir / "fixture_sources.csv", FIXTURE_FIELDNAMES, fixture_rows)
    write_csv(output_dir / "raw_hits.csv", RAW_HIT_FIELDNAMES, raw_rows)
    write_csv(output_dir / "terminal_hits.csv", TERMINAL_FIELDNAMES, terminal_rows)
    (output_dir / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output_dir / "index.html").write_text(
        build_html(summary, candidate_rows, fixture_rows, raw_rows, terminal_rows, output_dir, title)
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe external source support for Frontier80 palette-walk runs.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--raw-suffix", action="append", default=[".mix"])
    parser.add_argument("--fixture-limit", type=int, default=8)
    parser.add_argument("--raw-hit-limit", type=int, default=24)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Clean Nonzero Palette Walk External Source Probe",
    )
    args = parser.parse_args()

    summary = write_report(
        args.output,
        args.candidates,
        args.manifest,
        args.clean_fixtures,
        args.raw_root,
        raw_suffixes={suffix.lower() if suffix.startswith(".") else f".{suffix.lower()}" for suffix in args.raw_suffix},
        fixture_limit=args.fixture_limit,
        raw_hit_limit=args.raw_hit_limit,
        title=args.title,
    )
    print(f"Palette bytes: {summary['palette_bytes']}")
    print(f"Fixture best any max: {summary['fixture_best_any_exact_max']}")
    print(f"Raw exact hits: {summary['raw_palette_exact_hits']}")
    print(f"Raw head hits: {summary['raw_palette_head_hits']}")
    print(f"Terminal hits: {summary['terminal_sequence_hits']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
