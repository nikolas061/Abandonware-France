#!/usr/bin/env python3
"""Probe the dominant unresolved internal len64 zero-run signature."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_internal_probe")
DEFAULT_QUEUE = Path("output/tex_gap_decoder_unresolved_zero_queue/queue.csv")
DEFAULT_RUNS = Path("output/tex_gap_decoder_unresolved_run_probe/runs.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
TARGET_SIGNATURE = "internal|len64|left_nonzero|right_nonzero"

SUMMARY_FIELDNAMES = [
    "scope",
    "target_signature",
    "target_rows",
    "target_bytes",
    "fixture_rows",
    "span_rows",
    "barrel_rows",
    "dinodead_rows",
    "neighbor_signature_rows",
    "top_neighbor_signature",
    "top_neighbor_rows",
    "top_neighbor_bytes",
    "prev29_next29_rows",
    "prev29_next29_bytes",
    "context_files",
    "issue_rows",
]

TARGET_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "start",
    "end",
    "length",
    "prev_run_length",
    "next_run_length",
    "prev_tail_hex",
    "next_head_hex",
    "neighbor_signature",
    "prev_zero_delta",
    "next_zero_delta",
    "context_path",
    "issues",
]

NEIGHBOR_FIELDNAMES = [
    "neighbor_signature",
    "rows",
    "bytes",
    "fixtures",
    "spans",
    "context_files",
    "sample_pcx",
    "sample_frontier_id",
]

FIXTURE_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "target_rows",
    "target_bytes",
    "span_rows",
    "neighbor_signature_rows",
    "context_files",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def run_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("rank", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("span_index", ""),
        row.get("run_index", ""),
    )


def span_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        row.get("rank", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("span_index", ""),
    )


def sort_rank(value: str) -> int:
    return int(value) if value.isdigit() else 999999


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")


def read_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def context_filename(row: dict[str, str]) -> str:
    return (
        f"rank{int_value(row, 'rank'):03d}_"
        f"{safe_name(row.get('pcx_name', 'pcx'))}_"
        f"frontier{safe_name(row.get('frontier_id', ''))}_"
        f"span{int_value(row, 'span_index'):03d}_"
        f"run{int_value(row, 'run_index'):03d}_len64_context.bin"
    )


def build_rows(
    queue_rows: list[dict[str, str]],
    run_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    output_dir: Path,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    issues: list[str] = []
    target_queue = [row for row in queue_rows if row.get("signature") == TARGET_SIGNATURE]
    run_lookup = {run_key(row): row for row in run_rows}
    fixture_meta = {fixture_key(row): row for row in fixture_rows}
    fixture_bytes: dict[tuple[str, str, str], bytes] = {}
    for key, fixture in fixture_meta.items():
        local_issues: list[str] = []
        fixture_bytes[key] = read_bytes(
            fixture.get("expected_gap_path", ""),
            local_issues,
            "expected_gap",
        )
        issues.extend(f"{key}:{issue}" for issue in local_issues)

    contexts_dir = output_dir / "contexts"
    contexts_dir.mkdir(parents=True, exist_ok=True)
    target_rows: list[dict[str, str]] = []
    for queue in sorted(
        target_queue,
        key=lambda row: (
            sort_rank(row.get("rank", "")),
            int_value(row, "start"),
            int_value(row, "span_index"),
        ),
    ):
        row_issues: list[str] = []
        prev_run = run_lookup.get(
            (
                queue.get("rank", ""),
                queue.get("pcx_name", ""),
                queue.get("frontier_id", ""),
                queue.get("span_index", ""),
                str(int_value(queue, "run_index") - 1),
            ),
            {},
        )
        next_run = run_lookup.get(
            (
                queue.get("rank", ""),
                queue.get("pcx_name", ""),
                queue.get("frontier_id", ""),
                queue.get("span_index", ""),
                str(int_value(queue, "run_index") + 1),
            ),
            {},
        )
        if not prev_run:
            row_issues.append("missing_prev_run")
        if not next_run:
            row_issues.append("missing_next_run")
        if prev_run and prev_run.get("run_class") != "nonzero":
            row_issues.append("prev_run_not_nonzero")
        if next_run and next_run.get("run_class") != "nonzero":
            row_issues.append("next_run_not_nonzero")
        if int_value(queue, "length") != 64:
            row_issues.append("target_not_len64")

        expected = fixture_bytes.get(fixture_key(queue), b"")
        context_start = int_value(prev_run, "start") if prev_run else int_value(queue, "start")
        context_end = int_value(next_run, "end") if next_run else int_value(queue, "end")
        context_start = max(0, min(context_start, len(expected)))
        context_end = max(context_start, min(context_end, len(expected)))
        context_bytes = expected[context_start:context_end]
        context_path = contexts_dir / context_filename(queue)
        context_path.write_bytes(context_bytes)

        prev_length = int_value(prev_run, "length")
        next_length = int_value(next_run, "length")
        neighbor_signature = f"prev{prev_length}|zero64|next{next_length}"
        row = {
            "rank": queue.get("rank", ""),
            "archive": queue.get("archive", ""),
            "archive_tag": queue.get("archive_tag", ""),
            "pcx_name": queue.get("pcx_name", ""),
            "frontier_id": queue.get("frontier_id", ""),
            "span_index": queue.get("span_index", ""),
            "run_index": queue.get("run_index", ""),
            "start": queue.get("start", ""),
            "end": queue.get("end", ""),
            "length": queue.get("length", ""),
            "prev_run_length": str(prev_length),
            "next_run_length": str(next_length),
            "prev_tail_hex": prev_run.get("tail_hex", "")[-32:],
            "next_head_hex": next_run.get("head_hex", "")[:32],
            "neighbor_signature": neighbor_signature,
            "prev_zero_delta": "",
            "next_zero_delta": "",
            "context_path": context_path.as_posix(),
            "issues": ";".join(row_issues),
        }
        target_rows.append(row)

    by_fixture_start: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in target_rows:
        by_fixture_start[fixture_key(row)].append(row)
    for rows in by_fixture_start.values():
        rows.sort(key=lambda row: int_value(row, "start"))
        for index, row in enumerate(rows):
            if index:
                row["prev_zero_delta"] = str(
                    int_value(row, "start") - int_value(rows[index - 1], "start")
                )
            if index + 1 < len(rows):
                row["next_zero_delta"] = str(
                    int_value(rows[index + 1], "start") - int_value(row, "start")
                )

    neighbor_totals: dict[str, Counter[str]] = defaultdict(Counter)
    neighbor_fixtures: dict[str, set[tuple[str, str, str]]] = defaultdict(set)
    neighbor_spans: dict[str, set[tuple[str, str, str, str]]] = defaultdict(set)
    neighbor_sample: dict[str, dict[str, str]] = {}
    for row in target_rows:
        signature = row["neighbor_signature"]
        neighbor_totals[signature]["rows"] += 1
        neighbor_totals[signature]["bytes"] += int_value(row, "length")
        neighbor_totals[signature]["context_files"] += 1 if row.get("context_path") else 0
        neighbor_fixtures[signature].add(fixture_key(row))
        neighbor_spans[signature].add(span_key(row))
        neighbor_sample.setdefault(signature, row)

    neighbor_rows = []
    for signature, totals in neighbor_totals.items():
        sample = neighbor_sample[signature]
        neighbor_rows.append(
            {
                "neighbor_signature": signature,
                "rows": str(totals["rows"]),
                "bytes": str(totals["bytes"]),
                "fixtures": str(len(neighbor_fixtures[signature])),
                "spans": str(len(neighbor_spans[signature])),
                "context_files": str(totals["context_files"]),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    neighbor_rows.sort(
        key=lambda row: (-int_value(row, "rows"), -int_value(row, "bytes"), row["neighbor_signature"])
    )

    fixture_rows_out = []
    for key in sorted(by_fixture_start, key=lambda item: (sort_rank(item[0]), item[1], item[2])):
        rows = by_fixture_start[key]
        meta = fixture_meta.get(key, {})
        fixture_rows_out.append(
            {
                "rank": key[0],
                "archive": meta.get("archive", ""),
                "archive_tag": meta.get("archive_tag", ""),
                "pcx_name": key[1],
                "frontier_id": key[2],
                "target_rows": str(len(rows)),
                "target_bytes": str(sum(int_value(row, "length") for row in rows)),
                "span_rows": str(len({span_key(row) for row in rows})),
                "neighbor_signature_rows": str(len({row["neighbor_signature"] for row in rows})),
                "context_files": str(sum(1 for row in rows if row.get("context_path"))),
            }
        )

    prev29_next29 = [row for row in target_rows if row.get("neighbor_signature") == "prev29|zero64|next29"]
    top_neighbor = neighbor_rows[0] if neighbor_rows else {}
    row_issue_count = sum(1 for row in target_rows if row.get("issues"))
    summary = {
        "scope": "total",
        "target_signature": TARGET_SIGNATURE,
        "target_rows": str(len(target_rows)),
        "target_bytes": str(sum(int_value(row, "length") for row in target_rows)),
        "fixture_rows": str(len(fixture_rows_out)),
        "span_rows": str(len({span_key(row) for row in target_rows})),
        "barrel_rows": str(sum(1 for row in target_rows if row.get("pcx_name") == "barrel.pcx")),
        "dinodead_rows": str(sum(1 for row in target_rows if row.get("pcx_name") == "dinodead.pcx")),
        "neighbor_signature_rows": str(len(neighbor_rows)),
        "top_neighbor_signature": top_neighbor.get("neighbor_signature", ""),
        "top_neighbor_rows": top_neighbor.get("rows", "0"),
        "top_neighbor_bytes": top_neighbor.get("bytes", "0"),
        "prev29_next29_rows": str(len(prev29_next29)),
        "prev29_next29_bytes": str(sum(int_value(row, "length") for row in prev29_next29)),
        "context_files": str(sum(1 for row in target_rows if row.get("context_path"))),
        "issue_rows": str(len(issues) + row_issue_count),
    }
    return summary, target_rows, neighbor_rows, fixture_rows_out


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    target_rows: list[dict[str, str]],
    neighbor_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "targets": target_rows,
        "neighbors": neighbor_rows,
        "fixtures": fixture_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("by_neighbor_signature.csv", output_dir / "by_neighbor_signature.csv"),
            ("by_fixture.csv", output_dir / "by_fixture.csv"),
            ("contexts/", output_dir / "contexts"),
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
    <div class="sub">Isolates the dominant internal len64 unresolved zero-run signature.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Target rows</div><div class="value">{summary['target_rows']}</div></div>
    <div class="stat"><div class="label">Target bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Top neighbor</div><div class="value">{summary['top_neighbor_rows']}</div></div>
    <div class="stat"><div class="label">Context files</div><div class="value">{summary['context_files']}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{summary['issue_rows']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Neighbor signatures</h2>{render_table(neighbor_rows, NEIGHBOR_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>By fixture</h2>{render_table(fixture_rows, FIXTURE_FIELDNAMES, 80)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_INTERNAL_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe the dominant unresolved internal len64 zero-run signature."
    )
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Internal Len64 Probe")
    args = parser.parse_args()

    queue_rows = read_csv(args.queue)
    run_rows = read_csv(args.runs)
    fixture_rows = read_csv(args.fixtures)
    summary, target_rows, neighbor_rows, by_fixture_rows = build_rows(
        queue_rows,
        run_rows,
        fixture_rows,
        args.output,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(args.output / "by_neighbor_signature.csv", NEIGHBOR_FIELDNAMES, neighbor_rows)
    write_csv(args.output / "by_fixture.csv", FIXTURE_FIELDNAMES, by_fixture_rows)
    html_path = args.output / "index.html"
    html_path.write_text(
        build_html(summary, target_rows, neighbor_rows, by_fixture_rows, args.output, args.title)
    )

    print(f"Target rows: {summary['target_rows']}")
    print(f"Target bytes: {summary['target_bytes']}")
    print(f"Top neighbor: {summary['top_neighbor_signature']} ({summary['top_neighbor_rows']} rows)")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
