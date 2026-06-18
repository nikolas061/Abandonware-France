#!/usr/bin/env python3
"""Profile source dependencies for the stride-320 bounded prefix."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from lolg_tex_gap_decoder_frontier80_context_split_residual_low_payload_neighborhood_probe import read_csv
from lolg_tex_gap_opcode_probe import int_value, write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_source_dependency_probe"
)
DEFAULT_PAIR_ROWS = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_pair_selector_probe/pair_rows.csv"
)
DEFAULT_LOCAL_DELTA_SUMMARY = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_local_delta_transform_probe/summary.csv"
)
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_CLEAN_FIXTURES = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_single_row_delta_non_oracle_selector_promoted_replay/fixtures.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "top_pair_targets",
    "source_prefix_bytes",
    "source_start",
    "target_start",
    "best_support_start",
    "best_support_shift",
    "best_support_exact_bytes",
    "best_support_small_delta_le2_bytes",
    "best_support_small_delta_le4_bytes",
    "best_support_known_bytes",
    "best_support_ready_source_bytes",
    "best_support_blocker_bytes",
    "best_support_blocker_positions",
    "best_support_delta_min",
    "best_support_delta_max",
    "remaining_source_bytes",
    "remaining_source_offsets",
    "tail_exact_support_rows",
    "tail_le4_support_rows",
    "promotion_ready_bytes",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

CANDIDATE_FIELDNAMES = [
    "candidate_rank",
    "support_start",
    "source_start",
    "support_shift",
    "prefix_bytes",
    "exact_bytes",
    "small_delta_le2_bytes",
    "small_delta_le4_bytes",
    "support_known_bytes",
    "source_unknown_bytes",
    "ready_source_bytes",
    "blocker_bytes",
    "blocker_positions",
    "delta_min",
    "delta_max",
    "head_deltas",
    "tail_deltas",
]

BYTE_FIELDNAMES = [
    "byte_index",
    "support_offset",
    "source_offset",
    "support_value",
    "source_value",
    "delta",
    "abs_delta",
    "support_known",
    "source_known",
    "source_missing",
    "support_le4",
    "dependency_ready",
    "blocker_reason",
]

TAIL_SUPPORT_FIELDNAMES = [
    "source_byte_index",
    "source_offset",
    "source_value",
    "candidate_rank",
    "candidate_archive_tag",
    "candidate_pcx_name",
    "candidate_frontier_id",
    "candidate_offset",
    "candidate_value",
    "delta",
    "abs_delta",
    "same_fixture",
]


def int_field(row: dict[str, str], field: str, default: int = 0) -> int:
    try:
        return int(row.get(field, ""))
    except (TypeError, ValueError):
        return default


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def signed_delta(source: int, target: int) -> int:
    delta = (target - source) & 0xFF
    return delta - 256 if delta >= 128 else delta


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"{label}:read_failed:{exc}")
        return b""


def positions_text(positions: list[int]) -> str:
    return ";".join(str(position) for position in positions)


def build_candidate_rows(expected: bytes, mask: bytes, source_start: int, prefix: int) -> list[dict[str, str]]:
    source = expected[source_start : source_start + prefix]
    source_mask = mask[source_start : source_start + prefix]
    source_unknown = sum(1 for value in source_mask if not value)
    rows: list[dict[str, str]] = []
    if len(source) != prefix or len(source_mask) != prefix:
        return rows

    for support_start in range(0, len(expected) - prefix + 1):
        if support_start == source_start:
            continue
        support = expected[support_start : support_start + prefix]
        support_mask = mask[support_start : support_start + prefix]
        deltas = [signed_delta(support_value, source_value) for support_value, source_value in zip(support, source)]
        ready_positions = [
            index
            for index, delta in enumerate(deltas)
            if not source_mask[index] and support_mask[index] and abs(delta) <= 4
        ]
        blocker_positions = [
            index
            for index, delta in enumerate(deltas)
            if not source_mask[index] and not (support_mask[index] and abs(delta) <= 4)
        ]
        rows.append(
            {
                "candidate_rank": "0",
                "support_start": str(support_start),
                "source_start": str(source_start),
                "support_shift": str(support_start - source_start),
                "prefix_bytes": str(prefix),
                "exact_bytes": str(sum(1 for delta in deltas if delta == 0)),
                "small_delta_le2_bytes": str(sum(1 for delta in deltas if abs(delta) <= 2)),
                "small_delta_le4_bytes": str(sum(1 for delta in deltas if abs(delta) <= 4)),
                "support_known_bytes": str(sum(1 for value in support_mask if value)),
                "source_unknown_bytes": str(source_unknown),
                "ready_source_bytes": str(len(ready_positions)),
                "blocker_bytes": str(len(blocker_positions)),
                "blocker_positions": positions_text(blocker_positions),
                "delta_min": str(min(deltas) if deltas else 0),
                "delta_max": str(max(deltas) if deltas else 0),
                "head_deltas": " ".join(str(delta) for delta in deltas[:16]),
                "tail_deltas": " ".join(str(delta) for delta in deltas[-16:]),
            }
        )

    rows.sort(
        key=lambda row: (
            -int_value(row, "ready_source_bytes"),
            -int_value(row, "small_delta_le4_bytes"),
            -int_value(row, "support_known_bytes"),
            abs(int_value(row, "support_shift")),
            -int_value(row, "exact_bytes"),
            int_value(row, "support_start"),
        )
    )
    for candidate_rank, row in enumerate(rows, start=1):
        row["candidate_rank"] = str(candidate_rank)
    return rows


def blocker_reason(source_known: bool, support_known: bool, support_le4: bool) -> str:
    if source_known:
        return "source_already_known"
    if not support_known:
        return "support_unknown"
    if not support_le4:
        return "delta_outlier"
    return "ready"


def build_byte_rows(expected: bytes, mask: bytes, source_start: int, support_start: int, prefix: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    source = expected[source_start : source_start + prefix]
    source_mask = mask[source_start : source_start + prefix]
    support = expected[support_start : support_start + prefix]
    support_mask = mask[support_start : support_start + prefix]
    if len(source) != prefix or len(support) != prefix:
        return rows
    for index, (support_value, source_value) in enumerate(zip(support, source)):
        delta = signed_delta(support_value, source_value)
        source_known = bool(source_mask[index])
        support_known = bool(support_mask[index])
        support_le4 = abs(delta) <= 4
        ready = (not source_known) and support_known and support_le4
        rows.append(
            {
                "byte_index": str(index),
                "support_offset": str(support_start + index),
                "source_offset": str(source_start + index),
                "support_value": str(support_value),
                "source_value": str(source_value),
                "delta": str(delta),
                "abs_delta": str(abs(delta)),
                "support_known": "1" if support_known else "0",
                "source_known": "1" if source_known else "0",
                "source_missing": "0" if source_known else "1",
                "support_le4": "1" if support_le4 else "0",
                "dependency_ready": "1" if ready else "0",
                "blocker_reason": blocker_reason(source_known, support_known, support_le4),
            }
        )
    return rows


def build_tail_support_rows(
    source_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
    clean_rows: list[dict[str, str]],
    top_key: tuple[str, str, str],
    issues: list[str],
    *,
    per_byte_limit: int,
) -> list[dict[str, str]]:
    clean_by_key = {fixture_key(row): row for row in clean_rows}
    fixtures: list[tuple[dict[str, str], bytes, bytes]] = []
    for manifest in manifest_rows:
        key = fixture_key(manifest)
        clean = clean_by_key.get(key)
        if not clean:
            continue
        expected = load_bytes(manifest.get("expected_gap_path", ""), issues, f"{key}:expected")
        mask = load_bytes(clean.get("known_mask_path", ""), issues, f"{key}:known_mask")
        if expected and mask:
            fixtures.append((manifest, expected, mask))

    rows: list[dict[str, str]] = []
    for source_row in source_rows:
        source_value = int_value(source_row, "source_value")
        source_offset = int_value(source_row, "source_offset")
        source_byte_index = source_row.get("byte_index", "")
        candidates: list[dict[str, str]] = []
        for manifest, expected, mask in fixtures:
            key = fixture_key(manifest)
            for offset, (candidate_value, known) in enumerate(zip(expected, mask)):
                if not known:
                    continue
                delta = signed_delta(candidate_value, source_value)
                if abs(delta) > 4:
                    continue
                candidates.append(
                    {
                        "source_byte_index": source_byte_index,
                        "source_offset": str(source_offset),
                        "source_value": str(source_value),
                        "candidate_rank": manifest.get("rank", ""),
                        "candidate_archive_tag": manifest.get("archive_tag", ""),
                        "candidate_pcx_name": manifest.get("pcx_name", ""),
                        "candidate_frontier_id": manifest.get("frontier_id", ""),
                        "candidate_offset": str(offset),
                        "candidate_value": str(candidate_value),
                        "delta": str(delta),
                        "abs_delta": str(abs(delta)),
                        "same_fixture": "1" if key == top_key else "0",
                    }
                )
        candidates.sort(
            key=lambda row: (
                int_value(row, "abs_delta"),
                0 if row.get("same_fixture") == "1" else 1,
                int_value(row, "candidate_rank"),
                int_value(row, "candidate_frontier_id"),
                int_value(row, "candidate_offset"),
            )
        )
        rows.extend(candidates[:per_byte_limit])
    return rows


def build_summary(
    pair: dict[str, str],
    local_summary: dict[str, str],
    candidate_rows: list[dict[str, str]],
    byte_rows: list[dict[str, str]],
    tail_support_rows: list[dict[str, str]],
    issues: list[str],
) -> dict[str, str]:
    top = candidate_rows[0] if candidate_rows else {}
    remaining_rows = [row for row in byte_rows if row.get("dependency_ready") != "1" and row.get("source_missing") == "1"]
    remaining_offsets = [row.get("source_offset", "") for row in remaining_rows]
    tail_exact = sum(1 for row in tail_support_rows if row.get("delta") == "0")
    tail_le4 = len(tail_support_rows)
    ready = int_value(top, "ready_source_bytes")
    prefix = int_value(top, "prefix_bytes") or int_value(local_summary, "bounded_prefix_bytes")
    if ready >= max(0, prefix - 1) and remaining_rows and tail_exact:
        verdict = "frontier80_stride320_source_dependency_prefix32_ready_tail_selector_needed"
        next_probe = (
            "derive tail source byte selector for offset "
            f"{';'.join(remaining_offsets)} then guard 32-byte source prefix dependency"
        )
    elif ready == prefix and prefix:
        verdict = "frontier80_stride320_source_dependency_prefix_ready"
        next_probe = "promote guarded source prefix support for stride-320 local delta transform"
    elif ready:
        verdict = "frontier80_stride320_source_dependency_partial_support_needed"
        next_probe = "derive additional source support windows for stride-320 bounded prefix"
    else:
        verdict = "frontier80_stride320_source_dependency_no_local_support"
        next_probe = "return to corpus source dependency search for stride-320 bounded prefix"

    return {
        "scope": "top_pair_source_prefix",
        "top_pair_targets": ";".join(value for value in (pair.get("target_a", ""), pair.get("target_b", "")) if value),
        "source_prefix_bytes": str(prefix),
        "source_start": pair.get("start_a", "0"),
        "target_start": pair.get("start_b", "0"),
        "best_support_start": top.get("support_start", "0"),
        "best_support_shift": top.get("support_shift", "0"),
        "best_support_exact_bytes": top.get("exact_bytes", "0"),
        "best_support_small_delta_le2_bytes": top.get("small_delta_le2_bytes", "0"),
        "best_support_small_delta_le4_bytes": top.get("small_delta_le4_bytes", "0"),
        "best_support_known_bytes": top.get("support_known_bytes", "0"),
        "best_support_ready_source_bytes": str(ready),
        "best_support_blocker_bytes": top.get("blocker_bytes", "0"),
        "best_support_blocker_positions": top.get("blocker_positions", ""),
        "best_support_delta_min": top.get("delta_min", "0"),
        "best_support_delta_max": top.get("delta_max", "0"),
        "remaining_source_bytes": str(len(remaining_rows)),
        "remaining_source_offsets": ";".join(remaining_offsets),
        "tail_exact_support_rows": str(tail_exact),
        "tail_le4_support_rows": str(tail_le4),
        "promotion_ready_bytes": "0",
        "issue_rows": str(len(issues)),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }


def table_html(title: str, filename: str, rows: list[dict[str, str]], fields: list[str], limit: int = 96) -> str:
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
    candidate_rows: list[dict[str, str]],
    byte_rows: list[dict[str, str]],
    tail_support_rows: list[dict[str, str]],
    title: str,
) -> str:
    summary_json = html.escape(json.dumps(summary, indent=2))
    stats = "".join(
        f"<div class=\"stat\"><div class=\"label\">{html.escape(key)}</div>"
        f"<div class=\"value\">{html.escape(summary.get(key, ''))}</div></div>"
        for key in (
            "source_prefix_bytes",
            "best_support_start",
            "best_support_ready_source_bytes",
            "remaining_source_bytes",
            "tail_exact_support_rows",
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
  {table_html("Same-fixture support candidates", "support_candidates.csv", candidate_rows, CANDIDATE_FIELDNAMES)}
  {table_html("Best support byte dependencies", "byte_dependency_rows.csv", byte_rows, BYTE_FIELDNAMES)}
  {table_html("Tail byte support rows", "tail_support_rows.csv", tail_support_rows, TAIL_SUPPORT_FIELDNAMES)}
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--pair-rows", type=Path, default=DEFAULT_PAIR_ROWS)
    parser.add_argument("--local-delta-summary", type=Path, default=DEFAULT_LOCAL_DELTA_SUMMARY)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--clean-fixtures", type=Path, default=DEFAULT_CLEAN_FIXTURES)
    parser.add_argument("--tail-support-limit", type=int, default=64)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Stride-320 Source Dependency Probe",
    )
    args = parser.parse_args()

    issues: list[str] = []
    pair_rows = read_csv(args.pair_rows)
    local_summary_rows = read_csv(args.local_delta_summary)
    manifest_rows = read_csv(args.manifest)
    clean_rows = read_csv(args.clean_fixtures)
    if not pair_rows:
        issues.append(f"missing_pair_rows:{args.pair_rows}")
    pair = pair_rows[0] if pair_rows else {}
    local_summary = local_summary_rows[0] if local_summary_rows else {}
    prefix = int_value(local_summary, "bounded_prefix_bytes") or min(33, int_value(pair, "length"))
    source_start = int_value(pair, "start_a")
    target_key = fixture_key(pair)
    manifest_by_key = {fixture_key(row): row for row in manifest_rows}
    clean_by_key = {fixture_key(row): row for row in clean_rows}
    manifest = manifest_by_key.get(target_key)
    clean = clean_by_key.get(target_key)
    if not manifest:
        issues.append(f"{target_key}:missing_manifest")
    if not clean:
        issues.append(f"{target_key}:missing_clean_fixture")
    expected = load_bytes(manifest.get("expected_gap_path", "") if manifest else "", issues, f"{target_key}:expected")
    mask = load_bytes(clean.get("known_mask_path", "") if clean else "", issues, f"{target_key}:known_mask")

    candidate_rows = build_candidate_rows(expected, mask, source_start, prefix) if expected and mask else []
    best_support_start = int_value(candidate_rows[0], "support_start") if candidate_rows else 0
    byte_rows = build_byte_rows(expected, mask, source_start, best_support_start, prefix) if candidate_rows else []
    remaining_rows = [row for row in byte_rows if row.get("dependency_ready") != "1" and row.get("source_missing") == "1"]
    tail_support_rows = build_tail_support_rows(
        remaining_rows,
        manifest_rows,
        clean_rows,
        target_key,
        issues,
        per_byte_limit=args.tail_support_limit,
    )
    summary = build_summary(pair, local_summary, candidate_rows, byte_rows, tail_support_rows, issues)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "support_candidates.csv", CANDIDATE_FIELDNAMES, candidate_rows)
    write_csv(args.output / "byte_dependency_rows.csv", BYTE_FIELDNAMES, byte_rows)
    write_csv(args.output / "tail_support_rows.csv", TAIL_SUPPORT_FIELDNAMES, tail_support_rows)
    (args.output / "issues.txt").write_text("\n".join(issues))
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, candidate_rows, byte_rows, tail_support_rows, args.title))

    print(
        "Stride-320 source dependency: "
        f"support={summary['best_support_start']}->{summary['source_start']}, "
        f"ready={summary['best_support_ready_source_bytes']}/{summary['source_prefix_bytes']}, "
        f"remaining={summary['remaining_source_offsets']}"
    )
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
