#!/usr/bin/env python3
"""Correlate mixed jump rows with dominant-band control/source signals."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_dense_control_probe import (
    GROUP_FIELDNAMES,
    build_group_rows,
    direction_label,
    direction_label_sets,
    jump_pairs,
    load_fixture_pools,
    magnitude_label,
    magnitude_label_sets,
    nibble_pair_label_sets,
    operation_pools,
    phase_label_sets,
    score_pools,
    target_op_key,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import (
    DEFAULT_FIXTURES,
    DEFAULT_OPERATIONS,
    fixture_key,
    load_expected_by_fixture,
    op_key,
    read_csv,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_control_probe")
DEFAULT_TARGETS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_jump_probe/targets.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "operation_rows",
    "missing_operation_rows",
    "jump_delta_count",
    "long_island_bytes",
    "dominant_band_rows",
    "dominant_band_bytes",
    "zero_band_rows",
    "zero_band_bytes",
    "multi_band_rows",
    "multi_band_bytes",
    "candidate_windows",
    "direction_exact_total",
    "direction_best_single",
    "direction_ge50_rows",
    "direction_ge75_rows",
    "magnitude_exact_total",
    "magnitude_best_single",
    "magnitude_ge50_rows",
    "magnitude_ge75_rows",
    "nibble_pair_exact_total",
    "nibble_pair_best_single",
    "nibble_pair_ge50_rows",
    "nibble_pair_ge75_rows",
    "phase_exact_total",
    "phase_best_single",
    "phase_ge50_rows",
    "phase_ge75_rows",
    "phase_ge75_long_rows",
    "phase_ge75_long_bytes",
    "best_overall_signal",
    "best_overall_exact",
    "best_overall_ratio",
    "source_like_rows",
    "source_like_bytes",
    "promotion_ready_bytes",
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
    "jump_delta_count",
    "long_island_bytes",
    "dominant_band_pair",
    "dominant_band_count",
    "dominant_band_ratio",
    "zero_band_ratio",
    "band_pair_count",
    "operation_present",
    "candidate_windows",
    "best_direction_pool",
    "best_direction_transform",
    "best_direction_offset",
    "best_direction_exact",
    "best_direction_ratio",
    "best_magnitude_pool",
    "best_magnitude_transform",
    "best_magnitude_offset",
    "best_magnitude_exact",
    "best_magnitude_ratio",
    "best_nibble_pair_pool",
    "best_nibble_pair_transform",
    "best_nibble_pair_offset",
    "best_nibble_pair_exact",
    "best_nibble_pair_ratio",
    "best_phase_pool",
    "best_phase_transform",
    "best_phase_offset",
    "best_phase_exact",
    "best_phase_ratio",
    "best_signal_kind",
    "best_signal_pool",
    "best_signal_transform",
    "best_signal_exact",
    "best_signal_ratio",
    "head_hex",
    "tail_hex",
    "issues",
]

BAND_GROUP_FIELDNAMES = [
    "dominant_band_pair",
    "rows",
    "bytes",
    "jump_delta_count",
    "long_island_bytes",
    "phase_ge50_rows",
    "phase_ge75_rows",
    "phase_ge75_long_rows",
    "source_like_bytes",
    "best_signal_exact",
    "fixtures",
    "sample_pcx",
    "sample_frontier_id",
]


def ratio(numerator: int, denominator: int) -> str:
    return f"{(numerator / denominator) if denominator else 0.0:.6f}"


def best_signal_summary(rows: list[dict[str, str]]) -> tuple[str, int, str]:
    if not rows:
        return "", 0, "0.000000"
    best = max(
        rows,
        key=lambda row: (
            float(row.get("best_signal_ratio", "0") or 0),
            int_value(row, "best_signal_exact"),
            row.get("best_signal_kind", "") == "phase",
        ),
    )
    return (
        f"{best.get('best_signal_kind', '')}:{best.get('best_signal_pool', '')}:{best.get('best_signal_transform', '')}",
        int_value(best, "best_signal_exact"),
        best.get("best_signal_ratio", "0.000000"),
    )


def build_target_rows(
    target_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    operations = {op_key(row): row for row in operation_rows}
    fixture_pools = load_fixture_pools(fixture_rows)
    expected_by_fixture, fixture_issues = load_expected_by_fixture(fixture_rows)
    output: list[dict[str, str]] = []
    for target in target_rows:
        issues = [issue for issue in target.get("issues", "").split(";") if issue]
        issues.extend(issue for issue in fixture_issues if str(fixture_key(target)) in issue)
        expected_all = expected_by_fixture.get(fixture_key(target), b"")
        expected = expected_all[int_value(target, "start") : int_value(target, "end")]
        if not expected:
            issues.append("missing_expected_chunk")
            continue
        pairs = jump_pairs(expected)
        if not pairs:
            issues.append("missing_jump_pairs")
        directions = [direction_label(delta) for _left, _right, delta in pairs]
        magnitudes = [magnitude_label(delta) for _left, _right, delta in pairs]
        nibble_pairs = [f"{left >> 4:x}>{right >> 4:x}" for left, right, _delta in pairs]
        phases = [f"{direction_label(delta)}{magnitude_label(delta)}:{left >> 4:x}>{right >> 4:x}" for left, right, delta in pairs]
        operation = operations.get(target_op_key(target), {})
        if not operation:
            issues.append("missing_operation")
        pools = {**fixture_pools.get(fixture_key(target), {}), **operation_pools(operation)}
        pools = {name: data for name, data in pools.items() if data}

        direction_best, direction_windows = score_pools(directions, pools, direction_label_sets)
        magnitude_best, magnitude_windows = score_pools(magnitudes, pools, magnitude_label_sets)
        nibble_best, nibble_windows = score_pools(nibble_pairs, pools, nibble_pair_label_sets)
        phase_best, phase_windows = score_pools(phases, pools, phase_label_sets)
        scored = [
            ("direction", direction_best),
            ("magnitude", magnitude_best),
            ("nibble_pair", nibble_best),
            ("phase", phase_best),
        ]
        best_kind, best_signal = max(
            scored,
            key=lambda item: (
                float(item[1].get("ratio", "0") or 0),
                int_value(item[1], "exact"),
                item[0] == "phase",
            ),
        )
        output.append(
            {
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
                "jump_delta_count": str(len(pairs)),
                "long_island_bytes": target.get("long_island_bytes", "0"),
                "dominant_band_pair": target.get("dominant_band_pair", ""),
                "dominant_band_count": target.get("dominant_band_count", "0"),
                "dominant_band_ratio": target.get("dominant_band_ratio", "0"),
                "zero_band_ratio": target.get("zero_band_ratio", "0"),
                "band_pair_count": target.get("band_pair_count", "0"),
                "operation_present": "1" if operation else "0",
                "candidate_windows": str(direction_windows + magnitude_windows + nibble_windows + phase_windows),
                "best_direction_pool": direction_best["pool"],
                "best_direction_transform": direction_best["transform"],
                "best_direction_offset": direction_best["offset"],
                "best_direction_exact": direction_best["exact"],
                "best_direction_ratio": direction_best["ratio"],
                "best_magnitude_pool": magnitude_best["pool"],
                "best_magnitude_transform": magnitude_best["transform"],
                "best_magnitude_offset": magnitude_best["offset"],
                "best_magnitude_exact": magnitude_best["exact"],
                "best_magnitude_ratio": magnitude_best["ratio"],
                "best_nibble_pair_pool": nibble_best["pool"],
                "best_nibble_pair_transform": nibble_best["transform"],
                "best_nibble_pair_offset": nibble_best["offset"],
                "best_nibble_pair_exact": nibble_best["exact"],
                "best_nibble_pair_ratio": nibble_best["ratio"],
                "best_phase_pool": phase_best["pool"],
                "best_phase_transform": phase_best["transform"],
                "best_phase_offset": phase_best["offset"],
                "best_phase_exact": phase_best["exact"],
                "best_phase_ratio": phase_best["ratio"],
                "best_signal_kind": best_kind,
                "best_signal_pool": best_signal["pool"],
                "best_signal_transform": best_signal["transform"],
                "best_signal_exact": best_signal["exact"],
                "best_signal_ratio": best_signal["ratio"],
                "head_hex": expected[:16].hex(),
                "tail_hex": expected[-16:].hex(),
                "issues": ";".join(issues),
            }
        )
    return output


def build_band_groups(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    counters: dict[str, Counter[str]] = defaultdict(Counter)
    fixtures: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    samples: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row.get("dominant_band_pair", "")
        counters[key]["rows"] += 1
        counters[key]["bytes"] += int_value(row, "length")
        counters[key]["jump_delta_count"] += int_value(row, "jump_delta_count")
        counters[key]["long_island_bytes"] += int_value(row, "long_island_bytes")
        counters[key]["best_signal_exact"] += int_value(row, "best_signal_exact")
        phase_ratio = float(row.get("best_phase_ratio", "0") or 0)
        if phase_ratio >= 0.50:
            counters[key]["phase_ge50_rows"] += 1
        if phase_ratio >= 0.75:
            counters[key]["phase_ge75_rows"] += 1
            counters[key]["source_like_bytes"] += int_value(row, "length")
            if int_value(row, "jump_delta_count") >= 8:
                counters[key]["phase_ge75_long_rows"] += 1
        fixtures[key].add(fixture_key(row))
        samples.setdefault(key, row)
    output: list[dict[str, str]] = []
    for key, counter in counters.items():
        sample = samples[key]
        output.append(
            {
                "dominant_band_pair": key,
                "rows": str(counter["rows"]),
                "bytes": str(counter["bytes"]),
                "jump_delta_count": str(counter["jump_delta_count"]),
                "long_island_bytes": str(counter["long_island_bytes"]),
                "phase_ge50_rows": str(counter["phase_ge50_rows"]),
                "phase_ge75_rows": str(counter["phase_ge75_rows"]),
                "phase_ge75_long_rows": str(counter["phase_ge75_long_rows"]),
                "source_like_bytes": str(counter["source_like_bytes"]),
                "best_signal_exact": str(counter["best_signal_exact"]),
                "fixtures": str(len(fixtures[key])),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output.sort(key=lambda row: (-int_value(row, "bytes"), row.get("dominant_band_pair", "")))
    return output


def build_summary(rows: list[dict[str, str]]) -> dict[str, str]:
    best_signal, best_exact, best_ratio = best_signal_summary(rows)
    source_like = [row for row in rows if float(row.get("best_phase_ratio", "0") or 0) >= 0.75]
    long_source_like = [row for row in source_like if int_value(row, "jump_delta_count") >= 8]
    dominant_rows = [row for row in rows if float(row.get("dominant_band_ratio", "0") or 0) >= 0.40]
    zero_rows = [row for row in rows if float(row.get("zero_band_ratio", "0") or 0) >= 0.40]
    multi_rows = [row for row in rows if int_value(row, "band_pair_count") > 1]
    return {
        "scope": "total",
        "target_rows": str(len(rows)),
        "target_bytes": str(sum(int_value(row, "length") for row in rows)),
        "operation_rows": str(sum(1 for row in rows if row.get("operation_present") == "1")),
        "missing_operation_rows": str(sum(1 for row in rows if row.get("operation_present") != "1")),
        "jump_delta_count": str(sum(int_value(row, "jump_delta_count") for row in rows)),
        "long_island_bytes": str(sum(int_value(row, "long_island_bytes") for row in rows)),
        "dominant_band_rows": str(len(dominant_rows)),
        "dominant_band_bytes": str(sum(int_value(row, "length") for row in dominant_rows)),
        "zero_band_rows": str(len(zero_rows)),
        "zero_band_bytes": str(sum(int_value(row, "length") for row in zero_rows)),
        "multi_band_rows": str(len(multi_rows)),
        "multi_band_bytes": str(sum(int_value(row, "length") for row in multi_rows)),
        "candidate_windows": str(sum(int_value(row, "candidate_windows") for row in rows)),
        "direction_exact_total": str(sum(int_value(row, "best_direction_exact") for row in rows)),
        "direction_best_single": str(max((int_value(row, "best_direction_exact") for row in rows), default=0)),
        "direction_ge50_rows": str(sum(1 for row in rows if float(row.get("best_direction_ratio", "0") or 0) >= 0.50)),
        "direction_ge75_rows": str(sum(1 for row in rows if float(row.get("best_direction_ratio", "0") or 0) >= 0.75)),
        "magnitude_exact_total": str(sum(int_value(row, "best_magnitude_exact") for row in rows)),
        "magnitude_best_single": str(max((int_value(row, "best_magnitude_exact") for row in rows), default=0)),
        "magnitude_ge50_rows": str(sum(1 for row in rows if float(row.get("best_magnitude_ratio", "0") or 0) >= 0.50)),
        "magnitude_ge75_rows": str(sum(1 for row in rows if float(row.get("best_magnitude_ratio", "0") or 0) >= 0.75)),
        "nibble_pair_exact_total": str(sum(int_value(row, "best_nibble_pair_exact") for row in rows)),
        "nibble_pair_best_single": str(max((int_value(row, "best_nibble_pair_exact") for row in rows), default=0)),
        "nibble_pair_ge50_rows": str(sum(1 for row in rows if float(row.get("best_nibble_pair_ratio", "0") or 0) >= 0.50)),
        "nibble_pair_ge75_rows": str(sum(1 for row in rows if float(row.get("best_nibble_pair_ratio", "0") or 0) >= 0.75)),
        "phase_exact_total": str(sum(int_value(row, "best_phase_exact") for row in rows)),
        "phase_best_single": str(max((int_value(row, "best_phase_exact") for row in rows), default=0)),
        "phase_ge50_rows": str(sum(1 for row in rows if float(row.get("best_phase_ratio", "0") or 0) >= 0.50)),
        "phase_ge75_rows": str(len(source_like)),
        "phase_ge75_long_rows": str(len(long_source_like)),
        "phase_ge75_long_bytes": str(sum(int_value(row, "length") for row in long_source_like)),
        "best_overall_signal": best_signal,
        "best_overall_exact": str(best_exact),
        "best_overall_ratio": best_ratio,
        "source_like_rows": str(len(source_like)),
        "source_like_bytes": str(sum(int_value(row, "length") for row in source_like)),
        "promotion_ready_bytes": "0",
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
    rows: list[dict[str, str]],
    band_groups: list[dict[str, str]],
    signal_groups: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "targets": rows,
        "bandGroups": band_groups,
        "signalGroups": signal_groups,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("by_dominant_band.csv", output_dir / "by_dominant_band.csv"),
            ("by_best_signal.csv", output_dir / "by_best_signal.csv"),
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
table {{ width: 100%; border-collapse: collapse; min-width: 1650px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Scores mixed jump rows by dominant band against control/source signal families.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Mixed bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Candidate windows</div><div class="value">{summary['candidate_windows']}</div></div>
    <div class="stat"><div class="label">Phase rows >=75%</div><div class="value warn">{summary['phase_ge75_rows']}</div></div>
    <div class="stat"><div class="label">Long phase bytes >=75%</div><div class="value ok">{summary['phase_ge75_long_bytes']}</div></div>
    <div class="stat"><div class="label">Promotion-ready bytes</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Dominant bands</h2>{render_table(band_groups, BAND_GROUP_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Best signals</h2>{render_table(signal_groups, GROUP_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(rows, TARGET_FIELDNAMES, 120)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_MIXED_CONTROL_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe mixed jump rows against control signals by dominant band.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Mixed Control Probe",
    )
    args = parser.parse_args()

    rows = build_target_rows(read_csv(args.targets), read_csv(args.operations), read_csv(args.fixtures))
    band_groups = build_band_groups(rows)
    signal_groups = build_group_rows(rows)
    summary = build_summary(rows)
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, rows)
    write_csv(args.output / "by_dominant_band.csv", BAND_GROUP_FIELDNAMES, band_groups)
    write_csv(args.output / "by_best_signal.csv", GROUP_FIELDNAMES, signal_groups)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, band_groups, signal_groups, args.output, args.title))

    print(f"Mixed-control targets: {summary['target_rows']}")
    print(f"Mixed-control bytes: {summary['target_bytes']}")
    print(f"Phase rows >=75%: {summary['phase_ge75_rows']}")
    print(f"Long phase bytes >=75%: {summary['phase_ge75_long_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
