#!/usr/bin/env python3
"""Inspect value-side evidence behind direction-only noisy nonzero control rows."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_probe")
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
    "target_rows",
    "target_bytes",
    "surface_count",
    "direction_signal_groups",
    "value_signal_groups",
    "direction_value_groups",
    "value_ge75_rows",
    "value_ge75_bytes",
    "value_exact_rows",
    "value_exact_bytes",
    "magnitude_ge75_rows",
    "magnitude_ge75_bytes",
    "nibble_ge75_rows",
    "nibble_ge75_bytes",
    "byte_bucket_rows",
    "byte_bucket_bytes",
    "high_nibble_bucket_rows",
    "high_nibble_bucket_bytes",
    "low_nibble_bucket_rows",
    "low_nibble_bucket_bytes",
    "adjacent_delta_bucket_rows",
    "adjacent_delta_bucket_bytes",
    "repeated_direction_value_groups",
    "repeated_direction_value_bytes",
    "same_offset_groups",
    "same_offset_bytes",
    "conflicted_offset_groups",
    "conflicted_offset_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

TARGET_FIELDNAMES = [
    "surface",
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
    "direction_key",
    "direction_offset",
    "direction_exact",
    "direction_ratio",
    "best_value_kind",
    "best_value_key",
    "best_value_offset",
    "best_value_exact",
    "best_value_ratio",
    "magnitude_key",
    "magnitude_offset",
    "magnitude_exact",
    "magnitude_ratio",
    "nibble_key",
    "nibble_offset",
    "nibble_exact",
    "nibble_ratio",
    "direction_value_key",
    "verdict",
    "head_hex",
    "tail_hex",
    "issues",
]

SIGNAL_FIELDNAMES = [
    "signal_key",
    "rows",
    "bytes",
    "surfaces",
    "value_ge75_rows",
    "value_ge75_bytes",
    "value_exact_rows",
    "value_exact_bytes",
    "same_offset",
    "direction_offsets",
    "value_offsets",
    "sample_surface",
    "sample_pcx",
    "sample_frontier_id",
    "sample_start",
    "verdict",
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


def best_value_signal(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    candidates = [
        (
            "magnitude",
            signal_key(row, "magnitude"),
            row.get("best_magnitude_offset", ""),
            row.get("best_magnitude_exact", "0"),
            row.get("best_magnitude_ratio", "0"),
        ),
        (
            "nibble",
            signal_key(row, "nibble_pair"),
            row.get("best_nibble_pair_offset", ""),
            row.get("best_nibble_pair_exact", "0"),
            row.get("best_nibble_pair_ratio", "0"),
        ),
    ]
    candidates.sort(key=lambda item: (float(item[4] or 0), int(item[3] or 0)), reverse=True)
    return candidates[0]


def direction_only(row: dict[str, str]) -> bool:
    return float_value(row, "best_direction_ratio") >= 0.75 and float_value(row, "best_phase_ratio") < 0.75


def normalize_rows(surface: str, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in rows:
        if not direction_only(row):
            continue
        value_kind, value_key, value_offset, value_exact, value_ratio = best_value_signal(row)
        direction_key = signal_key(row, "direction")
        value_ratio_float = float(value_ratio or 0)
        length = int_value(row, "length")
        if value_ratio_float >= 1.0:
            verdict = "exact_bucket_review"
        elif value_ratio_float >= 0.75:
            verdict = "bucket_value_review"
        else:
            verdict = "weak_value_reject"
        output.append(
            {
                "surface": surface,
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
                "direction_key": direction_key,
                "direction_offset": row.get("best_direction_offset", ""),
                "direction_exact": row.get("best_direction_exact", "0"),
                "direction_ratio": row.get("best_direction_ratio", "0"),
                "best_value_kind": value_kind,
                "best_value_key": value_key,
                "best_value_offset": value_offset,
                "best_value_exact": value_exact,
                "best_value_ratio": value_ratio,
                "magnitude_key": signal_key(row, "magnitude"),
                "magnitude_offset": row.get("best_magnitude_offset", ""),
                "magnitude_exact": row.get("best_magnitude_exact", "0"),
                "magnitude_ratio": row.get("best_magnitude_ratio", "0"),
                "nibble_key": signal_key(row, "nibble_pair"),
                "nibble_offset": row.get("best_nibble_pair_offset", ""),
                "nibble_exact": row.get("best_nibble_pair_exact", "0"),
                "nibble_ratio": row.get("best_nibble_pair_ratio", "0"),
                "direction_value_key": f"{direction_key}|{value_kind}:{value_key}",
                "verdict": verdict,
                "head_hex": row.get("head_hex", ""),
                "tail_hex": row.get("tail_hex", ""),
                "issues": row.get("issues", ""),
            }
        )
    output.sort(
        key=lambda item: (
            item.get("verdict", ""),
            item.get("direction_value_key", ""),
            -int_value(item, "length"),
            item.get("pcx_name", ""),
            int_value(item, "start"),
        )
    )
    return output


def row_stats(rows: list[dict[str, str]]) -> Counter[str]:
    stats: Counter[str] = Counter()
    for row in rows:
        length = int_value(row, "length")
        stats["rows"] += 1
        stats["bytes"] += length
        if float_value(row, "best_value_ratio") >= 0.75:
            stats["value_ge75_rows"] += 1
            stats["value_ge75_bytes"] += length
        if float_value(row, "best_value_ratio") >= 1.0:
            stats["value_exact_rows"] += 1
            stats["value_exact_bytes"] += length
        if float_value(row, "magnitude_ratio") >= 0.75:
            stats["magnitude_ge75_rows"] += 1
            stats["magnitude_ge75_bytes"] += length
        if float_value(row, "nibble_ratio") >= 0.75:
            stats["nibble_ge75_rows"] += 1
            stats["nibble_ge75_bytes"] += length
        if row.get("best_value_key", "").endswith(":byte_bucket") and float_value(row, "best_value_ratio") >= 0.75:
            stats["byte_bucket_rows"] += 1
            stats["byte_bucket_bytes"] += length
        if row.get("best_value_key", "").endswith(":high_nibble_bucket") and float_value(row, "best_value_ratio") >= 0.75:
            stats["high_nibble_bucket_rows"] += 1
            stats["high_nibble_bucket_bytes"] += length
        if row.get("best_value_key", "").endswith(":low_nibble_bucket") and float_value(row, "best_value_ratio") >= 0.75:
            stats["low_nibble_bucket_rows"] += 1
            stats["low_nibble_bucket_bytes"] += length
        if row.get("best_value_key", "").endswith(":adjacent_delta_bucket") and float_value(row, "best_value_ratio") >= 0.75:
            stats["adjacent_delta_bucket_rows"] += 1
            stats["adjacent_delta_bucket_bytes"] += length
        if row.get("issues"):
            stats["issue_rows"] += 1
    return stats


def build_signal_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("direction_value_key", "")].append(row)
    output: list[dict[str, str]] = []
    for key, group_rows in grouped.items():
        stats = row_stats(group_rows)
        surfaces = sorted({row.get("surface", "") for row in group_rows})
        direction_offsets = sorted({row.get("direction_offset", "") for row in group_rows})
        value_offsets = sorted({row.get("best_value_offset", "") for row in group_rows})
        same_offset = len(direction_offsets) == 1 and len(value_offsets) == 1
        sample = group_rows[0]
        if len(group_rows) < 2:
            verdict = "single_context"
        elif same_offset:
            verdict = "same_offset_review"
        else:
            verdict = "offset_conflict_reject"
        output.append(
            {
                "signal_key": key,
                "rows": str(len(group_rows)),
                "bytes": str(sum(int_value(row, "length") for row in group_rows)),
                "surfaces": str(len(surfaces)),
                "value_ge75_rows": str(stats["value_ge75_rows"]),
                "value_ge75_bytes": str(stats["value_ge75_bytes"]),
                "value_exact_rows": str(stats["value_exact_rows"]),
                "value_exact_bytes": str(stats["value_exact_bytes"]),
                "same_offset": "1" if same_offset else "0",
                "direction_offsets": "|".join(direction_offsets),
                "value_offsets": "|".join(value_offsets),
                "sample_surface": sample.get("surface", ""),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
                "sample_start": sample.get("start", ""),
                "verdict": verdict,
            }
        )
    output.sort(key=lambda row: (-int_value(row, "bytes"), -int_value(row, "rows"), row.get("signal_key", "")))
    return output


def build_summary(rows: list[dict[str, str]], signal_rows: list[dict[str, str]]) -> dict[str, str]:
    stats = row_stats(rows)
    repeated = [row for row in signal_rows if int_value(row, "rows") > 1]
    same_offset = [row for row in repeated if row.get("same_offset") == "1"]
    conflicted = [row for row in repeated if row.get("same_offset") != "1"]
    return {
        "scope": "total",
        "target_rows": str(stats["rows"]),
        "target_bytes": str(stats["bytes"]),
        "surface_count": str(len({row.get("surface", "") for row in rows})),
        "direction_signal_groups": str(len({row.get("direction_key", "") for row in rows})),
        "value_signal_groups": str(len({f"{row.get('best_value_kind', '')}:{row.get('best_value_key', '')}" for row in rows})),
        "direction_value_groups": str(len(signal_rows)),
        "value_ge75_rows": str(stats["value_ge75_rows"]),
        "value_ge75_bytes": str(stats["value_ge75_bytes"]),
        "value_exact_rows": str(stats["value_exact_rows"]),
        "value_exact_bytes": str(stats["value_exact_bytes"]),
        "magnitude_ge75_rows": str(stats["magnitude_ge75_rows"]),
        "magnitude_ge75_bytes": str(stats["magnitude_ge75_bytes"]),
        "nibble_ge75_rows": str(stats["nibble_ge75_rows"]),
        "nibble_ge75_bytes": str(stats["nibble_ge75_bytes"]),
        "byte_bucket_rows": str(stats["byte_bucket_rows"]),
        "byte_bucket_bytes": str(stats["byte_bucket_bytes"]),
        "high_nibble_bucket_rows": str(stats["high_nibble_bucket_rows"]),
        "high_nibble_bucket_bytes": str(stats["high_nibble_bucket_bytes"]),
        "low_nibble_bucket_rows": str(stats["low_nibble_bucket_rows"]),
        "low_nibble_bucket_bytes": str(stats["low_nibble_bucket_bytes"]),
        "adjacent_delta_bucket_rows": str(stats["adjacent_delta_bucket_rows"]),
        "adjacent_delta_bucket_bytes": str(stats["adjacent_delta_bucket_bytes"]),
        "repeated_direction_value_groups": str(len(repeated)),
        "repeated_direction_value_bytes": str(sum(int_value(row, "bytes") for row in repeated)),
        "same_offset_groups": str(len(same_offset)),
        "same_offset_bytes": str(sum(int_value(row, "bytes") for row in same_offset)),
        "conflicted_offset_groups": str(len(conflicted)),
        "conflicted_offset_bytes": str(sum(int_value(row, "bytes") for row in conflicted)),
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
    signal_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "targets": rows, "signalRows": signal_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("by_direction_value.csv", output_dir / "by_direction_value.csv"),
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
    <div class="sub">Filters direction-only control rows and checks whether value-side bucket evidence is stable.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Rows</div><div class="value">{summary['target_rows']}</div></div>
    <div class="stat"><div class="label">Bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Value >=75 bytes</div><div class="value warn">{summary['value_ge75_bytes']}</div></div>
    <div class="stat"><div class="label">Offset-conflict bytes</div><div class="value warn">{summary['conflicted_offset_bytes']}</div></div>
    <div class="stat"><div class="label">Promotion-ready bytes</div><div class="value ok">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Direction/value groups</h2>{render_table(signal_rows, SIGNAL_FIELDNAMES, 160)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(rows, TARGET_FIELDNAMES, 180)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_DIRECTION_VALUE_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe value-side signals behind direction-only noisy control rows.")
    parser.add_argument("--mixed-targets", type=Path, default=DEFAULT_MIXED_TARGETS)
    parser.add_argument("--residual-targets", type=Path, default=DEFAULT_RESIDUAL_TARGETS)
    parser.add_argument("--dense-targets", type=Path, default=DEFAULT_DENSE_TARGETS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Direction Value Probe",
    )
    args = parser.parse_args()

    rows = (
        normalize_rows("mixed_control", read_csv(args.mixed_targets))
        + normalize_rows("residual_control", read_csv(args.residual_targets))
        + normalize_rows("dense_control", read_csv(args.dense_targets))
    )
    signal_rows = build_signal_rows(rows)
    summary = build_summary(rows, signal_rows)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, rows)
    write_csv(args.output / "by_direction_value.csv", SIGNAL_FIELDNAMES, signal_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, signal_rows, args.output, args.title), encoding="utf-8")

    print(f"Direction-only rows: {summary['target_rows']}")
    print(f"Value >=75 bytes: {summary['value_ge75_bytes']}")
    print(f"Offset-conflict bytes: {summary['conflicted_offset_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
