#!/usr/bin/env python3
"""Queue unresolved .tex nonzero runs by local context for decoder work."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_unresolved_zero_queue import (
    byte_class,
    byte_hex,
    fixture_key,
    length_bucket,
    position_class,
    read_bytes,
    read_csv,
    render_table,
    sort_rank,
    span_key,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_queue")
DEFAULT_SPANS = Path("output/tex_gap_decoder_len64_promoted_tiny_run_probe/by_span.csv")
DEFAULT_RUNS = Path("output/tex_gap_decoder_len64_promoted_tiny_run_probe/runs.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "fixture_rows",
    "span_rows",
    "nonzero_run_rows",
    "nonzero_bytes",
    "pure_nonzero_span_rows",
    "pure_nonzero_span_bytes",
    "internal_nonzero_run_rows",
    "internal_nonzero_bytes",
    "boundary_nonzero_run_rows",
    "boundary_nonzero_bytes",
    "large_run_rows",
    "large_run_bytes",
    "max_nonzero_run_bytes",
    "signature_rows",
    "issue_rows",
]

QUEUE_FIELDNAMES = [
    "priority",
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "position_class",
    "span_class",
    "length",
    "length_bucket",
    "start",
    "end",
    "span_start",
    "span_end",
    "head_hex",
    "tail_hex",
    "left_byte_hex",
    "right_byte_hex",
    "left_byte_class",
    "right_byte_class",
    "left_clean_distance",
    "right_clean_distance",
    "queue_class",
    "signature",
]

SIGNATURE_FIELDNAMES = [
    "signature",
    "rows",
    "bytes",
    "fixtures",
    "position_class",
    "length_bucket",
    "left_byte_class",
    "right_byte_class",
    "max_run_bytes",
    "sample_pcx",
    "sample_frontier_id",
]

FIXTURE_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "nonzero_run_rows",
    "nonzero_bytes",
    "pure_nonzero_span_rows",
    "pure_nonzero_span_bytes",
    "internal_nonzero_run_rows",
    "internal_nonzero_bytes",
    "boundary_nonzero_run_rows",
    "boundary_nonzero_bytes",
    "max_nonzero_run_bytes",
]


def queue_class(position: str, span_class: str, left_class: str, right_class: str) -> str:
    if position == "span_full" and span_class == "unresolved_nonzero":
        return "review_pure_nonzero_span"
    if position == "internal":
        return "review_internal_nonzero"
    return "review_boundary_nonzero"


def chunk_hex(data: bytes, start: int, end: int, *, tail: bool = False) -> str:
    chunk = data[max(0, start) : max(0, end)]
    if tail:
        return chunk[-16:].hex()
    return chunk[:16].hex()


def build_rows(
    span_rows: list[dict[str, str]],
    run_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    issues: list[str] = []
    spans = {span_key(row): row for row in span_rows}
    fixture_bytes: dict[tuple[str, str, str], bytes] = {}
    fixture_meta: dict[tuple[str, str, str], dict[str, str]] = {}
    for fixture in fixture_rows:
        key = fixture_key(fixture)
        fixture_meta[key] = fixture
        local_issues: list[str] = []
        fixture_bytes[key] = read_bytes(
            fixture.get("expected_gap_path", ""),
            local_issues,
            "expected_gap",
        )
        issues.extend(f"{key}:{issue}" for issue in local_issues)

    queue_rows: list[dict[str, str]] = []
    fixture_totals: dict[tuple[str, str, str], Counter[str]] = defaultdict(Counter)
    fixture_max: dict[tuple[str, str, str], int] = defaultdict(int)

    for run in run_rows:
        if run.get("run_class") != "nonzero":
            continue
        key = fixture_key(run)
        span = spans.get(span_key(run), {})
        expected = fixture_bytes.get(key, b"")
        start = int_value(run, "start")
        end = int_value(run, "end")
        length = int_value(run, "length")
        position = position_class(run)
        bucket = length_bucket(length)
        left_class = byte_class(expected, start - 1)
        right_class = byte_class(expected, end)
        span_class = span.get("span_class", "")
        qclass = queue_class(position, span_class, left_class, right_class)
        signature = f"{position}|{bucket}|left_{left_class}|right_{right_class}"
        priority = length * 10
        if qclass == "review_pure_nonzero_span":
            priority += 300
        elif qclass == "review_internal_nonzero":
            priority += 200
        else:
            priority += 100

        row = {
            "priority": str(priority),
            "rank": run.get("rank", ""),
            "archive": run.get("archive", ""),
            "archive_tag": run.get("archive_tag", ""),
            "pcx_name": run.get("pcx_name", ""),
            "frontier_id": run.get("frontier_id", ""),
            "span_index": run.get("span_index", ""),
            "run_index": run.get("run_index", ""),
            "position_class": position,
            "span_class": span_class,
            "length": str(length),
            "length_bucket": bucket,
            "start": run.get("start", ""),
            "end": run.get("end", ""),
            "span_start": run.get("span_start", ""),
            "span_end": run.get("span_end", ""),
            "head_hex": chunk_hex(expected, start, end),
            "tail_hex": chunk_hex(expected, start, end, tail=True),
            "left_byte_hex": byte_hex(expected, start - 1),
            "right_byte_hex": byte_hex(expected, end),
            "left_byte_class": left_class,
            "right_byte_class": right_class,
            "left_clean_distance": run.get("left_clean_distance", ""),
            "right_clean_distance": run.get("right_clean_distance", ""),
            "queue_class": qclass,
            "signature": signature,
        }
        queue_rows.append(row)

        totals = fixture_totals[key]
        totals["nonzero_run_rows"] += 1
        totals["nonzero_bytes"] += length
        if qclass == "review_pure_nonzero_span":
            totals["pure_nonzero_span_rows"] += 1
            totals["pure_nonzero_span_bytes"] += length
        if qclass == "review_internal_nonzero":
            totals["internal_nonzero_run_rows"] += 1
            totals["internal_nonzero_bytes"] += length
        if qclass == "review_boundary_nonzero":
            totals["boundary_nonzero_run_rows"] += 1
            totals["boundary_nonzero_bytes"] += length
        fixture_max[key] = max(fixture_max[key], length)

    queue_rows.sort(
        key=lambda row: (
            -int_value(row, "priority"),
            -int_value(row, "length"),
            sort_rank(row.get("rank", "")),
            int_value(row, "start"),
        )
    )

    signature_totals: dict[str, Counter[str]] = defaultdict(Counter)
    signature_fixtures: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    signature_sample: dict[str, dict[str, str]] = {}
    for row in queue_rows:
        signature = row["signature"]
        signature_totals[signature]["rows"] += 1
        signature_totals[signature]["bytes"] += int_value(row, "length")
        signature_totals[signature]["max_run_bytes"] = max(
            signature_totals[signature]["max_run_bytes"],
            int_value(row, "length"),
        )
        signature_fixtures[signature].add(fixture_key(row))
        signature_sample.setdefault(signature, row)

    signature_rows = []
    for signature, totals in signature_totals.items():
        sample = signature_sample[signature]
        signature_rows.append(
            {
                "signature": signature,
                "rows": str(totals["rows"]),
                "bytes": str(totals["bytes"]),
                "fixtures": str(len(signature_fixtures[signature])),
                "position_class": sample.get("position_class", ""),
                "length_bucket": sample.get("length_bucket", ""),
                "left_byte_class": sample.get("left_byte_class", ""),
                "right_byte_class": sample.get("right_byte_class", ""),
                "max_run_bytes": str(totals["max_run_bytes"]),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    signature_rows.sort(
        key=lambda row: (-int_value(row, "bytes"), -int_value(row, "rows"), row["signature"])
    )

    by_fixture_rows = []
    for key in sorted(fixture_totals, key=lambda item: (sort_rank(item[0]), item[1], item[2])):
        totals = fixture_totals[key]
        meta = fixture_meta.get(key, {})
        by_fixture_rows.append(
            {
                "rank": key[0],
                "archive": meta.get("archive", ""),
                "archive_tag": meta.get("archive_tag", ""),
                "pcx_name": key[1],
                "frontier_id": key[2],
                "nonzero_run_rows": str(totals["nonzero_run_rows"]),
                "nonzero_bytes": str(totals["nonzero_bytes"]),
                "pure_nonzero_span_rows": str(totals["pure_nonzero_span_rows"]),
                "pure_nonzero_span_bytes": str(totals["pure_nonzero_span_bytes"]),
                "internal_nonzero_run_rows": str(totals["internal_nonzero_run_rows"]),
                "internal_nonzero_bytes": str(totals["internal_nonzero_bytes"]),
                "boundary_nonzero_run_rows": str(totals["boundary_nonzero_run_rows"]),
                "boundary_nonzero_bytes": str(totals["boundary_nonzero_bytes"]),
                "max_nonzero_run_bytes": str(fixture_max[key]),
            }
        )

    pure_rows = [row for row in queue_rows if row.get("queue_class") == "review_pure_nonzero_span"]
    internal_rows = [row for row in queue_rows if row.get("queue_class") == "review_internal_nonzero"]
    boundary_rows = [row for row in queue_rows if row.get("queue_class") == "review_boundary_nonzero"]
    large_rows = [
        row
        for row in queue_rows
        if row.get("length_bucket") in {"len64", "multiple64", "large96", "large32"}
    ]
    summary = {
        "scope": "total",
        "fixture_rows": str(len(by_fixture_rows)),
        "span_rows": str(len(span_rows)),
        "nonzero_run_rows": str(len(queue_rows)),
        "nonzero_bytes": str(sum(int_value(row, "length") for row in queue_rows)),
        "pure_nonzero_span_rows": str(len(pure_rows)),
        "pure_nonzero_span_bytes": str(sum(int_value(row, "length") for row in pure_rows)),
        "internal_nonzero_run_rows": str(len(internal_rows)),
        "internal_nonzero_bytes": str(sum(int_value(row, "length") for row in internal_rows)),
        "boundary_nonzero_run_rows": str(len(boundary_rows)),
        "boundary_nonzero_bytes": str(sum(int_value(row, "length") for row in boundary_rows)),
        "large_run_rows": str(len(large_rows)),
        "large_run_bytes": str(sum(int_value(row, "length") for row in large_rows)),
        "max_nonzero_run_bytes": str(max([int_value(row, "length") for row in queue_rows] or [0])),
        "signature_rows": str(len(signature_rows)),
        "issue_rows": str(len(issues)),
    }
    return summary, queue_rows, signature_rows, by_fixture_rows


def build_html(
    summary: dict[str, str],
    queue_rows: list[dict[str, str]],
    signature_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "queue": queue_rows,
        "signatures": signature_rows,
        "fixtures": fixture_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("queue.csv", output_dir / "queue.csv"),
            ("by_signature.csv", output_dir / "by_signature.csv"),
            ("by_fixture.csv", output_dir / "by_fixture.csv"),
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
  --ok: #80df94;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.wrap {{ width: min(1680px, calc(100vw - 28px)); margin: 0 auto; }}
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
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1440px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Ranks remaining nonzero runs after the tiny promoted replay by position and neighbor context.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Nonzero runs</div><div class="value">{summary['nonzero_run_rows']}</div></div>
    <div class="stat"><div class="label">Nonzero bytes</div><div class="value">{summary['nonzero_bytes']}</div></div>
    <div class="stat"><div class="label">Pure span bytes</div><div class="value ok">{summary['pure_nonzero_span_bytes']}</div></div>
    <div class="stat"><div class="label">Max run</div><div class="value">{summary['max_nonzero_run_bytes']}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{summary['issue_rows']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Top signatures</h2>{render_table(signature_rows, SIGNATURE_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Queue</h2>{render_table(queue_rows, QUEUE_FIELDNAMES, 260)}</section>
  <section class="panel"><h2>By fixture</h2>{render_table(fixture_rows, FIXTURE_FIELDNAMES, 80)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_QUEUE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Queue remaining .tex nonzero runs after a promoted replay.")
    parser.add_argument("--spans", type=Path, default=DEFAULT_SPANS)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Promoted Nonzero Queue",
    )
    args = parser.parse_args()

    summary, queue_rows, signature_rows, by_fixture_rows = build_rows(
        read_csv(args.spans),
        read_csv(args.runs),
        read_csv(args.fixtures),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "queue.csv", QUEUE_FIELDNAMES, queue_rows)
    write_csv(args.output / "by_signature.csv", SIGNATURE_FIELDNAMES, signature_rows)
    write_csv(args.output / "by_fixture.csv", FIXTURE_FIELDNAMES, by_fixture_rows)
    html_path = args.output / "index.html"
    html_path.write_text(
        build_html(summary, queue_rows, signature_rows, by_fixture_rows, args.output, args.title)
    )

    print(f"Nonzero runs queued: {summary['nonzero_run_rows']}")
    print(f"Nonzero bytes queued: {summary['nonzero_bytes']}")
    print(f"Pure nonzero span bytes: {summary['pure_nonzero_span_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
