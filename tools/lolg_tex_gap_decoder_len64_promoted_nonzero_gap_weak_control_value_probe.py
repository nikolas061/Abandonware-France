#!/usr/bin/env python3
"""Review weak noisy control rows with source payload context."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_weak_control_value_probe")
DEFAULT_GATE_TARGETS = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_control_signal_gate_probe/targets.csv"
)
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
    "candidate_windows",
    "best_signal_groups",
    "best_signal_repeated_groups",
    "best_signal_repeated_bytes",
    "magnitude_rows",
    "magnitude_bytes",
    "magnitude_ge75_rows",
    "magnitude_ge75_bytes",
    "direction_near75_rows",
    "direction_near75_bytes",
    "phase_nonzero_rows",
    "phase_nonzero_bytes",
    "payload_signature_groups",
    "repeated_payload_groups",
    "repeated_payload_bytes",
    "source_join_missing_rows",
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
    "candidate_windows",
    "best_signal_kind",
    "best_signal_key",
    "best_signal_exact",
    "best_signal_ratio",
    "best_direction_key",
    "best_direction_exact",
    "best_direction_ratio",
    "best_phase_key",
    "best_phase_exact",
    "best_phase_ratio",
    "payload_signature",
    "head_hex",
    "tail_hex",
    "verdict",
    "issues",
]

GROUP_FIELDNAMES = [
    "best_signal_key",
    "rows",
    "bytes",
    "surfaces",
    "pcx_values",
    "ratio_min",
    "ratio_max",
    "exact_total",
    "payload_signatures",
    "repeated_payload_rows",
    "repeated_payload_bytes",
    "promotion_ready_bytes",
    "verdict",
    "sample_surface",
    "sample_pcx",
    "sample_frontier_id",
    "sample_start",
]

PAYLOAD_FIELDNAMES = [
    "payload_signature",
    "rows",
    "bytes",
    "best_signal_keys",
    "surfaces",
    "pcx_values",
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


def source_key(surface: str, row: dict[str, str]) -> tuple[str, str, str, str, str, str, str]:
    return (
        surface,
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("span_index", ""),
        row.get("run_index", ""),
        row.get("op_index", ""),
        row.get("start", ""),
    )


def build_source_index(
    mixed_rows: list[dict[str, str]],
    residual_rows: list[dict[str, str]],
    dense_rows: list[dict[str, str]],
) -> dict[tuple[str, str, str, str, str, str, str], dict[str, str]]:
    index: dict[tuple[str, str, str, str, str, str, str], dict[str, str]] = {}
    for surface, rows in (
        ("mixed_control", mixed_rows),
        ("residual_control", residual_rows),
        ("dense_control", dense_rows),
    ):
        for row in rows:
            index[source_key(surface, row)] = row
    return index


def payload_signature(row: dict[str, str]) -> str:
    return f"len={row.get('length', '0')}|head={row.get('head_hex', '')}|tail={row.get('tail_hex', '')}"


def normalize_rows(
    gate_rows: list[dict[str, str]],
    source_index: dict[tuple[str, str, str, str, str, str, str], dict[str, str]],
) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in gate_rows:
        if row.get("verdict") != "weak_control":
            continue
        source = source_index.get(source_key(row.get("surface", ""), row), {})
        head_hex = source.get("head_hex", "")
        tail_hex = source.get("tail_hex", "")
        issues = row.get("issues", "")
        if not source:
            issues = "source_join_missing" if not issues else f"{issues};source_join_missing"
        item = {
            "surface": row.get("surface", ""),
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
            "best_signal_kind": row.get("best_signal_kind", ""),
            "best_signal_key": signal_key(row, "signal"),
            "best_signal_exact": row.get("best_signal_exact", "0"),
            "best_signal_ratio": row.get("best_signal_ratio", "0"),
            "best_direction_key": signal_key(row, "direction"),
            "best_direction_exact": row.get("best_direction_exact", "0"),
            "best_direction_ratio": row.get("best_direction_ratio", "0"),
            "best_phase_key": signal_key(row, "phase"),
            "best_phase_exact": row.get("best_phase_exact", "0"),
            "best_phase_ratio": row.get("best_phase_ratio", "0"),
            "payload_signature": f"missing:{row.get('surface', '')}:{row.get('start', '')}",
            "head_hex": head_hex,
            "tail_hex": tail_hex,
            "verdict": "weak_value_review" if row.get("best_signal_kind") == "magnitude" else "weak_direction_review",
            "issues": issues,
        }
        if head_hex or tail_hex:
            item["payload_signature"] = payload_signature(item)
        output.append(item)
    output.sort(key=lambda item: (item.get("verdict", ""), item.get("best_signal_key", ""), -int_value(item, "length")))
    return output


def row_stats(rows: list[dict[str, str]]) -> Counter[str]:
    stats: Counter[str] = Counter()
    for row in rows:
        length = int_value(row, "length")
        stats["rows"] += 1
        stats["bytes"] += length
        stats["candidate_windows"] += int_value(row, "candidate_windows")
        if row.get("best_signal_kind") == "magnitude":
            stats["magnitude_rows"] += 1
            stats["magnitude_bytes"] += length
        if row.get("best_signal_kind") == "magnitude" and float_value(row, "best_signal_ratio") >= 0.75:
            stats["magnitude_ge75_rows"] += 1
            stats["magnitude_ge75_bytes"] += length
        if float_value(row, "best_direction_ratio") >= 0.70:
            stats["direction_near75_rows"] += 1
            stats["direction_near75_bytes"] += length
        if int_value(row, "best_phase_exact") > 0:
            stats["phase_nonzero_rows"] += 1
            stats["phase_nonzero_bytes"] += length
        if "source_join_missing" in row.get("issues", ""):
            stats["source_join_missing_rows"] += 1
        if row.get("issues"):
            stats["issue_rows"] += 1
    return stats


def ratio_range(rows: list[dict[str, str]]) -> tuple[str, str]:
    ratios = [float_value(row, "best_signal_ratio") for row in rows]
    if not ratios:
        return "0", "0"
    return f"{min(ratios):.6f}", f"{max(ratios):.6f}"


def build_payload_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("payload_signature", "")].append(row)
    output: list[dict[str, str]] = []
    for signature, group_rows in grouped.items():
        sample = group_rows[0]
        output.append(
            {
                "payload_signature": signature,
                "rows": str(len(group_rows)),
                "bytes": str(sum(int_value(row, "length") for row in group_rows)),
                "best_signal_keys": "|".join(sorted({row.get("best_signal_key", "") for row in group_rows})),
                "surfaces": "|".join(sorted({row.get("surface", "") for row in group_rows})),
                "pcx_values": "|".join(sorted({row.get("pcx_name", "") for row in group_rows})),
                "sample_surface": sample.get("surface", ""),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
                "sample_start": sample.get("start", ""),
            }
        )
    output.sort(key=lambda row: (-int_value(row, "bytes"), -int_value(row, "rows"), row.get("payload_signature", "")))
    return output


def build_group_rows(rows: list[dict[str, str]], payload_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    repeated_payloads = {row.get("payload_signature", "") for row in payload_rows if int_value(row, "rows") > 1}
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("best_signal_key", "")].append(row)
    output: list[dict[str, str]] = []
    for key, group_rows in grouped.items():
        stats = row_stats(group_rows)
        repeated_payload_group_rows = [row for row in group_rows if row.get("payload_signature", "") in repeated_payloads]
        ratio_min, ratio_max = ratio_range(group_rows)
        if len(group_rows) < 2:
            verdict = "single_weak_signal"
        elif repeated_payload_group_rows:
            verdict = "weak_payload_repeat_review"
        else:
            verdict = "weak_signal_context_conflict"
        sample = group_rows[0]
        output.append(
            {
                "best_signal_key": key,
                "rows": str(stats["rows"]),
                "bytes": str(stats["bytes"]),
                "surfaces": "|".join(sorted({row.get("surface", "") for row in group_rows})),
                "pcx_values": "|".join(sorted({row.get("pcx_name", "") for row in group_rows})),
                "ratio_min": ratio_min,
                "ratio_max": ratio_max,
                "exact_total": str(sum(int_value(row, "best_signal_exact") for row in group_rows)),
                "payload_signatures": str(len({row.get("payload_signature", "") for row in group_rows})),
                "repeated_payload_rows": str(len(repeated_payload_group_rows)),
                "repeated_payload_bytes": str(sum(int_value(row, "length") for row in repeated_payload_group_rows)),
                "promotion_ready_bytes": "0",
                "verdict": verdict,
                "sample_surface": sample.get("surface", ""),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
                "sample_start": sample.get("start", ""),
            }
        )
    output.sort(key=lambda row: (-int_value(row, "bytes"), -int_value(row, "rows"), row.get("best_signal_key", "")))
    return output


def build_summary(
    rows: list[dict[str, str]],
    group_rows: list[dict[str, str]],
    payload_rows: list[dict[str, str]],
) -> dict[str, str]:
    stats = row_stats(rows)
    repeated_signals = [row for row in group_rows if int_value(row, "rows") > 1]
    repeated_payloads = [row for row in payload_rows if int_value(row, "rows") > 1]
    return {
        "scope": "total",
        "target_rows": str(stats["rows"]),
        "target_bytes": str(stats["bytes"]),
        "surface_count": str(len({row.get("surface", "") for row in rows})),
        "candidate_windows": str(stats["candidate_windows"]),
        "best_signal_groups": str(len(group_rows)),
        "best_signal_repeated_groups": str(len(repeated_signals)),
        "best_signal_repeated_bytes": str(sum(int_value(row, "bytes") for row in repeated_signals)),
        "magnitude_rows": str(stats["magnitude_rows"]),
        "magnitude_bytes": str(stats["magnitude_bytes"]),
        "magnitude_ge75_rows": str(stats["magnitude_ge75_rows"]),
        "magnitude_ge75_bytes": str(stats["magnitude_ge75_bytes"]),
        "direction_near75_rows": str(stats["direction_near75_rows"]),
        "direction_near75_bytes": str(stats["direction_near75_bytes"]),
        "phase_nonzero_rows": str(stats["phase_nonzero_rows"]),
        "phase_nonzero_bytes": str(stats["phase_nonzero_bytes"]),
        "payload_signature_groups": str(len(payload_rows)),
        "repeated_payload_groups": str(len(repeated_payloads)),
        "repeated_payload_bytes": str(sum(int_value(row, "bytes") for row in repeated_payloads)),
        "source_join_missing_rows": str(stats["source_join_missing_rows"]),
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
    group_rows: list[dict[str, str]],
    payload_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "targets": rows, "groupRows": group_rows, "payloadRows": payload_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("by_signal.csv", output_dir / "by_signal.csv"),
            ("by_payload.csv", output_dir / "by_payload.csv"),
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
    <div class="sub">Joins weak control-signal rows back to source payload context.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Rows</div><div class="value">{summary['target_rows']}</div></div>
    <div class="stat"><div class="label">Bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Magnitude >=75 bytes</div><div class="value warn">{summary['magnitude_ge75_bytes']}</div></div>
    <div class="stat"><div class="label">Repeated payload bytes</div><div class="value warn">{summary['repeated_payload_bytes']}</div></div>
    <div class="stat"><div class="label">Promotion-ready bytes</div><div class="value ok">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Signals</h2>{render_table(group_rows, GROUP_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Payloads</h2>{render_table(payload_rows, PAYLOAD_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(rows, TARGET_FIELDNAMES, 120)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_WEAK_CONTROL_VALUE_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe weak noisy control rows with source payload context.")
    parser.add_argument("--gate-targets", type=Path, default=DEFAULT_GATE_TARGETS)
    parser.add_argument("--mixed-targets", type=Path, default=DEFAULT_MIXED_TARGETS)
    parser.add_argument("--residual-targets", type=Path, default=DEFAULT_RESIDUAL_TARGETS)
    parser.add_argument("--dense-targets", type=Path, default=DEFAULT_DENSE_TARGETS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Weak Control Value Probe",
    )
    args = parser.parse_args()

    source_index = build_source_index(
        read_csv(args.mixed_targets),
        read_csv(args.residual_targets),
        read_csv(args.dense_targets),
    )
    rows = normalize_rows(read_csv(args.gate_targets), source_index)
    payload_rows = build_payload_rows(rows)
    group_rows = build_group_rows(rows, payload_rows)
    summary = build_summary(rows, group_rows, payload_rows)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, rows)
    write_csv(args.output / "by_signal.csv", GROUP_FIELDNAMES, group_rows)
    write_csv(args.output / "by_payload.csv", PAYLOAD_FIELDNAMES, payload_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, group_rows, payload_rows, args.output, args.title), encoding="utf-8")

    print(f"Weak-control rows: {summary['target_rows']}")
    print(f"Magnitude >=75 bytes: {summary['magnitude_ge75_bytes']}")
    print(f"Repeated payload bytes: {summary['repeated_payload_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
