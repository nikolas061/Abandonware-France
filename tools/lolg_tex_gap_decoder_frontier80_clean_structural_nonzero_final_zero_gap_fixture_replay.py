#!/usr/bin/env python3
"""Integrate remaining zero-only gaps after final structural nonzero fixture replay."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_replay import (
    count_mask,
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
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_final_zero_gap_fixture_replay"
)
DEFAULT_BASE_FIXTURES = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_final_fixture_replay/fixtures.csv"
)
DEFAULT_ZERO_SPANS = Path(
    "output/tex_gap_decoder_clean_gap_queue_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_final_fixture_replay/spans.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "fixture_rows",
    "zero_span_rows",
    "promoted_rows",
    "base_clean_bytes",
    "zero_candidate_bytes",
    "zero_added_bytes",
    "zero_exact_bytes",
    "zero_false_bytes",
    "skipped_known_bytes",
    "total_clean_bytes",
    "rejected_false_bytes",
    "remaining_unresolved_bytes",
    "native_previews",
    "fullhd_previews",
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
    "zero_span_rows",
    "zero_candidate_bytes",
    "zero_added_bytes",
    "zero_exact_bytes",
    "zero_false_bytes",
    "skipped_known_bytes",
    "total_clean_bytes",
    "rejected_false_bytes",
    "remaining_unresolved_bytes",
    "decoded_path",
    "known_mask_path",
    "zero_mask_path",
    "native_preview_path",
    "fullhd_preview_path",
    "fullhd_width",
    "fullhd_height",
    "issues",
]

PROMOTION_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "start",
    "end",
    "length",
    "source_span_class",
    "zero_added_bytes",
    "zero_exact_bytes",
    "zero_false_bytes",
    "skipped_known_bytes",
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


def grouped_zero_spans(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("span_class") != "unresolved_zero":
            continue
        grouped[archive_key(row)].append(row)
    for group_rows in grouped.values():
        group_rows.sort(key=lambda row: (int_value(row, "start"), int_value(row, "end")))
    return dict(grouped)


def apply_zero_span(
    span: dict[str, str],
    expected: bytes,
    decoded: bytearray,
    known_mask: bytearray,
    zero_mask: bytearray,
) -> tuple[dict[str, str], Counter[str]]:
    issues: list[str] = []
    start = int_field(span, "start", -1)
    end = int_field(span, "end", -1)
    length = int_field(span, "length", -1)
    if start < 0 or end < start or end > len(expected):
        issues.append("span_range_out_of_bounds")
    if end - start != length:
        issues.append(f"span_length_mismatch:{end - start}!={length}")
    if span.get("span_class") != "unresolved_zero":
        issues.append(f"source_span_not_zero:{span.get('span_class', '')}")

    bounded_start = max(0, min(start, len(expected)))
    bounded_end = max(bounded_start, min(end, len(expected)))
    chunk = expected[bounded_start:bounded_end]
    if any(value != 0 for value in chunk):
        issues.append("span_contains_nonzero_expected_byte")

    stats: Counter[str] = Counter()
    stats["zero_candidate_bytes"] = max(0, bounded_end - bounded_start)
    skipped_known = 0
    added = 0
    exact = 0
    false = 0
    if not issues:
        for offset in range(bounded_start, bounded_end):
            if known_mask[offset]:
                skipped_known += 1
                if decoded[offset] != 0:
                    false += 1
                continue
            decoded[offset] = 0
            known_mask[offset] = 0xFF
            zero_mask[offset] = 0xFF
            added += 1
            exact += 1
    elif start >= 0 and end <= len(expected):
        false = sum(1 for value in chunk if value != 0)

    if false:
        issues.append(f"zero_would_write_false_bytes:{false}")
    stats["zero_added_bytes"] = added
    stats["zero_exact_bytes"] = exact
    stats["zero_false_bytes"] = false
    stats["skipped_known_bytes"] = skipped_known
    row = {
        "rank": span.get("rank", ""),
        "archive": span.get("archive", ""),
        "archive_tag": span.get("archive_tag", ""),
        "pcx_name": span.get("pcx_name", ""),
        "frontier_id": span.get("frontier_id", ""),
        "span_index": span.get("span_index", ""),
        "start": span.get("start", ""),
        "end": span.get("end", ""),
        "length": span.get("length", "0"),
        "source_span_class": span.get("span_class", ""),
        "zero_added_bytes": str(added),
        "zero_exact_bytes": str(exact),
        "zero_false_bytes": str(false),
        "skipped_known_bytes": str(skipped_known),
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
    zero_span_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    manifest_by_key = {archive_key(row): row for row in fixture_rows}
    frontiers = frontier_lookup(frontier_rows)
    zero_groups = grouped_zero_spans(zero_span_rows)

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
        zero_mask = bytearray(len(expected))
        stats: Counter[str] = Counter()
        for span in zero_groups.get(key, []):
            promotion_row, span_stats = apply_zero_span(span, expected, decoded, known_mask, zero_mask)
            promotion_rows.append(promotion_row)
            stats.update(span_stats)
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
        decoded_path = fixture_output_dir / f"{stem}_decoded_final_zero.bin"
        known_mask_path = fixture_output_dir / f"{stem}_known_mask.bin"
        zero_mask_path = fixture_output_dir / f"{stem}_zero_mask.bin"
        decoded_path.write_bytes(decoded)
        known_mask_path.write_bytes(known_mask)
        zero_mask_path.write_bytes(zero_mask)
        native_preview_path = native_preview_dir / f"{stem}_final_zero.png"
        fullhd_preview_path = fullhd_preview_dir / f"{stem}_final_zero_fullhd.png"
        fullhd_width, fullhd_height = render_preview(
            expected=expected,
            decoded=bytes(decoded),
            known_mask=bytes(known_mask),
            risk_mask=bytes(zero_mask),
            frontier=frontiers.get((key[0], key[1], key[2]), {}),
            native_path=native_preview_path,
            fullhd_path=fullhd_preview_path,
        )

        total_clean = count_mask(known_mask)
        rejected_false = count_mask(rejected_mask)
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
                "base_clean_bytes": base_fixture.get("total_clean_bytes", base_fixture.get("clean_bytes", "0")),
                "zero_span_rows": str(len(zero_groups.get(key, []))),
                "zero_candidate_bytes": str(stats["zero_candidate_bytes"]),
                "zero_added_bytes": str(stats["zero_added_bytes"]),
                "zero_exact_bytes": str(stats["zero_exact_bytes"]),
                "zero_false_bytes": str(stats["zero_false_bytes"]),
                "skipped_known_bytes": str(stats["skipped_known_bytes"]),
                "total_clean_bytes": str(total_clean),
                "rejected_false_bytes": str(rejected_false),
                "remaining_unresolved_bytes": str(remaining_unresolved),
                "decoded_path": decoded_path.as_posix(),
                "known_mask_path": known_mask_path.as_posix(),
                "zero_mask_path": zero_mask_path.as_posix(),
                "native_preview_path": native_preview_path.as_posix(),
                "fullhd_preview_path": fullhd_preview_path.as_posix(),
                "fullhd_width": str(fullhd_width),
                "fullhd_height": str(fullhd_height),
                "issues": ";".join(fixture_issues),
            }
        )

    zero_added = sum(int_field(row, "zero_added_bytes") for row in output_fixture_rows)
    zero_false = sum(int_field(row, "zero_false_bytes") for row in output_fixture_rows)
    promotion_ready = zero_added if issue_rows == 0 and zero_false == 0 and zero_added > 0 else 0
    ready = promotion_ready > 0
    summary = {
        "scope": "total",
        "fixture_rows": str(len(output_fixture_rows)),
        "zero_span_rows": str(sum(len(rows) for rows in zero_groups.values())),
        "promoted_rows": str(sum(1 for row in promotion_rows if int_field(row, "zero_added_bytes") > 0)),
        "base_clean_bytes": str(sum(int_field(row, "base_clean_bytes") for row in output_fixture_rows)),
        "zero_candidate_bytes": str(sum(int_field(row, "zero_candidate_bytes") for row in output_fixture_rows)),
        "zero_added_bytes": str(zero_added),
        "zero_exact_bytes": str(sum(int_field(row, "zero_exact_bytes") for row in output_fixture_rows)),
        "zero_false_bytes": str(zero_false),
        "skipped_known_bytes": str(sum(int_field(row, "skipped_known_bytes") for row in output_fixture_rows)),
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
        "promotion_ready_bytes": str(promotion_ready),
        "issue_rows": str(issue_rows),
        "review_verdict": (
            "frontier80_structural_nonzero_final_zero_gap_fixture_replay_ready"
            if ready
            else "frontier80_structural_nonzero_final_zero_gap_fixture_replay_issues"
        ),
        "next_probe": (
            "rerun Frontier80 clean-gap queue after final zero-gap fixture replay"
            if ready
            else "review final zero-gap fixture replay issues"
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
table {{ border-collapse: collapse; width: 100%; min-width: 1320px; }}
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
  <div class="box"><div class="num">{html.escape(summary['zero_added_bytes'])}</div><div class="muted">zero added bytes</div></div>
  <div class="box"><div class="num">{html.escape(summary['promoted_rows'])}/{html.escape(summary['zero_span_rows'])}</div><div class="muted">promoted zero spans</div></div>
  <div class="box"><div class="num">{html.escape(summary['zero_false_bytes'])}</div><div class="muted">false bytes</div></div>
  <div class="box"><div class="num">{html.escape(summary['remaining_unresolved_bytes'])}</div><div class="muted">remaining unresolved</div></div>
  <div class="box"><div class="num">{html.escape(summary['review_verdict'])}</div><div class="muted">verdict</div></div>
</div>
<p>{links}</p>
<p class="muted">{html.escape(summary['next_probe'])}</p>
<div class="panel"><h2>Promotions</h2>{render_table(promotion_rows, PROMOTION_FIELDNAMES)}</div>
<div class="panel"><h2>Fixtures</h2>{render_table(fixture_rows, FIXTURE_FIELDNAMES)}</div>
<script type="application/json" id="final-zero-gap-fixture-replay-data">{html.escape(data_json)}</script>
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
    parser.add_argument("--zero-spans", type=Path, default=DEFAULT_ZERO_SPANS)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Final Zero-Gap Fixture Replay",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, fixture_rows, promotion_rows = build_rows(
        output_dir=args.output,
        fixture_rows=read_csv(args.fixtures),
        frontier_rows=read_csv(args.frontiers),
        base_fixture_rows=read_csv(args.base_fixtures),
        clean_decision_rows=read_csv(args.clean_decisions),
        zero_span_rows=read_csv(args.zero_spans),
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "fixtures.csv", FIXTURE_FIELDNAMES, fixture_rows)
    write_csv(args.output / "promotions.csv", PROMOTION_FIELDNAMES, promotion_rows)
    (args.output / "index.html").write_text(
        build_html(summary, fixture_rows, promotion_rows, args.output, args.title),
        encoding="utf-8",
    )
    print(f"Promoted rows: {summary['promoted_rows']}/{summary['zero_span_rows']}")
    print(f"Added zero bytes: {summary['zero_added_bytes']}")
    print(f"False bytes: {summary['zero_false_bytes']}")
    print(f"Remaining unresolved bytes: {summary['remaining_unresolved_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
