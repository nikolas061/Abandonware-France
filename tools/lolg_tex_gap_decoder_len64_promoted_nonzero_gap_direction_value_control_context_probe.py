#!/usr/bin/env python3
"""Probe local control context around direction/value bucket evidence."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
from collections import defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_direction_value_source_value_probe import (
    fixture_key,
    load_fixture_sources,
    read_csv,
)
from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import DEFAULT_FIXTURES
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_control_context_probe"
)
DEFAULT_TARGETS = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_offset_probe/targets.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "fixture_keys",
    "context_radius",
    "direction_signal_groups",
    "repeated_direction_signal_groups",
    "repeated_direction_signal_bytes",
    "direction_context_groups",
    "repeated_direction_context_groups",
    "repeated_direction_context_bytes",
    "value_context_groups",
    "repeated_value_context_groups",
    "repeated_value_context_bytes",
    "combined_context_groups",
    "repeated_combined_context_groups",
    "repeated_combined_context_bytes",
    "op_phase_groups",
    "repeated_op_phase_groups",
    "repeated_op_phase_bytes",
    "stable_delta_groups",
    "stable_delta_bytes",
    "conflicted_delta_groups",
    "conflicted_delta_bytes",
    "payload_signature_groups",
    "repeated_payload_groups",
    "repeated_payload_bytes",
    "best_repeated_context",
    "best_repeated_context_rows",
    "best_repeated_context_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

TARGET_FIELDNAMES = [
    "rank",
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
    "direction_signal",
    "value_signal",
    "direction_offset",
    "value_offset",
    "offset_delta",
    "offset_delta_bucket",
    "op_phase_key",
    "direction_context_key",
    "value_context_key",
    "combined_context_key",
    "payload_signature",
    "payload_head_hex",
    "payload_tail_hex",
    "direction_context_hex",
    "value_context_hex",
    "verdict",
    "issues",
]

GROUP_FIELDNAMES = [
    "group_kind",
    "group_key",
    "rows",
    "bytes",
    "surfaces",
    "direction_value_keys",
    "offset_deltas",
    "stable_delta",
    "payload_signatures",
    "repeated_payload_rows",
    "repeated_payload_bytes",
    "promotion_ready_bytes",
    "verdict",
    "sample_pcx",
    "sample_frontier_id",
    "sample_start",
]


def payload_signature(data: bytes) -> str:
    return f"len={len(data)}|sha1={hashlib.sha1(data).hexdigest()[:16]}"


def split_direction_value_key(key: str) -> tuple[str, str]:
    direction, sep, value = key.partition("|")
    return direction if sep else key, value


def parse_signal(signal: str) -> tuple[str, str]:
    parts = signal.split(":")
    if len(parts) >= 2:
        return parts[0], ":".join(parts[1:])
    return "", signal


def parse_value_signal(signal: str) -> tuple[str, str, str]:
    parts = signal.split(":")
    if len(parts) >= 3:
        return parts[0], parts[1], ":".join(parts[2:])
    if len(parts) == 2:
        return parts[0], parts[1], ""
    return "", "", signal


def offset_delta_bucket(delta: int) -> str:
    magnitude = abs(delta)
    if magnitude == 0:
        return "zero"
    if magnitude <= 4:
        return "tiny"
    if magnitude <= 16:
        return "small"
    if magnitude <= 64:
        return "medium"
    if magnitude <= 512:
        return "large"
    return "huge"


def context_bytes(data: bytes, offset: int, radius: int) -> bytes:
    if not data:
        return b""
    start = max(0, offset - radius)
    end = min(len(data), offset + radius + 1)
    if start >= end:
        return b""
    return data[start:end]


def short_context_hex(data: bytes, offset: int, radius: int) -> str:
    chunk = context_bytes(data, offset, radius)
    return chunk.hex()


def classify(row: dict[str, str]) -> str:
    if not row.get("direction_context_hex") and not row.get("value_context_hex"):
        return "missing_context"
    if row.get("direction_context_key") == row.get("value_context_key"):
        return "shared_context_review"
    if row.get("offset_delta_bucket") == "zero":
        return "zero_delta_context_review"
    return "context_review"


def build_target_rows(
    target_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    radius: int,
) -> tuple[list[dict[str, str]], list[str]]:
    sources, metadata, fixture_issues = load_fixture_sources(fixture_rows)
    output: list[dict[str, str]] = []
    for target in target_rows:
        if target.get("verdict") not in {"exact_bucket_review", "bucket_value_review"}:
            continue
        issues = [issue for issue in target.get("issues", "").split(";") if issue]
        key = fixture_key(target)
        pools = sources.get(key, {})
        expected_all = pools.get("expected", b"")
        start = int_value(target, "start")
        end = int_value(target, "end")
        payload = expected_all[start:end]
        if not payload:
            issues.append("missing_expected_chunk")

        direction_signal, value_signal = split_direction_value_key(target.get("direction_value_key", ""))
        direction_pool, direction_transform = parse_signal(direction_signal)
        value_kind, value_pool, value_transform = parse_value_signal(value_signal)
        direction_offset = int_value(target, "direction_offset")
        value_offset = int_value(target, "best_value_offset")
        delta = int_value(target, "offset_delta")
        direction_source = pools.get(direction_pool, b"")
        value_source = pools.get(value_pool, b"")
        direction_context_hex = short_context_hex(direction_source, direction_offset, radius)
        value_context_hex = short_context_hex(value_source, value_offset, radius)
        if not direction_context_hex:
            issues.append("missing_direction_context")
        if not value_context_hex:
            issues.append("missing_value_context")
        op_index = int_value(target, "op_index")
        start_mod64 = int_value(target, "start_mod64")
        direction_context_key = (
            f"{direction_pool}:{direction_transform}:d{direction_offset % 16}:"
            f"{direction_context_hex}"
        )
        value_context_key = (
            f"{value_kind}:{value_pool}:{value_transform}:v{value_offset % 16}:"
            f"{value_context_hex}"
        )
        op_phase_key = (
            f"{target.get('surface', '')}|op{op_index % 8}|start{start_mod64 % 8}|"
            f"{direction_signal}|{value_kind}:{value_pool}:{value_transform}"
        )
        combined_context_key = (
            f"{target.get('surface', '')}|{offset_delta_bucket(delta)}|"
            f"{direction_context_key}|{value_context_key}"
        )
        fixture = metadata.get(key, {})
        row = {
            "rank": target.get("rank", fixture.get("rank", "")),
            "surface": target.get("surface", ""),
            "archive": target.get("archive", fixture.get("archive", "")),
            "archive_tag": target.get("archive_tag", fixture.get("archive_tag", "")),
            "pcx_name": target.get("pcx_name", ""),
            "frontier_id": target.get("frontier_id", ""),
            "span_index": target.get("span_index", ""),
            "run_index": target.get("run_index", ""),
            "op_index": target.get("op_index", ""),
            "length": str(len(payload)),
            "start": target.get("start", ""),
            "end": target.get("end", ""),
            "direction_value_key": target.get("direction_value_key", ""),
            "direction_signal": direction_signal,
            "value_signal": value_signal,
            "direction_offset": str(direction_offset),
            "value_offset": str(value_offset),
            "offset_delta": target.get("offset_delta", ""),
            "offset_delta_bucket": offset_delta_bucket(delta),
            "op_phase_key": op_phase_key,
            "direction_context_key": direction_context_key,
            "value_context_key": value_context_key,
            "combined_context_key": combined_context_key,
            "payload_signature": payload_signature(payload),
            "payload_head_hex": payload[:16].hex(),
            "payload_tail_hex": payload[-16:].hex(),
            "direction_context_hex": direction_context_hex,
            "value_context_hex": value_context_hex,
            "verdict": "",
            "issues": ";".join(issues),
        }
        row["verdict"] = classify(row)
        output.append(row)
    output.sort(
        key=lambda row: (
            row.get("verdict", ""),
            row.get("surface", ""),
            row.get("offset_delta_bucket", ""),
            -int_value(row, "length"),
            row.get("pcx_name", ""),
            int_value(row, "start"),
        )
    )
    return output, fixture_issues


def build_group_rows(rows: list[dict[str, str]], field: str, group_kind: str) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get(field, "")].append(row)
    output: list[dict[str, str]] = []
    for group_key, group in grouped.items():
        sample = group[0]
        payload_counts: dict[str, int] = defaultdict(int)
        for row in group:
            payload_counts[row.get("payload_signature", "")] += 1
        repeated_payloads = {key for key, count in payload_counts.items() if count > 1}
        repeated_payload_rows = [
            row for row in group if row.get("payload_signature", "") in repeated_payloads
        ]
        deltas = sorted({row.get("offset_delta", "") for row in group})
        stable_delta = len(deltas) == 1
        repeated = len(group) > 1
        output.append(
            {
                "group_kind": group_kind,
                "group_key": group_key,
                "rows": str(len(group)),
                "bytes": str(sum(int_value(row, "length") for row in group)),
                "surfaces": "|".join(sorted({row.get("surface", "") for row in group})),
                "direction_value_keys": "|".join(sorted({row.get("direction_value_key", "") for row in group})),
                "offset_deltas": "|".join(deltas),
                "stable_delta": "1" if stable_delta else "0",
                "payload_signatures": str(len(payload_counts)),
                "repeated_payload_rows": str(len(repeated_payload_rows)),
                "repeated_payload_bytes": str(sum(int_value(row, "length") for row in repeated_payload_rows)),
                "promotion_ready_bytes": "0",
                "verdict": (
                    f"{'repeated' if repeated else 'singleton'}_{group_kind}_"
                    f"{'stable' if stable_delta else 'conflicted'}"
                ),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
                "sample_start": sample.get("start", ""),
            }
        )
    output.sort(
        key=lambda row: (
            -int_value(row, "bytes"),
            -int_value(row, "repeated_payload_bytes"),
            row.get("group_key", ""),
        )
    )
    return output


def repeated_groups(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if int_value(row, "rows") > 1]


def build_summary(
    rows: list[dict[str, str]],
    direction_signal_rows: list[dict[str, str]],
    direction_context_rows: list[dict[str, str]],
    value_context_rows: list[dict[str, str]],
    combined_context_rows: list[dict[str, str]],
    op_phase_rows: list[dict[str, str]],
    payload_rows: list[dict[str, str]],
    radius: int,
) -> dict[str, str]:
    repeated_direction_signal = repeated_groups(direction_signal_rows)
    repeated_direction_context = repeated_groups(direction_context_rows)
    repeated_value_context = repeated_groups(value_context_rows)
    repeated_combined_context = repeated_groups(combined_context_rows)
    repeated_op_phase = repeated_groups(op_phase_rows)
    stable_delta = [row for row in combined_context_rows if int_value(row, "rows") > 1 and row.get("stable_delta") == "1"]
    conflicted_delta = [
        row for row in combined_context_rows if int_value(row, "rows") > 1 and row.get("stable_delta") != "1"
    ]
    repeated_payload = repeated_groups(payload_rows)
    repeated_context_candidates = (
        repeated_combined_context
        + repeated_direction_context
        + repeated_value_context
        + repeated_op_phase
    )
    best_context = max(repeated_context_candidates, key=lambda row: int_value(row, "bytes"), default={})
    return {
        "scope": "total",
        "target_rows": str(len(rows)),
        "target_bytes": str(sum(int_value(row, "length") for row in rows)),
        "fixture_keys": str(len({fixture_key(row) for row in rows})),
        "context_radius": str(radius),
        "direction_signal_groups": str(len(direction_signal_rows)),
        "repeated_direction_signal_groups": str(len(repeated_direction_signal)),
        "repeated_direction_signal_bytes": str(sum(int_value(row, "bytes") for row in repeated_direction_signal)),
        "direction_context_groups": str(len(direction_context_rows)),
        "repeated_direction_context_groups": str(len(repeated_direction_context)),
        "repeated_direction_context_bytes": str(sum(int_value(row, "bytes") for row in repeated_direction_context)),
        "value_context_groups": str(len(value_context_rows)),
        "repeated_value_context_groups": str(len(repeated_value_context)),
        "repeated_value_context_bytes": str(sum(int_value(row, "bytes") for row in repeated_value_context)),
        "combined_context_groups": str(len(combined_context_rows)),
        "repeated_combined_context_groups": str(len(repeated_combined_context)),
        "repeated_combined_context_bytes": str(sum(int_value(row, "bytes") for row in repeated_combined_context)),
        "op_phase_groups": str(len(op_phase_rows)),
        "repeated_op_phase_groups": str(len(repeated_op_phase)),
        "repeated_op_phase_bytes": str(sum(int_value(row, "bytes") for row in repeated_op_phase)),
        "stable_delta_groups": str(len(stable_delta)),
        "stable_delta_bytes": str(sum(int_value(row, "bytes") for row in stable_delta)),
        "conflicted_delta_groups": str(len(conflicted_delta)),
        "conflicted_delta_bytes": str(sum(int_value(row, "bytes") for row in conflicted_delta)),
        "payload_signature_groups": str(len(payload_rows)),
        "repeated_payload_groups": str(len(repeated_payload)),
        "repeated_payload_bytes": str(sum(int_value(row, "bytes") for row in repeated_payload)),
        "best_repeated_context": best_context.get("group_kind", ""),
        "best_repeated_context_rows": best_context.get("rows", "0"),
        "best_repeated_context_bytes": best_context.get("bytes", "0"),
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
    direction_signal_rows: list[dict[str, str]],
    direction_context_rows: list[dict[str, str]],
    value_context_rows: list[dict[str, str]],
    combined_context_rows: list[dict[str, str]],
    op_phase_rows: list[dict[str, str]],
    payload_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "targets": rows,
        "directionSignals": direction_signal_rows,
        "directionContexts": direction_context_rows,
        "valueContexts": value_context_rows,
        "combinedContexts": combined_context_rows,
        "opPhases": op_phase_rows,
        "payloads": payload_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("by_direction_signal.csv", output_dir / "by_direction_signal.csv"),
            ("by_direction_context.csv", output_dir / "by_direction_context.csv"),
            ("by_value_context.csv", output_dir / "by_value_context.csv"),
            ("by_combined_context.csv", output_dir / "by_combined_context.csv"),
            ("by_op_phase.csv", output_dir / "by_op_phase.csv"),
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
a {{ color: var(--accent); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
.links {{ display: flex; flex-wrap: wrap; gap: 10px; }}
.table-wrap {{ overflow: auto; max-height: 58vh; border: 1px solid var(--line); border-radius: 8px; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1200px; }}
th, td {{ padding: 6px 8px; border-bottom: 1px solid #26363b; text-align: left; vertical-align: top; }}
th {{ position: sticky; top: 0; background: #1d292d; z-index: 1; }}
td {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Local control context grouped against direction/value buckets and payload signatures.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Target rows</div><div class="value">{html.escape(summary['target_rows'])}</div></div>
    <div class="stat"><div class="label">Target bytes</div><div class="value">{html.escape(summary['target_bytes'])}</div></div>
    <div class="stat"><div class="label">Repeated combined bytes</div><div class="value">{html.escape(summary['repeated_combined_context_bytes'])}</div></div>
    <div class="stat"><div class="label">Repeated op-phase bytes</div><div class="value">{html.escape(summary['repeated_op_phase_bytes'])}</div></div>
    <div class="stat"><div class="label">Repeated payload bytes</div><div class="value">{html.escape(summary['repeated_payload_bytes'])}</div></div>
    <div class="stat"><div class="label">Promotion-ready bytes</div><div class="value">{html.escape(summary['promotion_ready_bytes'])}</div></div>
  </section>
  <section class="panel">
    <h2>Files</h2>
    <div class="links">{links}</div>
  </section>
  <section class="panel">
    <h2>Combined Context</h2>
    <div class="table-wrap">{render_table(combined_context_rows, GROUP_FIELDNAMES)}</div>
  </section>
  <section class="panel">
    <h2>Op Phase</h2>
    <div class="table-wrap">{render_table(op_phase_rows, GROUP_FIELDNAMES)}</div>
  </section>
  <section class="panel">
    <h2>Payload</h2>
    <div class="table-wrap">{render_table(payload_rows, GROUP_FIELDNAMES)}</div>
  </section>
  <section class="panel">
    <h2>Targets</h2>
    <div class="table-wrap">{render_table(rows, TARGET_FIELDNAMES)}</div>
  </section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_DIRECTION_VALUE_CONTROL_CONTEXT_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--radius", type=int, default=4)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Direction/Value Control Context Probe",
    )
    args = parser.parse_args()

    radius = max(args.radius, 0)
    rows, fixture_issues = build_target_rows(read_csv(args.targets), read_csv(args.fixtures), radius)
    if fixture_issues:
        fixture_issue_text = ";".join(sorted(set(fixture_issues)))
        for row in rows:
            row["issues"] = ";".join(issue for issue in (row.get("issues", ""), fixture_issue_text) if issue)
    direction_signal_rows = build_group_rows(rows, "direction_signal", "direction_signal")
    direction_context_rows = build_group_rows(rows, "direction_context_key", "direction_context")
    value_context_rows = build_group_rows(rows, "value_context_key", "value_context")
    combined_context_rows = build_group_rows(rows, "combined_context_key", "combined_context")
    op_phase_rows = build_group_rows(rows, "op_phase_key", "op_phase")
    payload_rows = build_group_rows(rows, "payload_signature", "payload")
    summary = build_summary(
        rows,
        direction_signal_rows,
        direction_context_rows,
        value_context_rows,
        combined_context_rows,
        op_phase_rows,
        payload_rows,
        radius,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, rows)
    write_csv(args.output / "by_direction_signal.csv", GROUP_FIELDNAMES, direction_signal_rows)
    write_csv(args.output / "by_direction_context.csv", GROUP_FIELDNAMES, direction_context_rows)
    write_csv(args.output / "by_value_context.csv", GROUP_FIELDNAMES, value_context_rows)
    write_csv(args.output / "by_combined_context.csv", GROUP_FIELDNAMES, combined_context_rows)
    write_csv(args.output / "by_op_phase.csv", GROUP_FIELDNAMES, op_phase_rows)
    write_csv(args.output / "by_payload.csv", GROUP_FIELDNAMES, payload_rows)
    html_path = args.output / "index.html"
    html_path.write_text(
        build_html(
            summary,
            rows,
            direction_signal_rows,
            direction_context_rows,
            value_context_rows,
            combined_context_rows,
            op_phase_rows,
            payload_rows,
            args.output,
            args.title,
        )
    )

    print(f"Control context rows: {summary['target_rows']}")
    print(f"Repeated combined context bytes: {summary['repeated_combined_context_bytes']}")
    print(f"Repeated op-phase bytes: {summary['repeated_op_phase_bytes']}")
    print(f"Repeated payload bytes: {summary['repeated_payload_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
