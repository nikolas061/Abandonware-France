#!/usr/bin/env python3
"""Profile LLSE marker records using the current material marker-length policy."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_large_body_control_grammar_probe import int_value, write_csv
from lolg_tex_large_llse_higharg2_refinement_probe import (
    is_known_marker_pair,
    marker_payload_start,
    marker_symmetric_header,
    relative_href,
)
from lolg_tex_large_llse_marker_pair_length_probe import (
    DEFAULT_OUTPUT as _PAIR_LENGTH_OUTPUT,
    MARKER_PAIRS,
)
from lolg_tex_large_llse_marker_semantics_probe import (
    DEFAULT_MIX_ENTRY_INDEX,
    DEFAULT_SEGMENTS,
    TARGET_CONTROL_PATH,
    load_body,
    read_csv,
    read_summary,
    render_table,
)


DEFAULT_OUTPUT = Path("output/tex_large_llse_marker_record_profile")
DEFAULT_PAIR_LENGTH_SUMMARY = _PAIR_LENGTH_OUTPUT / "summary.csv"
DEFAULT_COMBO_SUMMARY = Path("output/tex_large_llse_marker_pair_combo_probe/summary.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "segment_rows",
    "marker_record_rows",
    "pair_record_rows",
    "symmetric_record_rows",
    "pair_group_rows",
    "base_pair_policy",
    "symmetric_policy",
    "fixed_pair",
    "fixed_policy",
    "combo_verdict",
    "top_pair",
    "top_pair_count",
    "top_pair_policy",
    "top_pair_record_len",
    "top_pair_record_hex",
    "top_pair_after4",
    "issue_rows",
    "record_profile_verdict",
    "next_action",
]

PAIR_FIELDNAMES = [
    "rank",
    "segment_id",
    "pair",
    "kind",
    "policy",
    "record_len",
    "count",
    "ratio",
    "top_record_hex",
    "top_after4",
    "top_after8",
    "top_before4",
    "top_next_byte",
    "top_offset_mod4",
    "top_offset_mod8",
    "sample_offsets",
]

RECORD_FIELDNAMES = [
    "rank",
    "segment_id",
    "archive",
    "archive_tag",
    "pcx_name",
    "kind",
    "pair",
    "policy",
    "record_len",
    "record_offset",
    "record_end",
    "record_hex",
    "before4_hex",
    "after4_hex",
    "after8_hex",
    "next_byte",
]


def top_counter(counter: Counter[str], limit: int = 8) -> str:
    return "|".join(f"{key}:{count}" for key, count in counter.most_common(limit))


def ratio(count: int, total: int) -> str:
    return f"{count / max(1, total):.6f}"


def parse_skip_total(policy: str, default: int = 2) -> int:
    base = policy
    for suffix in ("_advance", "_line"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    if not base.startswith("skip"):
        return default
    try:
        return max(2, int(base[4:]))
    except ValueError:
        return default


def marker_policy_map(pair_summary: dict[str, str]) -> tuple[str, str, str, str, dict[str, str]]:
    base_policy = pair_summary.get("best_base_pair_policy", "skip7") or "skip7"
    symmetric_policy = pair_summary.get("best_symmetric_policy", "skip2") or "skip2"
    fixed_pair = pair_summary.get("best_override_pair", "")
    fixed_policy = pair_summary.get("best_override_policy", "")
    policy_by_pair = {pair: base_policy for pair in MARKER_PAIRS}
    if fixed_pair in policy_by_pair and fixed_policy:
        policy_by_pair[fixed_pair] = fixed_policy
    return base_policy, symmetric_policy, fixed_pair, fixed_policy, policy_by_pair


def record_row(
    source: dict[str, str],
    kind: str,
    pair: str,
    policy: str,
    payload: bytes,
    start: int,
    total: int,
) -> dict[str, str]:
    end = min(len(payload), start + total)
    return {
        "rank": "",
        "segment_id": source.get("segment_id", ""),
        "archive": source.get("archive", ""),
        "archive_tag": source.get("archive_tag", ""),
        "pcx_name": source.get("pcx_name", ""),
        "kind": kind,
        "pair": pair,
        "policy": policy,
        "record_len": str(total),
        "record_offset": str(start),
        "record_end": str(end),
        "record_hex": payload[start:end].hex(),
        "before4_hex": payload[max(0, start - 4) : start].hex(),
        "after4_hex": payload[end : end + 4].hex(),
        "after8_hex": payload[end : end + 8].hex(),
        "next_byte": f"{payload[end]:02x}" if end < len(payload) else "",
    }


def profile_payload(
    source: dict[str, str],
    body: bytes,
    policy_by_pair: dict[str, str],
    symmetric_policy: str,
) -> list[dict[str, str]]:
    payload_start = marker_payload_start(body)
    payload = body[payload_start:]
    rows: list[dict[str, str]] = []
    pos = 0
    while pos < len(payload):
        start = pos
        byte = payload[pos]
        pos += 1
        if marker_symmetric_header(payload, byte, pos):
            pair = f"{byte:02x}{payload[pos]:02x}" if pos < len(payload) else f"{byte:02x}"
            total = parse_skip_total(symmetric_policy)
            rows.append(record_row(source, "symmetric", pair, symmetric_policy, payload, start, total))
            pos = min(len(payload), start + total)
            continue
        if pos < len(payload) and is_known_marker_pair(byte, payload[pos]):
            pair = f"{byte:02x}{payload[pos]:02x}"
            policy = policy_by_pair.get(pair, "skip7")
            total = parse_skip_total(policy)
            rows.append(record_row(source, "pair", pair, policy, payload, start, total))
            pos = min(len(payload), start + total)
    for rank, row in enumerate(rows, 1):
        row["rank"] = str(rank)
    return rows


def summarize_pairs(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row["segment_id"], row["pair"], row["kind"], row["policy"])].append(row)
    output: list[dict[str, str]] = []
    total = len(rows)
    for (segment_id, pair, kind, policy), group in sorted(
        grouped.items(),
        key=lambda item: (-len(item[1]), item[0]),
    ):
        record_hex = Counter(row["record_hex"] for row in group)
        after4 = Counter(row["after4_hex"] for row in group)
        after8 = Counter(row["after8_hex"] for row in group)
        before4 = Counter(row["before4_hex"] for row in group)
        next_byte = Counter(row["next_byte"] for row in group)
        mod4 = Counter(str(int_value(row, "record_offset") % 4) for row in group)
        mod8 = Counter(str(int_value(row, "record_offset") % 8) for row in group)
        output.append(
            {
                "rank": "",
                "segment_id": segment_id,
                "pair": pair,
                "kind": kind,
                "policy": policy,
                "record_len": group[0].get("record_len", ""),
                "count": str(len(group)),
                "ratio": ratio(len(group), total),
                "top_record_hex": top_counter(record_hex),
                "top_after4": top_counter(after4),
                "top_after8": top_counter(after8),
                "top_before4": top_counter(before4),
                "top_next_byte": top_counter(next_byte),
                "top_offset_mod4": top_counter(mod4),
                "top_offset_mod8": top_counter(mod8),
                "sample_offsets": "|".join(row["record_offset"] for row in group[:12]),
            }
        )
    for rank, row in enumerate(output, 1):
        row["rank"] = str(rank)
    return output


def summary_row(
    detail_rows: list[dict[str, str]],
    pair_rows: list[dict[str, str]],
    pair_summary: dict[str, str],
    combo_summary: dict[str, str],
    base_policy: str,
    symmetric_policy: str,
    fixed_pair: str,
    fixed_policy: str,
    issue_rows: int,
) -> dict[str, str]:
    top_pair = pair_rows[0] if pair_rows else {}
    if issue_rows:
        verdict = "llse_marker_record_profile_issues"
        next_action = "fix LLSE marker record profile inputs"
    elif pair_rows:
        verdict = "llse_marker_record_profile_ready"
        next_action = (
            "derive LLSE marker record field semantics from "
            f"{top_pair.get('pair', '')} len {top_pair.get('record_len', '')}; "
            f"top record {top_pair.get('top_record_hex', '').split('|')[0]}"
        )
    else:
        verdict = "llse_marker_record_profile_empty"
        next_action = "review LLSE marker record profile inputs"
    return {
        "scope": "total",
        "segment_rows": str(len({row.get("segment_id", "") for row in detail_rows if row.get("segment_id")})),
        "marker_record_rows": str(len(detail_rows)),
        "pair_record_rows": str(sum(1 for row in detail_rows if row.get("kind") == "pair")),
        "symmetric_record_rows": str(sum(1 for row in detail_rows if row.get("kind") == "symmetric")),
        "pair_group_rows": str(len(pair_rows)),
        "base_pair_policy": base_policy,
        "symmetric_policy": symmetric_policy,
        "fixed_pair": fixed_pair,
        "fixed_policy": fixed_policy,
        "combo_verdict": combo_summary.get("combo_verdict", ""),
        "top_pair": top_pair.get("pair", ""),
        "top_pair_count": top_pair.get("count", ""),
        "top_pair_policy": top_pair.get("policy", ""),
        "top_pair_record_len": top_pair.get("record_len", ""),
        "top_pair_record_hex": top_pair.get("top_record_hex", ""),
        "top_pair_after4": top_pair.get("top_after4", ""),
        "issue_rows": str(issue_rows),
        "record_profile_verdict": verdict,
        "next_action": next_action,
    }


def build_html(summary: dict[str, str], pairs: list[dict[str, str]], records: list[dict[str, str]], output_dir: Path, title: str) -> str:
    payload = {"summary": summary, "pairs": pairs, "records": records}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f"<a href=\"{html.escape(relative_href(path, output_dir))}\">{html.escape(label)}</a>"
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("pairs.csv", output_dir / "pairs.csv"),
            ("records.csv", output_dir / "records.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme: dark; --bg: #101317; --panel: #181d23; --text: #e8edf2; --muted: #98a4b3; --accent: #74b8ff; --ok: #6fd08c; --warn: #f0b35a; }}
body {{ margin: 0; font-family: system-ui, sans-serif; background: var(--bg); color: var(--text); }}
header, main {{ max-width: 1450px; margin: 0 auto; padding: 24px; }}
h1 {{ margin: 0 0 8px; font-size: 26px; }}
h2 {{ margin: 0 0 12px; font-size: 18px; }}
.muted {{ color: var(--muted); }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin: 20px 0; }}
.stat, .panel {{ background: var(--panel); border: 1px solid #29313b; border-radius: 8px; padding: 14px; }}
.label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
.value {{ font-size: 24px; font-weight: 700; }}
.ok {{ color: var(--ok); }}
.warn {{ color: var(--warn); }}
a {{ color: var(--accent); text-decoration: none; margin-right: 10px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
th, td {{ border-bottom: 1px solid #29313b; padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); position: sticky; top: 0; background: var(--panel); }}
td {{ max-width: 560px; overflow-wrap: anywhere; }}
section {{ margin-bottom: 20px; }}
</style>
</head>
<body>
<header>
  <h1>{html.escape(title)}</h1>
  <div class="muted">Marker record byte profile using the current material LLSE marker-length policy.</div>
  <p>{links}</p>
</header>
<main>
  <section class="grid">
    <div class="stat"><div class="label">Records</div><div class="value">{html.escape(summary['marker_record_rows'])}</div></div>
    <div class="stat"><div class="label">Top Pair</div><div class="value">{html.escape(summary['top_pair'])}</div></div>
    <div class="stat"><div class="label">Top Len</div><div class="value warn">{html.escape(summary['top_pair_record_len'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel"><h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}</section>
  <section class="panel"><h2>Pairs</h2>{render_table(pairs, PAIR_FIELDNAMES)}</section>
  <section class="panel"><h2>Records</h2>{render_table(records[:256], RECORD_FIELDNAMES)}</section>
</main>
<script type="application/json" id="llse-marker-record-profile-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    pair_summary = read_summary(args.pair_length_summary)
    combo_summary = read_summary(args.combo_summary)
    base_policy, symmetric_policy, fixed_pair, fixed_policy, policy_by_pair = marker_policy_map(pair_summary)
    segment_rows = [row for row in read_csv(args.segments) if row.get("control_path") == TARGET_CONTROL_PATH]
    payload_cache: dict[Path, bytes] = {}
    records: list[dict[str, str]] = []
    issue_rows = 0
    for source in segment_rows:
        body, issues = load_body(source, payload_cache, args.mix_entry_index)
        if issues:
            issue_rows += 1
            continue
        records.extend(profile_payload(source, body, policy_by_pair, symmetric_policy))
    pairs = summarize_pairs(records)
    summary = summary_row(
        records,
        pairs,
        pair_summary,
        combo_summary,
        base_policy,
        symmetric_policy,
        fixed_pair,
        fixed_policy,
        issue_rows,
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "pairs.csv", PAIR_FIELDNAMES, pairs)
    write_csv(args.output / "records.csv", RECORD_FIELDNAMES, records)
    (args.output / "index.html").write_text(build_html(summary, pairs, records, args.output, args.title), encoding="utf-8")
    return summary, pairs, records


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile LLSE marker records.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--segments", type=Path, default=DEFAULT_SEGMENTS)
    parser.add_argument("--pair-length-summary", type=Path, default=DEFAULT_PAIR_LENGTH_SUMMARY)
    parser.add_argument("--combo-summary", type=Path, default=DEFAULT_COMBO_SUMMARY)
    parser.add_argument("--mix-entry-index", type=int, default=DEFAULT_MIX_ENTRY_INDEX)
    parser.add_argument("--title", default="Lands of Lore II .tex LLSE Marker Record Profile")
    args = parser.parse_args()

    summary, _pairs, _records = write_report(args)
    print(f"Segments: {summary['segment_rows']}")
    print(f"Marker records: {summary['marker_record_rows']}")
    print(f"Pair groups: {summary['pair_group_rows']}")
    print(f"Policy: base {summary['base_pair_policy']} fixed {summary['fixed_pair']} {summary['fixed_policy']}")
    print(f"Top pair: {summary['top_pair']} count {summary['top_pair_count']} len {summary['top_pair_record_len']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Record verdict: {summary['record_profile_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
