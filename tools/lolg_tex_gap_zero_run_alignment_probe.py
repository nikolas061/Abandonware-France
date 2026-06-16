#!/usr/bin/env python3
"""Analyze .tex zero-run alignment and nearby length evidence."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_zero_run_alignment_probe")
DEFAULT_OPERATIONS = Path("output/tex_gap_segmentation_control_correlation_probe/operations.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "operation_rows",
    "zero_ops",
    "zero_bytes",
    "length64_ops",
    "fill_to_mod64_ops",
    "full_aligned64_ops",
    "length_u8_hit_ops",
    "length_u16le_hit_ops",
    "gap_to_gap_zero_ops",
    "transition_rows",
    "length_rows",
    "fixture_rows",
    "issue_rows",
]

ZERO_FIELDNAMES = [
    "rank",
    "pcx_name",
    "frontier_id",
    "op_index",
    "expected_start",
    "expected_end",
    "length",
    "start_mod64",
    "end_mod64",
    "fill_to_mod64",
    "full_aligned64",
    "prev_kind",
    "next_kind",
    "length_u8_hit_offsets",
    "length_u16le_hit_offsets",
    "expected_hex",
    "issues",
]

LENGTH_FIELDNAMES = [
    "length",
    "zero_ops",
    "zero_bytes",
    "length_u8_hit_ops",
    "length_u16le_hit_ops",
    "pcx_names",
    "sample_rank",
    "sample_frontier_id",
]

TRANSITION_FIELDNAMES = [
    "prev_kind",
    "next_kind",
    "zero_ops",
    "zero_bytes",
    "length64_ops",
    "length_u8_hit_ops",
    "pcx_names",
]

FIXTURE_FIELDNAMES = [
    "rank",
    "pcx_name",
    "frontier_id",
    "zero_ops",
    "zero_bytes",
    "length64_ops",
    "fill_to_mod64_ops",
    "full_aligned64_ops",
    "length_u8_hit_ops",
    "issue_rows",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def fixture_id(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def build_zero_rows(operation_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, row in enumerate(operation_rows):
        if row.get("op_kind") != "zero":
            continue
        prev_row = (
            operation_rows[index - 1]
            if index > 0 and fixture_id(operation_rows[index - 1]) == fixture_id(row)
            else {}
        )
        next_row = (
            operation_rows[index + 1]
            if index + 1 < len(operation_rows) and fixture_id(operation_rows[index + 1]) == fixture_id(row)
            else {}
        )
        start = int_value(row, "expected_start")
        end = int_value(row, "expected_end")
        length = int_value(row, "length")
        start_mod = start % 64
        end_mod = end % 64
        fill_to_mod64 = start_mod != 0 and length == 64 - start_mod
        full_aligned64 = start_mod == 0 and length == 64
        rows.append(
            {
                "rank": row.get("rank", ""),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "op_index": row.get("op_index", ""),
                "expected_start": str(start),
                "expected_end": str(end),
                "length": str(length),
                "start_mod64": str(start_mod),
                "end_mod64": str(end_mod),
                "fill_to_mod64": "1" if fill_to_mod64 else "0",
                "full_aligned64": "1" if full_aligned64 else "0",
                "prev_kind": prev_row.get("op_kind", ""),
                "next_kind": next_row.get("op_kind", ""),
                "length_u8_hit_offsets": row.get("length_u8_hit_offsets", ""),
                "length_u16le_hit_offsets": row.get("length_u16le_hit_offsets", ""),
                "expected_hex": row.get("expected_hex", ""),
                "issues": row.get("issues", ""),
            }
        )
    return rows


def length_rows(zero_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in zero_rows:
        grouped[row.get("length", "")].append(row)
    rows: list[dict[str, str]] = []
    for length, matches in grouped.items():
        sample = matches[0]
        rows.append(
            {
                "length": length,
                "zero_ops": str(len(matches)),
                "zero_bytes": str(sum(int_value(row, "length") for row in matches)),
                "length_u8_hit_ops": str(sum(1 for row in matches if row.get("length_u8_hit_offsets"))),
                "length_u16le_hit_ops": str(sum(1 for row in matches if row.get("length_u16le_hit_offsets"))),
                "pcx_names": ";".join(sorted({row.get("pcx_name", "") for row in matches})),
                "sample_rank": sample.get("rank", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    return sorted(rows, key=lambda row: (-int_value(row, "zero_ops"), int_value(row, "length")))


def transition_rows(zero_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in zero_rows:
        grouped[(row.get("prev_kind", ""), row.get("next_kind", ""))].append(row)
    rows: list[dict[str, str]] = []
    for (prev_kind, next_kind), matches in grouped.items():
        rows.append(
            {
                "prev_kind": prev_kind,
                "next_kind": next_kind,
                "zero_ops": str(len(matches)),
                "zero_bytes": str(sum(int_value(row, "length") for row in matches)),
                "length64_ops": str(sum(1 for row in matches if int_value(row, "length") == 64)),
                "length_u8_hit_ops": str(sum(1 for row in matches if row.get("length_u8_hit_offsets"))),
                "pcx_names": ";".join(sorted({row.get("pcx_name", "") for row in matches})),
            }
        )
    return sorted(rows, key=lambda row: (-int_value(row, "zero_ops"), row.get("prev_kind", ""), row.get("next_kind", "")))


def fixture_rows(zero_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in zero_rows:
        grouped[fixture_id(row)].append(row)
    rows: list[dict[str, str]] = []
    for key, matches in sorted(grouped.items(), key=lambda item: int(item[0][0]) if item[0][0].isdigit() else 999999):
        rows.append(
            {
                "rank": key[0],
                "pcx_name": key[1],
                "frontier_id": key[2],
                "zero_ops": str(len(matches)),
                "zero_bytes": str(sum(int_value(row, "length") for row in matches)),
                "length64_ops": str(sum(1 for row in matches if int_value(row, "length") == 64)),
                "fill_to_mod64_ops": str(sum(1 for row in matches if row.get("fill_to_mod64") == "1")),
                "full_aligned64_ops": str(sum(1 for row in matches if row.get("full_aligned64") == "1")),
                "length_u8_hit_ops": str(sum(1 for row in matches if row.get("length_u8_hit_offsets"))),
                "issue_rows": str(sum(1 for row in matches if row.get("issues"))),
            }
        )
    return rows


def summary_row(
    operation_rows: list[dict[str, str]],
    zero_rows: list[dict[str, str]],
    lengths: list[dict[str, str]],
    transitions: list[dict[str, str]],
    fixtures: list[dict[str, str]],
) -> dict[str, str]:
    return {
        "scope": "total",
        "operation_rows": str(len(operation_rows)),
        "zero_ops": str(len(zero_rows)),
        "zero_bytes": str(sum(int_value(row, "length") for row in zero_rows)),
        "length64_ops": str(sum(1 for row in zero_rows if int_value(row, "length") == 64)),
        "fill_to_mod64_ops": str(sum(1 for row in zero_rows if row.get("fill_to_mod64") == "1")),
        "full_aligned64_ops": str(sum(1 for row in zero_rows if row.get("full_aligned64") == "1")),
        "length_u8_hit_ops": str(sum(1 for row in zero_rows if row.get("length_u8_hit_offsets"))),
        "length_u16le_hit_ops": str(sum(1 for row in zero_rows if row.get("length_u16le_hit_offsets"))),
        "gap_to_gap_zero_ops": str(
            sum(1 for row in zero_rows if row.get("prev_kind") == "gap" and row.get("next_kind") == "gap")
        ),
        "transition_rows": str(len(transitions)),
        "length_rows": str(len(lengths)),
        "fixture_rows": str(len(fixtures)),
        "issue_rows": str(sum(1 for row in zero_rows if row.get("issues"))),
    }


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 260) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    zero_rows: list[dict[str, str]],
    lengths: list[dict[str, str]],
    transitions: list[dict[str, str]],
    fixtures: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "zeroRuns": zero_rows,
        "lengths": lengths,
        "transitions": transitions,
        "fixtures": fixtures,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("zero_runs.csv", output_dir / "zero_runs.csv"),
            ("by_length.csv", output_dir / "by_length.csv"),
            ("by_transition.csv", output_dir / "by_transition.csv"),
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
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 23px; font-weight: 760; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 980px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Zero-run lengths, row alignment checks, operation transitions and nearby length hits.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Zero ops</div><div class="value">{html.escape(summary['zero_ops'])}</div></div>
    <div class="stat"><div class="label">Zero bytes</div><div class="value ok">{html.escape(summary['zero_bytes'])}</div></div>
    <div class="stat"><div class="label">Length 64 ops</div><div class="value">{html.escape(summary['length64_ops'])}</div></div>
    <div class="stat"><div class="label">Fill to mod64</div><div class="value">{html.escape(summary['fill_to_mod64_ops'])}</div></div>
    <div class="stat"><div class="label">Length u8 hits</div><div class="value">{html.escape(summary['length_u8_hit_ops'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel"><h2>Lengths</h2>{render_table(lengths, LENGTH_FIELDNAMES)}</section>
  <section class="panel"><h2>Transitions</h2>{render_table(transitions, TRANSITION_FIELDNAMES)}</section>
  <section class="panel"><h2>Fixtures</h2>{render_table(fixtures, FIXTURE_FIELDNAMES)}</section>
  <section class="panel"><h2>Zero runs</h2>{render_table(zero_rows, ZERO_FIELDNAMES)}</section>
</main>
<script>
const TEX_GAP_ZERO_RUN_ALIGNMENT_PROBE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    operations_path: Path,
    *,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    operation_rows = read_csv(operations_path)
    zeros = build_zero_rows(operation_rows)
    lengths = length_rows(zeros)
    transitions = transition_rows(zeros)
    fixtures = fixture_rows(zeros)
    summary = summary_row(operation_rows, zeros, lengths, transitions, fixtures)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "zero_runs.csv", ZERO_FIELDNAMES, zeros)
    write_csv(output_dir / "by_length.csv", LENGTH_FIELDNAMES, lengths)
    write_csv(output_dir / "by_transition.csv", TRANSITION_FIELDNAMES, transitions)
    write_csv(output_dir / "by_fixture.csv", FIXTURE_FIELDNAMES, fixtures)
    (output_dir / "index.html").write_text(build_html(summary, zeros, lengths, transitions, fixtures, output_dir, title))
    return summary, zeros


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze .tex zero-run alignment and length evidence.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument("--title", default="Lands of Lore II .tex Gap Zero Run Alignment Probe")
    args = parser.parse_args()

    summary, _zeros = write_report(args.output, args.operations, title=args.title)
    print(f"Zero ops: {summary['zero_ops']}")
    print(f"Zero bytes: {summary['zero_bytes']}")
    print(f"Length 64 ops: {summary['length64_ops']}")
    print(f"Fill to mod64 ops: {summary['fill_to_mod64_ops']}")
    print(f"Length u8 hit ops: {summary['length_u8_hit_ops']}")
    print(f"Issue rows: {summary['issue_rows']}")


if __name__ == "__main__":
    main()
