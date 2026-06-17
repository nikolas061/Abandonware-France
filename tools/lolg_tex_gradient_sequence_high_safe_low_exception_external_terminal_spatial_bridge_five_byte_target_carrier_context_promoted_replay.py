#!/usr/bin/env python3
"""Promote the carrier-local five-byte context split into fixture buffers."""

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
    parse_hex_byte,
)


DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_promoted_replay"
)
DEFAULT_BASE_FIXTURES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_second_promoted_replay/fixtures.csv"
)
DEFAULT_CONTEXT_REVIEW = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_review/summary.csv"
)
DEFAULT_TARGETS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_combinator/targets.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "fixture_rows",
    "target_rows",
    "promoted_rows",
    "base_clean_bytes",
    "context_candidate_bytes",
    "context_added_bytes",
    "context_exact_bytes",
    "context_false_bytes",
    "skipped_known_bytes",
    "skipped_rejected_bytes",
    "total_clean_bytes",
    "rejected_false_bytes",
    "remaining_unresolved_bytes",
    "native_previews",
    "fullhd_previews",
    "review_ready_rows",
    "target_span_keys",
    "threshold_context",
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
    "context_target_rows",
    "context_candidate_bytes",
    "context_added_bytes",
    "context_exact_bytes",
    "context_false_bytes",
    "skipped_known_bytes",
    "skipped_rejected_bytes",
    "total_clean_bytes",
    "rejected_false_bytes",
    "remaining_unresolved_bytes",
    "decoded_path",
    "known_mask_path",
    "context_mask_path",
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
    "best_family",
    "best_selector",
    "context_guard",
    "context_review_verdict",
    "context_candidate_bytes",
    "context_added_bytes",
    "context_exact_bytes",
    "context_false_bytes",
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
    "expected_byte",
    "predicted_byte",
    "base_known_overlap_bytes",
    "context_overlap_bytes",
    "rejected_overlap_bytes",
    "context_added_bytes",
    "context_exact_bytes",
    "context_false_bytes",
    "skipped_known_bytes",
    "skipped_rejected_bytes",
    "issues",
]


def context_ready(summary: dict[str, str]) -> bool:
    return (
        summary.get("review_verdict") == "context_review_promotion_ready"
        and int_value(summary, "promotion_ready_bytes") > 0
        and int_value(summary, "validated_false_rows") == 0
        and int_value(summary, "validated_unknown_rows") == 0
    )


def threshold_context(summary: dict[str, str]) -> str:
    return (
        f"{summary.get('best_context', '')}:"
        f"{summary.get('best_direction', '')}:"
        f"{summary.get('best_threshold', '')}"
    )


def promotable_targets(
    target_rows: list[dict[str, str]],
    context_summary: dict[str, str],
) -> list[dict[str, str]]:
    if not context_ready(context_summary):
        return []
    target_bytes = int_value(context_summary, "target_bytes")
    rows: list[dict[str, str]] = []
    for row in target_rows:
        if int_value(row, "span_length") != target_bytes:
            continue
        if row.get("best_output_hex", "") != row.get("expected_hex", ""):
            continue
        if row.get("best_guard", row.get("best_family", "")) == "target_signature_only":
            continue
        promoted = dict(row)
        promoted["context_guard"] = threshold_context(context_summary)
        promoted["context_review_verdict"] = context_summary.get("review_verdict", "")
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
    context_review_rows: list[dict[str, str]],
    target_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    context_summary = context_review_rows[0] if context_review_rows else {}
    selected_targets = promotable_targets(target_rows, context_summary)
    target_groups = grouped_targets(selected_targets)
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
        context_mask = bytearray(len(expected))
        stats: Counter[str] = Counter()

        for target in target_groups.get(key, []):
            target_issues: list[str] = []
            start = int_value(target, "span_start")
            expected_hex = target.get("expected_hex", "")
            predicted_hex = target.get("best_output_hex", "")
            try:
                expected_bytes = bytes.fromhex(expected_hex)
                predicted_bytes = bytes.fromhex(predicted_hex)
            except ValueError:
                expected_bytes = b""
                predicted_bytes = b""
                target_issues.append("invalid_target_hex")
            if len(expected_bytes) != int_value(target, "span_length"):
                target_issues.append("expected_length_mismatch")
            if len(predicted_bytes) != int_value(target, "span_length"):
                target_issues.append("predicted_length_mismatch")

            target_stats: Counter[str] = Counter()
            target_rank = str(len(output_target_rows) + 1)
            for offset_index, predicted_byte in enumerate(predicted_bytes):
                offset = start + offset_index
                byte_issues = list(target_issues)
                target_byte = expected_bytes[offset_index] if offset_index < len(expected_bytes) else None
                expected_byte_text = byte_hex(expected, offset)
                expected_value = None if expected_byte_text == "NA" else int(expected_byte_text, 16)
                parsed_predicted = parse_hex_byte(f"{predicted_byte:02x}", byte_issues, "predicted_byte")
                base_overlap = overlap_bytes(known_mask, offset, offset + 1)
                context_overlap = overlap_bytes(context_mask, offset, offset + 1)
                rejected_overlap = overlap_bytes(rejected_mask, offset, offset + 1)

                if offset < 0 or offset >= len(expected):
                    byte_issues.append("offset_out_of_range")
                if parsed_predicted is not None and target_byte is not None and parsed_predicted != target_byte:
                    byte_issues.append("target_prediction_mismatch")
                if parsed_predicted is not None and expected_value is not None and parsed_predicted != expected_value:
                    byte_issues.append("context_would_write_false_byte")
                if base_overlap and parsed_predicted is not None and offset < len(decoded) and decoded[offset] != parsed_predicted:
                    byte_issues.append("base_known_conflict")
                if context_overlap:
                    byte_issues.append("context_overlap")

                false_bytes = 1 if "context_would_write_false_byte" in byte_issues else 0
                added_bytes = 0
                exact_bytes = 0
                skipped_known = 0
                skipped_rejected = 0
                if not byte_issues:
                    if base_overlap:
                        skipped_known = 1
                    elif rejected_overlap:
                        skipped_rejected = 1
                    elif parsed_predicted is not None:
                        decoded[offset] = parsed_predicted
                        known_mask[offset] = 0xFF
                        context_mask[offset] = 0xFF
                        added_bytes = 1
                        exact_bytes = 1
                else:
                    issue_rows += 1

                stats["context_candidate_bytes"] += 1
                stats["context_added_bytes"] += added_bytes
                stats["context_exact_bytes"] += exact_bytes
                stats["context_false_bytes"] += false_bytes
                stats["skipped_known_bytes"] += skipped_known
                stats["skipped_rejected_bytes"] += skipped_rejected
                target_stats["context_candidate_bytes"] += 1
                target_stats["context_added_bytes"] += added_bytes
                target_stats["context_exact_bytes"] += exact_bytes
                target_stats["context_false_bytes"] += false_bytes
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
                        "relative_offset": str(offset_index),
                        "expected_byte": expected_byte_text,
                        "predicted_byte": f"{predicted_byte:02x}",
                        "base_known_overlap_bytes": str(base_overlap),
                        "context_overlap_bytes": str(context_overlap),
                        "rejected_overlap_bytes": str(rejected_overlap),
                        "context_added_bytes": str(added_bytes),
                        "context_exact_bytes": str(exact_bytes),
                        "context_false_bytes": str(false_bytes),
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
                    "best_family": target.get("best_family", ""),
                    "best_selector": target.get("best_selector", ""),
                    "context_guard": target.get("context_guard", ""),
                    "context_review_verdict": target.get("context_review_verdict", ""),
                    "context_candidate_bytes": str(target_stats["context_candidate_bytes"]),
                    "context_added_bytes": str(target_stats["context_added_bytes"]),
                    "context_exact_bytes": str(target_stats["context_exact_bytes"]),
                    "context_false_bytes": str(target_stats["context_false_bytes"]),
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
        decoded_path = fixture_output_dir / f"{stem}_decoded_carrier_context.bin"
        known_mask_path = fixture_output_dir / f"{stem}_known_mask.bin"
        context_mask_path = fixture_output_dir / f"{stem}_carrier_context_mask.bin"
        decoded_path.write_bytes(decoded)
        known_mask_path.write_bytes(known_mask)
        context_mask_path.write_bytes(context_mask)
        native_preview_path = native_preview_dir / f"{stem}_carrier_context.png"
        fullhd_preview_path = fullhd_preview_dir / f"{stem}_carrier_context_fullhd.png"
        fullhd_width, fullhd_height = render_preview(
            expected=expected,
            decoded=bytes(decoded),
            known_mask=bytes(known_mask),
            risk_mask=bytes(context_mask),
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
                "context_target_rows": str(len(target_groups.get(key, []))),
                "context_candidate_bytes": str(stats["context_candidate_bytes"]),
                "context_added_bytes": str(stats["context_added_bytes"]),
                "context_exact_bytes": str(stats["context_exact_bytes"]),
                "context_false_bytes": str(stats["context_false_bytes"]),
                "skipped_known_bytes": str(stats["skipped_known_bytes"]),
                "skipped_rejected_bytes": str(stats["skipped_rejected_bytes"]),
                "total_clean_bytes": str(total_clean),
                "rejected_false_bytes": str(rejected_false),
                "remaining_unresolved_bytes": str(max(0, fixture_bytes - total_clean - rejected_false)),
                "decoded_path": decoded_path.as_posix(),
                "known_mask_path": known_mask_path.as_posix(),
                "context_mask_path": context_mask_path.as_posix(),
                "native_preview_path": native_preview_path.as_posix(),
                "fullhd_preview_path": fullhd_preview_path.as_posix(),
                "fullhd_width": str(fullhd_width),
                "fullhd_height": str(fullhd_height),
                "issues": ";".join(fixture_issues),
            }
        )

    context_added = sum(int_value(row, "context_added_bytes") for row in output_fixture_rows)
    context_false = sum(int_value(row, "context_false_bytes") for row in output_fixture_rows)
    summary = {
        "scope": "total",
        "fixture_rows": str(len(output_fixture_rows)),
        "target_rows": str(len(output_target_rows)),
        "promoted_rows": str(sum(1 for row in output_target_rows if int_value(row, "context_added_bytes") > 0)),
        "base_clean_bytes": str(sum(int_value(row, "base_clean_bytes") for row in output_fixture_rows)),
        "context_candidate_bytes": str(sum(int_value(row, "context_candidate_bytes") for row in output_fixture_rows)),
        "context_added_bytes": str(context_added),
        "context_exact_bytes": str(sum(int_value(row, "context_exact_bytes") for row in output_fixture_rows)),
        "context_false_bytes": str(context_false),
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
        "review_ready_rows": "1" if context_ready(context_summary) else "0",
        "target_span_keys": ";".join(row.get("span_key", "") for row in output_target_rows),
        "threshold_context": threshold_context(context_summary),
        "promotion_ready_bytes": str(context_added if issue_rows == 0 and context_false == 0 else 0),
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
  <div class="box"><div class="num">{summary['context_added_bytes']}</div><div class="muted">context added bytes</div></div>
  <div class="box"><div class="num">{summary['promoted_rows']}/{summary['target_rows']}</div><div class="muted">promoted spans</div></div>
  <div class="box"><div class="num">{summary['context_false_bytes']}</div><div class="muted">false bytes</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
  <div class="box"><div class="num">{summary['remaining_unresolved_bytes']}</div><div class="muted">remaining unresolved</div></div>
</div>
<div class="panel"><h2>Files</h2>{links}</div>
<div class="panel"><h2>Fixtures</h2>{render_table(fixture_rows, FIXTURE_FIELDNAMES)}</div>
<div class="panel"><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</div>
<div class="panel"><h2>Bytes</h2>{render_table(byte_rows, BYTE_FIELDNAMES)}</div>
<script type="application/json" id="carrier-context-promoted-replay-data">{html.escape(data_json)}</script>
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
    parser.add_argument("--context-review", type=Path, default=DEFAULT_CONTEXT_REVIEW)
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Five-Byte Carrier Context Promoted Replay",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, fixture_rows, target_rows, byte_rows = build_rows(
        output_dir=args.output,
        fixture_rows=read_csv(args.fixtures),
        frontier_rows=read_csv(args.frontiers),
        base_fixture_rows=read_csv(args.base_fixtures),
        clean_decision_rows=read_csv(args.clean_decisions),
        context_review_rows=read_csv(args.context_review),
        target_rows=read_csv(args.targets),
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "fixtures.csv", FIXTURE_FIELDNAMES, fixture_rows)
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(args.output / "bytes.csv", BYTE_FIELDNAMES, byte_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, fixture_rows, target_rows, byte_rows, args.output, args.title), encoding="utf-8")

    print(f"Promoted spans: {summary['promoted_rows']}/{summary['target_rows']}")
    print(f"Added context bytes: {summary['context_added_bytes']}")
    print(f"False bytes: {summary['context_false_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
