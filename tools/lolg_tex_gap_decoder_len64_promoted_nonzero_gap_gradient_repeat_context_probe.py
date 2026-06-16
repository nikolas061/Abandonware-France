#!/usr/bin/env python3
"""Review repeated gradient shapes for exact payload and copy-distance context."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import (
    DEFAULT_FIXTURES,
    fixture_key,
    load_expected_by_fixture,
    read_csv as read_fixture_csv,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_repeat_context_probe")
DEFAULT_TARGETS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_probe/targets.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "shape_context_groups",
    "repeated_shape_context_groups",
    "repeated_shape_context_bytes",
    "payload_signature_groups",
    "repeated_payload_groups",
    "repeated_payload_bytes",
    "copy_distance_320_groups",
    "copy_distance_320_rows",
    "copy_distance_320_bytes",
    "copy_unlock_bytes",
    "control_ref_distinct_groups",
    "promotion_ready_bytes",
    "issue_rows",
]

TARGET_FIELDNAMES = [
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
    "control_ref_mod64",
    "gradient_class",
    "shape_context_key",
    "payload_signature",
    "copy_source_start",
    "copy_distance",
    "copy_unlock",
    "head_hex",
    "tail_hex",
    "issues",
]

GROUP_FIELDNAMES = [
    "shape_context_key",
    "rows",
    "bytes",
    "payload_signatures",
    "repeated_payload_rows",
    "repeated_payload_bytes",
    "start_values",
    "start_deltas",
    "start_mod64_values",
    "control_ref_mod64_values",
    "copy_distance_320",
    "copy_unlock_bytes",
    "promotion_ready_bytes",
    "verdict",
    "sample_pcx",
    "sample_frontier_id",
]

PAYLOAD_FIELDNAMES = [
    "payload_signature",
    "rows",
    "bytes",
    "shape_context_keys",
    "start_values",
    "start_deltas",
    "copy_distance_320",
    "copy_unlock_bytes",
    "sample_pcx",
    "sample_frontier_id",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def payload_signature(data: bytes) -> str:
    return f"len={len(data)}|sha1={hashlib.sha1(data).hexdigest()[:16]}"


def shape_context_key(row: dict[str, str]) -> str:
    return (
        f"class={row.get('gradient_class', '')}|len={row.get('length', '')}|"
        f"hist={row.get('delta_histogram_key', '')}|runs={row.get('delta_run_shape_key', '')}"
    )


def start_deltas(rows: list[dict[str, str]]) -> list[int]:
    starts = sorted(int_value(row, "start") for row in rows)
    return [right - left for left, right in zip(starts, starts[1:])]


def normalize_rows(
    target_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    histogram_counts = Counter(row.get("delta_histogram_key", "") for row in target_rows)
    run_counts = Counter(row.get("delta_run_shape_key", "") for row in target_rows)
    expected_by_fixture, fixture_issues = load_expected_by_fixture(fixture_rows)
    candidates = [
        row
        for row in target_rows
        if histogram_counts[row.get("delta_histogram_key", "")] > 1
        or run_counts[row.get("delta_run_shape_key", "")] > 1
    ]
    by_shape: dict[str, list[dict[str, str]]] = defaultdict(list)
    payloads: dict[int, bytes] = {}
    for index, row in enumerate(candidates):
        expected_all = expected_by_fixture.get(fixture_key(row), b"")
        payloads[index] = expected_all[int_value(row, "start") : int_value(row, "end")]
        by_shape[shape_context_key(row)].append({**row, "_candidate_index": str(index)})

    copy_sources: dict[int, tuple[str, str]] = {}
    for group_rows in by_shape.values():
        sorted_rows = sorted(group_rows, key=lambda row: int_value(row, "start"))
        for previous, current in zip(sorted_rows, sorted_rows[1:]):
            previous_index = int_value(previous, "_candidate_index")
            current_index = int_value(current, "_candidate_index")
            distance = int_value(current, "start") - int_value(previous, "start")
            if distance == 320 and payloads.get(previous_index) == payloads.get(current_index):
                copy_sources[current_index] = (previous.get("start", ""), str(distance))

    output: list[dict[str, str]] = []
    for index, row in enumerate(candidates):
        issues = [issue for issue in row.get("issues", "").split(";") if issue]
        issues.extend(issue for issue in fixture_issues if str(fixture_key(row)) in issue)
        payload = payloads[index]
        if not payload:
            issues.append("missing_expected_chunk")
        source_start, distance = copy_sources.get(index, ("", ""))
        output.append(
            {
                "archive": row.get("archive", ""),
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "span_index": row.get("span_index", ""),
                "run_index": row.get("run_index", ""),
                "op_index": row.get("op_index", ""),
                "length": row.get("length", str(len(payload))),
                "start": row.get("start", ""),
                "end": row.get("end", ""),
                "start_mod64": row.get("start_mod64", ""),
                "control_ref_mod64": row.get("control_ref_mod64", ""),
                "gradient_class": row.get("gradient_class", ""),
                "shape_context_key": shape_context_key(row),
                "payload_signature": payload_signature(payload) if payload else "",
                "copy_source_start": source_start,
                "copy_distance": distance,
                "copy_unlock": "1" if source_start else "0",
                "head_hex": payload[:16].hex(),
                "tail_hex": payload[-16:].hex() if payload else "",
                "issues": ";".join(issues),
            }
        )
    output.sort(key=lambda row: (row.get("shape_context_key", ""), int_value(row, "start")))
    return output


def build_payload_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("payload_signature", "")].append(row)
    output: list[dict[str, str]] = []
    for signature, group_rows in grouped.items():
        sorted_rows = sorted(group_rows, key=lambda row: int_value(row, "start"))
        deltas = start_deltas(sorted_rows)
        sample = sorted_rows[0]
        copy_unlock = [row for row in sorted_rows if row.get("copy_unlock") == "1"]
        output.append(
            {
                "payload_signature": signature,
                "rows": str(len(sorted_rows)),
                "bytes": str(sum(int_value(row, "length") for row in sorted_rows)),
                "shape_context_keys": "|".join(sorted({row.get("shape_context_key", "") for row in sorted_rows})),
                "start_values": "|".join(str(int_value(row, "start")) for row in sorted_rows),
                "start_deltas": "|".join(str(delta) for delta in deltas),
                "copy_distance_320": "1" if deltas and all(delta == 320 for delta in deltas) else "0",
                "copy_unlock_bytes": str(sum(int_value(row, "length") for row in copy_unlock)),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output.sort(key=lambda row: (-int_value(row, "bytes"), -int_value(row, "rows"), row.get("payload_signature", "")))
    return output


def build_group_rows(rows: list[dict[str, str]], payload_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    repeated_payloads = {row.get("payload_signature", "") for row in payload_rows if int_value(row, "rows") > 1}
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("shape_context_key", "")].append(row)
    output: list[dict[str, str]] = []
    for key, group_rows in grouped.items():
        sorted_rows = sorted(group_rows, key=lambda row: int_value(row, "start"))
        deltas = start_deltas(sorted_rows)
        repeated_payload_rows = [row for row in sorted_rows if row.get("payload_signature", "") in repeated_payloads]
        copy_unlock = [row for row in sorted_rows if row.get("copy_unlock") == "1"]
        copy_distance_320 = bool(deltas) and all(delta == 320 for delta in deltas)
        if not copy_distance_320:
            verdict = "repeated_gradient_context_conflict"
        elif copy_unlock:
            verdict = "copy_distance_320_review"
        else:
            verdict = "repeated_gradient_payload_review"
        sample = sorted_rows[0]
        output.append(
            {
                "shape_context_key": key,
                "rows": str(len(sorted_rows)),
                "bytes": str(sum(int_value(row, "length") for row in sorted_rows)),
                "payload_signatures": str(len({row.get("payload_signature", "") for row in sorted_rows})),
                "repeated_payload_rows": str(len(repeated_payload_rows)),
                "repeated_payload_bytes": str(sum(int_value(row, "length") for row in repeated_payload_rows)),
                "start_values": "|".join(str(int_value(row, "start")) for row in sorted_rows),
                "start_deltas": "|".join(str(delta) for delta in deltas),
                "start_mod64_values": "|".join(sorted({row.get("start_mod64", "") for row in sorted_rows})),
                "control_ref_mod64_values": "|".join(sorted({row.get("control_ref_mod64", "") for row in sorted_rows})),
                "copy_distance_320": "1" if copy_distance_320 else "0",
                "copy_unlock_bytes": str(sum(int_value(row, "length") for row in copy_unlock)),
                "promotion_ready_bytes": "0",
                "verdict": verdict,
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output.sort(key=lambda row: (-int_value(row, "bytes"), -int_value(row, "rows"), row.get("shape_context_key", "")))
    return output


def build_summary(
    rows: list[dict[str, str]],
    group_rows: list[dict[str, str]],
    payload_rows: list[dict[str, str]],
) -> dict[str, str]:
    repeated_shape = [row for row in group_rows if int_value(row, "rows") > 1]
    repeated_payloads = [row for row in payload_rows if int_value(row, "rows") > 1]
    copy_320 = [row for row in group_rows if row.get("copy_distance_320") == "1"]
    return {
        "scope": "total",
        "target_rows": str(len(rows)),
        "target_bytes": str(sum(int_value(row, "length") for row in rows)),
        "shape_context_groups": str(len(group_rows)),
        "repeated_shape_context_groups": str(len(repeated_shape)),
        "repeated_shape_context_bytes": str(sum(int_value(row, "bytes") for row in repeated_shape)),
        "payload_signature_groups": str(len(payload_rows)),
        "repeated_payload_groups": str(len(repeated_payloads)),
        "repeated_payload_bytes": str(sum(int_value(row, "bytes") for row in repeated_payloads)),
        "copy_distance_320_groups": str(len(copy_320)),
        "copy_distance_320_rows": str(sum(int_value(row, "rows") for row in copy_320)),
        "copy_distance_320_bytes": str(sum(int_value(row, "bytes") for row in copy_320)),
        "copy_unlock_bytes": str(sum(int_value(row, "copy_unlock_bytes") for row in group_rows)),
        "control_ref_distinct_groups": str(
            sum(1 for row in group_rows if len(row.get("control_ref_mod64_values", "").split("|")) > 1)
        ),
        "promotion_ready_bytes": "0",
        "issue_rows": str(sum(1 for row in rows if row.get("issues"))),
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
            ("by_shape_context.csv", output_dir / "by_shape_context.csv"),
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
    <div class="sub">Checks repeated gradient shapes for exact payload reuse and copy-distance context.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Rows</div><div class="value">{summary['target_rows']}</div></div>
    <div class="stat"><div class="label">Bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Repeated payload bytes</div><div class="value warn">{summary['repeated_payload_bytes']}</div></div>
    <div class="stat"><div class="label">Copy-unlock bytes</div><div class="value warn">{summary['copy_unlock_bytes']}</div></div>
    <div class="stat"><div class="label">Promotion-ready bytes</div><div class="value ok">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Shape contexts</h2>{render_table(group_rows, GROUP_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Payloads</h2>{render_table(payload_rows, PAYLOAD_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(rows, TARGET_FIELDNAMES, 120)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_GRADIENT_REPEAT_CONTEXT_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe repeated gradient shape payload and context reuse.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Gradient Repeat Context Probe",
    )
    args = parser.parse_args()

    rows = normalize_rows(read_csv(args.targets), read_fixture_csv(args.fixtures))
    payload_rows = build_payload_rows(rows)
    group_rows = build_group_rows(rows, payload_rows)
    summary = build_summary(rows, group_rows, payload_rows)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, rows)
    write_csv(args.output / "by_shape_context.csv", GROUP_FIELDNAMES, group_rows)
    write_csv(args.output / "by_payload.csv", PAYLOAD_FIELDNAMES, payload_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, group_rows, payload_rows, args.output, args.title))

    print(f"Gradient repeat rows: {summary['target_rows']}")
    print(f"Repeated payload bytes: {summary['repeated_payload_bytes']}")
    print(f"Copy-unlock bytes: {summary['copy_unlock_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
