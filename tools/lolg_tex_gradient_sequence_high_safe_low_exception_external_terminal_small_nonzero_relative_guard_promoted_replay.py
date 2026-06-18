#!/usr/bin/env python3
"""Promote the reviewed final small-nonzero relative guard into fixture buffers."""

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
    fixture_sort_key,
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
    byte_hex,
)


DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_relative_guard_promoted_replay"
)
DEFAULT_BASE_FIXTURES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer_guard_carrier_context_promoted_replay_promoted/fixtures.csv"
)
DEFAULT_REVIEW_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_relative_guard_review_delta_guard_promoted_replay/summary.csv"
)
DEFAULT_TARGETS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_relative_guard_review_delta_guard_promoted_replay/targets.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "fixture_rows",
    "target_rows",
    "promoted_rows",
    "base_clean_bytes",
    "relative_candidate_bytes",
    "relative_added_bytes",
    "relative_exact_bytes",
    "relative_false_bytes",
    "skipped_known_bytes",
    "skipped_rejected_bytes",
    "total_clean_bytes",
    "rejected_false_bytes",
    "remaining_unresolved_bytes",
    "native_previews",
    "fullhd_previews",
    "review_ready_rows",
    "target_span_keys",
    "best_formula",
    "best_guard_key",
    "promotion_ready_bytes",
    "issue_rows",
]

FIXTURE_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "fixture_bytes",
    "base_clean_bytes",
    "relative_target_rows",
    "relative_candidate_bytes",
    "relative_added_bytes",
    "relative_exact_bytes",
    "relative_false_bytes",
    "skipped_known_bytes",
    "skipped_rejected_bytes",
    "total_clean_bytes",
    "rejected_false_bytes",
    "remaining_unresolved_bytes",
    "decoded_path",
    "known_mask_path",
    "relative_mask_path",
    "native_preview_path",
    "fullhd_preview_path",
    "fullhd_width",
    "fullhd_height",
    "issues",
]

TARGET_FIELDNAMES = [
    "fixture_rank",
    "target_rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_key",
    "span_start",
    "span_end",
    "span_length",
    "expected_hex",
    "predicted_hex",
    "best_formula",
    "best_guard_key",
    "review_verdict",
    "source_offset",
    "source_known",
    "relative_candidate_bytes",
    "relative_added_bytes",
    "relative_exact_bytes",
    "relative_false_bytes",
    "skipped_known_bytes",
    "skipped_rejected_bytes",
    "issues",
]

BYTE_FIELDNAMES = [
    "target_rank",
    "byte_rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_key",
    "absolute_offset",
    "relative_offset",
    "source_offset",
    "source_known",
    "expected_byte",
    "predicted_byte",
    "base_known_overlap_bytes",
    "relative_overlap_bytes",
    "rejected_overlap_bytes",
    "relative_added_bytes",
    "relative_exact_bytes",
    "relative_false_bytes",
    "skipped_known_bytes",
    "skipped_rejected_bytes",
    "issues",
]


def review_ready(summary: dict[str, str]) -> bool:
    return (
        summary.get("review_verdict") == "relative_guard_review_promotion_ready"
        and int_value(summary, "promotion_ready_bytes") > 0
        and int_value(summary, "issue_rows") == 0
    )


def relative_source_offset(start: int, formula: str) -> int | None:
    if formula == "prev_byte-2:identity":
        return start - 2
    return None


def predicted_byte_from_formula(
    *,
    formula: str,
    start: int,
    decoded: bytearray,
    known_mask: bytearray,
    issues: list[str],
) -> tuple[int | None, int | None, int]:
    source_offset = relative_source_offset(start, formula)
    if source_offset is None:
        issues.append("unsupported_relative_formula")
        return None, None, 0
    if source_offset < 0 or source_offset >= len(decoded):
        issues.append("source_offset_out_of_range")
        return None, source_offset, 0
    source_known = 1 if source_offset < len(known_mask) and known_mask[source_offset] else 0
    if not source_known:
        issues.append("source_unknown")
        return None, source_offset, source_known
    return decoded[source_offset], source_offset, source_known


def selected_targets(
    target_rows: list[dict[str, str]],
    review_summary: dict[str, str],
) -> list[dict[str, str]]:
    if not review_ready(review_summary):
        return []
    rows: list[dict[str, str]] = []
    for row in target_rows:
        if row.get("review_verdict") != "relative_guard_review_promotion_ready":
            continue
        if int_value(row, "promotion_ready") <= 0:
            continue
        if int_value(row, "span_length") != 1:
            continue
        promoted = dict(row)
        promoted["best_formula"] = promoted.get("best_formula") or review_summary.get("best_formula", "")
        promoted["best_guard_key"] = promoted.get("best_guard_key") or review_summary.get("best_guard_key", "")
        rows.append(promoted)
    rows.sort(key=lambda row: (archive_key(row), int_value(row, "span_start"), int_value(row, "rank")))
    return rows


def grouped_targets(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[archive_key(row)].append(row)
    return grouped


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


def build_rows(
    *,
    output_dir: Path,
    fixture_rows: list[dict[str, str]],
    frontier_rows: list[dict[str, str]],
    base_fixture_rows: list[dict[str, str]],
    clean_decision_rows: list[dict[str, str]],
    review_summary_rows: list[dict[str, str]],
    target_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    review_summary = review_summary_rows[0] if review_summary_rows else {}
    targets = selected_targets(target_rows, review_summary)
    target_groups = grouped_targets(targets)
    manifest_by_key = {archive_key(row): row for row in fixture_rows}
    frontiers = frontier_lookup(frontier_rows)

    fixture_output_dir = output_dir / "fixtures"
    native_preview_dir = output_dir / "native"
    fullhd_preview_dir = output_dir / "fullhd"
    fixture_output_dir.mkdir(parents=True, exist_ok=True)
    native_preview_dir.mkdir(parents=True, exist_ok=True)
    fullhd_preview_dir.mkdir(parents=True, exist_ok=True)

    output_fixture_rows: list[dict[str, str]] = []
    output_target_rows: list[dict[str, str]] = []
    output_byte_rows: list[dict[str, str]] = []
    issue_rows = 0

    for base_fixture in sorted(base_fixture_rows, key=lambda row: fixture_sort_key(archive_key(row))):
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
        relative_mask = bytearray(len(expected))
        stats: Counter[str] = Counter()

        for target in target_groups.get(key, []):
            target_issues: list[str] = []
            start = int_value(target, "span_start")
            end = int_value(target, "span_end")
            expected_hex = target.get("expected_hex", "")
            formula = target.get("best_formula", review_summary.get("best_formula", ""))
            predicted_value, source_offset, source_known = predicted_byte_from_formula(
                formula=formula,
                start=start,
                decoded=decoded,
                known_mask=known_mask,
                issues=target_issues,
            )
            predicted_hex = "" if predicted_value is None else f"{predicted_value:02x}"
            if end - start != 1:
                target_issues.append("target_not_one_byte")
            if predicted_hex != expected_hex:
                target_issues.append("relative_prediction_mismatch")

            target_stats: Counter[str] = Counter()
            target_rank = str(len(output_target_rows) + 1)
            offset = start
            byte_issues = list(target_issues)
            expected_byte_text = byte_hex(expected, offset)
            expected_value = None if expected_byte_text == "NA" else int(expected_byte_text, 16)
            base_overlap = overlap_bytes(known_mask, offset, offset + 1)
            relative_overlap = overlap_bytes(relative_mask, offset, offset + 1)
            rejected_overlap = overlap_bytes(rejected_mask, offset, offset + 1)

            if offset < 0 or offset >= len(expected):
                byte_issues.append("offset_out_of_range")
            if predicted_value is not None and expected_value is not None and predicted_value != expected_value:
                byte_issues.append("relative_would_write_false_byte")
            if base_overlap and predicted_value is not None and offset < len(decoded) and decoded[offset] != predicted_value:
                byte_issues.append("base_known_conflict")
            if relative_overlap:
                byte_issues.append("relative_overlap")

            false_bytes = 1 if "relative_would_write_false_byte" in byte_issues else 0
            added_bytes = 0
            exact_bytes = 0
            skipped_known = 0
            skipped_rejected = 0
            if not byte_issues:
                if base_overlap:
                    skipped_known = 1
                elif rejected_overlap:
                    skipped_rejected = 1
                elif predicted_value is not None:
                    decoded[offset] = predicted_value
                    known_mask[offset] = 0xFF
                    relative_mask[offset] = 0xFF
                    added_bytes = 1
                    exact_bytes = 1
            else:
                issue_rows += 1

            stats["relative_candidate_bytes"] += 1
            stats["relative_added_bytes"] += added_bytes
            stats["relative_exact_bytes"] += exact_bytes
            stats["relative_false_bytes"] += false_bytes
            stats["skipped_known_bytes"] += skipped_known
            stats["skipped_rejected_bytes"] += skipped_rejected
            target_stats["relative_candidate_bytes"] += 1
            target_stats["relative_added_bytes"] += added_bytes
            target_stats["relative_exact_bytes"] += exact_bytes
            target_stats["relative_false_bytes"] += false_bytes
            target_stats["skipped_known_bytes"] += skipped_known
            target_stats["skipped_rejected_bytes"] += skipped_rejected
            output_byte_rows.append(
                {
                    "target_rank": target_rank,
                    "byte_rank": str(len(output_byte_rows) + 1),
                    "archive": key[0],
                    "archive_tag": manifest.get("archive_tag", base_fixture.get("archive_tag", "")),
                    "pcx_name": key[1],
                    "frontier_id": key[2],
                    "span_key": target.get("span_key", ""),
                    "absolute_offset": str(offset),
                    "relative_offset": "0",
                    "source_offset": "" if source_offset is None else str(source_offset),
                    "source_known": str(source_known),
                    "expected_byte": expected_byte_text,
                    "predicted_byte": predicted_hex,
                    "base_known_overlap_bytes": str(base_overlap),
                    "relative_overlap_bytes": str(relative_overlap),
                    "rejected_overlap_bytes": str(rejected_overlap),
                    "relative_added_bytes": str(added_bytes),
                    "relative_exact_bytes": str(exact_bytes),
                    "relative_false_bytes": str(false_bytes),
                    "skipped_known_bytes": str(skipped_known),
                    "skipped_rejected_bytes": str(skipped_rejected),
                    "issues": ";".join(byte_issues),
                }
            )
            output_target_rows.append(
                {
                    "fixture_rank": base_fixture.get("rank", ""),
                    "target_rank": target_rank,
                    "archive": key[0],
                    "archive_tag": manifest.get("archive_tag", base_fixture.get("archive_tag", "")),
                    "pcx_name": key[1],
                    "frontier_id": key[2],
                    "span_key": target.get("span_key", ""),
                    "span_start": target.get("span_start", ""),
                    "span_end": target.get("span_end", ""),
                    "span_length": target.get("span_length", ""),
                    "expected_hex": expected_hex,
                    "predicted_hex": predicted_hex,
                    "best_formula": formula,
                    "best_guard_key": target.get("best_guard_key", review_summary.get("best_guard_key", "")),
                    "review_verdict": target.get("review_verdict", ""),
                    "source_offset": "" if source_offset is None else str(source_offset),
                    "source_known": str(source_known),
                    "relative_candidate_bytes": str(target_stats["relative_candidate_bytes"]),
                    "relative_added_bytes": str(target_stats["relative_added_bytes"]),
                    "relative_exact_bytes": str(target_stats["relative_exact_bytes"]),
                    "relative_false_bytes": str(target_stats["relative_false_bytes"]),
                    "skipped_known_bytes": str(target_stats["skipped_known_bytes"]),
                    "skipped_rejected_bytes": str(target_stats["skipped_rejected_bytes"]),
                    "issues": ";".join(target_issues),
                }
            )

        if fixture_issues:
            issue_rows += 1
        stem = safe_stem(
            f"rank{int(base_fixture.get('rank', '0')):03d}"
            if base_fixture.get("rank", "").isdigit()
            else f"rank{base_fixture.get('rank', '')}",
            key[1],
            f"frontier{key[2]}",
        )
        decoded_path = fixture_output_dir / f"{stem}_decoded_relative_guard.bin"
        known_mask_path = fixture_output_dir / f"{stem}_known_mask.bin"
        relative_mask_path = fixture_output_dir / f"{stem}_relative_guard_mask.bin"
        decoded_path.write_bytes(decoded)
        known_mask_path.write_bytes(known_mask)
        relative_mask_path.write_bytes(relative_mask)
        native_preview_path = native_preview_dir / f"{stem}_relative_guard.png"
        fullhd_preview_path = fullhd_preview_dir / f"{stem}_relative_guard_fullhd.png"
        fullhd_width, fullhd_height = render_preview(
            expected=expected,
            decoded=bytes(decoded),
            known_mask=bytes(known_mask),
            risk_mask=bytes(relative_mask),
            frontier=frontiers.get((key[0], key[1], key[2]), {}),
            native_path=native_preview_path,
            fullhd_path=fullhd_preview_path,
        )

        base_clean = int_value(base_fixture, "total_clean_bytes")
        rejected_false = int_value(base_fixture, "rejected_false_bytes")
        total_clean = count_mask(known_mask)
        fixture_bytes = len(expected)
        output_fixture_rows.append(
            {
                "rank": base_fixture.get("rank", ""),
                "archive": key[0],
                "archive_tag": manifest.get("archive_tag", base_fixture.get("archive_tag", "")),
                "pcx_name": key[1],
                "frontier_id": key[2],
                "fixture_bytes": str(fixture_bytes),
                "base_clean_bytes": str(base_clean),
                "relative_target_rows": str(len(target_groups.get(key, []))),
                "relative_candidate_bytes": str(stats["relative_candidate_bytes"]),
                "relative_added_bytes": str(stats["relative_added_bytes"]),
                "relative_exact_bytes": str(stats["relative_exact_bytes"]),
                "relative_false_bytes": str(stats["relative_false_bytes"]),
                "skipped_known_bytes": str(stats["skipped_known_bytes"]),
                "skipped_rejected_bytes": str(stats["skipped_rejected_bytes"]),
                "total_clean_bytes": str(total_clean),
                "rejected_false_bytes": str(rejected_false),
                "remaining_unresolved_bytes": str(max(0, fixture_bytes - total_clean - rejected_false)),
                "decoded_path": decoded_path.as_posix(),
                "known_mask_path": known_mask_path.as_posix(),
                "relative_mask_path": relative_mask_path.as_posix(),
                "native_preview_path": native_preview_path.as_posix(),
                "fullhd_preview_path": fullhd_preview_path.as_posix(),
                "fullhd_width": str(fullhd_width),
                "fullhd_height": str(fullhd_height),
                "issues": ";".join(fixture_issues),
            }
        )

    relative_added = sum(int_value(row, "relative_added_bytes") for row in output_fixture_rows)
    relative_false = sum(int_value(row, "relative_false_bytes") for row in output_fixture_rows)
    summary = {
        "scope": "total",
        "fixture_rows": str(len(output_fixture_rows)),
        "target_rows": str(len(output_target_rows)),
        "promoted_rows": str(sum(1 for row in output_target_rows if int_value(row, "relative_added_bytes") > 0)),
        "base_clean_bytes": str(sum(int_value(row, "base_clean_bytes") for row in output_fixture_rows)),
        "relative_candidate_bytes": str(
            sum(int_value(row, "relative_candidate_bytes") for row in output_fixture_rows)
        ),
        "relative_added_bytes": str(relative_added),
        "relative_exact_bytes": str(sum(int_value(row, "relative_exact_bytes") for row in output_fixture_rows)),
        "relative_false_bytes": str(relative_false),
        "skipped_known_bytes": str(sum(int_value(row, "skipped_known_bytes") for row in output_fixture_rows)),
        "skipped_rejected_bytes": str(sum(int_value(row, "skipped_rejected_bytes") for row in output_fixture_rows)),
        "total_clean_bytes": str(sum(int_value(row, "total_clean_bytes") for row in output_fixture_rows)),
        "rejected_false_bytes": str(sum(int_value(row, "rejected_false_bytes") for row in output_fixture_rows)),
        "remaining_unresolved_bytes": str(sum(int_value(row, "remaining_unresolved_bytes") for row in output_fixture_rows)),
        "native_previews": str(sum(1 for row in output_fixture_rows if row.get("native_preview_path"))),
        "fullhd_previews": str(
            sum(
                1
                for row in output_fixture_rows
                if (row.get("fullhd_width"), row.get("fullhd_height")) == (str(TARGET_SIZE[0]), str(TARGET_SIZE[1]))
            )
        ),
        "review_ready_rows": "1" if review_ready(review_summary) else "0",
        "target_span_keys": ";".join(row.get("span_key", "") for row in output_target_rows),
        "best_formula": review_summary.get("best_formula", ""),
        "best_guard_key": review_summary.get("best_guard_key", ""),
        "promotion_ready_bytes": str(relative_added if issue_rows == 0 and relative_false == 0 else 0),
        "issue_rows": str(issue_rows),
    }
    return summary, output_fixture_rows, output_target_rows, output_byte_rows


def build_html(
    summary: dict[str, str],
    fixture_rows: list[dict[str, str]],
    target_rows: list[dict[str, str]],
    byte_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "fixtures": fixture_rows, "targets": target_rows, "bytes": byte_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("fixtures.csv", output_dir / "fixtures.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("bytes.csv", output_dir / "bytes.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #111416; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1550px; }}
th, td {{ border: 1px solid #31424a; padding: .45rem .55rem; vertical-align: top; }}
th {{ color: #9dafb5; background: #172023; text-align: left; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: .75rem; margin: 1rem 0; }}
.box {{ border: 1px solid #31424a; background: #172023; padding: .75rem; }}
.num {{ font-size: 1.35rem; font-weight: 750; }}
.muted {{ color: #9dafb5; }}
.panel {{ overflow-x: auto; margin-top: 1rem; }}
a {{ color: #77d3b1; text-decoration: none; margin-right: .75rem; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="grid">
  <div class="box"><div class="num">{summary['relative_added_bytes']}</div><div class="muted">relative added bytes</div></div>
  <div class="box"><div class="num">{summary['promoted_rows']}/{summary['target_rows']}</div><div class="muted">promoted spans</div></div>
  <div class="box"><div class="num">{summary['relative_false_bytes']}</div><div class="muted">false bytes</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
  <div class="box"><div class="num">{summary['remaining_unresolved_bytes']}</div><div class="muted">remaining unresolved</div></div>
</div>
<div class="panel"><h2>Files</h2>{links}</div>
<div class="panel"><h2>Fixtures</h2>{render_table(fixture_rows, FIXTURE_FIELDNAMES)}</div>
<div class="panel"><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</div>
<div class="panel"><h2>Bytes</h2>{render_table(byte_rows, BYTE_FIELDNAMES)}</div>
<script type="application/json" id="small-nonzero-relative-guard-promoted-replay-data">{html.escape(data_json)}</script>
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
    parser.add_argument("--review-summary", type=Path, default=DEFAULT_REVIEW_SUMMARY)
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Final Small Nonzero Relative Guard Promoted Replay",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, fixture_rows, target_rows, byte_rows = build_rows(
        output_dir=args.output,
        fixture_rows=read_csv(args.fixtures),
        frontier_rows=read_csv(args.frontiers),
        base_fixture_rows=read_csv(args.base_fixtures),
        clean_decision_rows=read_csv(args.clean_decisions),
        review_summary_rows=read_csv(args.review_summary),
        target_rows=read_csv(args.targets),
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "fixtures.csv", FIXTURE_FIELDNAMES, fixture_rows)
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(args.output / "bytes.csv", BYTE_FIELDNAMES, byte_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, fixture_rows, target_rows, byte_rows, args.output, args.title), encoding="utf-8")

    print(f"Promoted spans: {summary['promoted_rows']}/{summary['target_rows']}")
    print(f"Added relative bytes: {summary['relative_added_bytes']}")
    print(f"False bytes: {summary['relative_false_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
