#!/usr/bin/env python3
"""Profile fields inside the dominant LLSE marker record."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter
from pathlib import Path

from lolg_tex_large_body_control_grammar_probe import int_value, write_csv
from lolg_tex_large_llse_higharg2_refinement_probe import float_text, relative_href
from lolg_tex_large_llse_marker_record_profile import (
    DEFAULT_OUTPUT as _RECORD_PROFILE_OUTPUT,
    PAIR_FIELDNAMES as _PAIR_FIELDNAMES,
    RECORD_FIELDNAMES,
    SUMMARY_FIELDNAMES as _RECORD_SUMMARY_FIELDNAMES,
    read_summary,
    render_table,
)


DEFAULT_OUTPUT = Path("output/tex_large_llse_marker_record_field_profile")
DEFAULT_RECORD_SUMMARY = _RECORD_PROFILE_OUTPUT / "summary.csv"
DEFAULT_RECORDS = _RECORD_PROFILE_OUTPUT / "records.csv"

SUMMARY_FIELDNAMES = [
    "scope",
    "target_pair",
    "target_record_len",
    "record_rows",
    "field_rows",
    "tuple_rows",
    "sample_rows",
    "top_mod4_field",
    "top_mod4_ratio",
    "top_low_field",
    "top_low_ratio",
    "top_zero_field",
    "top_zero_ratio",
    "top_tuple_start",
    "top_tuple_len",
    "top_tuple_hex",
    "top_tuple_count",
    "top_tuple_ratio",
    "issue_rows",
    "field_profile_verdict",
    "next_action",
]

FIELD_FIELDNAMES = [
    "rank",
    "pair",
    "record_len",
    "field_index",
    "record_offset",
    "count",
    "unique_values",
    "zero_count",
    "zero_ratio",
    "low_count",
    "low_ratio",
    "high_count",
    "high_ratio",
    "mod4_top",
    "mod4_top_count",
    "mod4_top_ratio",
    "min_value",
    "max_value",
    "mean_value",
    "top_values",
    "top_signed",
]

TUPLE_FIELDNAMES = [
    "rank",
    "pair",
    "record_len",
    "tuple_start",
    "tuple_len",
    "count",
    "unique_tuples",
    "top_tuple_hex",
    "top_tuple_count",
    "top_tuple_ratio",
    "top_tuple_signed",
    "top_next_field",
    "top_prev_field",
    "sample_offsets",
]

SAMPLE_FIELDNAMES = [
    "rank",
    "record_offset",
    "record_hex",
    "fields_hex",
    "field0",
    "field1",
    "field2",
    "field3",
    "field4",
    "before4_hex",
    "after4_hex",
    "next_byte",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def ratio(count: int, total: int) -> str:
    return f"{count / max(1, total):.6f}"


def signed_byte(value: int) -> int:
    return value - 256 if value >= 128 else value


def top_counter(counter: Counter[str], limit: int = 12) -> str:
    return "|".join(f"{key}:{count}" for key, count in counter.most_common(limit))


def parse_record(row: dict[str, str]) -> bytes:
    try:
        return bytes.fromhex(row.get("record_hex", ""))
    except ValueError:
        return b""


def target_records(records: list[dict[str, str]], summary: dict[str, str], pair_arg: str, record_len_arg: int) -> tuple[str, int, list[dict[str, str]]]:
    pair = pair_arg or summary.get("top_pair", "")
    record_len = record_len_arg or int_value(summary, "top_pair_record_len")
    selected = [
        row
        for row in records
        if row.get("kind") == "pair"
        and row.get("pair") == pair
        and int_value(row, "record_len") == record_len
        and len(parse_record(row)) == record_len
    ]
    return pair, record_len, selected


def summarize_fields(pair: str, record_len: int, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    if record_len <= 2:
        return []
    field_rows: list[dict[str, str]] = []
    args_by_row = [parse_record(row)[2:] for row in rows]
    for index in range(record_len - 2):
        values = [args[index] for args in args_by_row if index < len(args)]
        counter = Counter(values)
        signed_counter = Counter(str(signed_byte(value)) for value in values)
        mod4_counter = Counter(str(value % 4) for value in values)
        zero_count = counter.get(0, 0)
        low_count = sum(count for value, count in counter.items() if value < 0x30)
        high_count = sum(count for value, count in counter.items() if value >= 0xC0)
        mod4_top, mod4_count = mod4_counter.most_common(1)[0] if mod4_counter else ("", 0)
        mean_value = sum(values) / max(1, len(values))
        field_rows.append(
            {
                "rank": "",
                "pair": pair,
                "record_len": str(record_len),
                "field_index": str(index),
                "record_offset": str(index + 2),
                "count": str(len(values)),
                "unique_values": str(len(counter)),
                "zero_count": str(zero_count),
                "zero_ratio": ratio(zero_count, len(values)),
                "low_count": str(low_count),
                "low_ratio": ratio(low_count, len(values)),
                "high_count": str(high_count),
                "high_ratio": ratio(high_count, len(values)),
                "mod4_top": mod4_top,
                "mod4_top_count": str(mod4_count),
                "mod4_top_ratio": ratio(mod4_count, len(values)),
                "min_value": f"{min(values):02x}" if values else "",
                "max_value": f"{max(values):02x}" if values else "",
                "mean_value": f"{mean_value:.3f}",
                "top_values": top_counter(Counter(f"{value:02x}" for value in values)),
                "top_signed": top_counter(signed_counter),
            }
        )
    field_rows.sort(
        key=lambda row: (
            -float_text(row.get("mod4_top_ratio")),
            -float_text(row.get("low_ratio")),
            int_value(row, "field_index"),
        )
    )
    for rank, row in enumerate(field_rows, 1):
        row["rank"] = str(rank)
    return field_rows


def summarize_tuples(pair: str, record_len: int, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    args_by_row = [(row, parse_record(row)[2:]) for row in rows]
    tuple_rows: list[dict[str, str]] = []
    arg_len = max(0, record_len - 2)
    for tuple_len in (2, 3):
        if tuple_len > arg_len:
            continue
        for start in range(0, arg_len - tuple_len + 1):
            tuples: list[bytes] = []
            offsets_by_tuple: dict[bytes, list[str]] = {}
            next_field = Counter()
            prev_field = Counter()
            for row, args in args_by_row:
                if start + tuple_len > len(args):
                    continue
                value = bytes(args[start : start + tuple_len])
                tuples.append(value)
                offsets_by_tuple.setdefault(value, []).append(row.get("record_offset", ""))
                if start + tuple_len < len(args):
                    next_field[f"{args[start + tuple_len]:02x}"] += 1
                if start > 0:
                    prev_field[f"{args[start - 1]:02x}"] += 1
            counter = Counter(tuples)
            if not counter:
                continue
            top_tuple, top_count = counter.most_common(1)[0]
            tuple_rows.append(
                {
                    "rank": "",
                    "pair": pair,
                    "record_len": str(record_len),
                    "tuple_start": str(start),
                    "tuple_len": str(tuple_len),
                    "count": str(len(tuples)),
                    "unique_tuples": str(len(counter)),
                    "top_tuple_hex": top_tuple.hex(),
                    "top_tuple_count": str(top_count),
                    "top_tuple_ratio": ratio(top_count, len(tuples)),
                    "top_tuple_signed": ",".join(str(signed_byte(value)) for value in top_tuple),
                    "top_next_field": top_counter(next_field),
                    "top_prev_field": top_counter(prev_field),
                    "sample_offsets": "|".join(offsets_by_tuple[top_tuple][:12]),
                }
            )
    tuple_rows.sort(
        key=lambda row: (
            -float_text(row.get("top_tuple_ratio")),
            int_value(row, "tuple_start"),
            int_value(row, "tuple_len"),
        )
    )
    for rank, row in enumerate(tuple_rows, 1):
        row["rank"] = str(rank)
    return tuple_rows


def sample_rows(rows: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    samples = []
    for rank, row in enumerate(rows[:limit], 1):
        record = parse_record(row)
        args = record[2:]
        values = [f"{value:02x}" for value in args]
        padded = values + [""] * max(0, 5 - len(values))
        samples.append(
            {
                "rank": str(rank),
                "record_offset": row.get("record_offset", ""),
                "record_hex": row.get("record_hex", ""),
                "fields_hex": " ".join(values),
                "field0": padded[0],
                "field1": padded[1],
                "field2": padded[2],
                "field3": padded[3],
                "field4": padded[4],
                "before4_hex": row.get("before4_hex", ""),
                "after4_hex": row.get("after4_hex", ""),
                "next_byte": row.get("next_byte", ""),
            }
        )
    return samples


def summary_row(
    pair: str,
    record_len: int,
    record_rows: list[dict[str, str]],
    field_rows: list[dict[str, str]],
    tuple_rows: list[dict[str, str]],
    samples: list[dict[str, str]],
    issue_rows: int,
) -> dict[str, str]:
    top_mod4 = field_rows[0] if field_rows else {}
    top_low = max(field_rows, key=lambda row: float_text(row.get("low_ratio")), default={})
    top_zero = max(field_rows, key=lambda row: float_text(row.get("zero_ratio")), default={})
    top_tuple = tuple_rows[0] if tuple_rows else {}
    if issue_rows:
        verdict = "llse_marker_record_field_profile_issues"
        next_action = "fix LLSE marker record field profile inputs"
    elif record_rows and field_rows:
        verdict = "llse_marker_record_field_profile_ready"
        next_action = (
            "test LLSE 2730 field semantics using "
            f"field {top_mod4.get('field_index', '')} mod4={top_mod4.get('mod4_top', '')} "
            f"and tuple {top_tuple.get('top_tuple_hex', '')}"
        )
    else:
        verdict = "llse_marker_record_field_profile_empty"
        next_action = "review LLSE marker record field profile inputs"
    return {
        "scope": "total",
        "target_pair": pair,
        "target_record_len": str(record_len),
        "record_rows": str(len(record_rows)),
        "field_rows": str(len(field_rows)),
        "tuple_rows": str(len(tuple_rows)),
        "sample_rows": str(len(samples)),
        "top_mod4_field": top_mod4.get("field_index", ""),
        "top_mod4_ratio": top_mod4.get("mod4_top_ratio", ""),
        "top_low_field": top_low.get("field_index", ""),
        "top_low_ratio": top_low.get("low_ratio", ""),
        "top_zero_field": top_zero.get("field_index", ""),
        "top_zero_ratio": top_zero.get("zero_ratio", ""),
        "top_tuple_start": top_tuple.get("tuple_start", ""),
        "top_tuple_len": top_tuple.get("tuple_len", ""),
        "top_tuple_hex": top_tuple.get("top_tuple_hex", ""),
        "top_tuple_count": top_tuple.get("top_tuple_count", ""),
        "top_tuple_ratio": top_tuple.get("top_tuple_ratio", ""),
        "issue_rows": str(issue_rows),
        "field_profile_verdict": verdict,
        "next_action": next_action,
    }


def build_html(
    summary: dict[str, str],
    fields: list[dict[str, str]],
    tuples: list[dict[str, str]],
    samples: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "fields": fields, "tuples": tuples, "samples": samples}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f"<a href=\"{html.escape(relative_href(path, output_dir))}\">{html.escape(label)}</a>"
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("fields.csv", output_dir / "fields.csv"),
            ("tuples.csv", output_dir / "tuples.csv"),
            ("samples.csv", output_dir / "samples.csv"),
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
  <div class="muted">Field and tuple profile for the dominant LLSE marker record.</div>
  <p>{links}</p>
</header>
<main>
  <section class="grid">
    <div class="stat"><div class="label">Records</div><div class="value">{html.escape(summary['record_rows'])}</div></div>
    <div class="stat"><div class="label">Top Field</div><div class="value">{html.escape(summary['top_mod4_field'])}</div></div>
    <div class="stat"><div class="label">Top Tuple</div><div class="value warn">{html.escape(summary['top_tuple_hex'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel"><h2>Summary</h2>{render_table([summary], SUMMARY_FIELDNAMES)}</section>
  <section class="panel"><h2>Fields</h2>{render_table(fields, FIELD_FIELDNAMES)}</section>
  <section class="panel"><h2>Tuples</h2>{render_table(tuples, TUPLE_FIELDNAMES)}</section>
  <section class="panel"><h2>Samples</h2>{render_table(samples, SAMPLE_FIELDNAMES)}</section>
</main>
<script type="application/json" id="llse-marker-record-field-profile-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    args.output.mkdir(parents=True, exist_ok=True)
    record_summary = read_summary(args.record_summary)
    records = read_csv(args.records)
    issue_rows = 0
    if not records:
        issue_rows = 1
    pair, record_len, selected = target_records(records, record_summary, args.pair, args.record_len)
    fields = summarize_fields(pair, record_len, selected)
    tuples = summarize_tuples(pair, record_len, selected)
    samples = sample_rows(selected, args.sample_limit)
    summary = summary_row(pair, record_len, selected, fields, tuples, samples, issue_rows)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "fields.csv", FIELD_FIELDNAMES, fields)
    write_csv(args.output / "tuples.csv", TUPLE_FIELDNAMES, tuples)
    write_csv(args.output / "samples.csv", SAMPLE_FIELDNAMES, samples)
    (args.output / "index.html").write_text(
        build_html(summary, fields, tuples, samples, args.output, args.title),
        encoding="utf-8",
    )
    return summary, fields, tuples


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile LLSE marker record fields.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--record-summary", type=Path, default=DEFAULT_RECORD_SUMMARY)
    parser.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    parser.add_argument("--pair", default="")
    parser.add_argument("--record-len", type=int, default=0)
    parser.add_argument("--sample-limit", type=int, default=128)
    parser.add_argument("--title", default="Lands of Lore II .tex LLSE Marker Record Field Profile")
    args = parser.parse_args()

    summary, _fields, _tuples = write_report(args)
    print(f"Target: {summary['target_pair']} len {summary['target_record_len']}")
    print(f"Records: {summary['record_rows']}")
    print(f"Fields: {summary['field_rows']}")
    print(f"Tuples: {summary['tuple_rows']}")
    print(f"Top mod4 field: {summary['top_mod4_field']} ratio {summary['top_mod4_ratio']}")
    print(f"Top tuple: {summary['top_tuple_hex']} count {summary['top_tuple_count']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Field verdict: {summary['field_profile_verdict']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
