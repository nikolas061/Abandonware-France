#!/usr/bin/env python3
"""Probe control/fragment pools for stable alternation length sequences."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path


DEFAULT_REPLAYS = Path("output/tex_micro_stable_alternation_replay/replays.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_OUTPUT = Path("output/tex_micro_stable_length_control")

SUMMARY_FIELDNAMES = [
    "scope",
    "segment_rows",
    "segment_bytes",
    "pool_rows",
    "ordered_pool_rows",
    "ordered_pool_bytes",
    "compact_pool_rows",
    "compact_pool_bytes",
    "unique_pool_rows",
    "unique_pool_bytes",
    "best_pool",
    "best_pool_ordered_bytes",
    "suffix_best_pool",
    "suffix_best_span",
    "suffix_best_gap_total",
    "promotion_ready_bytes",
    "issue_rows",
]

POOL_FIELDNAMES = [
    "rank",
    "segment_rank",
    "source_rank",
    "group_rank",
    "archive",
    "pcx_name",
    "frontier_id",
    "pool",
    "pool_bytes",
    "segment_bytes",
    "lengths",
    "is_suffix",
    "ordered_match_count",
    "best_offsets",
    "best_span",
    "best_gap_total",
    "compact_match",
    "unique_ordered_match",
    "verdict",
]

BEST_FIELDNAMES = [
    "rank",
    "segment_rank",
    "source_rank",
    "group_rank",
    "pcx_name",
    "frontier_id",
    "segment_bytes",
    "lengths",
    "is_suffix",
    "best_pool",
    "best_offsets",
    "best_span",
    "best_gap_total",
    "best_ordered_match_count",
    "best_compact_match",
    "best_unique_ordered_match",
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


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def load_pools(fixture_rows: list[dict[str, str]]) -> tuple[dict[tuple[str, str, str], dict[str, bytes]], list[str]]:
    pools: dict[tuple[str, str, str], dict[str, bytes]] = {}
    issues: list[str] = []
    for fixture in fixture_rows:
        local_issues: list[str] = []
        pools[locator_key(fixture)] = {
            "segment_gap": load_bytes(fixture.get("segment_gap_path", ""), local_issues, "segment_gap"),
            "control_prefix": load_bytes(fixture.get("control_prefix_path", ""), local_issues, "control_prefix"),
            "fragment": load_bytes(fixture.get("fragment_path", ""), local_issues, "fragment"),
        }
        issues.extend(f"{locator_key(fixture)}:{issue}" for issue in local_issues)
    return pools, issues


def parse_lengths(text: str) -> list[int]:
    return [int(part) for part in text.split(";") if part.isdigit()]


def format_offsets(offsets: list[int]) -> str:
    return ";".join(str(value) for value in offsets)


def find_ordered_matches(data: bytes, lengths: list[int], *, max_matches: int, max_span: int) -> list[list[int]]:
    positions_by_length = [
        [index for index, value in enumerate(data) if value == (length & 0xFF)]
        for length in lengths
    ]
    if not lengths or any(not positions for positions in positions_by_length):
        return []
    matches: list[list[int]] = []

    def visit(depth: int, previous: int, offsets: list[int]) -> None:
        if len(matches) >= max_matches:
            return
        if depth == len(lengths):
            matches.append(offsets.copy())
            return
        first = offsets[0] if offsets else None
        for position in positions_by_length[depth]:
            if position <= previous:
                continue
            if first is not None and position - first + 1 > max_span:
                continue
            offsets.append(position)
            visit(depth + 1, position, offsets)
            offsets.pop()

    visit(0, -1, [])
    matches.sort(key=lambda offsets: (offsets[-1] - offsets[0], sum(b - a - 1 for a, b in zip(offsets, offsets[1:])), offsets))
    return matches[:max_matches]


def metrics(offsets: list[int], count: int) -> tuple[int, int, bool]:
    if not offsets:
        return 0, 0, False
    span = offsets[-1] - offsets[0] + 1
    gap_total = sum(right - left - 1 for left, right in zip(offsets, offsets[1:]))
    return span, gap_total, span == count


def pool_score(row: dict[str, object]) -> tuple[int, int, int, int]:
    return (
        int(row["ordered_match_count"]) > 0,
        int(row["compact_match"]),
        -int(row["best_span"]) if int(row["best_span"]) else -999999,
        -int(row["best_gap_total"]) if int(row["best_span"]) else -999999,
    )


def build(
    replay_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    *,
    max_matches: int,
    max_span: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    pools_by_fixture, pool_issues = load_pools(fixture_rows)
    pool_rows: list[dict[str, object]] = []
    best_rows: list[dict[str, object]] = []

    for replay in replay_rows:
        lengths = parse_lengths(replay.get("lengths", ""))
        segment_rank = int_value(replay, "rank")
        local_pool_rows: list[dict[str, object]] = []
        for pool_name, data in pools_by_fixture.get(locator_key(replay), {}).items():
            matches = find_ordered_matches(data, lengths, max_matches=max_matches, max_span=max_span)
            best = matches[0] if matches else []
            span, gap_total, compact = metrics(best, len(lengths))
            row = {
                "rank": 0,
                "segment_rank": segment_rank,
                "source_rank": replay.get("source_rank", ""),
                "group_rank": replay.get("group_rank", ""),
                "archive": replay.get("archive", ""),
                "pcx_name": replay.get("pcx_name", ""),
                "frontier_id": replay.get("frontier_id", ""),
                "pool": pool_name,
                "pool_bytes": len(data),
                "segment_bytes": replay.get("segment_bytes", ""),
                "lengths": replay.get("lengths", ""),
                "is_suffix": replay.get("is_suffix", ""),
                "ordered_match_count": len(matches),
                "best_offsets": format_offsets(best),
                "best_span": span,
                "best_gap_total": gap_total,
                "compact_match": 1 if compact else 0,
                "unique_ordered_match": 1 if len(matches) == 1 and bool(best) else 0,
                "verdict": "control_length_compact_candidate"
                if compact
                else "control_length_ordered_review"
                if best
                else "control_length_missing",
            }
            pool_rows.append(row)
            local_pool_rows.append(row)
        best = max(local_pool_rows, key=pool_score, default={})
        best_rows.append(
            {
                "rank": len(best_rows) + 1,
                "segment_rank": segment_rank,
                "source_rank": replay.get("source_rank", ""),
                "group_rank": replay.get("group_rank", ""),
                "pcx_name": replay.get("pcx_name", ""),
                "frontier_id": replay.get("frontier_id", ""),
                "segment_bytes": replay.get("segment_bytes", ""),
                "lengths": replay.get("lengths", ""),
                "is_suffix": replay.get("is_suffix", ""),
                "best_pool": best.get("pool", ""),
                "best_offsets": best.get("best_offsets", ""),
                "best_span": best.get("best_span", 0),
                "best_gap_total": best.get("best_gap_total", 0),
                "best_ordered_match_count": best.get("ordered_match_count", 0),
                "best_compact_match": best.get("compact_match", 0),
                "best_unique_ordered_match": best.get("unique_ordered_match", 0),
                "verdict": best.get("verdict", "control_length_missing"),
            }
        )

    for index, row in enumerate(pool_rows, start=1):
        row["rank"] = index
    ordered = [row for row in pool_rows if int(row["ordered_match_count"]) > 0]
    compact = [row for row in pool_rows if int(row["compact_match"]) > 0]
    unique = [row for row in pool_rows if int(row["unique_ordered_match"]) > 0]
    suffix_best = [row for row in best_rows if str(row["is_suffix"]) == "1"]
    best_pool_counts: dict[str, int] = {}
    for row in best_rows:
        best_pool_counts[str(row["best_pool"])] = best_pool_counts.get(str(row["best_pool"]), 0) + int_value(row, "segment_bytes")
    best_pool = max(best_pool_counts.items(), key=lambda item: item[1], default=("", 0))
    summary = {
        "scope": "total",
        "segment_rows": len(best_rows),
        "segment_bytes": sum(int_value(row, "segment_bytes") for row in best_rows),
        "pool_rows": len(pool_rows),
        "ordered_pool_rows": len(ordered),
        "ordered_pool_bytes": sum(int_value(row, "segment_bytes") for row in ordered),
        "compact_pool_rows": len(compact),
        "compact_pool_bytes": sum(int_value(row, "segment_bytes") for row in compact),
        "unique_pool_rows": len(unique),
        "unique_pool_bytes": sum(int_value(row, "segment_bytes") for row in unique),
        "best_pool": best_pool[0],
        "best_pool_ordered_bytes": best_pool[1],
        "suffix_best_pool": suffix_best[0]["best_pool"] if suffix_best else "",
        "suffix_best_span": suffix_best[0]["best_span"] if suffix_best else 0,
        "suffix_best_gap_total": suffix_best[0]["best_gap_total"] if suffix_best else 0,
        "promotion_ready_bytes": 0,
        "issue_rows": len(pool_issues),
    }
    return summary, pool_rows, best_rows


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    pools: list[dict[str, object]],
    best: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps({"summary": summary, "pools": pools, "best": best}, indent=2, sort_keys=True)
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
  <div class="box"><div class="num">{summary['ordered_pool_bytes']}</div><div class="muted">ordered pool bytes</div></div>
  <div class="box"><div class="num">{summary['compact_pool_bytes']}</div><div class="muted">compact pool bytes</div></div>
  <div class="box"><div class="num">{summary['best_pool']}</div><div class="muted">best pool</div></div>
  <div class="box"><div class="num">{summary['suffix_best_pool']}</div><div class="muted">suffix best pool</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Best by Segment</h2>{render_table(best, BEST_FIELDNAMES)}</div>
<div class="panel"><h2>Pools</h2>{render_table(pools, POOL_FIELDNAMES)}</div>
<script type="application/json" id="stable-length-control-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe control pools for stable alternation length sequences.")
    parser.add_argument("--replays", type=Path, default=DEFAULT_REPLAYS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--max-matches", type=int, default=20)
    parser.add_argument("--max-span", type=int, default=512)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Micro Stable Length Control")
    args = parser.parse_args()

    summary, pools, best = build(
        read_rows(args.replays),
        read_rows(args.fixtures),
        max_matches=args.max_matches,
        max_span=args.max_span,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "pools.csv", POOL_FIELDNAMES, pools)
    write_csv(args.output / "best_by_segment.csv", BEST_FIELDNAMES, best)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, pools, best, args.title))

    print(f"Ordered pool bytes: {summary['ordered_pool_bytes']}")
    print(f"Compact pool bytes: {summary['compact_pool_bytes']}")
    print(f"Best pool: {summary['best_pool']}")
    print(f"Suffix best pool: {summary['suffix_best_pool']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
