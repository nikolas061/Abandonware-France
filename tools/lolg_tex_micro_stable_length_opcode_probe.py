#!/usr/bin/env python3
"""Probe local opcode neighborhoods around stable alternation length bytes."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path


DEFAULT_REPLAYS = Path("output/tex_micro_stable_alternation_replay/replays.csv")
DEFAULT_BEST = Path("output/tex_micro_stable_length_control/best_by_segment.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_OUTPUT = Path("output/tex_micro_stable_length_opcode")

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_rows",
    "candidate_bytes",
    "direct_after_rows",
    "direct_after_bytes",
    "direct_before_rows",
    "direct_before_bytes",
    "nearby_value_run_rows",
    "nearby_value_run_bytes",
    "fc_near_rows",
    "ff_near_rows",
    "repeated_context_rows",
    "repeated_context_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

ROW_FIELDNAMES = [
    "rank",
    "segment_rank",
    "source_rank",
    "group_rank",
    "archive",
    "pcx_name",
    "frontier_id",
    "run_index",
    "value_hex",
    "length",
    "offset",
    "prev4_hex",
    "next4_hex",
    "context_key",
    "direct_after",
    "direct_before",
    "nearby_value_run",
    "nearest_value_run_offset",
    "nearest_value_run_delta",
    "has_fc_near",
    "has_ff_near",
    "verdict",
]

GROUP_FIELDNAMES = [
    "rank",
    "context_key",
    "rows",
    "bytes",
    "lengths",
    "values",
    "offsets",
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


def int_value(row: dict[str, str] | dict[str, object], field: str) -> int:
    try:
        return int(row.get(field, "") or 0)
    except (TypeError, ValueError):
        return 0


def locator_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def parse_lengths(text: str) -> list[int]:
    return [int(part) for part in text.split(";") if part.isdigit()]


def parse_values(text: str) -> list[int]:
    values: list[int] = []
    for part in text.split(";"):
        part = part.strip()
        if not part:
            continue
        values.append(int(part, 16) if part.startswith("0x") else int(part))
    return values


def parse_offsets(text: str) -> list[int]:
    return [int(part) for part in text.split(";") if part.isdigit()]


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def build_fixture_map(fixture_rows: list[dict[str, str]]) -> tuple[dict[tuple[str, str, str], bytes], list[str]]:
    segments: dict[tuple[str, str, str], bytes] = {}
    issues: list[str] = []
    for fixture in fixture_rows:
        local_issues: list[str] = []
        segments[locator_key(fixture)] = load_bytes(fixture.get("segment_gap_path", ""), local_issues, "segment_gap")
        issues.extend(f"{locator_key(fixture)}:{issue}" for issue in local_issues)
    return segments, issues


def bytes_hex(data: bytes, start: int, end: int) -> str:
    return data[max(0, start) : min(len(data), end)].hex()


def direct_run(data: bytes, start: int, value: int, length: int) -> bool:
    if start < 0 or start + length > len(data):
        return False
    return data[start : start + length] == bytes([value]) * length


def nearest_value_run(data: bytes, offset: int, value: int, length: int, radius: int) -> tuple[bool, int, int]:
    best_offset = -1
    best_delta = 999999
    for start in range(max(0, offset - radius), min(len(data), offset + radius + 1)):
        if direct_run(data, start, value, length):
            delta = start - offset
            if abs(delta) < abs(best_delta):
                best_offset = start
                best_delta = delta
    return best_offset >= 0, best_offset, best_delta if best_offset >= 0 else 0


def make_context_key(data: bytes, offset: int) -> str:
    return f"p2={bytes_hex(data, offset - 2, offset)}|n2={bytes_hex(data, offset + 1, offset + 3)}"


def build(
    replay_rows: list[dict[str, str]],
    best_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    *,
    radius: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    segments, issues = build_fixture_map(fixture_rows)
    replays_by_rank = {row.get("rank", ""): row for row in replay_rows}
    rows: list[dict[str, object]] = []

    for best in best_rows:
        offsets = parse_offsets(best.get("best_offsets", ""))
        if not offsets or best.get("best_pool") != "segment_gap":
            continue
        replay = replays_by_rank.get(best.get("segment_rank", ""), {})
        lengths = parse_lengths(best.get("lengths", ""))
        values = parse_values(replay.get("values", ""))
        segment = segments.get(locator_key(replay), b"")
        if not values:
            issues.append(f"{locator_key(replay)}:missing_values")
            continue
        if len(offsets) != len(lengths):
            issues.append(f"{locator_key(replay)}:offset_length_count_mismatch")
            continue
        for run_index, (offset, length) in enumerate(zip(offsets, lengths), start=1):
            value = values[(run_index - 1) % len(values)]
            after = direct_run(segment, offset + 1, value, length)
            before = direct_run(segment, offset - length, value, length)
            nearby, nearest_offset, nearest_delta = nearest_value_run(segment, offset, value, length, radius)
            near = segment[max(0, offset - radius) : min(len(segment), offset + radius + 1)]
            has_fc = 0xFC in near
            has_ff = 0xFF in near
            verdict = (
                "length_opcode_direct_after_candidate"
                if after
                else "length_opcode_direct_before_candidate"
                if before
                else "length_opcode_nearby_value_review"
                if nearby
                else "length_opcode_local_value_missing"
            )
            rows.append(
                {
                    "rank": len(rows) + 1,
                    "segment_rank": best.get("segment_rank", ""),
                    "source_rank": best.get("source_rank", ""),
                    "group_rank": best.get("group_rank", ""),
                    "archive": replay.get("archive", ""),
                    "pcx_name": best.get("pcx_name", ""),
                    "frontier_id": best.get("frontier_id", ""),
                    "run_index": run_index,
                    "value_hex": f"0x{value:02x}",
                    "length": length,
                    "offset": offset,
                    "prev4_hex": bytes_hex(segment, offset - 4, offset),
                    "next4_hex": bytes_hex(segment, offset + 1, offset + 5),
                    "context_key": make_context_key(segment, offset),
                    "direct_after": 1 if after else 0,
                    "direct_before": 1 if before else 0,
                    "nearby_value_run": 1 if nearby else 0,
                    "nearest_value_run_offset": nearest_offset if nearby else "",
                    "nearest_value_run_delta": nearest_delta if nearby else "",
                    "has_fc_near": 1 if has_fc else 0,
                    "has_ff_near": 1 if has_ff else 0,
                    "verdict": verdict,
                }
            )

    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["context_key"])].append(row)
    group_rows: list[dict[str, object]] = []
    for context_key, group in grouped.items():
        if len(group) < 2:
            continue
        lengths = sorted({str(row["length"]) for row in group})
        values = sorted({str(row["value_hex"]) for row in group})
        group_rows.append(
            {
                "rank": 0,
                "context_key": context_key,
                "rows": len(group),
                "bytes": sum(int_value(row, "length") for row in group),
                "lengths": ";".join(lengths),
                "values": ";".join(values),
                "offsets": ";".join(str(row["offset"]) for row in group),
                "verdict": "repeated_context_stable" if len(lengths) == 1 and len(values) == 1 else "repeated_context_conflict",
            }
        )
    group_rows.sort(key=lambda row: (-int_value(row, "bytes"), str(row["context_key"])))
    for index, row in enumerate(group_rows, start=1):
        row["rank"] = index

    repeated_context_bytes = sum(int_value(row, "bytes") for row in group_rows)
    summary = {
        "scope": "total",
        "candidate_rows": len(rows),
        "candidate_bytes": sum(int_value(row, "length") for row in rows),
        "direct_after_rows": sum(int_value(row, "direct_after") for row in rows),
        "direct_after_bytes": sum(int_value(row, "length") for row in rows if int_value(row, "direct_after")),
        "direct_before_rows": sum(int_value(row, "direct_before") for row in rows),
        "direct_before_bytes": sum(int_value(row, "length") for row in rows if int_value(row, "direct_before")),
        "nearby_value_run_rows": sum(int_value(row, "nearby_value_run") for row in rows),
        "nearby_value_run_bytes": sum(int_value(row, "length") for row in rows if int_value(row, "nearby_value_run")),
        "fc_near_rows": sum(int_value(row, "has_fc_near") for row in rows),
        "ff_near_rows": sum(int_value(row, "has_ff_near") for row in rows),
        "repeated_context_rows": len(group_rows),
        "repeated_context_bytes": repeated_context_bytes,
        "promotion_ready_bytes": 0,
        "issue_rows": len(issues),
    }
    return summary, rows, group_rows


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    rows: list[dict[str, object]],
    groups: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps({"summary": summary, "rows": rows, "groups": groups}, indent=2, sort_keys=True)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #111416; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1500px; }}
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
  <div class="box"><div class="num">{summary['candidate_bytes']}</div><div class="muted">candidate bytes</div></div>
  <div class="box"><div class="num">{summary['direct_after_bytes']}</div><div class="muted">direct after bytes</div></div>
  <div class="box"><div class="num">{summary['direct_before_bytes']}</div><div class="muted">direct before bytes</div></div>
  <div class="box"><div class="num">{summary['nearby_value_run_bytes']}</div><div class="muted">nearby value-run bytes</div></div>
  <div class="box"><div class="num">{summary['repeated_context_bytes']}</div><div class="muted">repeated context bytes</div></div>
</div>
<div class="panel"><h2>Candidates</h2>{render_table(rows, ROW_FIELDNAMES)}</div>
<div class="panel"><h2>Repeated Contexts</h2>{render_table(groups, GROUP_FIELDNAMES)}</div>
<script type="application/json" id="stable-length-opcode-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe local opcode neighborhoods around stable length candidates.")
    parser.add_argument("--replays", type=Path, default=DEFAULT_REPLAYS)
    parser.add_argument("--best", type=Path, default=DEFAULT_BEST)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--radius", type=int, default=8)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Micro Stable Length Opcode")
    args = parser.parse_args()

    summary, rows, groups = build(
        read_rows(args.replays),
        read_rows(args.best),
        read_rows(args.fixtures),
        radius=args.radius,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "candidates.csv", ROW_FIELDNAMES, rows)
    write_csv(args.output / "context_groups.csv", GROUP_FIELDNAMES, groups)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, rows, groups, args.title))

    print(f"Candidate bytes: {summary['candidate_bytes']}")
    print(f"Direct after bytes: {summary['direct_after_bytes']}")
    print(f"Direct before bytes: {summary['direct_before_bytes']}")
    print(f"Nearby value-run bytes: {summary['nearby_value_run_bytes']}")
    print(f"Repeated context bytes: {summary['repeated_context_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
