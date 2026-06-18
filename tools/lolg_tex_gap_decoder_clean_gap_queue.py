#!/usr/bin/env python3
"""Rank the remaining .tex gap spans after the clean decoder replay."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_clean_gap_queue")
DEFAULT_FIXTURE_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CLEAN_FIXTURES = Path("output/tex_gap_decoder_clean_replay/fixtures.csv")
DEFAULT_CLEAN_DECISIONS = Path("output/tex_gap_decoder_clean_replay/decisions.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "fixture_rows",
    "total_bytes",
    "clean_bytes",
    "rejected_false_bytes",
    "unresolved_bytes",
    "unresolved_zero_bytes",
    "unresolved_nonzero_bytes",
    "unresolved_mixed_bytes",
    "span_rows",
    "unresolved_span_rows",
    "rejected_span_rows",
    "largest_unresolved_span",
    "issue_rows",
]

SPAN_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "span_class",
    "start",
    "end",
    "length",
    "zero_bytes",
    "nonzero_bytes",
    "first16_hex",
    "last16_hex",
    "left_clean_distance",
    "right_clean_distance",
]

FIXTURE_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "fixture_bytes",
    "clean_bytes",
    "rejected_false_bytes",
    "unresolved_bytes",
    "unresolved_zero_bytes",
    "unresolved_nonzero_bytes",
    "unresolved_mixed_bytes",
    "span_rows",
    "unresolved_span_rows",
    "rejected_span_rows",
    "largest_unresolved_span",
    "issues",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def fixture_sort_key(key: tuple[str, str, str]) -> tuple[int, str, str]:
    rank, pcx_name, frontier_id = key
    return int(rank) if rank.isdigit() else 999999, pcx_name, frontier_id


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    path = Path(path_text)
    try:
        return path.read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def mask_spans(mask: bytes, value: int) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    index = 0
    while index < len(mask):
        if mask[index] != value:
            index += 1
            continue
        start = index
        while index < len(mask) and mask[index] == value:
            index += 1
        spans.append((start, index))
    return spans


def classify_span(expected: bytes, start: int, end: int, prefix: str) -> tuple[str, int, int]:
    chunk = expected[start:end]
    zero_bytes = sum(1 for value in chunk if value == 0)
    nonzero_bytes = len(chunk) - zero_bytes
    if not chunk:
        return f"{prefix}_empty", zero_bytes, nonzero_bytes
    if zero_bytes == len(chunk):
        return f"{prefix}_zero", zero_bytes, nonzero_bytes
    if nonzero_bytes == len(chunk):
        return f"{prefix}_nonzero", zero_bytes, nonzero_bytes
    return f"{prefix}_mixed", zero_bytes, nonzero_bytes


def clean_distance(mask: bytes, start: int, end: int) -> tuple[str, str]:
    left = ""
    for index in range(start - 1, -1, -1):
        if mask[index]:
            left = str(start - index)
            break
    right = ""
    for index in range(end, len(mask)):
        if mask[index]:
            right = str(index - end + 1)
            break
    return left, right


def make_span_row(
    fixture: dict[str, str],
    expected: bytes,
    known_mask: bytes,
    *,
    span_index: int,
    span_class: str,
    start: int,
    end: int,
) -> dict[str, str]:
    zero_bytes = sum(1 for value in expected[start:end] if value == 0)
    nonzero_bytes = max(0, end - start - zero_bytes)
    left_distance, right_distance = clean_distance(known_mask, start, end)
    return {
        "rank": fixture.get("rank", ""),
        "archive": fixture.get("archive", ""),
        "archive_tag": fixture.get("archive_tag", ""),
        "pcx_name": fixture.get("pcx_name", ""),
        "frontier_id": fixture.get("frontier_id", ""),
        "span_index": str(span_index),
        "span_class": span_class,
        "start": str(start),
        "end": str(end),
        "length": str(max(0, end - start)),
        "zero_bytes": str(zero_bytes),
        "nonzero_bytes": str(nonzero_bytes),
        "first16_hex": expected[start : min(end, start + 16)].hex(),
        "last16_hex": expected[max(start, end - 16) : end].hex(),
        "left_clean_distance": left_distance,
        "right_clean_distance": right_distance,
    }


def build_rows(
    manifest_rows: list[dict[str, str]],
    clean_fixture_rows: list[dict[str, str]],
    decision_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    manifest_by_key = {fixture_key(row): row for row in manifest_rows}
    rejected_ranges: dict[tuple[str, str, str], list[tuple[int, int]]] = defaultdict(list)
    for row in decision_rows:
        if row.get("queue_verdict") != "reject_false_risk":
            continue
        rejected_ranges[fixture_key(row)].append(
            (int_value(row, "expected_start"), int_value(row, "expected_end"))
        )

    span_rows: list[dict[str, str]] = []
    fixture_rows: list[dict[str, str]] = []
    issue_rows = 0

    for clean_fixture in sorted(clean_fixture_rows, key=lambda row: fixture_sort_key(fixture_key(row))):
        key = fixture_key(clean_fixture)
        manifest = manifest_by_key.get(key, {})
        issues: list[str] = []
        expected = load_bytes(manifest.get("expected_gap_path", ""), issues, "expected")
        known_mask = load_bytes(clean_fixture.get("known_mask_path", ""), issues, "known_mask")
        if len(known_mask) != len(expected):
            issues.append("known_mask_size_mismatch")
            known_mask = known_mask[: len(expected)] + (b"\x00" * max(0, len(expected) - len(known_mask)))

        rejected_mask = bytearray(len(expected))
        for start, end in rejected_ranges.get(key, []):
            bounded_start = max(0, min(start, len(expected)))
            bounded_end = max(bounded_start, min(end, len(expected)))
            rejected_mask[bounded_start:bounded_end] = b"\xff" * (bounded_end - bounded_start)

        unresolved_mask = bytearray(len(expected))
        for index in range(len(expected)):
            if not known_mask[index] and not rejected_mask[index]:
                unresolved_mask[index] = 255

        fixture_span_rows: list[dict[str, str]] = []
        span_index = 0
        for start, end in mask_spans(bytes(rejected_mask), 255):
            span_index += 1
            span_class, _zero_bytes, _nonzero_bytes = classify_span(
                expected, start, end, "rejected_false_risk"
            )
            fixture_span_rows.append(
                make_span_row(
                    clean_fixture,
                    expected,
                    known_mask,
                    span_index=span_index,
                    span_class=span_class,
                    start=start,
                    end=end,
                )
            )
        for start, end in mask_spans(bytes(unresolved_mask), 255):
            span_index += 1
            span_class, _zero_bytes, _nonzero_bytes = classify_span(expected, start, end, "unresolved")
            fixture_span_rows.append(
                make_span_row(
                    clean_fixture,
                    expected,
                    known_mask,
                    span_index=span_index,
                    span_class=span_class,
                    start=start,
                    end=end,
                )
            )

        rejected_false_bytes = sum(
            int_value(row, "length")
            for row in fixture_span_rows
            if row.get("span_class", "").startswith("rejected_false_risk")
        )
        unresolved_rows = [
            row for row in fixture_span_rows if row.get("span_class", "").startswith("unresolved")
        ]
        unresolved_bytes = sum(int_value(row, "length") for row in unresolved_rows)
        unresolved_zero = sum(
            int_value(row, "length") for row in unresolved_rows if row.get("span_class") == "unresolved_zero"
        )
        unresolved_nonzero = sum(
            int_value(row, "length")
            for row in unresolved_rows
            if row.get("span_class") == "unresolved_nonzero"
        )
        unresolved_mixed = sum(
            int_value(row, "length") for row in unresolved_rows if row.get("span_class") == "unresolved_mixed"
        )
        largest_unresolved = max([int_value(row, "length") for row in unresolved_rows] or [0])
        span_rows.extend(fixture_span_rows)
        if issues:
            issue_rows += 1
        clean_byte_text = clean_fixture.get("clean_bytes") or clean_fixture.get("total_clean_bytes")
        if not clean_byte_text:
            clean_byte_text = str(sum(1 for value in known_mask if value))

        fixture_rows.append(
            {
                "rank": clean_fixture.get("rank", ""),
                "archive": clean_fixture.get("archive", ""),
                "archive_tag": clean_fixture.get("archive_tag", ""),
                "pcx_name": clean_fixture.get("pcx_name", ""),
                "frontier_id": clean_fixture.get("frontier_id", ""),
                "fixture_bytes": str(len(expected)),
                "clean_bytes": clean_byte_text,
                "rejected_false_bytes": str(rejected_false_bytes),
                "unresolved_bytes": str(unresolved_bytes),
                "unresolved_zero_bytes": str(unresolved_zero),
                "unresolved_nonzero_bytes": str(unresolved_nonzero),
                "unresolved_mixed_bytes": str(unresolved_mixed),
                "span_rows": str(len(fixture_span_rows)),
                "unresolved_span_rows": str(len(unresolved_rows)),
                "rejected_span_rows": str(len(fixture_span_rows) - len(unresolved_rows)),
                "largest_unresolved_span": str(largest_unresolved),
                "issues": ";".join(issues),
            }
        )

    span_rows.sort(
        key=lambda row: (
            row.get("span_class", "").startswith("rejected_false_risk"),
            -int_value(row, "length"),
            int_value(row, "rank"),
            int_value(row, "start"),
        )
    )
    total_bytes = sum(int_value(row, "fixture_bytes") for row in fixture_rows)
    clean_bytes = sum(int_value(row, "clean_bytes") for row in fixture_rows)
    rejected_false_bytes = sum(int_value(row, "rejected_false_bytes") for row in fixture_rows)
    unresolved_bytes = sum(int_value(row, "unresolved_bytes") for row in fixture_rows)
    summary = {
        "scope": "total",
        "fixture_rows": str(len(fixture_rows)),
        "total_bytes": str(total_bytes),
        "clean_bytes": str(clean_bytes),
        "rejected_false_bytes": str(rejected_false_bytes),
        "unresolved_bytes": str(unresolved_bytes),
        "unresolved_zero_bytes": str(sum(int_value(row, "unresolved_zero_bytes") for row in fixture_rows)),
        "unresolved_nonzero_bytes": str(
            sum(int_value(row, "unresolved_nonzero_bytes") for row in fixture_rows)
        ),
        "unresolved_mixed_bytes": str(
            sum(int_value(row, "unresolved_mixed_bytes") for row in fixture_rows)
        ),
        "span_rows": str(len(span_rows)),
        "unresolved_span_rows": str(
            sum(1 for row in span_rows if row.get("span_class", "").startswith("unresolved"))
        ),
        "rejected_span_rows": str(
            sum(1 for row in span_rows if row.get("span_class", "").startswith("rejected_false_risk"))
        ),
        "largest_unresolved_span": str(
            max(
                [
                    int_value(row, "length")
                    for row in span_rows
                    if row.get("span_class", "").startswith("unresolved")
                ]
                or [0]
            )
        ),
        "issue_rows": str(issue_rows),
    }
    return summary, span_rows, fixture_rows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    span_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "spans": span_rows, "fixtures": fixture_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("spans.csv", output_dir / "spans.csv"),
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
  --risk: #f0a064;
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
.risk {{ color: var(--risk); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1320px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Remaining spans after promoted clean replay, split from rejected false-risk bytes.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Clean bytes</div><div class="value ok">{html.escape(summary['clean_bytes'])}</div></div>
    <div class="stat"><div class="label">Rejected false-risk</div><div class="value risk">{html.escape(summary['rejected_false_bytes'])}</div></div>
    <div class="stat"><div class="label">Unresolved bytes</div><div class="value">{html.escape(summary['unresolved_bytes'])}</div></div>
    <div class="stat"><div class="label">Largest unresolved</div><div class="value">{html.escape(summary['largest_unresolved_span'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel"><h2>Spans</h2>{render_table(span_rows, SPAN_FIELDNAMES)}</section>
  <section class="panel"><h2>Fixtures</h2>{render_table(fixture_rows, FIXTURE_FIELDNAMES)}</section>
</main>
<script>
const TEX_GAP_DECODER_CLEAN_GAP_QUEUE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    manifest_path: Path,
    clean_fixtures_path: Path,
    clean_decisions_path: Path,
    *,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary, span_rows, fixture_rows = build_rows(
        read_csv(manifest_path),
        read_csv(clean_fixtures_path),
        read_csv(clean_decisions_path),
    )
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "spans.csv", SPAN_FIELDNAMES, span_rows)
    write_csv(output_dir / "by_fixture.csv", FIXTURE_FIELDNAMES, fixture_rows)
    (output_dir / "index.html").write_text(build_html(summary, span_rows, fixture_rows, output_dir, title))
    return summary, span_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank .tex clean replay remaining gap spans.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixture-manifest", type=Path, default=DEFAULT_FIXTURE_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("--clean-decisions", type=Path, default=DEFAULT_CLEAN_DECISIONS)
    parser.add_argument("--title", default="Lands of Lore II .tex Decoder Clean Gap Queue")
    args = parser.parse_args()

    summary, _span_rows = write_report(
        args.output,
        args.fixture_manifest,
        args.clean_fixtures,
        args.clean_decisions,
        title=args.title,
    )
    print(f"Clean bytes: {summary['clean_bytes']}")
    print(f"Rejected false-risk bytes: {summary['rejected_false_bytes']}")
    print(f"Unresolved bytes: {summary['unresolved_bytes']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
