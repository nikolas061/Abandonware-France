#!/usr/bin/env python3
"""Probe local source candidates for promoted nonzero gap operations."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_source_probe")
DEFAULT_TARGETS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_source_probe/targets.csv")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "target_rows",
    "target_bytes",
    "control_ref_rows",
    "missing_control_ref_rows",
    "candidate_rows_evaluated",
    "candidate_rows_written",
    "best_rows",
    "full_match_rows",
    "best_exact_bytes_total",
    "best_prefix_bytes_total",
    "best_single_exact_bytes",
    "best_single_prefix_bytes",
    "best_transform",
    "best_offset_delta",
    "issue_rows",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "run_index",
    "op_index",
    "length",
    "expected_start",
    "expected_end",
    "control_ref_offset",
    "candidate_offset",
    "candidate_end",
    "offset_delta",
    "transform",
    "parameter",
    "prefix_bytes",
    "prefix_ratio",
    "exact_bytes",
    "exact_ratio",
    "full_match",
    "expected_head_hex",
    "source_head_hex",
    "output_head_hex",
    "issues",
]

TRANSFORM_FIELDNAMES = [
    "transform",
    "best_rows",
    "best_exact_bytes",
    "best_prefix_bytes",
    "full_match_rows",
    "sample_pcx",
    "sample_frontier_id",
]

OFFSET_FIELDNAMES = [
    "offset_delta",
    "best_rows",
    "best_exact_bytes",
    "best_prefix_bytes",
    "full_match_rows",
    "sample_transform",
    "sample_pcx",
    "sample_frontier_id",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def common_prefix(left: bytes, right: bytes) -> int:
    limit = min(len(left), len(right))
    for index in range(limit):
        if left[index] != right[index]:
            return index
    return limit


def exact_count(left: bytes, right: bytes) -> int:
    return sum(1 for lvalue, rvalue in zip(left, right) if lvalue == rvalue)


def transform_rows(source: bytes, expected: bytes) -> list[tuple[str, str, bytes]]:
    rows: list[tuple[str, str, bytes]] = [
        ("identity", "", source),
        ("bit_not", "", bytes(value ^ 0xFF for value in source)),
        ("nibble_swap", "", bytes(((value & 0x0F) << 4) | (value >> 4) for value in source)),
        ("low7", "", bytes(value & 0x7F for value in source)),
        ("highbit_set", "", bytes(value | 0x80 for value in source)),
    ]
    if source and expected:
        xor_const = source[0] ^ expected[0]
        add_const = (expected[0] - source[0]) & 0xFF
        rows.extend(
            [
                ("xor_prefix", f"0x{xor_const:02x}", bytes(value ^ xor_const for value in source)),
                ("add_prefix", f"0x{add_const:02x}", bytes((value + add_const) & 0xFF for value in source)),
            ]
        )
    return rows


def candidate_offsets(
    segment_length: int,
    target_length: int,
    control_ref: int,
    *,
    search_radius: int,
    missing_full_search: bool,
) -> list[int]:
    if target_length <= 0 or segment_length < target_length:
        return []
    max_start = segment_length - target_length
    if control_ref >= 0:
        start = max(0, control_ref - search_radius)
        end = min(max_start, control_ref + search_radius)
        return list(range(start, end + 1))
    if missing_full_search:
        return list(range(0, max_start + 1))
    return []


def score_candidate(
    target: dict[str, str],
    expected: bytes,
    source: bytes,
    *,
    candidate_offset: int,
    control_ref: int,
    transform: str,
    parameter: str,
    output: bytes,
) -> dict[str, str]:
    prefix = common_prefix(output, expected)
    exact = exact_count(output, expected)
    length = len(expected)
    full = length > 0 and exact == length
    offset_delta = "" if control_ref < 0 else str(candidate_offset - control_ref)
    return {
        "rank": target.get("rank", ""),
        "archive": target.get("archive", ""),
        "archive_tag": target.get("archive_tag", ""),
        "pcx_name": target.get("pcx_name", ""),
        "frontier_id": target.get("frontier_id", ""),
        "span_index": target.get("span_index", ""),
        "run_index": target.get("run_index", ""),
        "op_index": target.get("op_index", ""),
        "length": str(length),
        "expected_start": target.get("start", ""),
        "expected_end": target.get("end", ""),
        "control_ref_offset": "" if control_ref < 0 else str(control_ref),
        "candidate_offset": str(candidate_offset),
        "candidate_end": str(candidate_offset + length),
        "offset_delta": offset_delta or "missing",
        "transform": transform,
        "parameter": parameter,
        "prefix_bytes": str(prefix),
        "prefix_ratio": f"{(prefix / length) if length else 0.0:.6f}",
        "exact_bytes": str(exact),
        "exact_ratio": f"{(exact / length) if length else 0.0:.6f}",
        "full_match": "1" if full else "0",
        "expected_head_hex": expected[:16].hex(),
        "source_head_hex": source[:16].hex(),
        "output_head_hex": output[:16].hex(),
        "issues": "",
    }


def best_sort_key(row: dict[str, str]) -> tuple[int, int, int, int, str]:
    delta = row.get("offset_delta", "")
    abs_delta = abs(int(delta)) if delta.lstrip("-").isdigit() else 999999
    transform_rank = {
        "identity": 0,
        "low7": 1,
        "highbit_set": 2,
        "nibble_swap": 3,
        "bit_not": 4,
        "xor_prefix": 5,
        "add_prefix": 6,
    }.get(row.get("transform", ""), 99)
    return (
        int_value(row, "exact_bytes"),
        int_value(row, "prefix_bytes"),
        -abs_delta,
        -transform_rank,
        row.get("candidate_offset", ""),
    )


def build_rows(
    target_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    *,
    search_radius: int,
    top_per_target: int,
    missing_full_search: bool,
) -> tuple[
    dict[str, str],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    fixtures = {fixture_key(row): row for row in fixture_rows}
    fixture_bytes: dict[tuple[str, str, str], tuple[bytes, bytes]] = {}
    issues: list[str] = []
    for key, fixture in fixtures.items():
        local_issues: list[str] = []
        segment = load_bytes(fixture.get("segment_gap_path", ""), local_issues, "segment")
        expected = load_bytes(fixture.get("expected_gap_path", ""), local_issues, "expected")
        fixture_bytes[key] = segment, expected
        issues.extend(f"{key}:{issue}" for issue in local_issues)

    gap_targets = [
        row
        for row in target_rows
        if row.get("op_kind") == "gap" and not row.get("issues")
    ]
    candidate_rows: list[dict[str, str]] = []
    best_rows: list[dict[str, str]] = []
    evaluated = 0

    for target in gap_targets:
        key = fixture_key(target)
        segment, expected_all = fixture_bytes.get(key, (b"", b""))
        start = int_value(target, "start")
        end = int_value(target, "end")
        expected = expected_all[start:end]
        length = len(expected)
        control_ref_text = target.get("control_ref_offset", "")
        control_ref = int(control_ref_text) if control_ref_text.isdigit() else -1
        local_candidates: list[dict[str, str]] = []
        for offset in candidate_offsets(
            len(segment),
            length,
            control_ref,
            search_radius=search_radius,
            missing_full_search=missing_full_search,
        ):
            source = segment[offset : offset + length]
            for transform, parameter, output in transform_rows(source, expected):
                evaluated += 1
                local_candidates.append(
                    score_candidate(
                        target,
                        expected,
                        source,
                        candidate_offset=offset,
                        control_ref=control_ref,
                        transform=transform,
                        parameter=parameter,
                        output=output,
                    )
                )
        local_candidates.sort(key=best_sort_key, reverse=True)
        best_rows.extend(local_candidates[:1])
        candidate_rows.extend(local_candidates[:top_per_target])

    best_rows.sort(key=best_sort_key, reverse=True)
    candidate_rows.sort(key=best_sort_key, reverse=True)

    by_transform: dict[str, Counter[str]] = defaultdict(Counter)
    transform_sample: dict[str, dict[str, str]] = {}
    by_offset: dict[str, Counter[str]] = defaultdict(Counter)
    offset_sample: dict[str, dict[str, str]] = {}
    for row in best_rows:
        transform = row.get("transform", "")
        by_transform[transform]["best_rows"] += 1
        by_transform[transform]["best_exact_bytes"] += int_value(row, "exact_bytes")
        by_transform[transform]["best_prefix_bytes"] += int_value(row, "prefix_bytes")
        by_transform[transform]["full_match_rows"] += 1 if row.get("full_match") == "1" else 0
        transform_sample.setdefault(transform, row)

        offset_delta = row.get("offset_delta", "") or "missing"
        by_offset[offset_delta]["best_rows"] += 1
        by_offset[offset_delta]["best_exact_bytes"] += int_value(row, "exact_bytes")
        by_offset[offset_delta]["best_prefix_bytes"] += int_value(row, "prefix_bytes")
        by_offset[offset_delta]["full_match_rows"] += 1 if row.get("full_match") == "1" else 0
        offset_sample.setdefault(offset_delta, row)

    transform_rows_out = []
    for transform, totals in by_transform.items():
        sample = transform_sample[transform]
        transform_rows_out.append(
            {
                "transform": transform,
                "best_rows": str(totals["best_rows"]),
                "best_exact_bytes": str(totals["best_exact_bytes"]),
                "best_prefix_bytes": str(totals["best_prefix_bytes"]),
                "full_match_rows": str(totals["full_match_rows"]),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    transform_rows_out.sort(
        key=lambda row: (-int_value(row, "best_exact_bytes"), -int_value(row, "best_rows"), row["transform"])
    )

    offset_rows_out = []
    for offset_delta, totals in by_offset.items():
        sample = offset_sample[offset_delta]
        offset_rows_out.append(
            {
                "offset_delta": offset_delta,
                "best_rows": str(totals["best_rows"]),
                "best_exact_bytes": str(totals["best_exact_bytes"]),
                "best_prefix_bytes": str(totals["best_prefix_bytes"]),
                "full_match_rows": str(totals["full_match_rows"]),
                "sample_transform": sample.get("transform", ""),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    offset_rows_out.sort(
        key=lambda row: (-int_value(row, "best_exact_bytes"), -int_value(row, "best_rows"), row["offset_delta"])
    )

    best = max(best_rows, key=best_sort_key, default={})
    top_transform = transform_rows_out[0] if transform_rows_out else {}
    top_offset = offset_rows_out[0] if offset_rows_out else {}
    summary = {
        "scope": "total",
        "target_rows": str(len(gap_targets)),
        "target_bytes": str(sum(int_value(row, "length") for row in gap_targets)),
        "control_ref_rows": str(sum(1 for row in gap_targets if row.get("control_ref_offset"))),
        "missing_control_ref_rows": str(sum(1 for row in gap_targets if not row.get("control_ref_offset"))),
        "candidate_rows_evaluated": str(evaluated),
        "candidate_rows_written": str(len(candidate_rows)),
        "best_rows": str(len(best_rows)),
        "full_match_rows": str(sum(1 for row in best_rows if row.get("full_match") == "1")),
        "best_exact_bytes_total": str(sum(int_value(row, "exact_bytes") for row in best_rows)),
        "best_prefix_bytes_total": str(sum(int_value(row, "prefix_bytes") for row in best_rows)),
        "best_single_exact_bytes": best.get("exact_bytes", "0"),
        "best_single_prefix_bytes": best.get("prefix_bytes", "0"),
        "best_transform": top_transform.get("transform", ""),
        "best_offset_delta": top_offset.get("offset_delta", ""),
        "issue_rows": str(len(issues)),
    }
    return summary, candidate_rows, best_rows, transform_rows_out, offset_rows_out


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    candidate_rows: list[dict[str, str]],
    best_rows: list[dict[str, str]],
    transform_rows: list[dict[str, str]],
    offset_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "candidates": candidate_rows,
        "bestByTarget": best_rows,
        "byTransform": transform_rows,
        "byOffsetDelta": offset_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
            ("best_by_target.csv", output_dir / "best_by_target.csv"),
            ("by_transform.csv", output_dir / "by_transform.csv"),
            ("by_offset_delta.csv", output_dir / "by_offset_delta.csv"),
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
  --warn: #f0c36a;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.wrap {{ width: min(1700px, calc(100vw - 28px)); margin: 0 auto; }}
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
.warn {{ color: var(--warn); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1500px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Scores local source windows around control references for nonzero gap operations.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Gap targets</div><div class="value">{summary['target_rows']}</div></div>
    <div class="stat"><div class="label">Gap bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="label">Best exact total</div><div class="value ok">{summary['best_exact_bytes_total']}</div></div>
    <div class="stat"><div class="label">Full matches</div><div class="value warn">{summary['full_match_rows']}</div></div>
    <div class="stat"><div class="label">Best transform</div><div class="value">{html.escape(summary['best_transform'])}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>By transform</h2>{render_table(transform_rows, TRANSFORM_FIELDNAMES, 80)}</section>
  <section class="panel"><h2>By offset delta</h2>{render_table(offset_rows, OFFSET_FIELDNAMES, 120)}</section>
  <section class="panel"><h2>Best by target</h2>{render_table(best_rows, CANDIDATE_FIELDNAMES, 260)}</section>
  <section class="panel"><h2>Candidate rows</h2>{render_table(candidate_rows, CANDIDATE_FIELDNAMES, 320)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_SOURCE_PROBE = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe source windows for promoted .tex nonzero gap operations.")
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--search-radius", type=int, default=384)
    parser.add_argument("--top-per-target", type=int, default=5)
    parser.add_argument("--no-missing-full-search", action="store_true")
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Source Probe",
    )
    args = parser.parse_args()

    summary, candidates, best_rows, transform_rows, offset_rows = build_rows(
        read_csv(args.targets),
        read_csv(args.fixtures),
        search_radius=args.search_radius,
        top_per_target=args.top_per_target,
        missing_full_search=not args.no_missing_full_search,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(args.output / "best_by_target.csv", CANDIDATE_FIELDNAMES, best_rows)
    write_csv(args.output / "by_transform.csv", TRANSFORM_FIELDNAMES, transform_rows)
    write_csv(args.output / "by_offset_delta.csv", OFFSET_FIELDNAMES, offset_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, candidates, best_rows, transform_rows, offset_rows, args.output, args.title))

    print(f"Gap targets: {summary['target_rows']}")
    print(f"Gap bytes: {summary['target_bytes']}")
    print(f"Best exact total: {summary['best_exact_bytes_total']}")
    print(f"Full matches: {summary['full_match_rows']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
