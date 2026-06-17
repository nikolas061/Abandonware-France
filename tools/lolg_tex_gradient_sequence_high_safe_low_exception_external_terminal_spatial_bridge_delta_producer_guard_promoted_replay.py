#!/usr/bin/env python3
"""Promote guarded compact/control bridge delta producer bytes into fixtures."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_decoder_len64_promoted_replay import count_mask, read_csv, rejected_ranges
from lolg_tex_gap_decoder_seed_replay import fixture_sort_key, load_bytes, safe_stem
from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_micro_mixed_value_payload_prefix_sequence_promoted_replay import (
    DEFAULT_CLEAN_DECISIONS,
    DEFAULT_FIXTURES,
    archive_key,
)
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value


DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer_guard_promoted_replay"
)
DEFAULT_BASE_FIXTURES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_promoted_replay/fixtures.csv"
)
DEFAULT_GUARD_TARGETS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer_guard/targets.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "fixture_rows",
    "target_rows",
    "promoted_rows",
    "base_clean_bytes",
    "guard_candidate_bytes",
    "guard_added_bytes",
    "guard_exact_bytes",
    "guard_false_bytes",
    "skipped_known_bytes",
    "skipped_rejected_bytes",
    "total_clean_bytes",
    "rejected_false_bytes",
    "remaining_unresolved_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

EXTRA_FIXTURE_FIELDNAMES = [
    "guard_target_rows",
    "guard_candidate_bytes",
    "guard_added_bytes",
    "guard_exact_bytes",
    "guard_false_bytes",
    "skipped_known_bytes",
    "skipped_rejected_bytes",
    "total_clean_bytes",
    "rejected_false_bytes",
    "remaining_unresolved_bytes",
    "guard_mask_path",
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
    "guard_family",
    "guard_key",
    "guard_direction",
    "guard_threshold",
    "guard_verdict",
    "guard_candidate_bytes",
    "guard_added_bytes",
    "guard_exact_bytes",
    "guard_false_bytes",
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
    "guard_overlap_bytes",
    "rejected_overlap_bytes",
    "guard_added_bytes",
    "guard_exact_bytes",
    "guard_false_bytes",
    "skipped_known_bytes",
    "skipped_rejected_bytes",
    "issues",
]


def read_rows_with_fields(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def context_ready(row: dict[str, str]) -> bool:
    return (
        row.get("promotion_ready") == "1"
        and row.get("guard_verdict") == "known_false_free_threshold"
        and row.get("expected_hex", "") == row.get("best_output_hex", "")
    )


def byte_text(value: int) -> str:
    return f"{value & 0xFF:02x}"


def grouped_targets(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if context_ready(row):
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


def fixture_fieldnames(base_fieldnames: list[str]) -> list[str]:
    fields = list(base_fieldnames)
    for field in EXTRA_FIXTURE_FIELDNAMES:
        if field not in fields:
            fields.append(field)
    return fields


def build_rows(
    *,
    output_dir: Path,
    manifest_rows: list[dict[str, str]],
    base_fixture_rows: list[dict[str, str]],
    base_fixture_fields: list[str],
    clean_decision_rows: list[dict[str, str]],
    guard_target_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[str]]:
    targets_by_fixture = grouped_targets(guard_target_rows)
    manifest_by_key = {archive_key(row): row for row in manifest_rows}
    fixture_output_dir = output_dir / "fixtures"
    fixture_output_dir.mkdir(parents=True, exist_ok=True)
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
        guard_mask = bytearray(len(expected))
        stats: Counter[str] = Counter()
        targets = targets_by_fixture.get(key, [])

        for target in targets:
            target_stats: Counter[str] = Counter()
            target_issues: list[str] = []
            start = int_value(target, "span_start", -1)
            end = int_value(target, "span_end", -1)
            predicted = bytes.fromhex(target.get("best_output_hex", ""))
            expected_hex = target.get("expected_hex", "")
            if start < 0 or end < start or len(predicted) != end - start:
                target_issues.append("invalid_guard_span")
            if predicted.hex() != expected_hex:
                target_issues.append("guard_output_mismatch")
            for rel, predicted_byte in enumerate(predicted):
                absolute = start + rel
                byte_issues: list[str] = []
                if absolute < 0 or absolute >= len(expected):
                    byte_issues.append("byte_out_of_range")
                    target_stats["guard_false_bytes"] += 1
                    continue
                target_stats["guard_candidate_bytes"] += 1
                base_known = 1 if known_mask[absolute] else 0
                guard_overlap = 1 if guard_mask[absolute] else 0
                rejected_overlap = 1 if rejected_mask[absolute] else 0
                expected_byte = expected[absolute]
                if base_known:
                    target_stats["skipped_known_bytes"] += 1
                    byte_issues.append("base_known")
                elif rejected_overlap:
                    target_stats["skipped_rejected_bytes"] += 1
                    byte_issues.append("rejected_clean_decision")
                elif predicted_byte == expected_byte:
                    decoded[absolute] = predicted_byte
                    known_mask[absolute] = 255
                    guard_mask[absolute] = 255
                    target_stats["guard_added_bytes"] += 1
                    target_stats["guard_exact_bytes"] += 1
                else:
                    target_stats["guard_false_bytes"] += 1
                    byte_issues.append("predicted_false")
                output_byte_rows.append(
                    {
                        "target_rank": "",
                        "byte_rank": str(rel + 1),
                        "archive": key[0],
                        "archive_tag": base_fixture.get("archive_tag", manifest.get("archive_tag", "")),
                        "pcx_name": key[1],
                        "frontier_id": key[2],
                        "span_key": target.get("span_key", ""),
                        "absolute_offset": str(absolute),
                        "relative_offset": str(rel),
                        "expected_byte": byte_text(expected_byte),
                        "predicted_byte": byte_text(predicted_byte),
                        "base_known_overlap_bytes": str(base_known),
                        "guard_overlap_bytes": str(guard_overlap),
                        "rejected_overlap_bytes": str(rejected_overlap),
                        "guard_added_bytes": "1" if "guard_added_bytes" in target_stats and not byte_issues else "0",
                        "guard_exact_bytes": "1" if predicted_byte == expected_byte and not byte_issues else "0",
                        "guard_false_bytes": "1" if "predicted_false" in byte_issues else "0",
                        "skipped_known_bytes": str(base_known),
                        "skipped_rejected_bytes": str(rejected_overlap),
                        "issues": ";".join(byte_issues),
                    }
                )
            stats.update(target_stats)
            output_target_rows.append(
                {
                    "fixture_rank": base_fixture.get("rank", ""),
                    "target_rank": "",
                    "archive": key[0],
                    "archive_tag": base_fixture.get("archive_tag", manifest.get("archive_tag", "")),
                    "pcx_name": key[1],
                    "frontier_id": key[2],
                    "span_key": target.get("span_key", ""),
                    "span_start": target.get("span_start", ""),
                    "span_end": target.get("span_end", ""),
                    "span_length": target.get("span_length", ""),
                    "expected_hex": expected_hex,
                    "predicted_hex": predicted.hex(),
                    "best_family": target.get("best_family", ""),
                    "best_selector": target.get("best_selector", ""),
                    "guard_family": target.get("guard_family", ""),
                    "guard_key": target.get("guard_key", ""),
                    "guard_direction": target.get("guard_direction", ""),
                    "guard_threshold": target.get("guard_threshold", ""),
                    "guard_verdict": target.get("guard_verdict", ""),
                    "guard_candidate_bytes": str(target_stats["guard_candidate_bytes"]),
                    "guard_added_bytes": str(target_stats["guard_added_bytes"]),
                    "guard_exact_bytes": str(target_stats["guard_exact_bytes"]),
                    "guard_false_bytes": str(target_stats["guard_false_bytes"]),
                    "skipped_known_bytes": str(target_stats["skipped_known_bytes"]),
                    "skipped_rejected_bytes": str(target_stats["skipped_rejected_bytes"]),
                    "issues": ";".join(target_issues),
                }
            )

        stem = safe_stem(*key)
        decoded_path = fixture_output_dir / f"{stem}.decoded.bin"
        known_path = fixture_output_dir / f"{stem}.known_mask.bin"
        guard_mask_path = fixture_output_dir / f"{stem}.guard_mask.bin"
        decoded_path.write_bytes(decoded)
        known_path.write_bytes(known_mask)
        guard_mask_path.write_bytes(guard_mask)
        if fixture_issues:
            issue_rows += 1
        output_fixture_rows.append(
            {
                **{field: base_fixture.get(field, "") for field in base_fixture_fields},
                "decoded_path": str(decoded_path),
                "known_mask_path": str(known_path),
                "guard_mask_path": str(guard_mask_path),
                "guard_target_rows": str(len(targets)),
                "guard_candidate_bytes": str(stats["guard_candidate_bytes"]),
                "guard_added_bytes": str(stats["guard_added_bytes"]),
                "guard_exact_bytes": str(stats["guard_exact_bytes"]),
                "guard_false_bytes": str(stats["guard_false_bytes"]),
                "skipped_known_bytes": str(stats["skipped_known_bytes"]),
                "skipped_rejected_bytes": str(stats["skipped_rejected_bytes"]),
                "total_clean_bytes": str(count_mask(known_mask)),
                "rejected_false_bytes": str(count_mask(rejected_mask)),
                "remaining_unresolved_bytes": str(max(0, len(expected) - count_mask(known_mask))),
                "issues": ";".join(fixture_issues),
            }
        )

    target_rank_by_span: dict[str, str] = {}
    for index, row in enumerate(output_target_rows, start=1):
        row["target_rank"] = str(index)
        target_rank_by_span[row.get("span_key", "")] = str(index)
    for row in output_byte_rows:
        row["target_rank"] = target_rank_by_span.get(row.get("span_key", ""), row.get("target_rank", ""))

    summary = {
        "scope": "total",
        "fixture_rows": str(len(output_fixture_rows)),
        "target_rows": str(len([row for row in guard_target_rows if context_ready(row)])),
        "promoted_rows": str(sum(1 for row in output_target_rows if int_value(row, "guard_added_bytes") > 0)),
        "base_clean_bytes": str(sum(int_value(row, "base_clean_bytes", int_value(row, "total_clean_bytes")) for row in base_fixture_rows)),
        "guard_candidate_bytes": str(sum(int_value(row, "guard_candidate_bytes") for row in output_fixture_rows)),
        "guard_added_bytes": str(sum(int_value(row, "guard_added_bytes") for row in output_fixture_rows)),
        "guard_exact_bytes": str(sum(int_value(row, "guard_exact_bytes") for row in output_fixture_rows)),
        "guard_false_bytes": str(sum(int_value(row, "guard_false_bytes") for row in output_fixture_rows)),
        "skipped_known_bytes": str(sum(int_value(row, "skipped_known_bytes") for row in output_fixture_rows)),
        "skipped_rejected_bytes": str(sum(int_value(row, "skipped_rejected_bytes") for row in output_fixture_rows)),
        "total_clean_bytes": str(sum(int_value(row, "total_clean_bytes") for row in output_fixture_rows)),
        "rejected_false_bytes": str(sum(int_value(row, "rejected_false_bytes") for row in output_fixture_rows)),
        "remaining_unresolved_bytes": str(sum(int_value(row, "remaining_unresolved_bytes") for row in output_fixture_rows)),
        "promotion_ready_bytes": str(sum(int_value(row, "guard_added_bytes") for row in output_fixture_rows)),
        "issue_rows": str(issue_rows + sum(1 for row in output_target_rows if row.get("issues"))),
    }
    return summary, output_fixture_rows, output_target_rows, output_byte_rows, fixture_fieldnames(base_fixture_fields)


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 140) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    fixture_rows: list[dict[str, str]],
    fixture_fields: list[str],
    target_rows: list[dict[str, str]],
    byte_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "fixtures": fixture_rows,
        "targets": target_rows,
        "bytes": byte_rows,
    }
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
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme: dark; --bg: #101417; --panel: #171f22; --line: #31424a; --text: #edf5f4; --muted: #9dafb5; --accent: #77d3b1; --warn: #f0b36c; }}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, sans-serif; }}
main {{ width: min(1680px, calc(100vw - 28px)); margin: 0 auto; padding: 22px 0 32px; display: grid; gap: 16px; }}
h1 {{ margin: 0; font-size: 22px; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.muted {{ color: var(--muted); }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.value {{ font-size: 22px; font-weight: 760; color: var(--accent); }}
.warn {{ color: var(--warn); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; min-width: 1420px; border-collapse: collapse; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<main>
  <header>
    <h1>{html.escape(title)}</h1>
    <div class="muted">Promotes only guarded compact/control bridge delta producer bytes over the current fixture base.</div>
  </header>
  <section class="stats">
    <div class="stat"><div class="muted">Guard candidate bytes</div><div class="value">{summary['guard_candidate_bytes']}</div></div>
    <div class="stat"><div class="muted">Added bytes</div><div class="value">{summary['guard_added_bytes']}</div></div>
    <div class="stat"><div class="muted">False bytes</div><div class="value warn">{summary['guard_false_bytes']}</div></div>
    <div class="stat"><div class="muted">Promotion-ready</div><div class="value">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2>{links}</section>
  <section class="panel"><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</section>
  <section class="panel"><h2>Bytes</h2>{render_table(byte_rows, BYTE_FIELDNAMES)}</section>
  <section class="panel"><h2>Fixtures</h2>{render_table(fixture_rows, fixture_fields)}</section>
  <script type="application/json" id="external-terminal-spatial-bridge-delta-producer-guard-promoted-data">{html.escape(data_json)}</script>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote guarded compact/control bridge delta producer bytes.")
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--base-fixtures", type=Path, default=DEFAULT_BASE_FIXTURES)
    parser.add_argument("--clean-decisions", type=Path, default=DEFAULT_CLEAN_DECISIONS)
    parser.add_argument("--guard-targets", type=Path, default=DEFAULT_GUARD_TARGETS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Guarded Delta Producer Promoted Replay",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    base_fixture_rows, base_fixture_fields = read_rows_with_fields(args.base_fixtures)
    summary, fixture_rows, target_rows, byte_rows, fixture_fields = build_rows(
        output_dir=args.output,
        manifest_rows=read_csv(args.fixtures),
        base_fixture_rows=base_fixture_rows,
        base_fixture_fields=base_fixture_fields,
        clean_decision_rows=read_csv(args.clean_decisions),
        guard_target_rows=read_csv(args.guard_targets),
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "fixtures.csv", fixture_fields, fixture_rows)
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(args.output / "bytes.csv", BYTE_FIELDNAMES, byte_rows)
    (args.output / "index.html").write_text(
        build_html(summary, fixture_rows, fixture_fields, target_rows, byte_rows, args.output, args.title),
        encoding="utf-8",
    )
    print(f"Fixture rows: {summary['fixture_rows']}")
    print(f"Promoted rows: {summary['promoted_rows']}")
    print(f"Guard added bytes: {summary['guard_added_bytes']}")
    print(f"Guard false bytes: {summary['guard_false_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
