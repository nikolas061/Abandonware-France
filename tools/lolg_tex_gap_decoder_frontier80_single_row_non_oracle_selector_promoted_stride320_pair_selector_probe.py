#!/usr/bin/env python3
"""Probe stride-320 paired-run selectors after the single-row source promotion."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from pathlib import Path

from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_neighborhood_probe import read_csv
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_pair_selector_probe"
)
DEFAULT_PAIRS = Path("output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_run_review/stride320_pairs.csv")
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CLEAN_FIXTURES = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_single_row_delta_non_oracle_selector_promoted_replay/fixtures.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "pair_rows",
    "total_pair_bytes",
    "source_known_bytes",
    "target_known_bytes",
    "largest_pair_length",
    "top_pair_targets",
    "top_pair_raw_exact_bytes",
    "top_pair_small_delta_le2_bytes",
    "top_pair_small_delta_le4_bytes",
    "top_pair_best_constant_delta",
    "top_pair_best_constant_exact_bytes",
    "top_pair_position_mode_leave_one_out_exact_bytes",
    "exact_raw_pair_rows",
    "exact_raw_pair_bytes",
    "promotion_ready_bytes",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

PAIR_FIELDNAMES = [
    "pair_rank",
    "target_a",
    "target_b",
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "length",
    "start_a",
    "start_b",
    "stride",
    "source_known_bytes",
    "target_known_bytes",
    "raw_exact_bytes",
    "small_delta_le2_bytes",
    "small_delta_le4_bytes",
    "best_constant_delta",
    "best_constant_exact_bytes",
    "position_mode_leave_one_out_exact_bytes",
    "top_delta",
    "top_delta_count",
    "delta_histogram_json",
    "head_delta",
    "tail_delta",
]

BYTE_FIELDNAMES = [
    "target_a",
    "target_b",
    "byte_index",
    "source_offset",
    "target_offset",
    "source_value",
    "target_value",
    "delta",
    "raw_exact",
    "position_mode_leave_one_out_delta",
    "position_mode_leave_one_out_exact",
]


def int_field(row: dict[str, str], field: str, default: int = 0) -> int:
    try:
        return int(row.get(field, ""))
    except (TypeError, ValueError):
        return default


def signed_delta(source: int, target: int) -> int:
    delta = (target - source) & 0xFF
    return delta - 256 if delta >= 128 else delta


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"{label}:read_failed:{exc}")
        return b""


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def exact_with_delta(source: bytes, target: bytes, delta: int) -> int:
    return sum(1 for source_value, target_value in zip(source, target) if ((source_value + delta) & 0xFF) == target_value)


def best_constant_delta(source: bytes, target: bytes, *, delta_min: int = -8, delta_max: int = 8) -> tuple[int, int]:
    best_delta = 0
    best_exact = -1
    for delta in range(delta_min, delta_max + 1):
        exact = exact_with_delta(source, target, delta)
        if exact > best_exact:
            best_delta = delta
            best_exact = exact
    return best_delta, max(0, best_exact)


def position_mode_deltas(records: list[dict[str, object]], current: dict[str, object]) -> dict[int, int]:
    length = int(current["length"])
    modes: dict[int, int] = {}
    for position in range(length):
        counter: Counter[int] = Counter()
        for record in records:
            if record is current or int(record["length"]) <= position:
                continue
            deltas = record["deltas"]
            assert isinstance(deltas, list)
            counter[int(deltas[position])] += 1
        modes[position] = counter.most_common(1)[0][0] if counter else 0
    return modes


def build_records(
    pairs: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
    clean_rows: list[dict[str, str]],
    issues: list[str],
) -> list[dict[str, object]]:
    manifest_by_key = {fixture_key(row): row for row in manifest_rows}
    clean_by_key = {fixture_key(row): row for row in clean_rows}
    records: list[dict[str, object]] = []
    for pair in pairs:
        key = fixture_key(pair)
        manifest = manifest_by_key.get(key)
        clean = clean_by_key.get(key)
        if not manifest:
            issues.append(f"{key}:missing_manifest")
            continue
        if not clean:
            issues.append(f"{key}:missing_clean_fixture")
            continue
        expected = load_bytes(manifest.get("expected_gap_path", ""), issues, f"{key}:expected")
        mask = load_bytes(clean.get("known_mask_path", ""), issues, f"{key}:known_mask")
        start_a = int_field(pair, "start_a")
        start_b = int_field(pair, "start_b")
        length = int_field(pair, "length")
        source = expected[start_a : start_a + length]
        target = expected[start_b : start_b + length]
        source_mask = mask[start_a : start_a + length]
        target_mask = mask[start_b : start_b + length]
        if len(source) != length or len(target) != length:
            issues.append(f"{pair.get('target_a', '')}:{pair.get('target_b', '')}:short_expected")
            continue
        if len(source_mask) != length or len(target_mask) != length:
            issues.append(f"{pair.get('target_a', '')}:{pair.get('target_b', '')}:short_mask")
            continue
        deltas = [signed_delta(source_value, target_value) for source_value, target_value in zip(source, target)]
        records.append(
            {
                "pair": pair,
                "source": source,
                "target": target,
                "source_mask": source_mask,
                "target_mask": target_mask,
                "deltas": deltas,
                "length": length,
            }
        )
    records.sort(
        key=lambda record: (
            -int(record["length"]),
            int_field(record["pair"], "rank"),
            int_field(record["pair"], "frontier_id"),
            int_field(record["pair"], "start_a"),
        )
    )
    return records


def build_pair_rows(records: list[dict[str, object]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    mode_cache = {id(record): position_mode_deltas(records, record) for record in records}
    for pair_rank, record in enumerate(records, start=1):
        pair = record["pair"]
        source = record["source"]
        target = record["target"]
        source_mask = record["source_mask"]
        target_mask = record["target_mask"]
        deltas = record["deltas"]
        assert isinstance(pair, dict)
        assert isinstance(source, bytes)
        assert isinstance(target, bytes)
        assert isinstance(source_mask, bytes)
        assert isinstance(target_mask, bytes)
        assert isinstance(deltas, list)
        counter = Counter(int(delta) for delta in deltas)
        top_delta, top_count = counter.most_common(1)[0] if counter else (0, 0)
        best_delta, best_exact = best_constant_delta(source, target)
        modes = mode_cache[id(record)]
        mode_exact = sum(
            1
            for position, source_value in enumerate(source)
            if ((source_value + modes.get(position, 0)) & 0xFF) == target[position]
        )
        rows.append(
            {
                "pair_rank": str(pair_rank),
                "target_a": pair.get("target_a", ""),
                "target_b": pair.get("target_b", ""),
                "rank": pair.get("rank", ""),
                "archive": pair.get("archive", ""),
                "archive_tag": pair.get("archive_tag", ""),
                "pcx_name": pair.get("pcx_name", ""),
                "frontier_id": pair.get("frontier_id", ""),
                "length": pair.get("length", "0"),
                "start_a": pair.get("start_a", ""),
                "start_b": pair.get("start_b", ""),
                "stride": pair.get("stride", ""),
                "source_known_bytes": str(sum(1 for value in source_mask if value)),
                "target_known_bytes": str(sum(1 for value in target_mask if value)),
                "raw_exact_bytes": str(sum(1 for delta in deltas if delta == 0)),
                "small_delta_le2_bytes": str(sum(1 for delta in deltas if abs(delta) <= 2)),
                "small_delta_le4_bytes": str(sum(1 for delta in deltas if abs(delta) <= 4)),
                "best_constant_delta": str(best_delta),
                "best_constant_exact_bytes": str(best_exact),
                "position_mode_leave_one_out_exact_bytes": str(mode_exact),
                "top_delta": str(top_delta),
                "top_delta_count": str(top_count),
                "delta_histogram_json": json.dumps(dict(sorted(counter.items())), separators=(",", ":")),
                "head_delta": " ".join(str(delta) for delta in deltas[:16]),
                "tail_delta": " ".join(str(delta) for delta in deltas[-16:]),
            }
        )
    return rows


def build_byte_rows(records: list[dict[str, object]], limit_pairs: int = 1) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for record in records[:limit_pairs]:
        pair = record["pair"]
        source = record["source"]
        target = record["target"]
        deltas = record["deltas"]
        assert isinstance(pair, dict)
        assert isinstance(source, bytes)
        assert isinstance(target, bytes)
        assert isinstance(deltas, list)
        modes = position_mode_deltas(records, record)
        start_a = int_field(pair, "start_a")
        start_b = int_field(pair, "start_b")
        for position, delta in enumerate(deltas):
            mode_delta = modes.get(position, 0)
            rows.append(
                {
                    "target_a": pair.get("target_a", ""),
                    "target_b": pair.get("target_b", ""),
                    "byte_index": str(position),
                    "source_offset": str(start_a + position),
                    "target_offset": str(start_b + position),
                    "source_value": str(source[position]),
                    "target_value": str(target[position]),
                    "delta": str(delta),
                    "raw_exact": "1" if delta == 0 else "0",
                    "position_mode_leave_one_out_delta": str(mode_delta),
                    "position_mode_leave_one_out_exact": "1" if ((source[position] + mode_delta) & 0xFF) == target[position] else "0",
                }
            )
    return rows


def build_summary(records: list[dict[str, object]], pair_rows: list[dict[str, str]], issues: list[str]) -> dict[str, str]:
    total_bytes = sum(int(record["length"]) for record in records)
    source_known = sum(int_value(row, "source_known_bytes") for row in pair_rows)
    target_known = sum(int_value(row, "target_known_bytes") for row in pair_rows)
    exact_raw_pairs = [
        row for row in pair_rows if int_value(row, "raw_exact_bytes") == int_value(row, "length") and int_value(row, "length") > 0
    ]
    top = pair_rows[0] if pair_rows else {}
    largest_length = int_value(top, "length")
    top_le4 = int_value(top, "small_delta_le4_bytes")
    if largest_length and top_le4 < largest_length:
        verdict = "frontier80_stride320_pair_selector_local_delta_transform_needed"
        next_probe = "derive local delta transform for 96-byte stride-320 pair"
    elif exact_raw_pairs and source_known == 0:
        verdict = "frontier80_stride320_pair_selector_source_dependency_needed"
        next_probe = "derive source dependencies for exact stride-320 paired runs"
    elif exact_raw_pairs:
        verdict = "frontier80_stride320_pair_selector_copy_candidates_ready"
        next_probe = "promote known-source stride-320 paired run copies"
    else:
        verdict = "frontier80_stride320_pair_selector_split_needed"
        next_probe = "split stride-320 paired runs by local delta context"
    return {
        "scope": "total",
        "pair_rows": str(len(records)),
        "total_pair_bytes": str(total_bytes),
        "source_known_bytes": str(source_known),
        "target_known_bytes": str(target_known),
        "largest_pair_length": str(largest_length),
        "top_pair_targets": ";".join(value for value in (top.get("target_a", ""), top.get("target_b", "")) if value),
        "top_pair_raw_exact_bytes": top.get("raw_exact_bytes", "0"),
        "top_pair_small_delta_le2_bytes": top.get("small_delta_le2_bytes", "0"),
        "top_pair_small_delta_le4_bytes": top.get("small_delta_le4_bytes", "0"),
        "top_pair_best_constant_delta": top.get("best_constant_delta", "0"),
        "top_pair_best_constant_exact_bytes": top.get("best_constant_exact_bytes", "0"),
        "top_pair_position_mode_leave_one_out_exact_bytes": top.get("position_mode_leave_one_out_exact_bytes", "0"),
        "exact_raw_pair_rows": str(len(exact_raw_pairs)),
        "exact_raw_pair_bytes": str(sum(int_value(row, "length") for row in exact_raw_pairs)),
        "promotion_ready_bytes": "0",
        "issue_rows": str(len(issues)),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }


def table_html(title: str, filename: str, rows: list[dict[str, str]], fields: list[str], limit: int = 64) -> str:
    if not rows:
        return f"<section><h2>{html.escape(title)}</h2><p>No rows.</p></section>"
    headers = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = []
    for row in rows[:limit]:
        body.append("<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>")
    return (
        f"<section><h2>{html.escape(title)}</h2><p><a href=\"{html.escape(filename)}\">"
        f"{html.escape(filename)}</a></p><table><thead><tr>{headers}</tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table></section>"
    )


def build_html(
    summary: dict[str, str],
    pair_rows: list[dict[str, str]],
    byte_rows: list[dict[str, str]],
    title: str,
) -> str:
    summary_json = html.escape(json.dumps(summary, indent=2))
    stats = "".join(
        f"<div class=\"stat\"><div class=\"label\">{html.escape(key)}</div>"
        f"<div class=\"value\">{html.escape(summary.get(key, ''))}</div></div>"
        for key in (
            "largest_pair_length",
            "top_pair_raw_exact_bytes",
            "top_pair_small_delta_le4_bytes",
            "top_pair_position_mode_leave_one_out_exact_bytes",
            "exact_raw_pair_bytes",
            "review_verdict",
        )
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: sans-serif; margin: 24px; color: #1f2933; }}
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
    .stat {{ border: 1px solid #d8dee4; border-radius: 6px; padding: 10px; background: #f8fafc; }}
    .label {{ font-size: 12px; color: #52606d; }}
    .value {{ font-weight: 700; overflow-wrap: anywhere; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 12px; margin-top: 8px; }}
    th, td {{ border: 1px solid #d8dee4; padding: 4px 6px; text-align: left; vertical-align: top; }}
    th {{ background: #eef2f7; }}
    pre {{ background: #f6f8fa; padding: 12px; overflow: auto; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <div class="stats">{stats}</div>
  <h2>Summary</h2>
  <pre>{summary_json}</pre>
  {table_html("Stride-320 pair candidates", "pair_rows.csv", pair_rows, PAIR_FIELDNAMES)}
  {table_html("Top pair byte deltas", "top_pair_byte_rows.csv", byte_rows, BYTE_FIELDNAMES)}
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--pairs", type=Path, default=DEFAULT_PAIRS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Stride-320 Paired Run Selector Probe",
    )
    args = parser.parse_args()

    issues: list[str] = []
    records = build_records(read_csv(args.pairs), read_csv(args.manifest), read_csv(args.clean_fixtures), issues)
    pair_rows = build_pair_rows(records)
    byte_rows = build_byte_rows(records)
    summary = build_summary(records, pair_rows, issues)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "pair_rows.csv", PAIR_FIELDNAMES, pair_rows)
    write_csv(args.output / "top_pair_byte_rows.csv", BYTE_FIELDNAMES, byte_rows)
    (args.output / "issues.txt").write_text("\n".join(issues))
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, pair_rows, byte_rows, args.title))

    print(
        "Stride-320 paired runs: "
        f"top={summary['top_pair_targets']}, "
        f"raw={summary['top_pair_raw_exact_bytes']}/"
        f"{summary['largest_pair_length']}, "
        f"le4={summary['top_pair_small_delta_le4_bytes']}"
    )
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
