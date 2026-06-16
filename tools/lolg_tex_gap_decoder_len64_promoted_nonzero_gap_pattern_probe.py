#!/usr/bin/env python3
"""Classify expected-byte patterns inside promoted nonzero gap operations."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_pattern_probe")
DEFAULT_TARGETS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_source_probe/targets.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "pattern_classes",
    "fill_rows",
    "fill_bytes",
    "small_palette_rows",
    "small_palette_bytes",
    "dominant_rows",
    "dominant_bytes",
    "ramp_rows",
    "ramp_bytes",
    "noisy_rows",
    "noisy_bytes",
    "max_same_run_bytes",
    "issue_rows",
]

PATTERN_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "op_index",
    "length",
    "start",
    "end",
    "start_mod64",
    "control_ref_offset",
    "length_u8_hit_offsets",
    "control_window_signature",
    "pattern_class",
    "unique_bytes",
    "dominant_byte_hex",
    "dominant_count",
    "dominant_ratio",
    "run_count",
    "max_same_run_bytes",
    "first_delta",
    "single_step",
    "head_hex",
    "tail_hex",
    "issues",
]

CLASS_FIELDNAMES = [
    "pattern_class",
    "rows",
    "bytes",
    "fixtures",
    "max_same_run_bytes",
    "avg_dominant_ratio",
    "sample_pcx",
    "sample_frontier_id",
]

BYTE_FIELDNAMES = [
    "dominant_byte_hex",
    "rows",
    "bytes",
    "pattern_classes",
    "sample_pcx",
    "sample_frontier_id",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def same_byte_runs(data: bytes) -> list[tuple[int, int, int]]:
    if not data:
        return []
    runs: list[tuple[int, int, int]] = []
    start = 0
    value = data[0]
    for index, current in enumerate(data[1:], start=1):
        if current != value:
            runs.append((start, index, value))
            start = index
            value = current
    runs.append((start, len(data), value))
    return runs


def single_step(data: bytes) -> tuple[bool, str]:
    if len(data) < 2:
        return False, ""
    step = (data[1] - data[0]) & 0xFF
    for left, right in zip(data, data[1:]):
        if ((right - left) & 0xFF) != step:
            return False, f"0x{step:02x}"
    return True, f"0x{step:02x}"


def classify_pattern(data: bytes, unique_count: int, dominant_ratio: float, ramp: bool) -> str:
    if not data:
        return "empty"
    if unique_count == 1:
        return "fill_single_byte"
    if ramp and len(data) >= 4:
        return "ramp_single_step"
    if unique_count <= 2:
        return "small_palette_2"
    if unique_count <= 4:
        return "small_palette_4"
    if dominant_ratio >= 0.75:
        return "dominant_75"
    if dominant_ratio >= 0.50:
        return "dominant_50"
    return "noisy"


def build_rows(
    target_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    fixtures = {fixture_key(row): row for row in fixture_rows}
    expected_by_fixture: dict[tuple[str, str, str], bytes] = {}
    issues: list[str] = []
    for key, fixture in fixtures.items():
        local_issues: list[str] = []
        expected_by_fixture[key] = load_bytes(fixture.get("expected_gap_path", ""), local_issues, "expected")
        issues.extend(f"{key}:{issue}" for issue in local_issues)

    rows: list[dict[str, str]] = []
    gap_targets = [row for row in target_rows if row.get("op_kind") == "gap" and not row.get("issues")]
    for target in gap_targets:
        key = fixture_key(target)
        expected_all = expected_by_fixture.get(key, b"")
        start = int_value(target, "start")
        end = int_value(target, "end")
        chunk = expected_all[start:end]
        counts = Counter(chunk)
        dominant_byte, dominant_count = counts.most_common(1)[0] if counts else (0, 0)
        dominant_ratio = dominant_count / len(chunk) if chunk else 0.0
        runs = same_byte_runs(chunk)
        max_run = max([run_end - run_start for run_start, run_end, _value in runs] or [0])
        ramp, first_delta = single_step(chunk)
        pattern_class = classify_pattern(chunk, len(counts), dominant_ratio, ramp)
        rows.append(
            {
                "rank": target.get("rank", ""),
                "archive": target.get("archive", ""),
                "archive_tag": target.get("archive_tag", ""),
                "pcx_name": target.get("pcx_name", ""),
                "frontier_id": target.get("frontier_id", ""),
                "span_index": target.get("span_index", ""),
                "run_index": target.get("run_index", ""),
                "op_index": target.get("op_index", ""),
                "length": str(len(chunk)),
                "start": target.get("start", ""),
                "end": target.get("end", ""),
                "start_mod64": str(start % 64),
                "control_ref_offset": target.get("control_ref_offset", ""),
                "length_u8_hit_offsets": target.get("length_u8_hit_offsets", ""),
                "control_window_signature": target.get("control_window_signature", ""),
                "pattern_class": pattern_class,
                "unique_bytes": str(len(counts)),
                "dominant_byte_hex": f"0x{dominant_byte:02x}" if chunk else "",
                "dominant_count": str(dominant_count),
                "dominant_ratio": f"{dominant_ratio:.6f}",
                "run_count": str(len(runs)),
                "max_same_run_bytes": str(max_run),
                "first_delta": first_delta,
                "single_step": "1" if ramp else "0",
                "head_hex": chunk[:16].hex(),
                "tail_hex": chunk[-16:].hex(),
                "issues": "",
            }
        )
    rows.sort(
        key=lambda row: (
            row.get("pattern_class", ""),
            -int_value(row, "length"),
            int_value(row, "rank"),
            int_value(row, "start"),
        )
    )

    class_totals: dict[str, Counter[str]] = defaultdict(Counter)
    class_fixtures: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    class_ratio: dict[str, float] = defaultdict(float)
    class_sample: dict[str, dict[str, str]] = {}
    byte_totals: dict[str, Counter[str]] = defaultdict(Counter)
    byte_classes: dict[str, set[str]] = defaultdict(set)
    byte_sample: dict[str, dict[str, str]] = {}
    for row in rows:
        pattern = row.get("pattern_class", "")
        length = int_value(row, "length")
        class_totals[pattern]["rows"] += 1
        class_totals[pattern]["bytes"] += length
        class_totals[pattern]["max_same_run_bytes"] = max(
            class_totals[pattern]["max_same_run_bytes"],
            int_value(row, "max_same_run_bytes"),
        )
        class_fixtures[pattern].add(fixture_key(row))
        class_ratio[pattern] += float(row.get("dominant_ratio", "0") or 0)
        class_sample.setdefault(pattern, row)

        byte = row.get("dominant_byte_hex", "")
        byte_totals[byte]["rows"] += 1
        byte_totals[byte]["bytes"] += length
        byte_classes[byte].add(pattern)
        byte_sample.setdefault(byte, row)

    class_rows = []
    for pattern, totals in class_totals.items():
        sample = class_sample[pattern]
        rows_count = int(totals["rows"])
        class_rows.append(
            {
                "pattern_class": pattern,
                "rows": str(rows_count),
                "bytes": str(totals["bytes"]),
                "fixtures": str(len(class_fixtures[pattern])),
                "max_same_run_bytes": str(totals["max_same_run_bytes"]),
                "avg_dominant_ratio": f"{(class_ratio[pattern] / rows_count) if rows_count else 0.0:.6f}",
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    class_rows.sort(key=lambda row: (-int_value(row, "bytes"), -int_value(row, "rows"), row["pattern_class"]))

    byte_rows = []
    for byte, totals in byte_totals.items():
        sample = byte_sample[byte]
        byte_rows.append(
            {
                "dominant_byte_hex": byte,
                "rows": str(totals["rows"]),
                "bytes": str(totals["bytes"]),
                "pattern_classes": ";".join(sorted(byte_classes[byte])),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    byte_rows.sort(key=lambda row: (-int_value(row, "bytes"), -int_value(row, "rows"), row["dominant_byte_hex"]))

    fill_rows = [row for row in rows if row.get("pattern_class") == "fill_single_byte"]
    small_rows = [row for row in rows if row.get("pattern_class") in {"small_palette_2", "small_palette_4"}]
    dominant_rows = [row for row in rows if row.get("pattern_class") in {"dominant_50", "dominant_75"}]
    ramp_rows = [row for row in rows if row.get("pattern_class") == "ramp_single_step"]
    noisy_rows = [row for row in rows if row.get("pattern_class") == "noisy"]
    summary = {
        "scope": "total",
        "target_rows": str(len(rows)),
        "target_bytes": str(sum(int_value(row, "length") for row in rows)),
        "pattern_classes": str(len(class_rows)),
        "fill_rows": str(len(fill_rows)),
        "fill_bytes": str(sum(int_value(row, "length") for row in fill_rows)),
        "small_palette_rows": str(len(small_rows)),
        "small_palette_bytes": str(sum(int_value(row, "length") for row in small_rows)),
        "dominant_rows": str(len(dominant_rows)),
        "dominant_bytes": str(sum(int_value(row, "length") for row in dominant_rows)),
        "ramp_rows": str(len(ramp_rows)),
        "ramp_bytes": str(sum(int_value(row, "length") for row in ramp_rows)),
        "noisy_rows": str(len(noisy_rows)),
        "noisy_bytes": str(sum(int_value(row, "length") for row in noisy_rows)),
        "max_same_run_bytes": str(max([int_value(row, "max_same_run_bytes") for row in rows] or [0])),
        "issue_rows": str(len(issues)),
    }
    return summary, rows, class_rows, byte_rows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    pattern_rows: list[dict[str, str]],
    class_rows: list[dict[str, str]],
    byte_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "patterns": pattern_rows,
        "classes": class_rows,
        "dominantBytes": byte_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("patterns.csv", output_dir / "patterns.csv"),
            ("by_pattern_class.csv", output_dir / "by_pattern_class.csv"),
            ("by_dominant_byte.csv", output_dir / "by_dominant_byte.csv"),
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
.wrap {{ width: min(1700px, calc(100vw - 28px)); margin: 0 auto; }}
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
table {{ width: 100%; border-collapse: collapse; min-width: 1500px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Classifies expected nonzero gap bytes by fill, ramp, palette size, and dominance.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Gap targets</div><div class="value">{summary['target_rows']}</div></div>
    <div class="stat"><div class="label">Gap bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Small palette bytes</div><div class="value ok">{summary['small_palette_bytes']}</div></div>
    <div class="stat"><div class="label">Dominant bytes</div><div class="value">{summary['dominant_bytes']}</div></div>
    <div class="stat"><div class="label">Noisy bytes</div><div class="value warn">{summary['noisy_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Pattern classes</h2>{render_table(class_rows, CLASS_FIELDNAMES, 80)}</section>
  <section class="panel"><h2>Dominant bytes</h2>{render_table(byte_rows, BYTE_FIELDNAMES, 80)}</section>
  <section class="panel"><h2>Patterns</h2>{render_table(pattern_rows, PATTERN_FIELDNAMES, 320)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_PATTERN_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Classify expected-byte patterns in promoted .tex nonzero gap rows.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Pattern Probe",
    )
    args = parser.parse_args()

    summary, pattern_rows, class_rows, byte_rows = build_rows(
        read_csv(args.targets),
        read_csv(args.fixtures),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "patterns.csv", PATTERN_FIELDNAMES, pattern_rows)
    write_csv(args.output / "by_pattern_class.csv", CLASS_FIELDNAMES, class_rows)
    write_csv(args.output / "by_dominant_byte.csv", BYTE_FIELDNAMES, byte_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, pattern_rows, class_rows, byte_rows, args.output, args.title))

    print(f"Gap targets: {summary['target_rows']}")
    print(f"Gap bytes: {summary['target_bytes']}")
    print(f"Small palette bytes: {summary['small_palette_bytes']}")
    print(f"Noisy bytes: {summary['noisy_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
