#!/usr/bin/env python3
"""Check repeated-nibble jump rows for reusable phase or payload context."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
from collections import defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_nonzero_gap_fill_selector_probe import (
    DEFAULT_FIXTURES,
    fixture_key,
    load_expected_by_fixture,
    read_csv as read_fixture_csv,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_repeated_nibble_context_probe")
DEFAULT_TARGETS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_repeated_nibble_probe/targets.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "band_pair_groups",
    "repeated_band_pair_groups",
    "repeated_band_pair_bytes",
    "phase_context_groups",
    "repeated_phase_context_groups",
    "repeated_phase_context_bytes",
    "payload_signature_groups",
    "repeated_payload_groups",
    "repeated_payload_bytes",
    "pingpong_rows",
    "pingpong_bytes",
    "source_ge50_rows",
    "source_ge50_bytes",
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
    "band_pair_key",
    "band_pair_ratio",
    "band_phase_shape_key",
    "exact_pair_shape_key",
    "pingpong",
    "best_signal_key",
    "best_signal_ratio",
    "payload_signature",
    "head_hex",
    "tail_hex",
    "issues",
]

GROUP_FIELDNAMES = [
    "context_kind",
    "context_key",
    "rows",
    "bytes",
    "payload_signatures",
    "repeated_payload_rows",
    "repeated_payload_bytes",
    "pingpong_rows",
    "source_ge50_rows",
    "start_values",
    "length_values",
    "promotion_ready_bytes",
    "verdict",
    "sample_pcx",
    "sample_frontier_id",
]

PAYLOAD_FIELDNAMES = [
    "payload_signature",
    "rows",
    "bytes",
    "band_pair_keys",
    "phase_context_keys",
    "fixtures",
    "sample_pcx",
    "sample_frontier_id",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def float_value(row: dict[str, str], field: str) -> float:
    try:
        return float(row.get(field, "0") or 0)
    except ValueError:
        return 0.0


def payload_signature(data: bytes) -> str:
    return f"len={len(data)}|sha1={hashlib.sha1(data).hexdigest()[:16]}"


def normalize_rows(
    target_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    expected_by_fixture, fixture_issues = load_expected_by_fixture(fixture_rows)
    output: list[dict[str, str]] = []
    for row in target_rows:
        issues = [issue for issue in row.get("issues", "").split(";") if issue]
        issues.extend(issue for issue in fixture_issues if str(fixture_key(row)) in issue)
        expected_all = expected_by_fixture.get(fixture_key(row), b"")
        payload = expected_all[int_value(row, "start") : int_value(row, "end")]
        if not payload:
            issues.append("missing_expected_chunk")
        signal_key = (
            f"{row.get('best_signal_kind', '')}:"
            f"{row.get('best_signal_pool', '')}:"
            f"{row.get('best_signal_transform', '')}"
        )
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
                "band_pair_key": row.get("band_pair_key", ""),
                "band_pair_ratio": row.get("band_pair_ratio", "0"),
                "band_phase_shape_key": row.get("band_phase_shape_key", ""),
                "exact_pair_shape_key": row.get("exact_pair_shape_key", ""),
                "pingpong": row.get("pingpong", "0"),
                "best_signal_key": signal_key,
                "best_signal_ratio": row.get("best_signal_ratio", "0"),
                "payload_signature": payload_signature(payload) if payload else "",
                "head_hex": payload[:16].hex(),
                "tail_hex": payload[-16:].hex() if payload else "",
                "issues": ";".join(issues),
            }
        )
    output.sort(key=lambda item: (item.get("band_pair_key", ""), item.get("band_phase_shape_key", ""), int_value(item, "start")))
    return output


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
                "band_pair_keys": "|".join(sorted({row.get("band_pair_key", "") for row in group_rows})),
                "phase_context_keys": "|".join(sorted({row.get("band_phase_shape_key", "") for row in group_rows})),
                "fixtures": str(len({fixture_key(row) for row in group_rows})),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output.sort(key=lambda row: (-int_value(row, "bytes"), -int_value(row, "rows"), row.get("payload_signature", "")))
    return output


def build_context_rows(
    rows: list[dict[str, str]],
    payload_rows: list[dict[str, str]],
    field: str,
    kind: str,
) -> list[dict[str, str]]:
    repeated_payloads = {row.get("payload_signature", "") for row in payload_rows if int_value(row, "rows") > 1}
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get(field, "")].append(row)
    output: list[dict[str, str]] = []
    for key, group_rows in grouped.items():
        sample = group_rows[0]
        repeated_payload_rows = [row for row in group_rows if row.get("payload_signature", "") in repeated_payloads]
        source_ge50 = [row for row in group_rows if float_value(row, "best_signal_ratio") >= 0.50]
        if len(group_rows) < 2:
            verdict = "single_context"
        elif repeated_payload_rows:
            verdict = "payload_repeat_review"
        elif source_ge50:
            verdict = "source_signal_context_review"
        else:
            verdict = "payload_unique_context_reject"
        output.append(
            {
                "context_kind": kind,
                "context_key": key,
                "rows": str(len(group_rows)),
                "bytes": str(sum(int_value(row, "length") for row in group_rows)),
                "payload_signatures": str(len({row.get("payload_signature", "") for row in group_rows})),
                "repeated_payload_rows": str(len(repeated_payload_rows)),
                "repeated_payload_bytes": str(sum(int_value(row, "length") for row in repeated_payload_rows)),
                "pingpong_rows": str(sum(1 for row in group_rows if row.get("pingpong") == "1")),
                "source_ge50_rows": str(len(source_ge50)),
                "start_values": "|".join(str(int_value(row, "start")) for row in sorted(group_rows, key=lambda item: int_value(item, "start"))),
                "length_values": "|".join(sorted({row.get("length", "") for row in group_rows})),
                "promotion_ready_bytes": "0",
                "verdict": verdict,
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output.sort(key=lambda row: (-int_value(row, "bytes"), -int_value(row, "rows"), row.get("context_key", "")))
    return output


def build_summary(
    rows: list[dict[str, str]],
    band_rows: list[dict[str, str]],
    phase_rows: list[dict[str, str]],
    payload_rows: list[dict[str, str]],
) -> dict[str, str]:
    repeated_band = [row for row in band_rows if int_value(row, "rows") > 1]
    repeated_phase = [row for row in phase_rows if int_value(row, "rows") > 1]
    repeated_payload = [row for row in payload_rows if int_value(row, "rows") > 1]
    pingpong = [row for row in rows if row.get("pingpong") == "1"]
    source_ge50 = [row for row in rows if float_value(row, "best_signal_ratio") >= 0.50]
    return {
        "scope": "total",
        "target_rows": str(len(rows)),
        "target_bytes": str(sum(int_value(row, "length") for row in rows)),
        "band_pair_groups": str(len(band_rows)),
        "repeated_band_pair_groups": str(len(repeated_band)),
        "repeated_band_pair_bytes": str(sum(int_value(row, "bytes") for row in repeated_band)),
        "phase_context_groups": str(len(phase_rows)),
        "repeated_phase_context_groups": str(len(repeated_phase)),
        "repeated_phase_context_bytes": str(sum(int_value(row, "bytes") for row in repeated_phase)),
        "payload_signature_groups": str(len(payload_rows)),
        "repeated_payload_groups": str(len(repeated_payload)),
        "repeated_payload_bytes": str(sum(int_value(row, "bytes") for row in repeated_payload)),
        "pingpong_rows": str(len(pingpong)),
        "pingpong_bytes": str(sum(int_value(row, "length") for row in pingpong)),
        "source_ge50_rows": str(len(source_ge50)),
        "source_ge50_bytes": str(sum(int_value(row, "length") for row in source_ge50)),
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
    band_rows: list[dict[str, str]],
    phase_rows: list[dict[str, str]],
    payload_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "targets": rows,
        "bandRows": band_rows,
        "phaseRows": phase_rows,
        "payloadRows": payload_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("by_band_context.csv", output_dir / "by_band_context.csv"),
            ("by_phase_context.csv", output_dir / "by_phase_context.csv"),
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
table {{ width: 100%; border-collapse: collapse; min-width: 1550px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Checks repeated-nibble jump rows for reusable phase or payload evidence.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Rows</div><div class="value">{summary['target_rows']}</div></div>
    <div class="stat"><div class="label">Bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Repeated band bytes</div><div class="value warn">{summary['repeated_band_pair_bytes']}</div></div>
    <div class="stat"><div class="label">Repeated payload bytes</div><div class="value warn">{summary['repeated_payload_bytes']}</div></div>
    <div class="stat"><div class="label">Promotion-ready bytes</div><div class="value ok">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Band contexts</h2>{render_table(band_rows, GROUP_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Phase contexts</h2>{render_table(phase_rows, GROUP_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Payloads</h2>{render_table(payload_rows, PAYLOAD_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(rows, TARGET_FIELDNAMES, 120)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_REPEATED_NIBBLE_CONTEXT_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe repeated-nibble context and payload reuse.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Repeated Nibble Context Probe",
    )
    args = parser.parse_args()

    rows = normalize_rows(read_csv(args.targets), read_fixture_csv(args.fixtures))
    payload_rows = build_payload_rows(rows)
    band_rows = build_context_rows(rows, payload_rows, "band_pair_key", "band_pair")
    phase_rows = build_context_rows(rows, payload_rows, "band_phase_shape_key", "band_phase")
    summary = build_summary(rows, band_rows, phase_rows, payload_rows)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, rows)
    write_csv(args.output / "by_band_context.csv", GROUP_FIELDNAMES, band_rows)
    write_csv(args.output / "by_phase_context.csv", GROUP_FIELDNAMES, phase_rows)
    write_csv(args.output / "by_payload.csv", PAYLOAD_FIELDNAMES, payload_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, band_rows, phase_rows, payload_rows, args.output, args.title))

    print(f"Repeated-nibble context rows: {summary['target_rows']}")
    print(f"Repeated band bytes: {summary['repeated_band_pair_bytes']}")
    print(f"Repeated payload bytes: {summary['repeated_payload_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
