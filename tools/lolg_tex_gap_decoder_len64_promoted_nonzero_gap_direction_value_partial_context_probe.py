#!/usr/bin/env python3
"""Review partial value-bucket direction rows for reusable context or payloads."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_partial_context_probe")
DEFAULT_TARGETS = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_offset_probe/targets.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "direction_value_groups",
    "repeated_key_groups",
    "repeated_key_bytes",
    "ratio_ge90_rows",
    "ratio_ge90_bytes",
    "ratio_ge80_rows",
    "ratio_ge80_bytes",
    "best_value_exact_total",
    "same_delta_groups",
    "same_delta_bytes",
    "conflicted_delta_groups",
    "conflicted_delta_bytes",
    "payload_signature_groups",
    "repeated_payload_groups",
    "repeated_payload_bytes",
    "singleton_rows",
    "singleton_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

GROUP_FIELDNAMES = [
    "direction_value_key",
    "rows",
    "bytes",
    "surfaces",
    "pcx_values",
    "ratio_min",
    "ratio_max",
    "best_value_exact_total",
    "offset_deltas",
    "start_mod64_values",
    "payload_signatures",
    "same_delta",
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
    "direction_value_keys",
    "surfaces",
    "pcx_values",
    "ratio_min",
    "ratio_max",
    "sample_surface",
    "sample_pcx",
    "sample_frontier_id",
    "sample_start",
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
    "length",
    "start",
    "end",
    "direction_value_key",
    "offset_delta",
    "start_mod64",
    "payload_signature",
    "best_value_ratio",
    "best_value_exact",
    "head_hex",
    "tail_hex",
    "issues",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def float_value(row: dict[str, str], field: str) -> float:
    try:
        return float(row.get(field, "0") or 0)
    except ValueError:
        return 0.0


def payload_signature(row: dict[str, str]) -> str:
    return f"len={row.get('length', '0')}|head={row.get('head_hex', '')}|tail={row.get('tail_hex', '')}"


def normalize_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in rows:
        ratio = float_value(row, "best_value_ratio")
        if ratio < 0.75 or ratio >= 1.0:
            continue
        output.append(
            {
                "surface": row.get("surface", ""),
                "archive": row.get("archive", ""),
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "span_index": row.get("span_index", ""),
                "run_index": row.get("run_index", ""),
                "op_index": row.get("op_index", ""),
                "length": row.get("length", "0"),
                "start": row.get("start", ""),
                "end": row.get("end", ""),
                "direction_value_key": row.get("direction_value_key", ""),
                "offset_delta": row.get("offset_delta", ""),
                "start_mod64": row.get("start_mod64", ""),
                "payload_signature": payload_signature(row),
                "best_value_ratio": row.get("best_value_ratio", "0"),
                "best_value_exact": row.get("best_value_exact", "0"),
                "head_hex": row.get("head_hex", ""),
                "tail_hex": row.get("tail_hex", ""),
                "issues": row.get("issues", ""),
            }
        )
    output.sort(
        key=lambda row: (
            row.get("direction_value_key", ""),
            row.get("payload_signature", ""),
            row.get("offset_delta", ""),
            int_value(row, "start"),
        )
    )
    return output


def row_stats(rows: list[dict[str, str]]) -> Counter[str]:
    stats: Counter[str] = Counter()
    for row in rows:
        length = int_value(row, "length")
        ratio = float_value(row, "best_value_ratio")
        stats["rows"] += 1
        stats["bytes"] += length
        stats["best_value_exact_total"] += int_value(row, "best_value_exact")
        if ratio >= 0.90:
            stats["ratio_ge90_rows"] += 1
            stats["ratio_ge90_bytes"] += length
        if ratio >= 0.80:
            stats["ratio_ge80_rows"] += 1
            stats["ratio_ge80_bytes"] += length
        if row.get("issues"):
            stats["issue_rows"] += 1
    return stats


def ratio_range(rows: list[dict[str, str]]) -> tuple[str, str]:
    ratios = [float_value(row, "best_value_ratio") for row in rows]
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
        ratio_min, ratio_max = ratio_range(group_rows)
        output.append(
            {
                "payload_signature": signature,
                "rows": str(len(group_rows)),
                "bytes": str(sum(int_value(row, "length") for row in group_rows)),
                "direction_value_keys": "|".join(sorted({row.get("direction_value_key", "") for row in group_rows})),
                "surfaces": "|".join(sorted({row.get("surface", "") for row in group_rows})),
                "pcx_values": "|".join(sorted({row.get("pcx_name", "") for row in group_rows})),
                "ratio_min": ratio_min,
                "ratio_max": ratio_max,
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
        grouped[row.get("direction_value_key", "")].append(row)
    output: list[dict[str, str]] = []
    for key, group_rows in grouped.items():
        stats = row_stats(group_rows)
        payloads = sorted({row.get("payload_signature", "") for row in group_rows})
        repeated_payload_group_rows = [row for row in group_rows if row.get("payload_signature", "") in repeated_payloads]
        offset_deltas = sorted({row.get("offset_delta", "") for row in group_rows})
        same_delta = len(offset_deltas) == 1
        ratio_min, ratio_max = ratio_range(group_rows)
        if len(group_rows) < 2:
            verdict = "single_partial_context"
        elif repeated_payload_group_rows:
            verdict = "partial_payload_repeat_review"
        elif same_delta:
            verdict = "same_delta_partial_review"
        else:
            verdict = "partial_context_conflict_reject"
        sample = group_rows[0]
        output.append(
            {
                "direction_value_key": key,
                "rows": str(stats["rows"]),
                "bytes": str(stats["bytes"]),
                "surfaces": "|".join(sorted({row.get("surface", "") for row in group_rows})),
                "pcx_values": "|".join(sorted({row.get("pcx_name", "") for row in group_rows})),
                "ratio_min": ratio_min,
                "ratio_max": ratio_max,
                "best_value_exact_total": str(stats["best_value_exact_total"]),
                "offset_deltas": "|".join(offset_deltas),
                "start_mod64_values": "|".join(sorted({row.get("start_mod64", "") for row in group_rows})),
                "payload_signatures": str(len(payloads)),
                "same_delta": "1" if same_delta else "0",
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
    output.sort(key=lambda row: (-int_value(row, "bytes"), -int_value(row, "rows"), row.get("direction_value_key", "")))
    return output


def build_summary(
    rows: list[dict[str, str]],
    group_rows: list[dict[str, str]],
    payload_rows: list[dict[str, str]],
) -> dict[str, str]:
    stats = row_stats(rows)
    repeated = [row for row in group_rows if int_value(row, "rows") > 1]
    same_delta = [row for row in repeated if row.get("same_delta") == "1"]
    conflicted = [row for row in repeated if row.get("same_delta") != "1"]
    repeated_payloads = [row for row in payload_rows if int_value(row, "rows") > 1]
    singletons = [row for row in group_rows if int_value(row, "rows") == 1]
    return {
        "scope": "total",
        "target_rows": str(stats["rows"]),
        "target_bytes": str(stats["bytes"]),
        "direction_value_groups": str(len(group_rows)),
        "repeated_key_groups": str(len(repeated)),
        "repeated_key_bytes": str(sum(int_value(row, "bytes") for row in repeated)),
        "ratio_ge90_rows": str(stats["ratio_ge90_rows"]),
        "ratio_ge90_bytes": str(stats["ratio_ge90_bytes"]),
        "ratio_ge80_rows": str(stats["ratio_ge80_rows"]),
        "ratio_ge80_bytes": str(stats["ratio_ge80_bytes"]),
        "best_value_exact_total": str(stats["best_value_exact_total"]),
        "same_delta_groups": str(len(same_delta)),
        "same_delta_bytes": str(sum(int_value(row, "bytes") for row in same_delta)),
        "conflicted_delta_groups": str(len(conflicted)),
        "conflicted_delta_bytes": str(sum(int_value(row, "bytes") for row in conflicted)),
        "payload_signature_groups": str(len(payload_rows)),
        "repeated_payload_groups": str(len(repeated_payloads)),
        "repeated_payload_bytes": str(sum(int_value(row, "bytes") for row in repeated_payloads)),
        "singleton_rows": str(sum(int_value(row, "rows") for row in singletons)),
        "singleton_bytes": str(sum(int_value(row, "bytes") for row in singletons)),
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
            ("by_partial_context.csv", output_dir / "by_partial_context.csv"),
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
    <div class="sub">Checks partial value-bucket rows for reusable payload or context evidence.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Rows</div><div class="value">{summary['target_rows']}</div></div>
    <div class="stat"><div class="label">Bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Ratio >=90 bytes</div><div class="value warn">{summary['ratio_ge90_bytes']}</div></div>
    <div class="stat"><div class="label">Repeated payload bytes</div><div class="value warn">{summary['repeated_payload_bytes']}</div></div>
    <div class="stat"><div class="label">Promotion-ready bytes</div><div class="value ok">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Partial context groups</h2>{render_table(group_rows, GROUP_FIELDNAMES, 160)}</section>
  <section class="panel"><h2>Payloads</h2>{render_table(payload_rows, PAYLOAD_FIELDNAMES, 160)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(rows, TARGET_FIELDNAMES, 180)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_DIRECTION_VALUE_PARTIAL_CONTEXT_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe partial value-bucket direction rows.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Direction Value Partial Context Probe",
    )
    args = parser.parse_args()

    rows = normalize_rows(read_csv(args.targets))
    payload_rows = build_payload_rows(rows)
    group_rows = build_group_rows(rows, payload_rows)
    summary = build_summary(rows, group_rows, payload_rows)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, rows)
    write_csv(args.output / "by_partial_context.csv", GROUP_FIELDNAMES, group_rows)
    write_csv(args.output / "by_payload.csv", PAYLOAD_FIELDNAMES, payload_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, group_rows, payload_rows, args.output, args.title), encoding="utf-8")

    print(f"Partial direction/value rows: {summary['target_rows']}")
    print(f"Partial direction/value bytes: {summary['target_bytes']}")
    print(f"Repeated key bytes: {summary['repeated_key_bytes']}")
    print(f"Repeated payload bytes: {summary['repeated_payload_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
