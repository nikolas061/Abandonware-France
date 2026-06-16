#!/usr/bin/env python3
"""Correlate promoted nonzero gap patterns with control-derived selectors."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_control_pattern_probe")
DEFAULT_PATTERNS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_pattern_probe/patterns.csv")
DEFAULT_BEST_SOURCE = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_source_probe/best_by_target.csv")

STRUCTURED_CLASSES = {"fill_single_byte", "small_palette_2", "small_palette_4"}
SMALL_PALETTE_CLASSES = {"small_palette_2", "small_palette_4"}
RISK_CLASSES = {"dominant_50", "dominant_75", "noisy", "ramp_single_step"}

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "structured_rows",
    "structured_bytes",
    "fill_rows",
    "fill_bytes",
    "small_palette_rows",
    "small_palette_bytes",
    "dominant_rows",
    "dominant_bytes",
    "noisy_rows",
    "noisy_bytes",
    "selector_families",
    "selector_groups",
    "pure_selector_groups",
    "repeated_pure_selector_groups",
    "strong_pure_selector_groups",
    "largest_pure_selector_rows",
    "largest_pure_selector_bytes",
    "largest_pure_selector_family",
    "largest_pure_selector_key",
    "largest_pure_selector_coverage",
    "largest_repeated_pure_selector_rows",
    "largest_repeated_pure_selector_bytes",
    "largest_repeated_pure_selector_family",
    "largest_repeated_pure_selector_key",
    "issue_rows",
]

ANNOTATION_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "op_index",
    "length",
    "length_bucket",
    "start",
    "end",
    "start_mod64",
    "control_ref_offset",
    "length_u8_hit_flag",
    "length_u8_hit_offsets",
    "control_window_signature",
    "pattern_class",
    "coarse_pattern",
    "structured_flag",
    "unique_bytes",
    "dominant_byte_hex",
    "dominant_count",
    "dominant_ratio",
    "run_count",
    "max_same_run_bytes",
    "source_best_transform",
    "source_best_offset_delta",
    "source_best_prefix_bytes",
    "source_best_exact_bytes",
    "source_best_full_match",
    "head_hex",
    "tail_hex",
    "issues",
]

SELECTOR_FIELDNAMES = [
    "selector_family",
    "selector_key",
    "rows",
    "bytes",
    "structured_rows",
    "structured_bytes",
    "fill_rows",
    "fill_bytes",
    "small_palette_rows",
    "small_palette_bytes",
    "dominant_rows",
    "dominant_bytes",
    "noisy_rows",
    "noisy_bytes",
    "risky_rows",
    "risky_bytes",
    "precision_rows",
    "precision_bytes",
    "structured_coverage",
    "fixtures",
    "pattern_classes",
    "dominant_bytes_seen",
    "sample_pcx",
    "sample_frontier_id",
    "sample_start",
    "verdict",
]

PATTERN_CONTROL_FIELDNAMES = [
    "pattern_class",
    "control_window_signature",
    "control_ref_offset",
    "start_mod64",
    "length_u8_hit_flag",
    "rows",
    "bytes",
    "fixtures",
    "dominant_bytes_seen",
    "sample_pcx",
    "sample_frontier_id",
]

TRANSFORM_FIELDNAMES = [
    "pattern_class",
    "source_best_transform",
    "source_best_full_match",
    "rows",
    "bytes",
    "exact_bytes_total",
    "max_exact_bytes",
    "fixtures",
    "sample_pcx",
    "sample_frontier_id",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def best_source_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("rank", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("expected_start", ""),
        row.get("expected_end", ""),
    )


def pattern_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("rank", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("start", ""),
        row.get("end", ""),
    )


def length_bucket(length: int) -> str:
    if length < 8:
        return "tiny_lt8"
    if length < 32:
        return "small_lt32"
    if length < 64:
        return "medium_lt64"
    if length % 64 == 0:
        return "multiple64"
    return "large_ge64"


def coarse_pattern(pattern_class: str) -> str:
    if pattern_class == "fill_single_byte":
        return "fill"
    if pattern_class in SMALL_PALETTE_CLASSES:
        return "small_palette"
    if pattern_class in {"dominant_50", "dominant_75"}:
        return "dominant"
    if pattern_class == "ramp_single_step":
        return "ramp"
    if pattern_class == "noisy":
        return "noisy"
    return pattern_class or "missing"


def length_hit_flag(row: dict[str, str]) -> str:
    return "len_u8_hit" if row.get("length_u8_hit_offsets") else "no_len_u8_hit"


def annotate_rows(
    pattern_rows: list[dict[str, str]],
    best_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    best_lookup = {best_source_key(row): row for row in best_rows}
    rows: list[dict[str, str]] = []
    for pattern in pattern_rows:
        best = best_lookup.get(pattern_key(pattern), {})
        pattern_class = pattern.get("pattern_class", "")
        length = int_value(pattern, "length")
        issues = [issue for issue in pattern.get("issues", "").split(";") if issue]
        if pattern_class not in STRUCTURED_CLASSES and pattern_class not in RISK_CLASSES:
            issues.append("unknown_pattern_class")
        rows.append(
            {
                "rank": pattern.get("rank", ""),
                "archive": pattern.get("archive", ""),
                "archive_tag": pattern.get("archive_tag", ""),
                "pcx_name": pattern.get("pcx_name", ""),
                "frontier_id": pattern.get("frontier_id", ""),
                "span_index": pattern.get("span_index", ""),
                "run_index": pattern.get("run_index", ""),
                "op_index": pattern.get("op_index", ""),
                "length": str(length),
                "length_bucket": length_bucket(length),
                "start": pattern.get("start", ""),
                "end": pattern.get("end", ""),
                "start_mod64": pattern.get("start_mod64", ""),
                "control_ref_offset": pattern.get("control_ref_offset", "") or "missing",
                "length_u8_hit_flag": length_hit_flag(pattern),
                "length_u8_hit_offsets": pattern.get("length_u8_hit_offsets", ""),
                "control_window_signature": pattern.get("control_window_signature", "") or "missing",
                "pattern_class": pattern_class,
                "coarse_pattern": coarse_pattern(pattern_class),
                "structured_flag": "1" if pattern_class in STRUCTURED_CLASSES else "0",
                "unique_bytes": pattern.get("unique_bytes", ""),
                "dominant_byte_hex": pattern.get("dominant_byte_hex", ""),
                "dominant_count": pattern.get("dominant_count", ""),
                "dominant_ratio": pattern.get("dominant_ratio", ""),
                "run_count": pattern.get("run_count", ""),
                "max_same_run_bytes": pattern.get("max_same_run_bytes", ""),
                "source_best_transform": best.get("transform", ""),
                "source_best_offset_delta": best.get("offset_delta", ""),
                "source_best_prefix_bytes": best.get("prefix_bytes", ""),
                "source_best_exact_bytes": best.get("exact_bytes", ""),
                "source_best_full_match": best.get("full_match", ""),
                "head_hex": pattern.get("head_hex", ""),
                "tail_hex": pattern.get("tail_hex", ""),
                "issues": ";".join(issues),
            }
        )
    return rows


def selector_values(row: dict[str, str]) -> list[tuple[str, str]]:
    signature = row.get("control_window_signature", "") or "missing"
    ref = row.get("control_ref_offset", "") or "missing"
    start_mod64 = row.get("start_mod64", "") or "missing"
    length_hit = row.get("length_u8_hit_flag", "") or "missing"
    bucket = row.get("length_bucket", "") or "missing"
    return [
        ("control_signature", signature),
        ("control_ref", ref),
        ("start_mod64", f"mod64={start_mod64}"),
        ("control_signature_start_mod64", f"{signature}|mod64={start_mod64}"),
        ("control_ref_start_mod64", f"ref={ref}|mod64={start_mod64}"),
        ("control_signature_length_hit", f"{signature}|{length_hit}"),
        ("control_ref_length_hit", f"ref={ref}|{length_hit}"),
        ("control_signature_length_bucket", f"{signature}|bucket={bucket}"),
        ("control_ref_length_bucket", f"ref={ref}|bucket={bucket}"),
        ("control_signature_ref", f"{signature}|ref={ref}"),
    ]


def verdict_for(row: dict[str, str]) -> str:
    if int_value(row, "structured_bytes") <= 0:
        return "reject_no_structured_bytes"
    if int_value(row, "risky_bytes") == 0:
        if int_value(row, "structured_bytes") >= 64 and int_value(row, "fixtures") >= 2:
            return "pure_control_candidate"
        if int_value(row, "rows") >= 2 and int_value(row, "fixtures") >= 2:
            return "pure_repeated_review"
        return "pure_review"
    precision = float(row.get("precision_bytes", "0") or 0)
    if precision >= 0.80 and int_value(row, "structured_bytes") >= 64:
        return "mixed_high_precision_review"
    return "mixed_risk"


def build_selector_rows(rows: list[dict[str, str]], total_structured_bytes: int) -> list[dict[str, str]]:
    counters: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    fixtures: dict[tuple[str, str], set[tuple[str, str, str]]] = defaultdict(set)
    classes: dict[tuple[str, str], set[str]] = defaultdict(set)
    dominant_bytes: dict[tuple[str, str], set[str]] = defaultdict(set)
    samples: dict[tuple[str, str], dict[str, str]] = {}

    for row in rows:
        length = int_value(row, "length")
        pattern = row.get("pattern_class", "")
        structured = pattern in STRUCTURED_CLASSES
        key_rows = selector_values(row)
        for family, value in key_rows:
            key = family, value
            counters[key]["rows"] += 1
            counters[key]["bytes"] += length
            counters[key]["structured_rows"] += 1 if structured else 0
            counters[key]["structured_bytes"] += length if structured else 0
            counters[key]["fill_rows"] += 1 if pattern == "fill_single_byte" else 0
            counters[key]["fill_bytes"] += length if pattern == "fill_single_byte" else 0
            counters[key]["small_palette_rows"] += 1 if pattern in SMALL_PALETTE_CLASSES else 0
            counters[key]["small_palette_bytes"] += length if pattern in SMALL_PALETTE_CLASSES else 0
            counters[key]["dominant_rows"] += 1 if pattern in {"dominant_50", "dominant_75"} else 0
            counters[key]["dominant_bytes"] += length if pattern in {"dominant_50", "dominant_75"} else 0
            counters[key]["noisy_rows"] += 1 if pattern == "noisy" else 0
            counters[key]["noisy_bytes"] += length if pattern == "noisy" else 0
            fixtures[key].add(fixture_key(row))
            classes[key].add(pattern)
            if row.get("dominant_byte_hex"):
                dominant_bytes[key].add(row["dominant_byte_hex"])
            samples.setdefault(key, row)

    selector_rows: list[dict[str, str]] = []
    for (family, value), counter in counters.items():
        rows_count = int(counter["rows"])
        bytes_count = int(counter["bytes"])
        structured_rows = int(counter["structured_rows"])
        structured_bytes = int(counter["structured_bytes"])
        risky_rows = rows_count - structured_rows
        risky_bytes = bytes_count - structured_bytes
        sample = samples[(family, value)]
        selector = {
            "selector_family": family,
            "selector_key": value,
            "rows": str(rows_count),
            "bytes": str(bytes_count),
            "structured_rows": str(structured_rows),
            "structured_bytes": str(structured_bytes),
            "fill_rows": str(counter["fill_rows"]),
            "fill_bytes": str(counter["fill_bytes"]),
            "small_palette_rows": str(counter["small_palette_rows"]),
            "small_palette_bytes": str(counter["small_palette_bytes"]),
            "dominant_rows": str(counter["dominant_rows"]),
            "dominant_bytes": str(counter["dominant_bytes"]),
            "noisy_rows": str(counter["noisy_rows"]),
            "noisy_bytes": str(counter["noisy_bytes"]),
            "risky_rows": str(risky_rows),
            "risky_bytes": str(risky_bytes),
            "precision_rows": f"{(structured_rows / rows_count) if rows_count else 0.0:.6f}",
            "precision_bytes": f"{(structured_bytes / bytes_count) if bytes_count else 0.0:.6f}",
            "structured_coverage": f"{(structured_bytes / total_structured_bytes) if total_structured_bytes else 0.0:.6f}",
            "fixtures": str(len(fixtures[(family, value)])),
            "pattern_classes": ";".join(sorted(classes[(family, value)])),
            "dominant_bytes_seen": ";".join(sorted(dominant_bytes[(family, value)])),
            "sample_pcx": sample.get("pcx_name", ""),
            "sample_frontier_id": sample.get("frontier_id", ""),
            "sample_start": sample.get("start", ""),
        }
        selector["verdict"] = verdict_for(selector)
        selector_rows.append(selector)

    selector_rows.sort(
        key=lambda row: (
            0 if row.get("verdict") == "pure_control_candidate" else 1,
            0 if row.get("verdict") == "pure_repeated_review" else 1,
            -float(row.get("precision_bytes", "0") or 0),
            -int_value(row, "structured_bytes"),
            -int_value(row, "bytes"),
            row.get("selector_family", ""),
            row.get("selector_key", ""),
        )
    )
    return selector_rows


def build_pattern_control_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    counters: dict[tuple[str, str, str, str, str], Counter[str]] = defaultdict(Counter)
    fixtures: dict[tuple[str, str, str, str, str], set[tuple[str, str, str]]] = defaultdict(set)
    dominant_bytes: dict[tuple[str, str, str, str, str], set[str]] = defaultdict(set)
    samples: dict[tuple[str, str, str, str, str], dict[str, str]] = {}
    for row in rows:
        key = (
            row.get("pattern_class", ""),
            row.get("control_window_signature", ""),
            row.get("control_ref_offset", ""),
            row.get("start_mod64", ""),
            row.get("length_u8_hit_flag", ""),
        )
        counters[key]["rows"] += 1
        counters[key]["bytes"] += int_value(row, "length")
        fixtures[key].add(fixture_key(row))
        if row.get("dominant_byte_hex"):
            dominant_bytes[key].add(row["dominant_byte_hex"])
        samples.setdefault(key, row)

    output_rows: list[dict[str, str]] = []
    for key, counter in counters.items():
        pattern, signature, ref, start_mod64, length_hit = key
        sample = samples[key]
        output_rows.append(
            {
                "pattern_class": pattern,
                "control_window_signature": signature,
                "control_ref_offset": ref,
                "start_mod64": start_mod64,
                "length_u8_hit_flag": length_hit,
                "rows": str(counter["rows"]),
                "bytes": str(counter["bytes"]),
                "fixtures": str(len(fixtures[key])),
                "dominant_bytes_seen": ";".join(sorted(dominant_bytes[key])),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output_rows.sort(
        key=lambda row: (
            row.get("pattern_class", ""),
            -int_value(row, "bytes"),
            -int_value(row, "rows"),
            row.get("control_window_signature", ""),
        )
    )
    return output_rows


def build_transform_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    counters: dict[tuple[str, str, str], Counter[str]] = defaultdict(Counter)
    fixtures: dict[tuple[str, str, str], set[tuple[str, str, str]]] = defaultdict(set)
    samples: dict[tuple[str, str, str], dict[str, str]] = {}
    for row in rows:
        key = (
            row.get("pattern_class", ""),
            row.get("source_best_transform", "") or "missing",
            row.get("source_best_full_match", "") or "0",
        )
        exact = int_value(row, "source_best_exact_bytes")
        counters[key]["rows"] += 1
        counters[key]["bytes"] += int_value(row, "length")
        counters[key]["exact_bytes_total"] += exact
        counters[key]["max_exact_bytes"] = max(counters[key]["max_exact_bytes"], exact)
        fixtures[key].add(fixture_key(row))
        samples.setdefault(key, row)

    output_rows: list[dict[str, str]] = []
    for key, counter in counters.items():
        pattern, transform, full_match = key
        sample = samples[key]
        output_rows.append(
            {
                "pattern_class": pattern,
                "source_best_transform": transform,
                "source_best_full_match": full_match,
                "rows": str(counter["rows"]),
                "bytes": str(counter["bytes"]),
                "exact_bytes_total": str(counter["exact_bytes_total"]),
                "max_exact_bytes": str(counter["max_exact_bytes"]),
                "fixtures": str(len(fixtures[key])),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output_rows.sort(
        key=lambda row: (
            row.get("pattern_class", ""),
            -int_value(row, "exact_bytes_total"),
            -int_value(row, "bytes"),
            row.get("source_best_transform", ""),
        )
    )
    return output_rows


def build_summary(rows: list[dict[str, str]], selector_rows: list[dict[str, str]]) -> dict[str, str]:
    target_bytes = sum(int_value(row, "length") for row in rows)
    structured = [row for row in rows if row.get("pattern_class") in STRUCTURED_CLASSES]
    fills = [row for row in rows if row.get("pattern_class") == "fill_single_byte"]
    small = [row for row in rows if row.get("pattern_class") in SMALL_PALETTE_CLASSES]
    dominant = [row for row in rows if row.get("pattern_class") in {"dominant_50", "dominant_75"}]
    noisy = [row for row in rows if row.get("pattern_class") == "noisy"]
    pure = [
        row
        for row in selector_rows
        if int_value(row, "structured_bytes") > 0 and int_value(row, "risky_bytes") == 0
    ]
    repeated = [row for row in pure if row.get("verdict") == "pure_repeated_review"]
    strong = [row for row in pure if row.get("verdict") == "pure_control_candidate"]
    largest = max(pure, key=lambda row: int_value(row, "structured_bytes"), default={})
    largest_repeated = max(repeated, key=lambda row: int_value(row, "structured_bytes"), default={})
    families = sorted({row.get("selector_family", "") for row in selector_rows})
    return {
        "scope": "total",
        "target_rows": str(len(rows)),
        "target_bytes": str(target_bytes),
        "structured_rows": str(len(structured)),
        "structured_bytes": str(sum(int_value(row, "length") for row in structured)),
        "fill_rows": str(len(fills)),
        "fill_bytes": str(sum(int_value(row, "length") for row in fills)),
        "small_palette_rows": str(len(small)),
        "small_palette_bytes": str(sum(int_value(row, "length") for row in small)),
        "dominant_rows": str(len(dominant)),
        "dominant_bytes": str(sum(int_value(row, "length") for row in dominant)),
        "noisy_rows": str(len(noisy)),
        "noisy_bytes": str(sum(int_value(row, "length") for row in noisy)),
        "selector_families": str(len(families)),
        "selector_groups": str(len(selector_rows)),
        "pure_selector_groups": str(len(pure)),
        "repeated_pure_selector_groups": str(len(repeated)),
        "strong_pure_selector_groups": str(len(strong)),
        "largest_pure_selector_rows": largest.get("structured_rows", "0"),
        "largest_pure_selector_bytes": largest.get("structured_bytes", "0"),
        "largest_pure_selector_family": largest.get("selector_family", ""),
        "largest_pure_selector_key": largest.get("selector_key", ""),
        "largest_pure_selector_coverage": largest.get("structured_coverage", "0.000000"),
        "largest_repeated_pure_selector_rows": largest_repeated.get("structured_rows", "0"),
        "largest_repeated_pure_selector_bytes": largest_repeated.get("structured_bytes", "0"),
        "largest_repeated_pure_selector_family": largest_repeated.get("selector_family", ""),
        "largest_repeated_pure_selector_key": largest_repeated.get("selector_key", ""),
        "issue_rows": str(sum(1 for row in rows if row.get("issues"))),
    }


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    annotations: list[dict[str, str]],
    selectors: list[dict[str, str]],
    pattern_controls: list[dict[str, str]],
    transforms: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "annotations": annotations,
        "selectors": selectors,
        "patternControls": pattern_controls,
        "transforms": transforms,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("target_annotations.csv", output_dir / "target_annotations.csv"),
            ("selector_candidates.csv", output_dir / "selector_candidates.csv"),
            ("by_pattern_control.csv", output_dir / "by_pattern_control.csv"),
            ("by_best_transform.csv", output_dir / "by_best_transform.csv"),
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
  --bg: #111416;
  --panel: #172023;
  --line: #31424a;
  --text: #edf5f4;
  --muted: #9dafb5;
  --accent: #77d3b1;
  --ok: #80df94;
  --warn: #f0c36a;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.wrap {{ width: min(1740px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12191b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 720; letter-spacing: 0; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 22px; font-weight: 760; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.warn {{ color: var(--warn); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1600px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Groups fill and small-palette nonzero gap rows by control-derived selector candidates.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Target bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Structured bytes</div><div class="value ok">{summary['structured_bytes']}</div></div>
    <div class="stat"><div class="label">Pure selector groups</div><div class="value">{summary['pure_selector_groups']}</div></div>
    <div class="stat"><div class="label">Repeated pure groups</div><div class="value">{summary['repeated_pure_selector_groups']}</div></div>
    <div class="stat"><div class="label">Strong pure groups</div><div class="value ok">{summary['strong_pure_selector_groups']}</div></div>
    <div class="stat"><div class="label">Largest pure bytes</div><div class="value warn">{summary['largest_pure_selector_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Selector candidates</h2>{render_table(selectors, SELECTOR_FIELDNAMES, 260)}</section>
  <section class="panel"><h2>Pattern controls</h2>{render_table(pattern_controls, PATTERN_CONTROL_FIELDNAMES, 260)}</section>
  <section class="panel"><h2>Best source transforms</h2>{render_table(transforms, TRANSFORM_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Target annotations</h2>{render_table(annotations, ANNOTATION_FIELDNAMES, 360)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_CONTROL_PATTERN_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Correlate promoted .tex nonzero gap patterns with controls.")
    parser.add_argument("--patterns", type=Path, default=DEFAULT_PATTERNS)
    parser.add_argument("--best-source", type=Path, default=DEFAULT_BEST_SOURCE)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Control Pattern Probe",
    )
    args = parser.parse_args()

    annotations = annotate_rows(read_csv(args.patterns), read_csv(args.best_source))
    total_structured = sum(
        int_value(row, "length") for row in annotations if row.get("pattern_class") in STRUCTURED_CLASSES
    )
    selectors = build_selector_rows(annotations, total_structured)
    pattern_controls = build_pattern_control_rows(annotations)
    transforms = build_transform_rows(annotations)
    summary = build_summary(annotations, selectors)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "target_annotations.csv", ANNOTATION_FIELDNAMES, annotations)
    write_csv(args.output / "selector_candidates.csv", SELECTOR_FIELDNAMES, selectors)
    write_csv(args.output / "by_pattern_control.csv", PATTERN_CONTROL_FIELDNAMES, pattern_controls)
    write_csv(args.output / "by_best_transform.csv", TRANSFORM_FIELDNAMES, transforms)
    html_path = args.output / "index.html"
    html_path.write_text(
        build_html(summary, annotations, selectors, pattern_controls, transforms, args.output, args.title)
    )

    print(f"Targets: {summary['target_rows']}")
    print(f"Structured bytes: {summary['structured_bytes']}")
    print(f"Pure selector groups: {summary['pure_selector_groups']}")
    print(f"Repeated pure selector groups: {summary['repeated_pure_selector_groups']}")
    print(f"Strong pure selector groups: {summary['strong_pure_selector_groups']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
