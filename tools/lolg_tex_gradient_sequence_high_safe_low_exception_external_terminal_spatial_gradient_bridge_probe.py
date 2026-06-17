#!/usr/bin/env python3
"""Probe spatial gradient bridge signatures for external terminal gaps."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv


DEFAULT_TARGETS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector/targets.csv"
)
DEFAULT_SMALL_GAPS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector/small_gaps.csv"
)
DEFAULT_FIXTURES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_second_promoted_replay/fixtures.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_gradient_bridge"
)

DEFAULT_MAX_DISTANCE = 16
DEFAULT_MAX_DELTA = 4

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_spans",
    "target_bytes",
    "known_reference_rows",
    "target_anchor_supported_spans",
    "target_anchor_supported_bytes",
    "target_signature_seen_spans",
    "target_signature_seen_bytes",
    "unique_target_signatures",
    "known_signature_rows",
    "repeated_known_signatures",
    "best_target_span",
    "best_target_signature",
    "best_target_known_signature_rows",
    "next_probe",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

TARGET_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_key",
    "span_start",
    "span_end",
    "span_length",
    "expected_hex",
    "gap_role",
    "best_anchor_side",
    "best_anchor_rel",
    "best_anchor_byte",
    "best_delta_signature",
    "best_known_signature_rows",
    "best_known_signature_spans",
    "anchor_candidates",
    "verdict",
    "issues",
]

SIGNATURE_FIELDNAMES = [
    "rank",
    "scope",
    "span_key",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_start",
    "span_end",
    "span_length",
    "anchor_side",
    "anchor_rel",
    "anchor_offset",
    "anchor_byte",
    "delta_signature",
    "known_signature_rows",
    "known_signature_spans",
    "expected_hex",
]

KNOWN_SIGNATURE_FIELDNAMES = [
    "rank",
    "anchor_side",
    "delta_signature",
    "rows",
    "spans",
    "bytes",
    "span_keys",
    "sample_span",
    "verdict",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def int_value(row: dict[str, str] | dict[str, object], field: str, default: int = 0) -> int:
    try:
        return int(str(row.get(field, "")))
    except (TypeError, ValueError):
        return default


def row_key(row: dict[str, str] | dict[str, object]) -> tuple[str, str, str]:
    return str(row.get("archive", "")), str(row.get("pcx_name", "")), str(row.get("frontier_id", ""))


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def signed_delta(target: int, anchor: int) -> int:
    return ((target - anchor + 128) & 0xFF) - 128


def signature_key(row: dict[str, str]) -> tuple[str, str]:
    return row.get("anchor_side", ""), row.get("delta_signature", "")


def load_buffers(fixture_rows: list[dict[str, str]]) -> tuple[dict[tuple[str, str, str], tuple[bytes, bytes]], list[str]]:
    buffers: dict[tuple[str, str, str], tuple[bytes, bytes]] = {}
    issues: list[str] = []
    for row in fixture_rows:
        local_issues: list[str] = []
        decoded = load_bytes(row.get("decoded_path", ""), local_issues, "decoded")
        known_mask = load_bytes(row.get("known_mask_path", ""), local_issues, "known_mask")
        if decoded and known_mask and len(decoded) != len(known_mask):
            local_issues.append("decoded_known_mask_size_mismatch")
        if local_issues:
            issues.extend(f"{'|'.join(row_key(row))}:{issue}" for issue in local_issues)
        if decoded and known_mask:
            buffers[row_key(row)] = (decoded, known_mask)
    return buffers, issues


def anchor_signatures(
    row: dict[str, str],
    decoded: bytes,
    known_mask: bytes,
    *,
    max_distance: int,
    max_delta: int,
) -> list[dict[str, str]]:
    start = int_value(row, "expected_start", int_value(row, "span_start"))
    end = int_value(row, "expected_end", int_value(row, "span_end"))
    expected = bytes.fromhex(row.get("expected_hex", ""))
    if end > min(len(decoded), len(known_mask)) or len(expected) != end - start:
        return []
    rows: list[dict[str, str]] = []
    for anchor_offset in range(max(0, start - max_distance), min(len(decoded), end + max_distance)):
        if start <= anchor_offset < end:
            continue
        if not known_mask[anchor_offset]:
            continue
        anchor_value = decoded[anchor_offset]
        deltas: list[int] = []
        for value in expected:
            delta = signed_delta(value, anchor_value)
            if abs(delta) > max_delta:
                break
            deltas.append(delta)
        if len(deltas) != len(expected):
            continue
        side = "left" if anchor_offset < start else "right"
        rows.append(
            {
                "rank": "",
                "scope": "",
                "span_key": row.get("span_key", ""),
                "archive": row.get("archive", ""),
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "span_start": str(start),
                "span_end": str(end),
                "span_length": str(len(expected)),
                "anchor_side": side,
                "anchor_rel": str(anchor_offset - start),
                "anchor_offset": str(anchor_offset),
                "anchor_byte": f"{anchor_value:02x}",
                "delta_signature": ",".join(str(delta) for delta in deltas),
                "known_signature_rows": "0",
                "known_signature_spans": "0",
                "expected_hex": expected.hex(),
            }
        )
    return rows


def build(
    target_rows_in: list[dict[str, str]],
    small_gap_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    *,
    max_distance: int,
    max_delta: int,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    buffers, buffer_issues = load_buffers(fixture_rows)
    target_keys = {row.get("span_key", "") for row in target_rows_in}
    target_lookup = {row.get("span_key", ""): row for row in small_gap_rows if row.get("span_key", "") in target_keys}
    target_rows = [target_lookup.get(row.get("span_key", ""), row) for row in target_rows_in]
    known_rows = [row for row in small_gap_rows if row.get("known_in_replay") == "1"]

    known_signature_rows: list[dict[str, str]] = []
    signature_spans: dict[tuple[str, str], set[str]] = defaultdict(set)
    signature_bytes: Counter[tuple[str, str]] = Counter()
    for row in known_rows:
        buffer = buffers.get(row_key(row))
        if buffer is None:
            continue
        decoded, known_mask = buffer
        for sig in anchor_signatures(row, decoded, known_mask, max_distance=max_distance, max_delta=max_delta):
            sig["scope"] = "known"
            known_signature_rows.append(sig)
            key = signature_key(sig)
            signature_spans[key].add(sig.get("span_key", ""))
            signature_bytes[key] += int_value(sig, "span_length")

    known_counts = Counter(signature_key(row) for row in known_signature_rows)

    known_summary_rows: list[dict[str, str]] = []
    for key, count in known_counts.items():
        side, delta_signature = key
        spans = sorted(signature_spans[key])
        known_summary_rows.append(
            {
                "rank": "",
                "anchor_side": side,
                "delta_signature": delta_signature,
                "rows": str(count),
                "spans": str(len(spans)),
                "bytes": str(signature_bytes[key]),
                "span_keys": ";".join(spans[:12]),
                "sample_span": spans[0] if spans else "",
                "verdict": "repeated_known_signature" if len(spans) > 1 else "single_known_signature",
            }
        )
    known_summary_rows.sort(
        key=lambda row: (
            -int_value(row, "spans"),
            -int_value(row, "rows"),
            -int_value(row, "bytes"),
            row.get("anchor_side", ""),
            row.get("delta_signature", ""),
        )
    )
    for index, row in enumerate(known_summary_rows, start=1):
        row["rank"] = str(index)

    signature_rows: list[dict[str, str]] = []
    target_output_rows: list[dict[str, str]] = []
    supported_spans = 0
    supported_bytes = 0
    seen_spans = 0
    seen_bytes = 0
    unique_signatures: set[tuple[str, str]] = set()

    for index, row in enumerate(target_rows, start=1):
        issues: list[str] = []
        buffer = buffers.get(row_key(row))
        signatures: list[dict[str, str]] = []
        if buffer is None:
            issues.append("missing_replay_buffer")
        else:
            decoded, known_mask = buffer
            signatures = anchor_signatures(row, decoded, known_mask, max_distance=max_distance, max_delta=max_delta)
        for sig in signatures:
            sig["scope"] = "target"
            key = signature_key(sig)
            sig["known_signature_rows"] = str(known_counts.get(key, 0))
            sig["known_signature_spans"] = str(len(signature_spans.get(key, set())))
            signature_rows.append(sig)
        signatures.sort(
            key=lambda sig: (
                -int_value(sig, "known_signature_spans"),
                -int_value(sig, "known_signature_rows"),
                abs(int_value(sig, "anchor_rel")),
                sig.get("anchor_side", ""),
                sig.get("delta_signature", ""),
            )
        )
        best = signatures[0] if signatures else {}
        span_length = int_value(row, "span_length", int_value(row, "length"))
        if signatures:
            supported_spans += 1
            supported_bytes += span_length
            unique_signatures.add(signature_key(best))
        if int_value(best, "known_signature_spans") > 0:
            seen_spans += 1
            seen_bytes += span_length
        if not signatures and not issues:
            issues.append("missing_anchor_signature")
        verdict_value = "unique_bridge_signature"
        if not signatures:
            verdict_value = "missing_anchor_signature"
        elif int_value(best, "known_signature_spans") > 0 and span_length <= 1:
            verdict_value = "weak_known_single_byte_signature"
        elif int_value(best, "known_signature_spans") > 0:
            verdict_value = "known_signature_review"
        target_output_rows.append(
            {
                "rank": str(index),
                "archive": row.get("archive", ""),
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "span_key": row.get("span_key", ""),
                "span_start": row.get("span_start", row.get("expected_start", "")),
                "span_end": row.get("span_end", row.get("expected_end", "")),
                "span_length": str(span_length),
                "expected_hex": row.get("expected_hex", ""),
                "gap_role": row.get("gap_role", ""),
                "best_anchor_side": best.get("anchor_side", ""),
                "best_anchor_rel": best.get("anchor_rel", ""),
                "best_anchor_byte": best.get("anchor_byte", ""),
                "best_delta_signature": best.get("delta_signature", ""),
                "best_known_signature_rows": best.get("known_signature_rows", "0"),
                "best_known_signature_spans": best.get("known_signature_spans", "0"),
                "anchor_candidates": str(len(signatures)),
                "verdict": verdict_value,
                "issues": ";".join(issues),
            }
        )

    signature_rows.sort(
        key=lambda row: (
            row.get("scope", ""),
            row.get("span_key", ""),
            -int_value(row, "known_signature_spans"),
            abs(int_value(row, "anchor_rel")),
        )
    )
    for index, row in enumerate(signature_rows, start=1):
        row["rank"] = str(index)

    best_target = max(
        target_output_rows,
        key=lambda row: (
            int_value(row, "best_known_signature_spans"),
            int_value(row, "span_length"),
            int_value(row, "anchor_candidates"),
        ),
        default={},
    )
    target_bytes = sum(int_value(row, "span_length", int_value(row, "length")) for row in target_rows)
    summary = {
        "scope": "total",
        "candidate_mode": "external_terminal_spatial_gradient_bridge_probe",
        "target_spans": str(len(target_rows)),
        "target_bytes": str(target_bytes),
        "known_reference_rows": str(len(known_rows)),
        "target_anchor_supported_spans": str(supported_spans),
        "target_anchor_supported_bytes": str(supported_bytes),
        "target_signature_seen_spans": str(seen_spans),
        "target_signature_seen_bytes": str(seen_bytes),
        "unique_target_signatures": str(len(unique_signatures)),
        "known_signature_rows": str(len(known_signature_rows)),
        "repeated_known_signatures": str(
            sum(1 for row in known_summary_rows if row.get("verdict") == "repeated_known_signature")
        ),
        "best_target_span": best_target.get("span_key", ""),
        "best_target_signature": best_target.get("best_delta_signature", ""),
        "best_target_known_signature_rows": best_target.get("best_known_signature_rows", "0"),
        "next_probe": (
            "derive non-oracle selector for unique frontier 80 spatial bridge signatures"
            if supported_bytes == target_bytes and seen_bytes < target_bytes
            else "expand spatial bridge anchors for unresolved external terminal bytes"
        ),
        "promotion_candidate_bytes": "0",
        "promotion_ready_bytes": "0",
        "issue_rows": str(len(buffer_issues) + sum(1 for row in target_output_rows if row.get("issues"))),
    }
    return summary, target_output_rows, signature_rows, known_summary_rows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    target_rows: list[dict[str, str]],
    signature_rows: list[dict[str, str]],
    known_signature_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "targets": target_rows,
        "signatures": signature_rows,
        "known_signatures": known_signature_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("signatures.csv", output_dir / "signatures.csv"),
            ("known_signatures.csv", output_dir / "known_signatures.csv"),
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
  --bg: #101417;
  --panel: #171f22;
  --line: #31424a;
  --text: #edf5f4;
  --muted: #9dafb5;
  --accent: #77d3b1;
  --warn: #f0b36c;
}}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, sans-serif; }}
main {{ width: min(1680px, calc(100vw - 28px)); margin: 0 auto; padding: 22px 0 32px; display: grid; gap: 16px; }}
h1 {{ margin: 0; font-size: 22px; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.muted {{ color: var(--muted); }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.value {{ font-size: 22px; font-weight: 760; color: var(--accent); }}
.warn {{ color: var(--warn); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; min-width: 1280px; border-collapse: collapse; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
code {{ color: var(--accent); }}
</style>
</head>
<body>
<main>
  <header>
    <h1>{html.escape(title)}</h1>
    <div class="muted">Finds known spatial anchors whose byte plus small signed deltas can cover each external terminal span.</div>
  </header>
  <section class="stats">
    <div class="stat"><div class="muted">Target bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="muted">Anchor-supported</div><div class="value">{summary['target_anchor_supported_bytes']}</div></div>
    <div class="stat"><div class="muted">Seen signatures</div><div class="value warn">{summary['target_signature_seen_bytes']}</div></div>
    <div class="stat"><div class="muted">Known signatures</div><div class="value">{summary['known_signature_rows']}</div></div>
    <div class="stat"><div class="muted">Promotion-ready</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2>{links}</section>
  <section class="panel">
    <h2>Next</h2>
    <p><code>{html.escape(summary['next_probe'])}</code></p>
    <p class="muted">Best seen signature: <code>{html.escape(summary['best_target_span'])}</code> / <code>{html.escape(summary['best_target_signature'])}</code>.</p>
  </section>
  <section class="panel"><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</section>
  <section class="panel"><h2>Signatures</h2>{render_table(signature_rows, SIGNATURE_FIELDNAMES)}</section>
  <section class="panel"><h2>Known signatures</h2>{render_table(known_signature_rows, KNOWN_SIGNATURE_FIELDNAMES)}</section>
  <script type="application/json" id="external-terminal-spatial-bridge-data">{html.escape(data_json)}</script>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe spatial gradient bridge signatures for external terminal gaps.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--small-gaps", type=Path, default=DEFAULT_SMALL_GAPS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--max-distance", type=int, default=DEFAULT_MAX_DISTANCE)
    parser.add_argument("--max-delta", type=int, default=DEFAULT_MAX_DELTA)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex External Terminal Spatial Gradient Bridge Probe",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, target_rows, signature_rows, known_signature_rows = build(
        read_csv(args.targets),
        read_csv(args.small_gaps),
        read_csv(args.fixtures),
        max_distance=args.max_distance,
        max_delta=args.max_delta,
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(args.output / "signatures.csv", SIGNATURE_FIELDNAMES, signature_rows)
    write_csv(args.output / "known_signatures.csv", KNOWN_SIGNATURE_FIELDNAMES, known_signature_rows)
    html_path = args.output / "index.html"
    html_path.write_text(
        build_html(summary, target_rows, signature_rows, known_signature_rows, args.output, args.title),
        encoding="utf-8",
    )

    print(f"Target bytes: {summary['target_bytes']}")
    print(f"Anchor-supported bytes: {summary['target_anchor_supported_bytes']}")
    print(f"Seen signature bytes: {summary['target_signature_seen_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"Next probe: {summary['next_probe']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
