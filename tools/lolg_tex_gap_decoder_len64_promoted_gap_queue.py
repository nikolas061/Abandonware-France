#!/usr/bin/env python3
"""Rank remaining .tex gap spans after the promoted len64 replay."""

from __future__ import annotations

import argparse
import html
import json
from collections import defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_clean_gap_queue import (
    SPAN_FIELDNAMES,
    classify_span,
    fixture_key,
    fixture_sort_key,
    load_bytes,
    make_span_row,
    mask_spans,
    read_csv,
    render_table,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_gap_queue")
DEFAULT_FIXTURE_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_PROMOTED_FIXTURES = Path("output/tex_gap_decoder_len64_promoted_replay/fixtures.csv")
DEFAULT_CLEAN_DECISIONS = Path("output/tex_gap_decoder_clean_replay/decisions.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "fixture_rows",
    "total_bytes",
    "base_clean_bytes",
    "selector_added_bytes",
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

FIXTURE_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "fixture_bytes",
    "base_clean_bytes",
    "selector_added_bytes",
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


def build_rows(
    manifest_rows: list[dict[str, str]],
    promoted_fixture_rows: list[dict[str, str]],
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

    for promoted_fixture in sorted(
        promoted_fixture_rows,
        key=lambda row: fixture_sort_key(fixture_key(row)),
    ):
        key = fixture_key(promoted_fixture)
        manifest = manifest_by_key.get(key, {})
        issues: list[str] = []
        expected = load_bytes(manifest.get("expected_gap_path", ""), issues, "expected")
        known_mask = load_bytes(promoted_fixture.get("known_mask_path", ""), issues, "known_mask")
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
                expected,
                start,
                end,
                "rejected_false_risk",
            )
            fixture_span_rows.append(
                make_span_row(
                    promoted_fixture,
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
                    promoted_fixture,
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
        if unresolved_bytes != int_value(promoted_fixture, "remaining_unresolved_bytes"):
            issues.append("remaining_unresolved_mismatch")
        if rejected_false_bytes != int_value(promoted_fixture, "rejected_false_bytes"):
            issues.append("rejected_false_mismatch")

        span_rows.extend(fixture_span_rows)
        if issues:
            issue_rows += 1

        fixture_rows.append(
            {
                "rank": promoted_fixture.get("rank", ""),
                "archive": promoted_fixture.get("archive", ""),
                "archive_tag": promoted_fixture.get("archive_tag", ""),
                "pcx_name": promoted_fixture.get("pcx_name", ""),
                "frontier_id": promoted_fixture.get("frontier_id", ""),
                "fixture_bytes": str(len(expected)),
                "base_clean_bytes": promoted_fixture.get("base_clean_bytes", "0"),
                "selector_added_bytes": promoted_fixture.get("selector_added_bytes", "0"),
                "clean_bytes": promoted_fixture.get("total_clean_bytes", "0"),
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
    summary = {
        "scope": "total",
        "fixture_rows": str(len(fixture_rows)),
        "total_bytes": str(sum(int_value(row, "fixture_bytes") for row in fixture_rows)),
        "base_clean_bytes": str(sum(int_value(row, "base_clean_bytes") for row in fixture_rows)),
        "selector_added_bytes": str(sum(int_value(row, "selector_added_bytes") for row in fixture_rows)),
        "clean_bytes": str(sum(int_value(row, "clean_bytes") for row in fixture_rows)),
        "rejected_false_bytes": str(sum(int_value(row, "rejected_false_bytes") for row in fixture_rows)),
        "unresolved_bytes": str(sum(int_value(row, "unresolved_bytes") for row in fixture_rows)),
        "unresolved_zero_bytes": str(sum(int_value(row, "unresolved_zero_bytes") for row in fixture_rows)),
        "unresolved_nonzero_bytes": str(
            sum(int_value(row, "unresolved_nonzero_bytes") for row in fixture_rows)
        ),
        "unresolved_mixed_bytes": str(sum(int_value(row, "unresolved_mixed_bytes") for row in fixture_rows)),
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
    <div class="sub">Remaining spans after the len64-promoted clean replay.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Clean bytes</div><div class="value ok">{html.escape(summary['clean_bytes'])}</div></div>
    <div class="stat"><div class="label">Len64 added</div><div class="value ok">{html.escape(summary['selector_added_bytes'])}</div></div>
    <div class="stat"><div class="label">Rejected false-risk</div><div class="value risk">{html.escape(summary['rejected_false_bytes'])}</div></div>
    <div class="stat"><div class="label">Unresolved bytes</div><div class="value">{html.escape(summary['unresolved_bytes'])}</div></div>
    <div class="stat"><div class="label">Largest unresolved</div><div class="value">{html.escape(summary['largest_unresolved_span'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel"><h2>Spans</h2>{render_table(span_rows, SPAN_FIELDNAMES)}</section>
  <section class="panel"><h2>Fixtures</h2>{render_table(fixture_rows, FIXTURE_FIELDNAMES)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_GAP_QUEUE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    manifest_path: Path,
    promoted_fixtures_path: Path,
    clean_decisions_path: Path,
    *,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary, span_rows, fixture_rows = build_rows(
        read_csv(manifest_path),
        read_csv(promoted_fixtures_path),
        read_csv(clean_decisions_path),
    )
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "spans.csv", SPAN_FIELDNAMES, span_rows)
    write_csv(output_dir / "by_fixture.csv", FIXTURE_FIELDNAMES, fixture_rows)
    (output_dir / "index.html").write_text(build_html(summary, span_rows, fixture_rows, output_dir, title))
    return summary, span_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank .tex gaps after the promoted len64 replay.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixture-manifest", type=Path, default=DEFAULT_FIXTURE_MANIFEST)
    parser.add_argument("--promoted-fixtures", type=Path, default=DEFAULT_PROMOTED_FIXTURES)
    parser.add_argument("--clean-decisions", type=Path, default=DEFAULT_CLEAN_DECISIONS)
    parser.add_argument("--title", default="Lands of Lore II .tex Len64 Promoted Gap Queue")
    args = parser.parse_args()

    summary, _span_rows = write_report(
        args.output,
        args.fixture_manifest,
        args.promoted_fixtures,
        args.clean_decisions,
        title=args.title,
    )
    print(f"Clean bytes: {summary['clean_bytes']}")
    print(f"Len64 added bytes: {summary['selector_added_bytes']}")
    print(f"Rejected false-risk bytes: {summary['rejected_false_bytes']}")
    print(f"Unresolved bytes: {summary['unresolved_bytes']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
