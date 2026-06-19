#!/usr/bin/env python3
"""Split normalized palette-walk candidates into source and terminal evidence."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter
from pathlib import Path

from lolg_tex_gap_decoder_frontier80_clean_nonzero_palette_walk_producer_probe import (
    fixture_key,
    key_text,
    normalize_bytes,
    read_csv,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_clean_nonzero_palette_walk_source_terminal_split_probe")
DEFAULT_CANDIDATES = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_producer_probe/candidates.csv"
)
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_runs",
    "candidate_bytes",
    "palette_bytes",
    "terminal_segments",
    "terminal_bytes",
    "source_rows",
    "best_source_exact_min",
    "best_source_exact_max",
    "best_source_exact_ratio_max",
    "terminal_sequence_hits",
    "terminal_sequence_hit_bytes",
    "terminal_byte_hit_bytes",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

SOURCE_FIELDNAMES = [
    "target_id",
    "rank",
    "pcx_name",
    "frontier_id",
    "source_name",
    "source_bytes",
    "transform",
    "parameter",
    "target_palette_bytes",
    "best_exact_bytes",
    "best_exact_ratio",
    "best_source_start",
    "source_head_hex",
    "transformed_head_hex",
    "target_head_hex",
]

TERMINAL_FIELDNAMES = [
    "target_id",
    "terminal_index",
    "rank",
    "pcx_name",
    "frontier_id",
    "run_offset_start",
    "run_offset_end",
    "absolute_start",
    "absolute_end",
    "length",
    "terminal_hex",
    "segment_exact_pos",
    "control_exact_pos",
    "fragment_exact_pos",
    "segment_byte_hits",
    "control_byte_hits",
    "fragment_byte_hits",
    "best_source_name",
    "best_source_exact_pos",
    "sequence_hit",
]

CANDIDATE_FIELDNAMES = [
    "target_id",
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "start",
    "end",
    "length",
    "palette_bytes",
    "terminal_bytes",
    "best_source_name",
    "best_source_transform",
    "best_source_parameter",
    "best_source_exact_bytes",
    "best_source_exact_ratio",
    "terminal_sequence_hits",
    "terminal_sequence_hit_bytes",
    "terminal_byte_hit_bytes",
    "verdict",
    "next_probe",
]


def manifest_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def load_bytes(path_text: str, issues: list[str], label: str, target_id: str) -> bytes:
    if not path_text:
        issues.append(f"{target_id}:missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"{target_id}:read_{label}_failed:{exc}")
        return b""


def transform_bytes(data: bytes, transform: str, parameter: int = 0) -> bytes:
    if transform == "identity":
        return data
    if transform == "normalize":
        return normalize_bytes(data)[0]
    if transform == "low7":
        return bytes(value & 0x7F for value in data)
    if transform == "not":
        return bytes(value ^ 0xFF for value in data)
    if transform == "minus11":
        return bytes((value - 0x11) & 0xFF for value in data)
    if transform == "plus11":
        return bytes((value + 0x11) & 0xFF for value in data)
    if transform == "add":
        return bytes((value + parameter) & 0xFF for value in data)
    if transform == "xor":
        return bytes(value ^ parameter for value in data)
    raise ValueError(f"unknown transform: {transform}")


def exact_count(left: bytes, right: bytes) -> int:
    return sum(1 for left_value, right_value in zip(left, right) if left_value == right_value)


def best_window(source: bytes, target: bytes) -> tuple[int, int]:
    if not target or len(source) < len(target):
        return 0, 0
    best_exact = -1
    best_start = 0
    for start in range(0, len(source) - len(target) + 1):
        exact = exact_count(source[start : start + len(target)], target)
        if exact > best_exact:
            best_exact = exact
            best_start = start
    return max(best_exact, 0), best_start


def best_constant_window(source: bytes, target: bytes, transform: str) -> tuple[int, int, int]:
    if not target or len(source) < len(target):
        return 0, 0, 0
    best_exact = -1
    best_start = 0
    best_parameter = 0
    for start in range(0, len(source) - len(target) + 1):
        window = source[start : start + len(target)]
        if transform == "add":
            counts = Counter((target_value - source_value) & 0xFF for source_value, target_value in zip(window, target))
        elif transform == "xor":
            counts = Counter(source_value ^ target_value for source_value, target_value in zip(window, target))
        else:
            raise ValueError(transform)
        parameter, exact = counts.most_common(1)[0]
        if exact > best_exact:
            best_exact = exact
            best_start = start
            best_parameter = parameter
    return max(best_exact, 0), best_start, best_parameter


def source_bytes(manifest: dict[str, str], issues: list[str], target_id: str) -> dict[str, bytes]:
    return {
        "segment": load_bytes(manifest.get("segment_gap_path", ""), issues, "segment", target_id),
        "control": load_bytes(manifest.get("control_prefix_path", ""), issues, "control", target_id),
        "fragment": load_bytes(manifest.get("fragment_path", ""), issues, "fragment", target_id),
    }


def palette_target(data: bytes) -> tuple[bytes, list[bool]]:
    normalized, _modes, palette_hits = normalize_bytes(data)
    return bytes(value for value, hit in zip(normalized, palette_hits) if hit), palette_hits


def terminal_ranges(palette_hits: list[bool]) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    start: int | None = None
    for index, hit in enumerate(palette_hits):
        if hit:
            if start is not None:
                ranges.append((start, index))
                start = None
        elif start is None:
            start = index
    if start is not None:
        ranges.append((start, len(palette_hits)))
    return ranges


def build_source_rows(
    candidate: dict[str, str],
    manifest: dict[str, str],
    expected: bytes,
    sources: dict[str, bytes],
) -> list[dict[str, str]]:
    start = int_value(candidate, "start")
    end = int_value(candidate, "end")
    data = expected[start:end]
    target_palette, _palette_hits = palette_target(data)
    rows: list[dict[str, str]] = []
    for source_name, source in sources.items():
        for transform in ("identity", "normalize", "low7", "not", "minus11", "plus11"):
            transformed = transform_bytes(source, transform)
            exact, source_start = best_window(transformed, target_palette)
            rows.append(
                source_row(candidate, manifest, source_name, source, transformed, target_palette, transform, "", exact, source_start)
            )
        for transform in ("add", "xor"):
            exact, source_start, parameter = best_constant_window(source, target_palette, transform)
            transformed = transform_bytes(source, transform, parameter)
            rows.append(
                source_row(
                    candidate,
                    manifest,
                    source_name,
                    source,
                    transformed,
                    target_palette,
                    transform,
                    f"0x{parameter:02x}",
                    exact,
                    source_start,
                )
            )
    rows.sort(
        key=lambda row: (
            -int_value(row, "best_exact_bytes"),
            row.get("source_name", ""),
            row.get("transform", ""),
            int_value(row, "best_source_start"),
        )
    )
    return rows


def source_row(
    candidate: dict[str, str],
    manifest: dict[str, str],
    source_name: str,
    source: bytes,
    transformed: bytes,
    target: bytes,
    transform: str,
    parameter: str,
    exact: int,
    source_start: int,
) -> dict[str, str]:
    target_len = len(target)
    return {
        "target_id": candidate.get("target_id", ""),
        "rank": candidate.get("rank", manifest.get("rank", "")),
        "pcx_name": candidate.get("pcx_name", manifest.get("pcx_name", "")),
        "frontier_id": candidate.get("frontier_id", manifest.get("frontier_id", "")),
        "source_name": source_name,
        "source_bytes": str(len(source)),
        "transform": transform,
        "parameter": parameter,
        "target_palette_bytes": str(target_len),
        "best_exact_bytes": str(exact),
        "best_exact_ratio": f"{exact / target_len:.6f}" if target_len else "0.000000",
        "best_source_start": str(source_start),
        "source_head_hex": source[source_start : source_start + 16].hex() if source else "",
        "transformed_head_hex": transformed[source_start : source_start + 16].hex() if transformed else "",
        "target_head_hex": target[:16].hex(),
    }


def byte_hit_count(source: bytes, data: bytes) -> int:
    return sum(1 for value in data if bytes([value]) in source)


def build_terminal_rows(
    candidate: dict[str, str],
    manifest: dict[str, str],
    expected: bytes,
    sources: dict[str, bytes],
) -> list[dict[str, str]]:
    start = int_value(candidate, "start")
    end = int_value(candidate, "end")
    data = expected[start:end]
    _target_palette, palette_hits = palette_target(data)
    rows: list[dict[str, str]] = []
    for terminal_index, (run_start, run_end) in enumerate(terminal_ranges(palette_hits)):
        chunk = data[run_start:run_end]
        positions = {name: source.find(chunk) for name, source in sources.items()}
        best_name = ""
        best_pos = -1
        for name in ("fragment", "control", "segment"):
            if positions.get(name, -1) >= 0:
                best_name = name
                best_pos = positions[name]
                break
        rows.append(
            {
                "target_id": candidate.get("target_id", ""),
                "terminal_index": str(terminal_index),
                "rank": candidate.get("rank", manifest.get("rank", "")),
                "pcx_name": candidate.get("pcx_name", manifest.get("pcx_name", "")),
                "frontier_id": candidate.get("frontier_id", manifest.get("frontier_id", "")),
                "run_offset_start": str(run_start),
                "run_offset_end": str(run_end),
                "absolute_start": str(start + run_start),
                "absolute_end": str(start + run_end),
                "length": str(len(chunk)),
                "terminal_hex": chunk.hex(),
                "segment_exact_pos": str(positions.get("segment", -1)),
                "control_exact_pos": str(positions.get("control", -1)),
                "fragment_exact_pos": str(positions.get("fragment", -1)),
                "segment_byte_hits": str(byte_hit_count(sources.get("segment", b""), chunk)),
                "control_byte_hits": str(byte_hit_count(sources.get("control", b""), chunk)),
                "fragment_byte_hits": str(byte_hit_count(sources.get("fragment", b""), chunk)),
                "best_source_name": best_name,
                "best_source_exact_pos": "" if best_pos < 0 else str(best_pos),
                "sequence_hit": "1" if best_pos >= 0 else "0",
            }
        )
    return rows


def candidate_record(
    candidate: dict[str, str],
    source_rows: list[dict[str, str]],
    terminal_rows: list[dict[str, str]],
) -> dict[str, str]:
    best_source = source_rows[0] if source_rows else {}
    terminal_bytes = sum(int_value(row, "length") for row in terminal_rows)
    terminal_sequence_hits = sum(1 for row in terminal_rows if row.get("sequence_hit") == "1")
    terminal_sequence_hit_bytes = sum(
        int_value(row, "length") for row in terminal_rows if row.get("sequence_hit") == "1"
    )
    terminal_byte_hit_bytes = sum(
        max(
            int_value(row, "segment_byte_hits"),
            int_value(row, "control_byte_hits"),
            int_value(row, "fragment_byte_hits"),
        )
        for row in terminal_rows
    )
    palette_bytes = int_value(candidate, "normalized_palette_bytes")
    source_exact = int_value(best_source, "best_exact_bytes")
    ready = source_exact >= palette_bytes and terminal_sequence_hit_bytes >= terminal_bytes
    verdict = (
        "palette_walk_source_terminal_split_ready"
        if ready
        else "palette_walk_source_terminal_split_external_source_needed"
    )
    next_probe = (
        "promote source-terminal split palette-walk producer"
        if ready
        else "expand palette-walk source search beyond local segment/control and split d2/0a/5f terminal marker"
    )
    return {
        "target_id": candidate.get("target_id", ""),
        "rank": candidate.get("rank", ""),
        "archive": candidate.get("archive", ""),
        "archive_tag": candidate.get("archive_tag", ""),
        "pcx_name": candidate.get("pcx_name", ""),
        "frontier_id": candidate.get("frontier_id", ""),
        "start": candidate.get("start", ""),
        "end": candidate.get("end", ""),
        "length": candidate.get("length", ""),
        "palette_bytes": str(palette_bytes),
        "terminal_bytes": str(terminal_bytes),
        "best_source_name": best_source.get("source_name", ""),
        "best_source_transform": best_source.get("transform", ""),
        "best_source_parameter": best_source.get("parameter", ""),
        "best_source_exact_bytes": str(source_exact),
        "best_source_exact_ratio": best_source.get("best_exact_ratio", "0.000000"),
        "terminal_sequence_hits": str(terminal_sequence_hits),
        "terminal_sequence_hit_bytes": str(terminal_sequence_hit_bytes),
        "terminal_byte_hit_bytes": str(terminal_byte_hit_bytes),
        "verdict": verdict,
        "next_probe": next_probe,
    }


def build_summary(
    candidate_rows: list[dict[str, str]],
    source_rows: list[dict[str, str]],
    terminal_rows: list[dict[str, str]],
    issue_count: int,
) -> dict[str, str]:
    palette_bytes = sum(int_value(row, "palette_bytes") for row in candidate_rows)
    terminal_bytes = sum(int_value(row, "terminal_bytes") for row in candidate_rows)
    best_values = [int_value(row, "best_source_exact_bytes") for row in candidate_rows]
    best_ratio_values = [float(row.get("best_source_exact_ratio", "0") or 0) for row in candidate_rows]
    terminal_sequence_hits = sum(int_value(row, "terminal_sequence_hits") for row in candidate_rows)
    terminal_sequence_hit_bytes = sum(int_value(row, "terminal_sequence_hit_bytes") for row in candidate_rows)
    terminal_byte_hit_bytes = sum(int_value(row, "terminal_byte_hit_bytes") for row in candidate_rows)
    ready = bool(candidate_rows) and all(row.get("verdict", "").endswith("_ready") for row in candidate_rows)
    if ready:
        verdict = "frontier80_clean_nonzero_palette_walk_source_terminal_split_ready"
        next_probe = "promote source-terminal split palette-walk producer"
    elif candidate_rows:
        verdict = "frontier80_clean_nonzero_palette_walk_source_terminal_split_external_source_needed"
        next_probe = "expand palette-walk source search beyond local segment/control and split d2/0a/5f terminal marker"
    else:
        verdict = "frontier80_clean_nonzero_palette_walk_source_terminal_split_no_candidates"
        next_probe = "return to clean-gap nonzero run queue"
    return {
        "scope": "total",
        "candidate_runs": str(len(candidate_rows)),
        "candidate_bytes": str(sum(int_value(row, "length") for row in candidate_rows)),
        "palette_bytes": str(palette_bytes),
        "terminal_segments": str(len(terminal_rows)),
        "terminal_bytes": str(terminal_bytes),
        "source_rows": str(len(source_rows)),
        "best_source_exact_min": str(min(best_values) if best_values else 0),
        "best_source_exact_max": str(max(best_values) if best_values else 0),
        "best_source_exact_ratio_max": f"{max(best_ratio_values) if best_ratio_values else 0:.6f}",
        "terminal_sequence_hits": str(terminal_sequence_hits),
        "terminal_sequence_hit_bytes": str(terminal_sequence_hit_bytes),
        "terminal_byte_hit_bytes": str(terminal_byte_hit_bytes),
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
    source_rows: list[dict[str, str]],
    terminal_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "candidates": candidate_rows,
        "sources": source_rows,
        "terminals": terminal_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
            ("source_scores.csv", output_dir / "source_scores.csv"),
            ("terminal_segments.csv", output_dir / "terminal_segments.csv"),
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
    <div class="sub">Scores local source streams for normalized palette bytes and searches terminal marker sequences.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Palette bytes</div><div class="value">{html.escape(summary['palette_bytes'])}</div></div>
    <div class="stat"><div class="label">Terminal bytes</div><div class="value">{html.escape(summary['terminal_bytes'])}</div></div>
    <div class="stat"><div class="label">Best source max</div><div class="value warn">{html.escape(summary['best_source_exact_max'])}</div></div>
    <div class="stat"><div class="label">Terminal sequence bytes</div><div class="value">{html.escape(summary['terminal_sequence_hit_bytes'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="sub">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</div></section>
  <section class="panel"><h2>Candidates</h2>{render_table(candidate_rows, CANDIDATE_FIELDNAMES)}</section>
  <section class="panel"><h2>Source scores</h2>{render_table(source_rows, SOURCE_FIELDNAMES)}</section>
  <section class="panel"><h2>Terminal segments</h2>{render_table(terminal_rows, TERMINAL_FIELDNAMES)}</section>
</main>
<script type="application/json" id="palette-walk-source-terminal-data">{data_json}</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    candidates_path: Path,
    manifest_path: Path,
    *,
    title: str,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    manifest_rows = {manifest_key(row): row for row in read_csv(manifest_path)}
    candidate_rows: list[dict[str, str]] = []
    source_rows: list[dict[str, str]] = []
    terminal_rows: list[dict[str, str]] = []
    for candidate in read_csv(candidates_path):
        key = fixture_key(candidate)
        manifest = manifest_rows.get(key)
        if not manifest:
            issues.append(f"{candidate.get('target_id', key_text(key))}:missing_manifest")
            continue
        expected = load_bytes(manifest.get("expected_gap_path", ""), issues, "expected", candidate.get("target_id", ""))
        sources = source_bytes(manifest, issues, candidate.get("target_id", ""))
        local_source_rows = build_source_rows(candidate, manifest, expected, sources)
        local_terminal_rows = build_terminal_rows(candidate, manifest, expected, sources)
        candidate_rows.append(candidate_record(candidate, local_source_rows, local_terminal_rows))
        source_rows.extend(local_source_rows)
        terminal_rows.extend(local_terminal_rows)

    summary = build_summary(candidate_rows, source_rows, terminal_rows, len(issues))
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "candidates.csv", CANDIDATE_FIELDNAMES, candidate_rows)
    write_csv(output_dir / "source_scores.csv", SOURCE_FIELDNAMES, source_rows)
    write_csv(output_dir / "terminal_segments.csv", TERMINAL_FIELDNAMES, terminal_rows)
    (output_dir / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output_dir / "index.html").write_text(
        build_html(summary, candidate_rows, source_rows, terminal_rows, output_dir, title)
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Split Frontier80 palette-walk source and terminal evidence.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Clean Nonzero Palette Walk Source Terminal Split Probe",
    )
    args = parser.parse_args()

    summary = write_report(args.output, args.candidates, args.manifest, title=args.title)
    print(f"Palette bytes: {summary['palette_bytes']}")
    print(f"Terminal bytes: {summary['terminal_bytes']}")
    print(f"Best source max: {summary['best_source_exact_max']}")
    print(f"Terminal sequence hit bytes: {summary['terminal_sequence_hit_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
