#!/usr/bin/env python3
"""Check mixed-token control signals for reusable context or payloads."""

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


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_token_control_context_probe")
DEFAULT_TARGETS = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_token_control_probe/targets.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "signal_groups",
    "repeated_signal_groups",
    "repeated_signal_bytes",
    "signal_top_groups",
    "repeated_signal_top_groups",
    "repeated_signal_top_bytes",
    "offset_context_groups",
    "repeated_offset_context_groups",
    "repeated_offset_context_bytes",
    "payload_signature_groups",
    "repeated_payload_groups",
    "repeated_payload_bytes",
    "full_byte_ge50_rows",
    "full_byte_ge50_bytes",
    "profile_like_rows",
    "profile_like_bytes",
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
    "top_nibble",
    "control_ref_mod64",
    "best_signal_key",
    "signal_top_key",
    "offset_context_key",
    "best_signal_ratio",
    "best_signal_exact",
    "best_signal_offset",
    "best_signal_offset_mod64",
    "best_byte_ratio",
    "best_byte_exact",
    "payload_signature",
    "head_hex",
    "tail_hex",
    "verdict",
    "issues",
]

SIGNAL_FIELDNAMES = [
    "signal_top_key",
    "rows",
    "bytes",
    "signal_key",
    "top_nibble",
    "ratio_min",
    "ratio_max",
    "ge75_rows",
    "byte_ge50_rows",
    "profile_like_rows",
    "offset_mod64_values",
    "control_ref_mod64_values",
    "payload_signatures",
    "repeated_payload_rows",
    "repeated_payload_bytes",
    "promotion_ready_bytes",
    "verdict",
    "sample_pcx",
    "sample_frontier_id",
]

OFFSET_FIELDNAMES = [
    "offset_context_key",
    "rows",
    "bytes",
    "signal_top_key",
    "payload_signatures",
    "repeated_payload_rows",
    "repeated_payload_bytes",
    "promotion_ready_bytes",
    "verdict",
    "sample_pcx",
    "sample_frontier_id",
]

PAYLOAD_FIELDNAMES = [
    "payload_signature",
    "rows",
    "bytes",
    "signal_top_keys",
    "offset_context_keys",
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


def ratio(values: list[float]) -> tuple[str, str]:
    if not values:
        return "0.000000", "0.000000"
    return f"{min(values):.6f}", f"{max(values):.6f}"


def signal_offset(row: dict[str, str]) -> str:
    kind = row.get("best_signal_kind", "")
    field = {
        "top_nibble": "best_top_nibble_offset",
        "low_nibble": "best_low_nibble_offset",
        "signed_delta": "best_signed_delta_offset",
        "byte": "best_byte_offset",
    }.get(kind, "")
    return row.get(field, "0") if field else "0"


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
        start = int_value(row, "start")
        end = int_value(row, "end")
        payload = expected_all[start:end]
        if not payload:
            issues.append("missing_expected_chunk")
        signal_key = (
            f"{row.get('best_signal_kind', '')}:"
            f"{row.get('best_signal_pool', '')}:"
            f"{row.get('best_signal_transform', '')}"
        )
        offset = signal_offset(row)
        offset_mod64 = str(int(offset or 0) % 64)
        signal_top_key = f"{signal_key}|top={row.get('top_nibble', '')}"
        offset_context_key = (
            f"{signal_top_key}|offset_mod64={offset_mod64}|"
            f"control_ref_mod64={row.get('control_ref_mod64', '')}"
        )
        byte_ratio = float_value(row, "best_byte_ratio")
        profile_like = row.get("verdict", "") in {
            "byte_profile_review",
            "long_profile_review",
            "short_profile_review",
        }
        verdict = "byte_profile_review" if byte_ratio >= 0.50 else row.get("verdict", "")
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
                "top_nibble": row.get("top_nibble", ""),
                "control_ref_mod64": row.get("control_ref_mod64", ""),
                "best_signal_key": signal_key,
                "signal_top_key": signal_top_key,
                "offset_context_key": offset_context_key,
                "best_signal_ratio": row.get("best_signal_ratio", "0"),
                "best_signal_exact": row.get("best_signal_exact", "0"),
                "best_signal_offset": offset,
                "best_signal_offset_mod64": offset_mod64,
                "best_byte_ratio": row.get("best_byte_ratio", "0"),
                "best_byte_exact": row.get("best_byte_exact", "0"),
                "payload_signature": payload_signature(payload) if payload else "",
                "head_hex": payload[:16].hex(),
                "tail_hex": payload[-16:].hex() if payload else "",
                "verdict": verdict if not profile_like else row.get("verdict", ""),
                "issues": ";".join(issues),
            }
        )
    output.sort(
        key=lambda item: (
            item.get("signal_top_key", ""),
            -int_value(item, "length"),
            item.get("pcx_name", ""),
            int_value(item, "start"),
        )
    )
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
                "signal_top_keys": "|".join(sorted({row.get("signal_top_key", "") for row in group_rows})),
                "offset_context_keys": "|".join(sorted({row.get("offset_context_key", "") for row in group_rows})),
                "fixtures": str(len({fixture_key(row) for row in group_rows})),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output.sort(key=lambda item: (-int_value(item, "bytes"), -int_value(item, "rows"), item.get("payload_signature", "")))
    return output


def build_signal_rows(rows: list[dict[str, str]], payload_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    repeated_payloads = {row.get("payload_signature", "") for row in payload_rows if int_value(row, "rows") > 1}
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("signal_top_key", "")].append(row)
    output: list[dict[str, str]] = []
    for key, group_rows in grouped.items():
        sample = group_rows[0]
        repeated_payload_rows = [row for row in group_rows if row.get("payload_signature", "") in repeated_payloads]
        byte_ge50 = [row for row in group_rows if float_value(row, "best_byte_ratio") >= 0.50]
        profile_like = [
            row
            for row in group_rows
            if row.get("verdict") in {"byte_profile_review", "long_profile_review", "short_profile_review"}
        ]
        ratios = [float_value(row, "best_signal_ratio") for row in group_rows]
        ratio_min, ratio_max = ratio(ratios)
        if len(group_rows) < 2:
            verdict = "single_signal_context"
        elif repeated_payload_rows:
            verdict = "payload_repeat_review"
        elif byte_ge50:
            verdict = "byte_profile_review"
        else:
            verdict = "signal_payload_unique_reject"
        output.append(
            {
                "signal_top_key": key,
                "rows": str(len(group_rows)),
                "bytes": str(sum(int_value(row, "length") for row in group_rows)),
                "signal_key": sample.get("best_signal_key", ""),
                "top_nibble": sample.get("top_nibble", ""),
                "ratio_min": ratio_min,
                "ratio_max": ratio_max,
                "ge75_rows": str(sum(1 for row in group_rows if float_value(row, "best_signal_ratio") >= 0.75)),
                "byte_ge50_rows": str(len(byte_ge50)),
                "profile_like_rows": str(len(profile_like)),
                "offset_mod64_values": "|".join(sorted({row.get("best_signal_offset_mod64", "") for row in group_rows})),
                "control_ref_mod64_values": "|".join(sorted({row.get("control_ref_mod64", "") for row in group_rows})),
                "payload_signatures": str(len({row.get("payload_signature", "") for row in group_rows})),
                "repeated_payload_rows": str(len(repeated_payload_rows)),
                "repeated_payload_bytes": str(sum(int_value(row, "length") for row in repeated_payload_rows)),
                "promotion_ready_bytes": "0",
                "verdict": verdict,
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output.sort(key=lambda item: (-int_value(item, "bytes"), -int_value(item, "rows"), item.get("signal_top_key", "")))
    return output


def build_offset_rows(rows: list[dict[str, str]], payload_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    repeated_payloads = {row.get("payload_signature", "") for row in payload_rows if int_value(row, "rows") > 1}
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("offset_context_key", "")].append(row)
    output: list[dict[str, str]] = []
    for key, group_rows in grouped.items():
        sample = group_rows[0]
        repeated_payload_rows = [row for row in group_rows if row.get("payload_signature", "") in repeated_payloads]
        if len(group_rows) < 2:
            verdict = "single_offset_context"
        elif repeated_payload_rows:
            verdict = "offset_payload_repeat_review"
        else:
            verdict = "offset_payload_unique_reject"
        output.append(
            {
                "offset_context_key": key,
                "rows": str(len(group_rows)),
                "bytes": str(sum(int_value(row, "length") for row in group_rows)),
                "signal_top_key": sample.get("signal_top_key", ""),
                "payload_signatures": str(len({row.get("payload_signature", "") for row in group_rows})),
                "repeated_payload_rows": str(len(repeated_payload_rows)),
                "repeated_payload_bytes": str(sum(int_value(row, "length") for row in repeated_payload_rows)),
                "promotion_ready_bytes": "0",
                "verdict": verdict,
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output.sort(key=lambda item: (-int_value(item, "bytes"), -int_value(item, "rows"), item.get("offset_context_key", "")))
    return output


def build_summary(
    rows: list[dict[str, str]],
    signal_rows: list[dict[str, str]],
    offset_rows: list[dict[str, str]],
    payload_rows: list[dict[str, str]],
) -> dict[str, str]:
    repeated_signal = [row for row in signal_rows if int_value(row, "rows") > 1]
    repeated_offset = [row for row in offset_rows if int_value(row, "rows") > 1]
    repeated_payload = [row for row in payload_rows if int_value(row, "rows") > 1]
    signal_keys = {row.get("best_signal_key", "") for row in rows}
    full_byte_ge50 = [row for row in rows if float_value(row, "best_byte_ratio") >= 0.50]
    profile_like = [
        row
        for row in rows
        if row.get("verdict") in {"byte_profile_review", "long_profile_review", "short_profile_review"}
    ]
    return {
        "scope": "total",
        "target_rows": str(len(rows)),
        "target_bytes": str(sum(int_value(row, "length") for row in rows)),
        "signal_groups": str(len(signal_keys)),
        "repeated_signal_groups": str(sum(1 for key in signal_keys if sum(1 for row in rows if row.get("best_signal_key") == key) > 1)),
        "repeated_signal_bytes": str(
            sum(
                int_value(row, "length")
                for row in rows
                if sum(1 for peer in rows if peer.get("best_signal_key") == row.get("best_signal_key")) > 1
            )
        ),
        "signal_top_groups": str(len(signal_rows)),
        "repeated_signal_top_groups": str(len(repeated_signal)),
        "repeated_signal_top_bytes": str(sum(int_value(row, "bytes") for row in repeated_signal)),
        "offset_context_groups": str(len(offset_rows)),
        "repeated_offset_context_groups": str(len(repeated_offset)),
        "repeated_offset_context_bytes": str(sum(int_value(row, "bytes") for row in repeated_offset)),
        "payload_signature_groups": str(len(payload_rows)),
        "repeated_payload_groups": str(len(repeated_payload)),
        "repeated_payload_bytes": str(sum(int_value(row, "bytes") for row in repeated_payload)),
        "full_byte_ge50_rows": str(len(full_byte_ge50)),
        "full_byte_ge50_bytes": str(sum(int_value(row, "length") for row in full_byte_ge50)),
        "profile_like_rows": str(len(profile_like)),
        "profile_like_bytes": str(sum(int_value(row, "length") for row in profile_like)),
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
    signal_rows: list[dict[str, str]],
    offset_rows: list[dict[str, str]],
    payload_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "targets": rows,
        "signalRows": signal_rows,
        "offsetRows": offset_rows,
        "payloadRows": payload_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("by_signal_context.csv", output_dir / "by_signal_context.csv"),
            ("by_offset_context.csv", output_dir / "by_offset_context.csv"),
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
table {{ width: 100%; border-collapse: collapse; min-width: 1800px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Checks mixed-token control signals for repeated context and exact payload reuse.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Rows</div><div class="value">{summary['target_rows']}</div></div>
    <div class="stat"><div class="label">Bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Repeated signal-top bytes</div><div class="value warn">{summary['repeated_signal_top_bytes']}</div></div>
    <div class="stat"><div class="label">Repeated payload bytes</div><div class="value warn">{summary['repeated_payload_bytes']}</div></div>
    <div class="stat"><div class="label">Promotion-ready bytes</div><div class="value ok">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Signal contexts</h2>{render_table(signal_rows, SIGNAL_FIELDNAMES, 160)}</section>
  <section class="panel"><h2>Offset contexts</h2>{render_table(offset_rows, OFFSET_FIELDNAMES, 160)}</section>
  <section class="panel"><h2>Payloads</h2>{render_table(payload_rows, PAYLOAD_FIELDNAMES, 160)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(rows, TARGET_FIELDNAMES, 180)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_MIXED_TOKEN_CONTROL_CONTEXT_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe mixed-token control signal context and payload reuse.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Mixed Token Control Context Probe",
    )
    args = parser.parse_args()

    rows = normalize_rows(read_csv(args.targets), read_fixture_csv(args.fixtures))
    payload_rows = build_payload_rows(rows)
    signal_rows = build_signal_rows(rows, payload_rows)
    offset_rows = build_offset_rows(rows, payload_rows)
    summary = build_summary(rows, signal_rows, offset_rows, payload_rows)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, rows)
    write_csv(args.output / "by_signal_context.csv", SIGNAL_FIELDNAMES, signal_rows)
    write_csv(args.output / "by_offset_context.csv", OFFSET_FIELDNAMES, offset_rows)
    write_csv(args.output / "by_payload.csv", PAYLOAD_FIELDNAMES, payload_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, signal_rows, offset_rows, payload_rows, args.output, args.title))

    print(f"Mixed-token control context rows: {summary['target_rows']}")
    print(f"Repeated signal-top bytes: {summary['repeated_signal_top_bytes']}")
    print(f"Repeated payload bytes: {summary['repeated_payload_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
