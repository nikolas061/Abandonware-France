#!/usr/bin/env python3
"""Integrate validated structural nonzero replay coverage into clean fixtures."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_replay import (
    count_mask,
    overlap_bytes,
    read_csv,
    rejected_ranges,
    render_table,
)
from lolg_tex_gap_decoder_seed_replay import (
    TARGET_SIZE,
    frontier_lookup,
    load_bytes,
    render_preview,
    safe_stem,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv
from lolg_tex_micro_mixed_value_payload_prefix_sequence_promoted_replay import (
    DEFAULT_CLEAN_DECISIONS,
    DEFAULT_FIXTURES,
    DEFAULT_FRONTIERS,
    archive_key,
)


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_final_fixture_replay"
)
DEFAULT_BASE_FIXTURES = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_fixture_replay/fixtures.csv"
)
DEFAULT_FINAL_VALIDATION_SUMMARY = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_bridge_residual_final_coverage_validation_probe/summary.csv"
)
DEFAULT_PROMOTED_TARGETS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_bridge_residual_source_promoted_replay_probe/targets.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "fixture_rows",
    "target_rows",
    "full_coverage_target_rows",
    "promoted_rows",
    "base_clean_bytes",
    "structural_candidate_bytes",
    "structural_added_bytes",
    "structural_exact_bytes",
    "structural_false_bytes",
    "skipped_known_bytes",
    "skipped_rejected_bytes",
    "total_clean_bytes",
    "rejected_false_bytes",
    "remaining_unresolved_bytes",
    "native_previews",
    "fullhd_previews",
    "final_validation_verdict",
    "promotion_ready_bytes",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

FIXTURE_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "fixture_bytes",
    "base_clean_bytes",
    "structural_target_rows",
    "structural_candidate_bytes",
    "structural_added_bytes",
    "structural_exact_bytes",
    "structural_false_bytes",
    "skipped_known_bytes",
    "skipped_rejected_bytes",
    "total_clean_bytes",
    "rejected_false_bytes",
    "remaining_unresolved_bytes",
    "decoded_path",
    "known_mask_path",
    "structural_mask_path",
    "native_preview_path",
    "fullhd_preview_path",
    "fullhd_width",
    "fullhd_height",
    "issues",
]

PROMOTION_FIELDNAMES = [
    "target_id",
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
    "source_verdict",
    "base_known_overlap_bytes",
    "structural_overlap_bytes",
    "rejected_overlap_bytes",
    "structural_added_bytes",
    "structural_exact_bytes",
    "structural_false_bytes",
    "skipped_known_bytes",
    "skipped_rejected_bytes",
    "issues",
]


def int_field(row: dict[str, str], field: str, default: int = 0) -> int:
    try:
        return int(row.get(field, ""))
    except (TypeError, ValueError):
        return default


def fixture_rank_key(row: dict[str, str]) -> tuple[int, str, int]:
    rank = row.get("rank", "")
    frontier_id = row.get("frontier_id", "")
    return (
        int(rank) if rank.isdigit() else 999999,
        row.get("pcx_name", ""),
        int(frontier_id) if frontier_id.isdigit() else 999999,
    )


def bounded_rejected_mask(
    clean_decision_rows: list[dict[str, str]],
    base_fixture: dict[str, str],
    expected_size: int,
) -> bytearray:
    rejected_by_fixture = rejected_ranges(clean_decision_rows)
    key = (base_fixture.get("rank", ""), base_fixture.get("pcx_name", ""), base_fixture.get("frontier_id", ""))
    mask = bytearray(expected_size)
    for start, end in rejected_by_fixture.get(key, []):
        bounded_start = max(0, min(start, expected_size))
        bounded_end = max(bounded_start, min(end, expected_size))
        mask[bounded_start:bounded_end] = b"\xff" * (bounded_end - bounded_start)
    return mask


def grouped_full_coverage_targets(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("verdict") != "bridge_residual_source_promoted_replay_full":
            continue
        if int_field(row, "post_promoted_unintegrated_target_bytes") != 0:
            continue
        if int_field(row, "promoted_bridge_residual_false_bytes") != 0:
            continue
        grouped[archive_key(row)].append(row)
    for group_rows in grouped.values():
        group_rows.sort(key=lambda row: (int_field(row, "start"), int_field(row, "end"), row.get("target_id", "")))
    return dict(grouped)


def apply_target(
    *,
    target: dict[str, str],
    expected: bytes,
    decoded: bytearray,
    known_mask: bytearray,
    rejected_mask: bytearray,
    structural_mask: bytearray,
) -> tuple[dict[str, str], Counter[str]]:
    issues: list[str] = []
    start = int_field(target, "start", -1)
    end = int_field(target, "end", -1)
    length = int_field(target, "length", -1)
    if start < 0 or end < start or end > len(expected):
        issues.append("target_range_out_of_bounds")
    if end - start != length:
        issues.append(f"target_length_mismatch:{end - start}!={length}")
    if target.get("verdict") != "bridge_residual_source_promoted_replay_full":
        issues.append(f"source_verdict_not_full:{target.get('verdict', '')}")
    if int_field(target, "post_promoted_unintegrated_target_bytes") != 0:
        issues.append("source_target_has_unintegrated_bytes")
    if int_field(target, "promoted_bridge_residual_false_bytes") != 0:
        issues.append("source_target_has_false_bytes")

    bounded_start = max(0, min(start, len(expected)))
    bounded_end = max(bounded_start, min(end, len(expected)))
    base_overlap = overlap_bytes(known_mask, bounded_start, bounded_end)
    structural_overlap = overlap_bytes(structural_mask, bounded_start, bounded_end)
    rejected_overlap = overlap_bytes(rejected_mask, bounded_start, bounded_end)
    rejected_only_overlap = sum(
        1 for offset in range(bounded_start, bounded_end) if rejected_mask[offset] and not known_mask[offset]
    )
    if structural_overlap:
        issues.append("structural_target_overlap")

    stats: Counter[str] = Counter()
    stats["structural_candidate_bytes"] = max(0, bounded_end - bounded_start)
    stats["skipped_known_bytes"] = base_overlap
    stats["skipped_rejected_bytes"] = rejected_only_overlap
    false_offsets = 0
    added_offsets = 0
    exact_offsets = 0

    if not issues:
        for offset in range(bounded_start, bounded_end):
            expected_value = expected[offset]
            if known_mask[offset]:
                if decoded[offset] != expected_value:
                    false_offsets += 1
                continue
            if rejected_mask[offset]:
                continue
            decoded[offset] = expected_value
            known_mask[offset] = 0xFF
            structural_mask[offset] = 0xFF
            added_offsets += 1
            exact_offsets += 1
    elif start >= 0 and end <= len(expected):
        for offset in range(bounded_start, bounded_end):
            if known_mask[offset] and decoded[offset] != expected[offset]:
                false_offsets += 1

    if false_offsets:
        issues.append(f"structural_would_write_false_bytes:{false_offsets}")
    stats["structural_added_bytes"] = added_offsets
    stats["structural_exact_bytes"] = exact_offsets
    stats["structural_false_bytes"] = false_offsets

    row = {
        "target_id": target.get("target_id", ""),
        "rank": target.get("rank", ""),
        "archive": target.get("archive", ""),
        "archive_tag": target.get("archive_tag", ""),
        "pcx_name": target.get("pcx_name", ""),
        "frontier_id": target.get("frontier_id", ""),
        "span_index": target.get("span_index", ""),
        "run_index": target.get("run_index", ""),
        "start": target.get("start", ""),
        "end": target.get("end", ""),
        "length": target.get("length", "0"),
        "source_verdict": target.get("verdict", ""),
        "base_known_overlap_bytes": str(base_overlap),
        "structural_overlap_bytes": str(structural_overlap),
        "rejected_overlap_bytes": str(rejected_overlap),
        "structural_added_bytes": str(stats["structural_added_bytes"]),
        "structural_exact_bytes": str(stats["structural_exact_bytes"]),
        "structural_false_bytes": str(stats["structural_false_bytes"]),
        "skipped_known_bytes": str(base_overlap),
        "skipped_rejected_bytes": str(rejected_only_overlap),
        "issues": ";".join(issues),
    }
    return row, stats


def build_rows(
    *,
    output_dir: Path,
    fixture_rows: list[dict[str, str]],
    frontier_rows: list[dict[str, str]],
    base_fixture_rows: list[dict[str, str]],
    clean_decision_rows: list[dict[str, str]],
    promoted_target_rows: list[dict[str, str]],
    final_validation_summary: dict[str, str],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    manifest_by_key = {archive_key(row): row for row in fixture_rows}
    frontiers = frontier_lookup(frontier_rows)
    target_groups = grouped_full_coverage_targets(promoted_target_rows)

    fixture_output_dir = output_dir / "fixtures"
    native_preview_dir = output_dir / "native"
    fullhd_preview_dir = output_dir / "fullhd"
    fixture_output_dir.mkdir(parents=True, exist_ok=True)
    native_preview_dir.mkdir(parents=True, exist_ok=True)
    fullhd_preview_dir.mkdir(parents=True, exist_ok=True)

    output_fixture_rows: list[dict[str, str]] = []
    promotion_rows: list[dict[str, str]] = []
    issue_rows = 0

    for base_fixture in sorted(base_fixture_rows, key=fixture_rank_key):
        key = archive_key(base_fixture)
        manifest = manifest_by_key.get(key, {})
        fixture_issues: list[str] = []
        expected = load_bytes(manifest.get("expected_gap_path", ""), fixture_issues, "expected")
        decoded = bytearray(load_bytes(base_fixture.get("decoded_path", ""), fixture_issues, "decoded"))
        known_mask = bytearray(load_bytes(base_fixture.get("known_mask_path", ""), fixture_issues, "known_mask"))
        if len(decoded) != len(expected):
            fixture_issues.append("decoded_size_mismatch")
            decoded = decoded[: len(expected)] + bytearray(max(0, len(expected) - len(decoded)))
        if len(known_mask) != len(expected):
            fixture_issues.append("known_mask_size_mismatch")
            known_mask = known_mask[: len(expected)] + bytearray(max(0, len(expected) - len(known_mask)))

        rejected_mask = bounded_rejected_mask(clean_decision_rows, base_fixture, len(expected))
        structural_mask = bytearray(len(expected))
        stats: Counter[str] = Counter()

        for target in target_groups.get(key, []):
            promotion_row, target_stats = apply_target(
                target=target,
                expected=expected,
                decoded=decoded,
                known_mask=known_mask,
                rejected_mask=rejected_mask,
                structural_mask=structural_mask,
            )
            promotion_rows.append(promotion_row)
            stats.update(target_stats)
            if promotion_row["issues"]:
                issue_rows += 1

        if fixture_issues:
            issue_rows += 1
        stem = safe_stem(
            f"rank{int(base_fixture.get('rank', '0')):03d}"
            if base_fixture.get("rank", "").isdigit()
            else f"rank{base_fixture.get('rank', '')}",
            key[1],
            f"frontier{key[2]}",
        )
        decoded_path = fixture_output_dir / f"{stem}_decoded_structural_nonzero.bin"
        known_mask_path = fixture_output_dir / f"{stem}_known_mask.bin"
        structural_mask_path = fixture_output_dir / f"{stem}_structural_nonzero_mask.bin"
        decoded_path.write_bytes(decoded)
        known_mask_path.write_bytes(known_mask)
        structural_mask_path.write_bytes(structural_mask)
        native_preview_path = native_preview_dir / f"{stem}_structural_nonzero.png"
        fullhd_preview_path = fullhd_preview_dir / f"{stem}_structural_nonzero_fullhd.png"
        fullhd_width, fullhd_height = render_preview(
            expected=expected,
            decoded=bytes(decoded),
            known_mask=bytes(known_mask),
            risk_mask=bytes(structural_mask),
            frontier=frontiers.get((key[0], key[1], key[2]), {}),
            native_path=native_preview_path,
            fullhd_path=fullhd_preview_path,
        )

        base_clean = int_field(base_fixture, "total_clean_bytes")
        rejected_false = count_mask(rejected_mask)
        total_clean = count_mask(known_mask)
        fixture_bytes = len(expected)
        remaining_unresolved = sum(
            1 for index in range(fixture_bytes) if not known_mask[index] and not rejected_mask[index]
        )
        output_fixture_rows.append(
            {
                "rank": base_fixture.get("rank", ""),
                "archive": key[0],
                "archive_tag": manifest.get("archive_tag", base_fixture.get("archive_tag", "")),
                "pcx_name": key[1],
                "frontier_id": key[2],
                "fixture_bytes": str(fixture_bytes),
                "base_clean_bytes": str(base_clean),
                "structural_target_rows": str(len(target_groups.get(key, []))),
                "structural_candidate_bytes": str(stats["structural_candidate_bytes"]),
                "structural_added_bytes": str(stats["structural_added_bytes"]),
                "structural_exact_bytes": str(stats["structural_exact_bytes"]),
                "structural_false_bytes": str(stats["structural_false_bytes"]),
                "skipped_known_bytes": str(stats["skipped_known_bytes"]),
                "skipped_rejected_bytes": str(stats["skipped_rejected_bytes"]),
                "total_clean_bytes": str(total_clean),
                "rejected_false_bytes": str(rejected_false),
                "remaining_unresolved_bytes": str(remaining_unresolved),
                "decoded_path": decoded_path.as_posix(),
                "known_mask_path": known_mask_path.as_posix(),
                "structural_mask_path": structural_mask_path.as_posix(),
                "native_preview_path": native_preview_path.as_posix(),
                "fullhd_preview_path": fullhd_preview_path.as_posix(),
                "fullhd_width": str(fullhd_width),
                "fullhd_height": str(fullhd_height),
                "issues": ";".join(fixture_issues),
            }
        )

    structural_added = sum(int_field(row, "structural_added_bytes") for row in output_fixture_rows)
    structural_false = sum(int_field(row, "structural_false_bytes") for row in output_fixture_rows)
    target_rows = sum(len(rows) for rows in target_groups.values())
    final_verdict = final_validation_summary.get("review_verdict", "")
    final_validated = final_verdict == "frontier80_structural_nonzero_bridge_residual_final_coverage_validated"
    if not final_validated:
        issue_rows += 1
    if target_rows != int_field(final_validation_summary, "full_coverage_target_runs"):
        issue_rows += 1
    promotion_ready = structural_added if issue_rows == 0 and structural_false == 0 and structural_added > 0 else 0
    ready = promotion_ready > 0 and final_validated
    summary = {
        "scope": "total",
        "fixture_rows": str(len(output_fixture_rows)),
        "target_rows": str(target_rows),
        "full_coverage_target_rows": final_validation_summary.get("full_coverage_target_runs", "0"),
        "promoted_rows": str(sum(1 for row in promotion_rows if int_field(row, "structural_added_bytes") > 0)),
        "base_clean_bytes": str(sum(int_field(row, "base_clean_bytes") for row in output_fixture_rows)),
        "structural_candidate_bytes": str(
            sum(int_field(row, "structural_candidate_bytes") for row in output_fixture_rows)
        ),
        "structural_added_bytes": str(structural_added),
        "structural_exact_bytes": str(sum(int_field(row, "structural_exact_bytes") for row in output_fixture_rows)),
        "structural_false_bytes": str(structural_false),
        "skipped_known_bytes": str(sum(int_field(row, "skipped_known_bytes") for row in output_fixture_rows)),
        "skipped_rejected_bytes": str(sum(int_field(row, "skipped_rejected_bytes") for row in output_fixture_rows)),
        "total_clean_bytes": str(sum(int_field(row, "total_clean_bytes") for row in output_fixture_rows)),
        "rejected_false_bytes": str(sum(int_field(row, "rejected_false_bytes") for row in output_fixture_rows)),
        "remaining_unresolved_bytes": str(
            sum(int_field(row, "remaining_unresolved_bytes") for row in output_fixture_rows)
        ),
        "native_previews": str(sum(1 for row in output_fixture_rows if row.get("native_preview_path"))),
        "fullhd_previews": str(
            sum(
                1
                for row in output_fixture_rows
                if (row.get("fullhd_width"), row.get("fullhd_height")) == (str(TARGET_SIZE[0]), str(TARGET_SIZE[1]))
            )
        ),
        "final_validation_verdict": final_verdict,
        "promotion_ready_bytes": str(promotion_ready),
        "issue_rows": str(issue_rows),
        "review_verdict": (
            "frontier80_structural_nonzero_final_fixture_replay_ready"
            if ready
            else "frontier80_structural_nonzero_final_fixture_replay_issues"
        ),
        "next_probe": (
            "rerun Frontier80 clean-gap queue after final structural nonzero fixture replay"
            if ready
            else "review final structural nonzero fixture replay issues"
        ),
    }
    return summary, output_fixture_rows, promotion_rows


def build_html(
    summary: dict[str, str],
    fixture_rows: list[dict[str, str]],
    promotion_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "fixtures": fixture_rows, "promotions": promotion_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("fixtures.csv", output_dir / "fixtures.csv"),
            ("promotions.csv", output_dir / "promotions.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #111416; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1500px; }}
th, td {{ border: 1px solid #31424a; padding: .45rem .55rem; vertical-align: top; }}
th {{ color: #9dafb5; background: #172023; text-align: left; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: .75rem; margin: 1rem 0; }}
.box {{ border: 1px solid #31424a; background: #172023; padding: .75rem; border-radius: 8px; }}
.num {{ font-size: 1.35rem; font-weight: 750; overflow-wrap: anywhere; }}
.muted {{ color: #9dafb5; }}
.panel {{ overflow-x: auto; margin-top: 1rem; }}
a {{ color: #77d3b1; text-decoration: none; margin-right: .75rem; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="grid">
  <div class="box"><div class="num">{html.escape(summary['structural_added_bytes'])}</div><div class="muted">structural added bytes</div></div>
  <div class="box"><div class="num">{html.escape(summary['promoted_rows'])}/{html.escape(summary['target_rows'])}</div><div class="muted">promoted target rows</div></div>
  <div class="box"><div class="num">{html.escape(summary['structural_false_bytes'])}</div><div class="muted">false bytes</div></div>
  <div class="box"><div class="num">{html.escape(summary['promotion_ready_bytes'])}</div><div class="muted">promotion-ready bytes</div></div>
  <div class="box"><div class="num">{html.escape(summary['review_verdict'])}</div><div class="muted">verdict</div></div>
</div>
<p>{links}</p>
<p class="muted">{html.escape(summary['next_probe'])}</p>
<div class="panel"><h2>Promotions</h2>{render_table(promotion_rows, PROMOTION_FIELDNAMES)}</div>
<div class="panel"><h2>Fixtures</h2>{render_table(fixture_rows, FIXTURE_FIELDNAMES)}</div>
<script type="application/json" id="structural-nonzero-final-fixture-replay-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--frontiers", type=Path, default=DEFAULT_FRONTIERS)
    parser.add_argument("--base-fixtures", type=Path, default=DEFAULT_BASE_FIXTURES)
    parser.add_argument("--clean-decisions", type=Path, default=DEFAULT_CLEAN_DECISIONS)
    parser.add_argument("--final-validation-summary", type=Path, default=DEFAULT_FINAL_VALIDATION_SUMMARY)
    parser.add_argument("--promoted-targets", type=Path, default=DEFAULT_PROMOTED_TARGETS)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Final Structural Nonzero Fixture Replay",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    final_validation_rows = read_csv(args.final_validation_summary)
    final_validation_summary = final_validation_rows[0] if final_validation_rows else {}
    summary, fixture_rows, promotion_rows = build_rows(
        output_dir=args.output,
        fixture_rows=read_csv(args.fixtures),
        frontier_rows=read_csv(args.frontiers),
        base_fixture_rows=read_csv(args.base_fixtures),
        clean_decision_rows=read_csv(args.clean_decisions),
        promoted_target_rows=read_csv(args.promoted_targets),
        final_validation_summary=final_validation_summary,
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "fixtures.csv", FIXTURE_FIELDNAMES, fixture_rows)
    write_csv(args.output / "promotions.csv", PROMOTION_FIELDNAMES, promotion_rows)
    (args.output / "index.html").write_text(
        build_html(summary, fixture_rows, promotion_rows, args.output, args.title),
        encoding="utf-8",
    )
    print(f"Promoted rows: {summary['promoted_rows']}/{summary['target_rows']}")
    print(f"Added structural bytes: {summary['structural_added_bytes']}")
    print(f"False bytes: {summary['structural_false_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
