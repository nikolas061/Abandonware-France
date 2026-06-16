#!/usr/bin/env python3
"""Gate noisy nonzero control-signal matches across mixed/residual/dense rows."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_control_signal_gate_probe")
DEFAULT_MIXED_TARGETS = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_control_probe/targets.csv"
)
DEFAULT_RESIDUAL_TARGETS = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_residual_control_probe/targets.csv"
)
DEFAULT_DENSE_TARGETS = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_dense_control_probe/targets.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "surface_count",
    "surface_rows",
    "surface_bytes",
    "jump_delta_count",
    "candidate_windows",
    "direction_ge75_rows",
    "direction_ge75_bytes",
    "phase_ge75_rows",
    "phase_ge75_bytes",
    "phase_ge75_long_rows",
    "phase_ge75_long_bytes",
    "direction_only_rows",
    "direction_only_bytes",
    "short_phase_rows",
    "short_phase_bytes",
    "long_phase_rows",
    "long_phase_bytes",
    "weak_control_rows",
    "weak_control_bytes",
    "shared_direction_signal_groups",
    "shared_phase_signal_groups",
    "best_direction_signal",
    "best_direction_signal_rows",
    "best_direction_signal_bytes",
    "best_phase_signal",
    "best_phase_signal_rows",
    "best_phase_signal_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

TARGET_FIELDNAMES = [
    "surface",
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "op_index",
    "jump_structure_class",
    "dense_class",
    "length",
    "start",
    "end",
    "jump_delta_count",
    "candidate_windows",
    "best_direction_pool",
    "best_direction_transform",
    "best_direction_exact",
    "best_direction_ratio",
    "best_phase_pool",
    "best_phase_transform",
    "best_phase_exact",
    "best_phase_ratio",
    "best_signal_kind",
    "best_signal_pool",
    "best_signal_transform",
    "best_signal_exact",
    "best_signal_ratio",
    "verdict",
    "issues",
]

SURFACE_FIELDNAMES = [
    "surface",
    "rows",
    "bytes",
    "jump_delta_count",
    "candidate_windows",
    "direction_ge75_rows",
    "direction_ge75_bytes",
    "phase_ge75_rows",
    "phase_ge75_bytes",
    "phase_ge75_long_rows",
    "phase_ge75_long_bytes",
    "direction_only_rows",
    "direction_only_bytes",
    "short_phase_rows",
    "short_phase_bytes",
    "long_phase_rows",
    "long_phase_bytes",
    "weak_control_rows",
    "weak_control_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

SIGNAL_FIELDNAMES = [
    "signal_kind",
    "signal_key",
    "rows",
    "bytes",
    "surfaces",
    "direction_ge75_rows",
    "direction_ge75_bytes",
    "phase_ge75_rows",
    "phase_ge75_bytes",
    "direction_only_rows",
    "direction_only_bytes",
    "short_phase_rows",
    "short_phase_bytes",
    "long_phase_rows",
    "long_phase_bytes",
    "sample_surface",
    "sample_pcx",
    "sample_frontier_id",
    "sample_start",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def float_value(row: dict[str, str], field: str) -> float:
    try:
        return float(row.get(field, "0") or 0)
    except ValueError:
        return 0.0


def signal_key(row: dict[str, str], prefix: str) -> str:
    pool = row.get(f"best_{prefix}_pool", "")
    transform = row.get(f"best_{prefix}_transform", "")
    if not pool and not transform:
        return ""
    return f"{pool}:{transform}"


def classify(row: dict[str, str]) -> str:
    direction_ge75 = float_value(row, "best_direction_ratio") >= 0.75
    phase_ge75 = float_value(row, "best_phase_ratio") >= 0.75
    long_phase = int_value(row, "jump_delta_count") >= 8
    if phase_ge75 and long_phase:
        return "long_phase_review"
    if phase_ge75:
        return "short_phase_review"
    if direction_ge75:
        return "direction_only_reject"
    return "weak_control"


def normalize_rows(surface: str, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in rows:
        verdict = classify(row)
        output.append(
            {
                "surface": surface,
                "rank": row.get("rank", ""),
                "archive": row.get("archive", ""),
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "span_index": row.get("span_index", ""),
                "run_index": row.get("run_index", ""),
                "op_index": row.get("op_index", ""),
                "jump_structure_class": row.get("jump_structure_class", ""),
                "dense_class": row.get("dense_class", ""),
                "length": row.get("length", "0"),
                "start": row.get("start", ""),
                "end": row.get("end", ""),
                "jump_delta_count": row.get("jump_delta_count", "0"),
                "candidate_windows": row.get("candidate_windows", "0"),
                "best_direction_pool": row.get("best_direction_pool", ""),
                "best_direction_transform": row.get("best_direction_transform", ""),
                "best_direction_exact": row.get("best_direction_exact", "0"),
                "best_direction_ratio": row.get("best_direction_ratio", "0"),
                "best_phase_pool": row.get("best_phase_pool", ""),
                "best_phase_transform": row.get("best_phase_transform", ""),
                "best_phase_exact": row.get("best_phase_exact", "0"),
                "best_phase_ratio": row.get("best_phase_ratio", "0"),
                "best_signal_kind": row.get("best_signal_kind", ""),
                "best_signal_pool": row.get("best_signal_pool", ""),
                "best_signal_transform": row.get("best_signal_transform", ""),
                "best_signal_exact": row.get("best_signal_exact", "0"),
                "best_signal_ratio": row.get("best_signal_ratio", "0"),
                "verdict": verdict,
                "issues": row.get("issues", ""),
            }
        )
    output.sort(
        key=lambda row: (
            row.get("verdict", ""),
            row.get("surface", ""),
            -int_value(row, "length"),
            row.get("pcx_name", ""),
            int_value(row, "start"),
        )
    )
    return output


def row_stats(rows: list[dict[str, str]]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for row in rows:
        length = int_value(row, "length")
        verdict = row.get("verdict", "")
        direction_ge75 = float_value(row, "best_direction_ratio") >= 0.75
        phase_ge75 = float_value(row, "best_phase_ratio") >= 0.75
        counter["rows"] += 1
        counter["bytes"] += length
        counter["jump_delta_count"] += int_value(row, "jump_delta_count")
        counter["candidate_windows"] += int_value(row, "candidate_windows")
        if direction_ge75:
            counter["direction_ge75_rows"] += 1
            counter["direction_ge75_bytes"] += length
        if phase_ge75:
            counter["phase_ge75_rows"] += 1
            counter["phase_ge75_bytes"] += length
        if verdict == "long_phase_review":
            counter["phase_ge75_long_rows"] += 1
            counter["phase_ge75_long_bytes"] += length
            counter["long_phase_rows"] += 1
            counter["long_phase_bytes"] += length
        elif verdict == "short_phase_review":
            counter["short_phase_rows"] += 1
            counter["short_phase_bytes"] += length
        elif verdict == "direction_only_reject":
            counter["direction_only_rows"] += 1
            counter["direction_only_bytes"] += length
        elif verdict == "weak_control":
            counter["weak_control_rows"] += 1
            counter["weak_control_bytes"] += length
        if row.get("issues"):
            counter["issue_rows"] += 1
    return counter


def build_surface_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("surface", "")].append(row)
    output: list[dict[str, str]] = []
    for surface, surface_rows in grouped.items():
        stats = row_stats(surface_rows)
        output.append(
            {
                "surface": surface,
                "rows": str(stats["rows"]),
                "bytes": str(stats["bytes"]),
                "jump_delta_count": str(stats["jump_delta_count"]),
                "candidate_windows": str(stats["candidate_windows"]),
                "direction_ge75_rows": str(stats["direction_ge75_rows"]),
                "direction_ge75_bytes": str(stats["direction_ge75_bytes"]),
                "phase_ge75_rows": str(stats["phase_ge75_rows"]),
                "phase_ge75_bytes": str(stats["phase_ge75_bytes"]),
                "phase_ge75_long_rows": str(stats["phase_ge75_long_rows"]),
                "phase_ge75_long_bytes": str(stats["phase_ge75_long_bytes"]),
                "direction_only_rows": str(stats["direction_only_rows"]),
                "direction_only_bytes": str(stats["direction_only_bytes"]),
                "short_phase_rows": str(stats["short_phase_rows"]),
                "short_phase_bytes": str(stats["short_phase_bytes"]),
                "long_phase_rows": str(stats["long_phase_rows"]),
                "long_phase_bytes": str(stats["long_phase_bytes"]),
                "weak_control_rows": str(stats["weak_control_rows"]),
                "weak_control_bytes": str(stats["weak_control_bytes"]),
                "promotion_ready_bytes": "0",
                "issue_rows": str(stats["issue_rows"]),
            }
        )
    output.sort(key=lambda row: row.get("surface", ""))
    return output


def build_signal_rows(rows: list[dict[str, str]], kind: str) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = signal_key(row, kind)
        if key:
            grouped[key].append(row)
    output: list[dict[str, str]] = []
    for key, signal_rows in grouped.items():
        stats = row_stats(signal_rows)
        surfaces = sorted({row.get("surface", "") for row in signal_rows})
        sample = signal_rows[0]
        output.append(
            {
                "signal_kind": kind,
                "signal_key": key,
                "rows": str(stats["rows"]),
                "bytes": str(stats["bytes"]),
                "surfaces": str(len(surfaces)),
                "direction_ge75_rows": str(stats["direction_ge75_rows"]),
                "direction_ge75_bytes": str(stats["direction_ge75_bytes"]),
                "phase_ge75_rows": str(stats["phase_ge75_rows"]),
                "phase_ge75_bytes": str(stats["phase_ge75_bytes"]),
                "direction_only_rows": str(stats["direction_only_rows"]),
                "direction_only_bytes": str(stats["direction_only_bytes"]),
                "short_phase_rows": str(stats["short_phase_rows"]),
                "short_phase_bytes": str(stats["short_phase_bytes"]),
                "long_phase_rows": str(stats["long_phase_rows"]),
                "long_phase_bytes": str(stats["long_phase_bytes"]),
                "sample_surface": sample.get("surface", ""),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
                "sample_start": sample.get("start", ""),
            }
        )
    output.sort(key=lambda row: (-int_value(row, "bytes"), -int_value(row, "rows"), row.get("signal_key", "")))
    return output


def best_signal(rows: list[dict[str, str]]) -> tuple[str, str, str]:
    if not rows:
        return "", "0", "0"
    best = rows[0]
    return best.get("signal_key", ""), best.get("rows", "0"), best.get("bytes", "0")


def build_summary(
    rows: list[dict[str, str]],
    surface_rows: list[dict[str, str]],
    direction_groups: list[dict[str, str]],
    phase_groups: list[dict[str, str]],
) -> dict[str, str]:
    stats = row_stats(rows)
    best_direction = best_signal(direction_groups)
    best_phase = best_signal(phase_groups)
    return {
        "scope": "total",
        "surface_count": str(len(surface_rows)),
        "surface_rows": str(stats["rows"]),
        "surface_bytes": str(stats["bytes"]),
        "jump_delta_count": str(stats["jump_delta_count"]),
        "candidate_windows": str(stats["candidate_windows"]),
        "direction_ge75_rows": str(stats["direction_ge75_rows"]),
        "direction_ge75_bytes": str(stats["direction_ge75_bytes"]),
        "phase_ge75_rows": str(stats["phase_ge75_rows"]),
        "phase_ge75_bytes": str(stats["phase_ge75_bytes"]),
        "phase_ge75_long_rows": str(stats["phase_ge75_long_rows"]),
        "phase_ge75_long_bytes": str(stats["phase_ge75_long_bytes"]),
        "direction_only_rows": str(stats["direction_only_rows"]),
        "direction_only_bytes": str(stats["direction_only_bytes"]),
        "short_phase_rows": str(stats["short_phase_rows"]),
        "short_phase_bytes": str(stats["short_phase_bytes"]),
        "long_phase_rows": str(stats["long_phase_rows"]),
        "long_phase_bytes": str(stats["long_phase_bytes"]),
        "weak_control_rows": str(stats["weak_control_rows"]),
        "weak_control_bytes": str(stats["weak_control_bytes"]),
        "shared_direction_signal_groups": str(sum(1 for row in direction_groups if int_value(row, "rows") > 1)),
        "shared_phase_signal_groups": str(sum(1 for row in phase_groups if int_value(row, "rows") > 1)),
        "best_direction_signal": best_direction[0],
        "best_direction_signal_rows": best_direction[1],
        "best_direction_signal_bytes": best_direction[2],
        "best_phase_signal": best_phase[0],
        "best_phase_signal_rows": best_phase[1],
        "best_phase_signal_bytes": best_phase[2],
        "promotion_ready_bytes": "0",
        "issue_rows": str(stats["issue_rows"]),
    }


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    rows: list[dict[str, str]],
    surface_rows: list[dict[str, str]],
    signal_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "targets": rows,
        "surfaceRows": surface_rows,
        "signalRows": signal_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("by_surface.csv", output_dir / "by_surface.csv"),
            ("by_signal.csv", output_dir / "by_signal.csv"),
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
    <div class="sub">Aggregates direction-only and phase-control matches across noisy nonzero control probes.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Rows</div><div class="value">{summary['surface_rows']}</div></div>
    <div class="stat"><div class="label">Bytes</div><div class="value">{summary['surface_bytes']}</div></div>
    <div class="stat"><div class="label">Direction-only bytes</div><div class="value warn">{summary['direction_only_bytes']}</div></div>
    <div class="stat"><div class="label">Long phase bytes</div><div class="value ok">{summary['phase_ge75_long_bytes']}</div></div>
    <div class="stat"><div class="label">Promotion-ready bytes</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Surfaces</h2>{render_table(surface_rows, SURFACE_FIELDNAMES, 20)}</section>
  <section class="panel"><h2>Signals</h2>{render_table(signal_rows, SIGNAL_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(rows, TARGET_FIELDNAMES, 180)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_CONTROL_SIGNAL_GATE_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Gate noisy nonzero control signal matches.")
    parser.add_argument("--mixed-targets", type=Path, default=DEFAULT_MIXED_TARGETS)
    parser.add_argument("--residual-targets", type=Path, default=DEFAULT_RESIDUAL_TARGETS)
    parser.add_argument("--dense-targets", type=Path, default=DEFAULT_DENSE_TARGETS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Control Signal Gate Probe",
    )
    args = parser.parse_args()

    rows = (
        normalize_rows("mixed_control", read_csv(args.mixed_targets))
        + normalize_rows("residual_control", read_csv(args.residual_targets))
        + normalize_rows("dense_control", read_csv(args.dense_targets))
    )
    surface_rows = build_surface_rows(rows)
    direction_groups = build_signal_rows(rows, "direction")
    phase_groups = build_signal_rows(rows, "phase")
    signal_rows = sorted(
        direction_groups + phase_groups,
        key=lambda row: (
            row.get("signal_kind", ""),
            -int_value(row, "bytes"),
            -int_value(row, "rows"),
            row.get("signal_key", ""),
        ),
    )
    summary = build_summary(rows, surface_rows, direction_groups, phase_groups)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, rows)
    write_csv(args.output / "by_surface.csv", SURFACE_FIELDNAMES, surface_rows)
    write_csv(args.output / "by_signal.csv", SIGNAL_FIELDNAMES, signal_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, surface_rows, signal_rows, args.output, args.title))

    print(f"Control-signal rows: {summary['surface_rows']}")
    print(f"Direction-only bytes: {summary['direction_only_bytes']}")
    print(f"Long phase bytes: {summary['phase_ge75_long_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
