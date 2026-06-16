#!/usr/bin/env python3
"""Probe unresolved source chunks behind stable micro-token backrefs."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_BACKREF_TARGETS = Path("output/tex_micro_stable_backrefs/targets.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_REPLAY_FIXTURES = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_fill_replay/fixtures.csv")
DEFAULT_OUTPUT = Path("output/tex_micro_stable_sources")

SUMMARY_FIELDNAMES = [
    "scope",
    "source_rows",
    "source_bytes",
    "candidate_rows_evaluated",
    "candidate_rows_written",
    "full_match_rows",
    "best_exact_bytes_total",
    "best_prefix_bytes_total",
    "best_single_exact_bytes",
    "best_single_prefix_bytes",
    "best_pool",
    "best_transform",
    "best_offset_delta",
    "known_source_bytes_before_probe",
    "promotion_ready_bytes",
    "issue_rows",
]

SOURCE_FIELDNAMES = [
    "rank",
    "group_rank",
    "archive",
    "pcx_name",
    "frontier_id",
    "start",
    "end",
    "length",
    "expected_run_key",
    "known_mask_bytes",
    "best_pool",
    "best_offset",
    "best_offset_delta",
    "best_transform",
    "best_parameter",
    "best_prefix_bytes",
    "best_exact_bytes",
    "best_full_match",
    "expected_head_hex",
    "best_source_head_hex",
    "best_output_head_hex",
    "verdict",
    "issues",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "group_rank",
    "archive",
    "pcx_name",
    "frontier_id",
    "start",
    "end",
    "length",
    "pool",
    "offset",
    "offset_delta",
    "transform",
    "parameter",
    "prefix_bytes",
    "exact_bytes",
    "full_match",
    "expected_head_hex",
    "source_head_hex",
    "output_head_hex",
]

GROUP_FIELDNAMES = [
    "kind",
    "key",
    "rows",
    "bytes",
    "full_match_rows",
    "exact_bytes",
    "prefix_bytes",
    "sample_pcx",
    "sample_frontier_id",
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


def load_fixture_pools(fixture_rows: list[dict[str, str]], replay_rows: list[dict[str, str]]) -> tuple[dict[tuple[str, str, str], dict[str, bytes]], list[str]]:
    pools: dict[tuple[str, str, str], dict[str, bytes]] = {}
    issues: list[str] = []
    for fixture in fixture_rows:
        key = locator_key(fixture)
        local_issues: list[str] = []
        pools[key] = {
            "expected": load_bytes(fixture.get("expected_gap_path", ""), local_issues, "expected"),
            "segment_gap": load_bytes(fixture.get("segment_gap_path", ""), local_issues, "segment_gap"),
            "control_prefix": load_bytes(fixture.get("control_prefix_path", ""), local_issues, "control_prefix"),
            "fragment": load_bytes(fixture.get("fragment_path", ""), local_issues, "fragment"),
        }
        issues.extend(f"{key}:{issue}" for issue in local_issues)

    for replay in replay_rows:
        key = locator_key(replay)
        local_issues = []
        pools.setdefault(key, {})
        pools[key]["decoded_replay"] = load_bytes(replay.get("decoded_path", ""), local_issues, "decoded_replay")
        pools[key]["known_mask"] = load_bytes(replay.get("known_mask_path", ""), local_issues, "known_mask")
        issues.extend(f"{key}:{issue}" for issue in local_issues)
    return pools, issues


def common_prefix(left: bytes, right: bytes) -> int:
    for index, (left_value, right_value) in enumerate(zip(left, right)):
        if left_value != right_value:
            return index
    return min(len(left), len(right))


def exact_count(left: bytes, right: bytes) -> int:
    return sum(1 for left_value, right_value in zip(left, right) if left_value == right_value)


def run_key(data: bytes) -> str:
    if not data:
        return "empty"
    runs: list[str] = []
    current = data[0]
    count = 1
    for value in data[1:]:
        if value == current:
            count += 1
            continue
        runs.append(f"{current:02x}x{count}")
        current = value
        count = 1
    runs.append(f"{current:02x}x{count}")
    preview = ".".join(runs[:14])
    suffix = "..." if len(runs) > 14 else ""
    return f"runs={len(runs)}|{preview}{suffix}"


def transform_rows(source: bytes, expected: bytes) -> list[tuple[str, str, bytes]]:
    rows: list[tuple[str, str, bytes]] = [
        ("identity", "", source),
        ("low7", "", bytes(value & 0x7F for value in source)),
        ("highbit_set", "", bytes(value | 0x80 for value in source)),
        ("bit_not", "", bytes(value ^ 0xFF for value in source)),
        ("nibble_swap", "", bytes(((value & 0x0F) << 4) | (value >> 4) for value in source)),
    ]
    if source and expected:
        xor_value = source[0] ^ expected[0]
        add_value = (expected[0] - source[0]) & 0xFF
        rows.extend(
            [
                ("xor_prefix", f"0x{xor_value:02x}", bytes(value ^ xor_value for value in source)),
                ("add_prefix", f"0x{add_value:02x}", bytes((value + add_value) & 0xFF for value in source)),
            ]
        )
    return rows


def candidate_offsets(pool_length: int, length: int, start: int, search_radius: int, full_search_limit: int) -> list[int]:
    if length <= 0 or pool_length < length:
        return []
    max_start = pool_length - length
    if pool_length <= full_search_limit:
        return list(range(max_start + 1))
    left = max(0, start - search_radius)
    right = min(max_start, start + search_radius)
    return list(range(left, right + 1))


def score_candidate(
    target: dict[str, str],
    expected: bytes,
    pool: str,
    offset: int,
    source: bytes,
    transform: str,
    parameter: str,
    output: bytes,
) -> dict[str, object]:
    prefix = common_prefix(output, expected)
    exact = exact_count(output, expected)
    length = len(expected)
    return {
        "rank": target.get("rank", ""),
        "group_rank": target.get("group_rank", ""),
        "archive": target.get("archive", ""),
        "pcx_name": target.get("pcx_name", ""),
        "frontier_id": target.get("frontier_id", ""),
        "start": target.get("start", ""),
        "end": target.get("end", ""),
        "length": length,
        "pool": pool,
        "offset": offset,
        "offset_delta": offset - int_value(target, "start"),
        "transform": transform,
        "parameter": parameter,
        "prefix_bytes": prefix,
        "exact_bytes": exact,
        "full_match": 1 if length and exact == length else 0,
        "expected_head_hex": expected[:16].hex(),
        "source_head_hex": source[:16].hex(),
        "output_head_hex": output[:16].hex(),
    }


def candidate_sort_key(row: dict[str, object]) -> tuple[int, int, int, int, int]:
    transform_rank = {
        "identity": 0,
        "low7": 1,
        "highbit_set": 2,
        "nibble_swap": 3,
        "bit_not": 4,
        "xor_prefix": 5,
        "add_prefix": 6,
    }.get(str(row.get("transform", "")), 99)
    pool_rank = {
        "decoded_replay": 0,
        "segment_gap": 1,
        "control_prefix": 2,
        "fragment": 3,
    }.get(str(row.get("pool", "")), 99)
    return (
        int(row.get("full_match", 0)),
        int(row.get("exact_bytes", 0)),
        int(row.get("prefix_bytes", 0)),
        -abs(int(row.get("offset_delta", 999999))),
        -((pool_rank * 100) + transform_rank),
    )


def build_group_rows(best_rows: list[dict[str, object]], kind: str) -> list[dict[str, object]]:
    counters: dict[str, Counter[str]] = defaultdict(Counter)
    samples: dict[str, dict[str, object]] = {}
    for row in best_rows:
        key = str(row.get(kind, ""))
        counters[key]["rows"] += 1
        counters[key]["bytes"] += int(row["length"])
        counters[key]["full_match_rows"] += int(row["full_match"])
        counters[key]["exact_bytes"] += int(row["exact_bytes"])
        counters[key]["prefix_bytes"] += int(row["prefix_bytes"])
        samples.setdefault(key, row)

    rows: list[dict[str, object]] = []
    for key, counter in counters.items():
        sample = samples[key]
        rows.append(
            {
                "kind": kind,
                "key": key,
                "rows": counter["rows"],
                "bytes": counter["bytes"],
                "full_match_rows": counter["full_match_rows"],
                "exact_bytes": counter["exact_bytes"],
                "prefix_bytes": counter["prefix_bytes"],
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    rows.sort(key=lambda row: (-int(row["exact_bytes"]), -int(row["prefix_bytes"]), str(row["key"])))
    return rows


def build(
    backref_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
    *,
    top_per_source: int,
    search_radius: int,
    full_search_limit: int,
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    pools_by_fixture, fixture_issues = load_fixture_pools(fixture_rows, replay_rows)
    source_rows = [
        row
        for row in backref_rows
        if row.get("best_exact") == "0" and row.get("verdict") == "blocked_review"
    ]
    source_outputs: list[dict[str, object]] = []
    candidates: list[dict[str, object]] = []
    best_rows: list[dict[str, object]] = []
    evaluated = 0

    for target in source_rows:
        issues = [issue for issue in target.get("issues", "").split(";") if issue]
        fixture_pools = pools_by_fixture.get(locator_key(target), {})
        expected_all = fixture_pools.get("expected", b"")
        mask = fixture_pools.get("known_mask", b"")
        start = int_value(target, "start")
        end = int_value(target, "end")
        expected = expected_all[start:end]
        if not expected:
            issues.append("missing_expected_chunk")
            continue
        known_mask_bytes = sum(1 for value in mask[start:end] if value) if len(mask) >= end else 0
        local_candidates: list[dict[str, object]] = []
        for pool_name in ("segment_gap", "control_prefix", "fragment"):
            pool_data = fixture_pools.get(pool_name, b"")
            for offset in candidate_offsets(len(pool_data), len(expected), start, search_radius, full_search_limit):
                source = pool_data[offset : offset + len(expected)]
                for transform, parameter, output in transform_rows(source, expected):
                    evaluated += 1
                    local_candidates.append(
                        score_candidate(target, expected, pool_name, offset, source, transform, parameter, output)
                    )

        local_candidates.sort(key=candidate_sort_key, reverse=True)
        best = local_candidates[0] if local_candidates else {}
        best_rows.extend(local_candidates[:1])
        candidates.extend(local_candidates[:top_per_source])
        source_outputs.append(
            {
                "rank": target.get("rank", ""),
                "group_rank": target.get("group_rank", ""),
                "archive": target.get("archive", ""),
                "pcx_name": target.get("pcx_name", ""),
                "frontier_id": target.get("frontier_id", ""),
                "start": start,
                "end": end,
                "length": len(expected),
                "expected_run_key": run_key(expected),
                "known_mask_bytes": known_mask_bytes,
                "best_pool": best.get("pool", ""),
                "best_offset": best.get("offset", ""),
                "best_offset_delta": best.get("offset_delta", ""),
                "best_transform": best.get("transform", ""),
                "best_parameter": best.get("parameter", ""),
                "best_prefix_bytes": best.get("prefix_bytes", 0),
                "best_exact_bytes": best.get("exact_bytes", 0),
                "best_full_match": best.get("full_match", 0),
                "expected_head_hex": expected[:16].hex(),
                "best_source_head_hex": best.get("source_head_hex", ""),
                "best_output_head_hex": best.get("output_head_hex", ""),
                "verdict": "full_source_match" if best.get("full_match") else "encoded_source_review",
                "issues": ";".join(issues),
            }
        )

    best_rows.sort(key=candidate_sort_key, reverse=True)
    candidates.sort(key=candidate_sort_key, reverse=True)
    by_pool = build_group_rows(best_rows, "pool")
    by_transform = build_group_rows(best_rows, "transform")
    best = best_rows[0] if best_rows else {}
    summary = {
        "scope": "total",
        "source_rows": len(source_outputs),
        "source_bytes": sum(int(row["length"]) for row in source_outputs),
        "candidate_rows_evaluated": evaluated,
        "candidate_rows_written": len(candidates),
        "full_match_rows": sum(int(row["best_full_match"]) for row in source_outputs),
        "best_exact_bytes_total": sum(int(row["best_exact_bytes"]) for row in source_outputs),
        "best_prefix_bytes_total": sum(int(row["best_prefix_bytes"]) for row in source_outputs),
        "best_single_exact_bytes": best.get("exact_bytes", 0),
        "best_single_prefix_bytes": best.get("prefix_bytes", 0),
        "best_pool": by_pool[0]["key"] if by_pool else "",
        "best_transform": by_transform[0]["key"] if by_transform else "",
        "best_offset_delta": best.get("offset_delta", ""),
        "known_source_bytes_before_probe": sum(int(row["known_mask_bytes"]) for row in source_outputs),
        "promotion_ready_bytes": 0,
        "issue_rows": sum(1 for row in source_outputs if row.get("issues")) + len(fixture_issues),
    }
    return summary, source_outputs, candidates, by_pool + by_transform


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 200) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    sources: list[dict[str, object]],
    candidates: list[dict[str, object]],
    groups: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {"summary": summary, "sources": sources, "candidates": candidates, "groups": groups},
        indent=2,
        sort_keys=True,
    )
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
  <div class="box"><div class="num">{summary['source_rows']}</div><div class="muted">source rows</div></div>
  <div class="box"><div class="num">{summary['source_bytes']}</div><div class="muted">source bytes</div></div>
  <div class="box"><div class="num">{summary['best_exact_bytes_total']}</div><div class="muted">best exact bytes</div></div>
  <div class="box"><div class="num">{summary['known_source_bytes_before_probe']}</div><div class="muted">known-source bytes before probe</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Sources</h2>{render_table(sources, SOURCE_FIELDNAMES)}</div>
<div class="panel"><h2>Groups</h2>{render_table(groups, GROUP_FIELDNAMES)}</div>
<div class="panel"><h2>Candidates</h2>{render_table(candidates, CANDIDATE_FIELDNAMES)}</div>
<script type="application/json" id="stable-source-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe unresolved sources behind stable .tex micro-token backrefs.")
    parser.add_argument("--backref-targets", type=Path, default=DEFAULT_BACKREF_TARGETS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--replay-fixtures", type=Path, default=DEFAULT_REPLAY_FIXTURES)
    parser.add_argument("--top-per-source", type=int, default=12)
    parser.add_argument("--search-radius", type=int, default=384)
    parser.add_argument("--full-search-limit", type=int, default=5000)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Micro Stable Sources")
    args = parser.parse_args()

    summary, sources, candidates, groups = build(
        read_rows(args.backref_targets),
        read_rows(args.fixtures),
        read_rows(args.replay_fixtures),
        top_per_source=args.top_per_source,
        search_radius=args.search_radius,
        full_search_limit=args.full_search_limit,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "sources.csv", SOURCE_FIELDNAMES, sources)
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(args.output / "groups.csv", GROUP_FIELDNAMES, groups)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, sources, candidates, groups, args.title))

    print(f"Source rows: {summary['source_rows']}")
    print(f"Source bytes: {summary['source_bytes']}")
    print(f"Best exact bytes: {summary['best_exact_bytes_total']}")
    print(f"Known-source bytes before probe: {summary['known_source_bytes_before_probe']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
