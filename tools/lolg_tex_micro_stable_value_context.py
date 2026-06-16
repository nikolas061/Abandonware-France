#!/usr/bin/env python3
"""Group opcode neighborhoods for local stable-source value hits."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_RUNS = Path("output/tex_micro_stable_source_grammar/runs.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_OUTPUT = Path("output/tex_micro_stable_value_context")

SUMMARY_FIELDNAMES = [
    "scope",
    "run_rows",
    "value_hit_rows",
    "value_hit_bytes",
    "context_groups",
    "repeated_context_groups",
    "repeated_context_rows",
    "repeated_context_bytes",
    "repeated_value_length_context_rows",
    "repeated_value_length_context_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

CONTEXT_FIELDNAMES = [
    "rank",
    "source_rank",
    "group_rank",
    "archive",
    "pcx_name",
    "frontier_id",
    "run_index",
    "run_value_hex",
    "run_length",
    "run_start",
    "nearest_value_offset",
    "offset_delta",
    "context_key",
    "context_hex",
    "left_hex",
    "right_hex",
    "verdict",
]

GROUP_FIELDNAMES = [
    "rank",
    "group_key",
    "rows",
    "bytes",
    "values",
    "lengths",
    "fixtures",
    "offset_deltas",
    "repeated_value_length_rows",
    "repeated_value_length_bytes",
    "sample_context_hex",
    "sample_pcx",
    "sample_frontier_id",
    "verdict",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, str], field: str) -> int:
    try:
        return int(row.get(field, "") or 0)
    except ValueError:
        return 0


def locator_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def load_segments(fixture_rows: list[dict[str, str]]) -> tuple[dict[tuple[str, str, str], bytes], list[str]]:
    segments: dict[tuple[str, str, str], bytes] = {}
    issues: list[str] = []
    for fixture in fixture_rows:
        local_issues: list[str] = []
        segments[locator_key(fixture)] = load_bytes(fixture.get("segment_gap_path", ""), local_issues, "segment")
        issues.extend(f"{locator_key(fixture)}:{issue}" for issue in local_issues)
    return segments, issues


def parse_offsets(text: str) -> list[int]:
    offsets: list[int] = []
    for part in text.split(";"):
        if part.lstrip("-").isdigit():
            offsets.append(int(part))
    return offsets


def nearest(offsets: list[int], target: int) -> int | None:
    if not offsets:
        return None
    return min(offsets, key=lambda value: (abs(value - target), value))


def context_key(data: bytes) -> str:
    return f"len={len(data)}|hex={data.hex()}"


def build(
    run_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    *,
    radius: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    segments, segment_issues = load_segments(fixture_rows)
    contexts: list[dict[str, object]] = []
    issues: list[str] = list(segment_issues)

    for run in run_rows:
        offsets = parse_offsets(run.get("local_value_offsets", ""))
        run_start = int_value(run, "run_start")
        chosen = nearest(offsets, run_start)
        if chosen is None:
            continue
        segment = segments.get(locator_key(run), b"")
        if not segment:
            issues.append(f"{locator_key(run)}:missing_segment")
            continue
        left = max(0, chosen - radius)
        right = min(len(segment), chosen + radius + 1)
        context = segment[left:right]
        left_context = segment[left:chosen]
        right_context = segment[chosen + 1 : right]
        contexts.append(
            {
                "rank": 0,
                "source_rank": run.get("source_rank", ""),
                "group_rank": run.get("group_rank", ""),
                "archive": run.get("archive", ""),
                "pcx_name": run.get("pcx_name", ""),
                "frontier_id": run.get("frontier_id", ""),
                "run_index": run.get("run_index", ""),
                "run_value_hex": run.get("run_value_hex", ""),
                "run_length": int_value(run, "run_length"),
                "run_start": run_start,
                "nearest_value_offset": chosen,
                "offset_delta": chosen - run_start,
                "context_key": context_key(context),
                "context_hex": context.hex(),
                "left_hex": left_context.hex(),
                "right_hex": right_context.hex(),
                "verdict": "value_context_review",
            }
        )

    group_map: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in contexts:
        group_map[str(row["context_key"])].append(row)

    groups: list[dict[str, object]] = []
    for key, rows in group_map.items():
        value_length_counts = Counter((row["run_value_hex"], row["run_length"]) for row in rows)
        repeated_value_length_rows = [
            row for row in rows if value_length_counts[(row["run_value_hex"], row["run_length"])] > 1
        ]
        groups.append(
            {
                "rank": 0,
                "group_key": key,
                "rows": len(rows),
                "bytes": sum(int(row["run_length"]) for row in rows),
                "values": ";".join(sorted({str(row["run_value_hex"]) for row in rows})),
                "lengths": ";".join(str(value) for value in sorted({int(row["run_length"]) for row in rows})),
                "fixtures": len({(row["archive"], row["pcx_name"], row["frontier_id"]) for row in rows}),
                "offset_deltas": ";".join(str(value) for value in sorted({int(row["offset_delta"]) for row in rows})),
                "repeated_value_length_rows": len(repeated_value_length_rows),
                "repeated_value_length_bytes": sum(int(row["run_length"]) for row in repeated_value_length_rows),
                "sample_context_hex": rows[0]["context_hex"],
                "sample_pcx": rows[0]["pcx_name"],
                "sample_frontier_id": rows[0]["frontier_id"],
                "verdict": "repeated_context_review" if len(rows) > 1 else "singleton_context_review",
            }
        )

    groups.sort(key=lambda row: (-int(row["rows"]), -int(row["bytes"]), str(row["group_key"])))
    group_rank = {str(row["group_key"]): index for index, row in enumerate(groups, start=1)}
    for index, row in enumerate(groups, start=1):
        row["rank"] = index
    contexts.sort(key=lambda row: (group_rank[str(row["context_key"])], int(row["source_rank"]), int(row["run_index"])))
    for index, row in enumerate(contexts, start=1):
        row["rank"] = index

    repeated_groups = [row for row in groups if int(row["rows"]) > 1]
    summary = {
        "scope": "total",
        "run_rows": len(run_rows),
        "value_hit_rows": len(contexts),
        "value_hit_bytes": sum(int(row["run_length"]) for row in contexts),
        "context_groups": len(groups),
        "repeated_context_groups": len(repeated_groups),
        "repeated_context_rows": sum(int(row["rows"]) for row in repeated_groups),
        "repeated_context_bytes": sum(int(row["bytes"]) for row in repeated_groups),
        "repeated_value_length_context_rows": sum(int(row["repeated_value_length_rows"]) for row in repeated_groups),
        "repeated_value_length_context_bytes": sum(int(row["repeated_value_length_bytes"]) for row in repeated_groups),
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues),
    }
    return summary, contexts, groups


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    contexts: list[dict[str, object]],
    groups: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps({"summary": summary, "contexts": contexts, "groups": groups}, indent=2, sort_keys=True)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #111416; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1700px; }}
th, td {{ border: 1px solid #31424a; padding: .45rem .55rem; vertical-align: top; }}
th {{ color: #9dafb5; background: #172023; text-align: left; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: .75rem; margin: 1rem 0; }}
.box {{ border: 1px solid #31424a; background: #172023; padding: .75rem; }}
.num {{ font-size: 1.35rem; font-weight: 750; }}
.muted {{ color: #9dafb5; }}
.panel {{ overflow-x: auto; margin-top: 1rem; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="grid">
  <div class="box"><div class="num">{summary['value_hit_rows']}</div><div class="muted">value-hit rows</div></div>
  <div class="box"><div class="num">{summary['context_groups']}</div><div class="muted">context groups</div></div>
  <div class="box"><div class="num">{summary['repeated_context_bytes']}</div><div class="muted">repeated context bytes</div></div>
  <div class="box"><div class="num">{summary['repeated_value_length_context_bytes']}</div><div class="muted">repeated value/length bytes</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Groups</h2>{render_table(groups, GROUP_FIELDNAMES)}</div>
<div class="panel"><h2>Contexts</h2>{render_table(contexts, CONTEXT_FIELDNAMES)}</div>
<script type="application/json" id="stable-value-context-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Group stable source local value opcode contexts.")
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--radius", type=int, default=4)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Micro Stable Value Context")
    args = parser.parse_args()

    summary, contexts, groups = build(read_rows(args.runs), read_rows(args.fixtures), radius=args.radius)
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "contexts.csv", CONTEXT_FIELDNAMES, contexts)
    write_csv(args.output / "groups.csv", GROUP_FIELDNAMES, groups)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, contexts, groups, args.title))

    print(f"Value-hit rows: {summary['value_hit_rows']}")
    print(f"Context groups: {summary['context_groups']}")
    print(f"Repeated context bytes: {summary['repeated_context_bytes']}")
    print(f"Repeated value/length bytes: {summary['repeated_value_length_context_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
