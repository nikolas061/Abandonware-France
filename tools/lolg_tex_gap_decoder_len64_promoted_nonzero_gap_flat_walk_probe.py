#!/usr/bin/env python3
"""Probe flat-run walks inside gradient-like noisy nonzero gap rows."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import (
    DEFAULT_FIXTURES,
    fixture_key,
    load_expected_by_fixture,
    read_csv,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_probe")
DEFAULT_TARGETS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_probe/targets.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "value_run_count",
    "plateau_bytes",
    "plateau_ratio",
    "transition_count",
    "small_transition_count",
    "small_transition_ratio",
    "long_plateau_rows",
    "long_plateau_bytes",
    "dominant_value_rows",
    "dominant_value_bytes",
    "run_length_shape_groups",
    "run_length_repeated_groups",
    "run_length_repeated_rows",
    "run_length_repeated_bytes",
    "transition_shape_groups",
    "transition_repeated_groups",
    "transition_repeated_rows",
    "transition_repeated_bytes",
    "best_run_length_shape_rows",
    "best_run_length_shape_bytes",
    "best_transition_shape_rows",
    "best_transition_shape_bytes",
    "issue_rows",
]

TARGET_FIELDNAMES = [
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
    "control_ref_mod64",
    "control_window_signature",
    "unique_bytes",
    "dominant_byte_hex",
    "dominant_ratio",
    "value_run_count",
    "max_value_run",
    "plateau_bytes",
    "plateau_ratio",
    "transition_count",
    "small_transition_count",
    "small_transition_ratio",
    "dominant_run_value_hex",
    "dominant_run_count",
    "run_length_shape_key",
    "run_length_shape_preview",
    "transition_shape_key",
    "transition_shape_preview",
    "run_value_shape_key",
    "run_value_shape_preview",
    "top_nibble",
    "top_nibble_ratio",
    "head_hex",
    "tail_hex",
    "issues",
]

GROUP_FIELDNAMES = [
    "shape_kind",
    "shape_key",
    "shape_preview",
    "rows",
    "bytes",
    "value_run_count",
    "plateau_bytes",
    "transition_count",
    "small_transition_count",
    "fixtures",
    "sample_pcx",
    "sample_frontier_id",
]


def signed_delta(left: int, right: int) -> int:
    return ((right - left + 128) & 0xFF) - 128


def value_runs(data: bytes) -> list[tuple[int, int]]:
    if not data:
        return []
    runs: list[tuple[int, int]] = []
    current = data[0]
    count = 1
    for value in data[1:]:
        if value == current:
            count += 1
            continue
        runs.append((current, count))
        current = value
        count = 1
    runs.append((current, count))
    return runs


def shape_key(shape: str) -> str:
    digest = hashlib.sha1(shape.encode("ascii")).hexdigest()[:14]
    return f"len={len(shape)}|sha1={digest}"


def preview_text(value: str, limit: int = 120) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]}..."


def first_use_shape(values: list[int]) -> str:
    rank_by_value: dict[int, int] = {}
    output: list[str] = []
    for value in values:
        if value not in rank_by_value:
            rank_by_value[value] = len(rank_by_value)
        output.append(f"{rank_by_value[value]:x}")
    return ".".join(output)


def top_nibble_stats(data: bytes) -> tuple[str, float]:
    if not data:
        return "", 0.0
    nibble, count = Counter(value >> 4 for value in data).most_common(1)[0]
    return f"0x{nibble:x}", count / len(data)


def build_target_rows(
    target_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[str]]:
    expected_by_fixture, fixture_issues = load_expected_by_fixture(fixture_rows)
    rows: list[dict[str, str]] = []
    for target in target_rows:
        if target.get("gradient_class") != "flat_run_walk":
            continue
        issues = [issue for issue in target.get("issues", "").split(";") if issue]
        expected_all = expected_by_fixture.get(fixture_key(target), b"")
        start = int_value(target, "start")
        end = int_value(target, "end")
        expected = expected_all[start:end]
        if not expected:
            issues.append("missing_expected_chunk")
            continue
        runs = value_runs(expected)
        run_lengths = [count for _value, count in runs]
        run_values = [value for value, _count in runs]
        transitions = [signed_delta(run_values[index - 1], run_values[index]) for index in range(1, len(run_values))]
        small_transitions = [value for value in transitions if abs(value) <= 4]
        plateau_bytes = sum(max(0, count - 1) for count in run_lengths)
        dominant_run_value, dominant_run_count = Counter(run_values).most_common(1)[0]
        run_length_shape = ".".join(str(length) for length in run_lengths)
        transition_shape = ".".join(str(value) if -8 <= value <= 8 else "outside" for value in transitions)
        run_value_shape = first_use_shape(run_values)
        top_nibble, top_nibble_ratio = top_nibble_stats(expected)
        row = {
            "rank": target.get("rank", ""),
            "archive": target.get("archive", ""),
            "archive_tag": target.get("archive_tag", ""),
            "pcx_name": target.get("pcx_name", ""),
            "frontier_id": target.get("frontier_id", ""),
            "span_index": target.get("span_index", ""),
            "run_index": target.get("run_index", ""),
            "op_index": target.get("op_index", ""),
            "length": str(len(expected)),
            "start": target.get("start", ""),
            "end": target.get("end", ""),
            "start_mod64": target.get("start_mod64", ""),
            "control_ref_offset": target.get("control_ref_offset", ""),
            "control_ref_mod64": target.get("control_ref_mod64", ""),
            "control_window_signature": target.get("control_window_signature", ""),
            "unique_bytes": target.get("unique_bytes", ""),
            "dominant_byte_hex": target.get("dominant_byte_hex", ""),
            "dominant_ratio": target.get("dominant_ratio", ""),
            "value_run_count": str(len(runs)),
            "max_value_run": str(max(run_lengths, default=0)),
            "plateau_bytes": str(plateau_bytes),
            "plateau_ratio": f"{plateau_bytes / len(expected):.6f}",
            "transition_count": str(len(transitions)),
            "small_transition_count": str(len(small_transitions)),
            "small_transition_ratio": f"{(len(small_transitions) / len(transitions)) if transitions else 0.0:.6f}",
            "dominant_run_value_hex": f"0x{dominant_run_value:02x}",
            "dominant_run_count": str(dominant_run_count),
            "run_length_shape_key": shape_key(run_length_shape),
            "run_length_shape_preview": preview_text(run_length_shape),
            "transition_shape_key": shape_key(transition_shape),
            "transition_shape_preview": preview_text(transition_shape),
            "run_value_shape_key": shape_key(run_value_shape),
            "run_value_shape_preview": preview_text(run_value_shape),
            "top_nibble": top_nibble,
            "top_nibble_ratio": f"{top_nibble_ratio:.6f}",
            "head_hex": expected[:16].hex(),
            "tail_hex": expected[-16:].hex(),
            "issues": ";".join(issues),
        }
        rows.append(row)
    return rows, fixture_issues


def build_group_rows(rows: list[dict[str, str]], key_field: str, preview_field: str, kind: str) -> list[dict[str, str]]:
    counters: dict[str, Counter[str]] = defaultdict(Counter)
    previews: dict[str, str] = {}
    fixtures: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    samples: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row.get(key_field, "")
        counters[key]["rows"] += 1
        counters[key]["bytes"] += int_value(row, "length")
        counters[key]["value_run_count"] += int_value(row, "value_run_count")
        counters[key]["plateau_bytes"] += int_value(row, "plateau_bytes")
        counters[key]["transition_count"] += int_value(row, "transition_count")
        counters[key]["small_transition_count"] += int_value(row, "small_transition_count")
        previews.setdefault(key, row.get(preview_field, ""))
        fixtures[key].add(fixture_key(row))
        samples.setdefault(key, row)

    output: list[dict[str, str]] = []
    for key, counter in counters.items():
        sample = samples[key]
        output.append(
            {
                "shape_kind": kind,
                "shape_key": key,
                "shape_preview": previews.get(key, ""),
                "rows": str(counter["rows"]),
                "bytes": str(counter["bytes"]),
                "value_run_count": str(counter["value_run_count"]),
                "plateau_bytes": str(counter["plateau_bytes"]),
                "transition_count": str(counter["transition_count"]),
                "small_transition_count": str(counter["small_transition_count"]),
                "fixtures": str(len(fixtures[key])),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output.sort(key=lambda row: (-int_value(row, "rows"), -int_value(row, "bytes"), row.get("shape_key", "")))
    return output


def repeated_stats(groups: list[dict[str, str]]) -> tuple[int, int, int]:
    repeated = [row for row in groups if int_value(row, "rows") > 1]
    return len(repeated), sum(int_value(row, "rows") for row in repeated), sum(int_value(row, "bytes") for row in repeated)


def sum_bytes(rows: list[dict[str, str]]) -> int:
    return sum(int_value(row, "length") for row in rows)


def build_summary(
    rows: list[dict[str, str]],
    run_groups: list[dict[str, str]],
    transition_groups: list[dict[str, str]],
    fixture_issue_count: int,
) -> dict[str, str]:
    transition_count = sum(int_value(row, "transition_count") for row in rows)
    small_transition_count = sum(int_value(row, "small_transition_count") for row in rows)
    long_plateau = [row for row in rows if int_value(row, "max_value_run") >= 8]
    dominant_value = [row for row in rows if float(row.get("dominant_ratio", "0") or 0) >= 0.40]
    run_repeated = repeated_stats(run_groups)
    transition_repeated = repeated_stats(transition_groups)
    best_run = max(run_groups, key=lambda row: int_value(row, "bytes"), default={})
    best_transition = max(transition_groups, key=lambda row: int_value(row, "bytes"), default={})
    plateau_bytes = sum(int_value(row, "plateau_bytes") for row in rows)
    target_bytes = sum_bytes(rows)
    return {
        "scope": "total",
        "target_rows": str(len(rows)),
        "target_bytes": str(target_bytes),
        "value_run_count": str(sum(int_value(row, "value_run_count") for row in rows)),
        "plateau_bytes": str(plateau_bytes),
        "plateau_ratio": f"{(plateau_bytes / target_bytes) if target_bytes else 0.0:.6f}",
        "transition_count": str(transition_count),
        "small_transition_count": str(small_transition_count),
        "small_transition_ratio": f"{(small_transition_count / transition_count) if transition_count else 0.0:.6f}",
        "long_plateau_rows": str(len(long_plateau)),
        "long_plateau_bytes": str(sum_bytes(long_plateau)),
        "dominant_value_rows": str(len(dominant_value)),
        "dominant_value_bytes": str(sum_bytes(dominant_value)),
        "run_length_shape_groups": str(len(run_groups)),
        "run_length_repeated_groups": str(run_repeated[0]),
        "run_length_repeated_rows": str(run_repeated[1]),
        "run_length_repeated_bytes": str(run_repeated[2]),
        "transition_shape_groups": str(len(transition_groups)),
        "transition_repeated_groups": str(transition_repeated[0]),
        "transition_repeated_rows": str(transition_repeated[1]),
        "transition_repeated_bytes": str(transition_repeated[2]),
        "best_run_length_shape_rows": best_run.get("rows", "0"),
        "best_run_length_shape_bytes": best_run.get("bytes", "0"),
        "best_transition_shape_rows": best_transition.get("rows", "0"),
        "best_transition_shape_bytes": best_transition.get("bytes", "0"),
        "issue_rows": str(sum(1 for row in rows if row.get("issues")) + fixture_issue_count),
    }


def build_rows(
    target_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    rows, fixture_issues = build_target_rows(target_rows, fixture_rows)
    run_groups = build_group_rows(rows, "run_length_shape_key", "run_length_shape_preview", "run_length_shape")
    transition_groups = build_group_rows(rows, "transition_shape_key", "transition_shape_preview", "transition_shape")
    value_groups = build_group_rows(rows, "run_value_shape_key", "run_value_shape_preview", "run_value_shape")
    summary = build_summary(rows, run_groups, transition_groups, len(fixture_issues))
    return summary, rows, run_groups, transition_groups, value_groups


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    rows: list[dict[str, str]],
    run_groups: list[dict[str, str]],
    transition_groups: list[dict[str, str]],
    value_groups: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "targets": rows,
        "runGroups": run_groups,
        "transitionGroups": transition_groups,
        "valueGroups": value_groups,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("by_run_length_shape.csv", output_dir / "by_run_length_shape.csv"),
            ("by_transition_shape.csv", output_dir / "by_transition_shape.csv"),
            ("by_run_value_shape.csv", output_dir / "by_run_value_shape.csv"),
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
table {{ width: 100%; border-collapse: collapse; min-width: 1700px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Breaks flat-run gradient walks into plateau lengths and value transitions.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Flat walk bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Plateau bytes</div><div class="value ok">{summary['plateau_bytes']}</div></div>
    <div class="stat"><div class="label">Small transition ratio</div><div class="value">{summary['small_transition_ratio']}</div></div>
    <div class="stat"><div class="label">Repeated run-shape bytes</div><div class="value warn">{summary['run_length_repeated_bytes']}</div></div>
    <div class="stat"><div class="label">Dominant-value bytes</div><div class="value">{summary['dominant_value_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Run-length shapes</h2>{render_table(run_groups, GROUP_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Transition shapes</h2>{render_table(transition_groups, GROUP_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Run value shapes</h2>{render_table(value_groups, GROUP_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(rows, TARGET_FIELDNAMES, 120)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_FLAT_WALK_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe flat-run walks for gradient-like .tex nonzero gaps.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Flat Walk Probe",
    )
    args = parser.parse_args()

    summary, rows, run_groups, transition_groups, value_groups = build_rows(
        read_csv(args.targets),
        read_csv(args.fixtures),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, rows)
    write_csv(args.output / "by_run_length_shape.csv", GROUP_FIELDNAMES, run_groups)
    write_csv(args.output / "by_transition_shape.csv", GROUP_FIELDNAMES, transition_groups)
    write_csv(args.output / "by_run_value_shape.csv", GROUP_FIELDNAMES, value_groups)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, run_groups, transition_groups, value_groups, args.output, args.title))

    print(f"Flat-walk targets: {summary['target_rows']}")
    print(f"Flat-walk bytes: {summary['target_bytes']}")
    print(f"Plateau bytes: {summary['plateau_bytes']}")
    print(f"Repeated run-shape bytes: {summary['run_length_repeated_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
