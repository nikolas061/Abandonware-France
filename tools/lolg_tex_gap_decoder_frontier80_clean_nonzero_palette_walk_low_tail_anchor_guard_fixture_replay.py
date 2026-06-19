#!/usr/bin/env python3
"""Promote low-tail guarded palette-walk values into Frontier80 fixtures."""

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
    byte_hex,
)


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_clean_nonzero_palette_walk_low_tail_anchor_guard_fixture_replay"
)
DEFAULT_BASE_FIXTURES = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_fixture_replay/fixtures.csv"
)
DEFAULT_VALUE_RUNS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_value_producer_probe/runs.csv"
)
DEFAULT_VALUE_ROWS = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_value_producer_probe/value_rows.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "fixture_rows",
    "value_rows",
    "promoted_rows",
    "base_clean_bytes",
    "palette_candidate_bytes",
    "palette_added_bytes",
    "palette_exact_bytes",
    "palette_false_bytes",
    "skipped_known_bytes",
    "skipped_rejected_bytes",
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
    "palette_value_rows",
    "palette_candidate_bytes",
    "palette_added_bytes",
    "palette_exact_bytes",
    "palette_false_bytes",
    "skipped_known_bytes",
    "skipped_rejected_bytes",
    "total_clean_bytes",
    "rejected_false_bytes",
    "remaining_unresolved_bytes",
    "decoded_path",
    "known_mask_path",
    "palette_mask_path",
    "native_preview_path",
    "fullhd_preview_path",
    "fullhd_width",
    "fullhd_height",
    "issues",
]

PROMOTION_FIELDNAMES = [
    "target_id",
    "palette_index",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "source_offset",
    "run_offset",
    "mode",
    "source_class",
    "normalized_value_hex",
    "predicted_byte",
    "expected_byte",
    "guard_key",
    "base_known_overlap_bytes",
    "palette_overlap_bytes",
    "rejected_overlap_bytes",
    "palette_added_bytes",
    "palette_exact_bytes",
    "palette_false_bytes",
    "skipped_known_bytes",
    "skipped_rejected_bytes",
    "issues",
]


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def fixture_rank_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def int_field(row: dict[str, str], field: str, default: int = 0) -> int:
    try:
        return int(row.get(field, ""))
    except (TypeError, ValueError):
        return default


def parse_hex_byte(value: str) -> int | None:
    text = value.strip().lower()
    if not text:
        return None
    if text.startswith("0x"):
        text = text[2:]
    try:
        return int(text, 16)
    except ValueError:
        return None


def hex_byte(value: int | None) -> str:
    return "" if value is None else f"{value & 0xFF:02x}"


def raw_palette_value(normalized: int | None, mode: str, issues: list[str]) -> int | None:
    if normalized is None:
        issues.append("missing_normalized_value")
        return None
    if mode == "high_add_0x11":
        return (normalized + 0x11) & 0xFF
    if mode == "low_identity":
        return normalized
    if mode == "invert_low_control":
        return normalized ^ 0xFF
    issues.append(f"unsupported_palette_mode:{mode}")
    return None


def manifest_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def value_targets(
    run_rows: list[dict[str, str]],
    value_rows: list[dict[str, str]],
) -> dict[tuple[str, str, str], list[dict[str, str]]]:
    runs = {row.get("target_id", ""): row for row in run_rows}
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in value_rows:
        run = runs.get(row.get("target_id", ""), {})
        if not run:
            continue
        key = fixture_key(run)
        merged = dict(row)
        merged.update(
            {
                "rank": run.get("rank", ""),
                "archive": run.get("archive", ""),
                "archive_tag": run.get("archive_tag", ""),
                "pcx_name": run.get("pcx_name", ""),
                "frontier_id": run.get("frontier_id", ""),
            }
        )
        grouped[key].append(merged)
    for rows in grouped.values():
        rows.sort(key=lambda row: (int_value(row, "absolute"), int_value(row, "palette_index")))
    return dict(grouped)


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
    value_run_rows: list[dict[str, str]],
    value_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    manifest_by_key = {manifest_key(row): row for row in fixture_rows}
    frontiers = frontier_lookup(frontier_rows)
    target_groups = value_targets(value_run_rows, value_rows)

    fixture_output_dir = output_dir / "fixtures"
    native_preview_dir = output_dir / "native"
    fullhd_preview_dir = output_dir / "fullhd"
    fixture_output_dir.mkdir(parents=True, exist_ok=True)
    native_preview_dir.mkdir(parents=True, exist_ok=True)
    fullhd_preview_dir.mkdir(parents=True, exist_ok=True)

    output_fixture_rows: list[dict[str, str]] = []
    promotion_rows: list[dict[str, str]] = []
    issue_rows = 0

    for base_fixture in sorted(base_fixture_rows, key=lambda row: fixture_sort_key(fixture_rank_key(row))):
        key = fixture_key(base_fixture)
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
        palette_mask = bytearray(len(expected))
        stats: Counter[str] = Counter()

        for target in target_groups.get(key, []):
            target_issues: list[str] = []
            offset = int_field(target, "absolute", -1)
            normalized = parse_hex_byte(target.get("produced_value_hex", ""))
            predicted = raw_palette_value(normalized, target.get("mode", ""), target_issues)
            expected_text = byte_hex(expected, offset)
            expected_value = None if expected_text == "NA" else int(expected_text, 16)
            base_overlap = overlap_bytes(known_mask, offset, offset + 1)
            palette_overlap = overlap_bytes(palette_mask, offset, offset + 1)
            rejected_overlap = overlap_bytes(rejected_mask, offset, offset + 1)

            if target.get("exact") != "1":
                target_issues.append("value_producer_not_exact")
            if offset < 0 or offset >= len(expected):
                target_issues.append("offset_out_of_range")
            if predicted is not None and expected_value is not None and predicted != expected_value:
                target_issues.append("palette_would_write_false_byte")
            if base_overlap and predicted is not None and offset < len(decoded) and decoded[offset] != predicted:
                target_issues.append("base_known_conflict")
            if palette_overlap:
                target_issues.append("palette_overlap")

            false_bytes = 1 if "palette_would_write_false_byte" in target_issues else 0
            added_bytes = 0
            exact_bytes = 0
            skipped_known = 0
            skipped_rejected = 0
            if not target_issues:
                if base_overlap:
                    skipped_known = 1
                elif rejected_overlap:
                    skipped_rejected = 1
                elif predicted is not None:
                    decoded[offset] = predicted
                    known_mask[offset] = 0xFF
                    palette_mask[offset] = 0xFF
                    added_bytes = 1
                    exact_bytes = 1
            else:
                issue_rows += 1

            stats["palette_candidate_bytes"] += 1
            stats["palette_added_bytes"] += added_bytes
            stats["palette_exact_bytes"] += exact_bytes
            stats["palette_false_bytes"] += false_bytes
            stats["skipped_known_bytes"] += skipped_known
            stats["skipped_rejected_bytes"] += skipped_rejected
            promotion_rows.append(
                {
                    "target_id": target.get("target_id", ""),
                    "palette_index": target.get("palette_index", ""),
                    "archive": key[0],
                    "archive_tag": manifest.get("archive_tag", base_fixture.get("archive_tag", "")),
                    "pcx_name": key[1],
                    "frontier_id": key[2],
                    "source_offset": str(offset),
                    "run_offset": target.get("run_offset", ""),
                    "mode": target.get("mode", ""),
                    "source_class": target.get("source_class", ""),
                    "normalized_value_hex": target.get("produced_value_hex", ""),
                    "predicted_byte": hex_byte(predicted),
                    "expected_byte": expected_text,
                    "guard_key": target.get("guard_key", ""),
                    "base_known_overlap_bytes": str(base_overlap),
                    "palette_overlap_bytes": str(palette_overlap),
                    "rejected_overlap_bytes": str(rejected_overlap),
                    "palette_added_bytes": str(added_bytes),
                    "palette_exact_bytes": str(exact_bytes),
                    "palette_false_bytes": str(false_bytes),
                    "skipped_known_bytes": str(skipped_known),
                    "skipped_rejected_bytes": str(skipped_rejected),
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
        decoded_path = fixture_output_dir / f"{stem}_decoded_palette_walk.bin"
        known_mask_path = fixture_output_dir / f"{stem}_known_mask.bin"
        palette_mask_path = fixture_output_dir / f"{stem}_palette_walk_mask.bin"
        decoded_path.write_bytes(decoded)
        known_mask_path.write_bytes(known_mask)
        palette_mask_path.write_bytes(palette_mask)
        native_preview_path = native_preview_dir / f"{stem}_palette_walk.png"
        fullhd_preview_path = fullhd_preview_dir / f"{stem}_palette_walk_fullhd.png"
        fullhd_width, fullhd_height = render_preview(
            expected=expected,
            decoded=bytes(decoded),
            known_mask=bytes(known_mask),
            risk_mask=bytes(palette_mask),
            frontier=frontiers.get((key[0], key[1], key[2]), {}),
            native_path=native_preview_path,
            fullhd_path=fullhd_preview_path,
        )

        base_clean = int_field(base_fixture, "total_clean_bytes")
        rejected_false = int_field(base_fixture, "rejected_false_bytes")
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
                "palette_value_rows": str(len(target_groups.get(key, []))),
                "palette_candidate_bytes": str(stats["palette_candidate_bytes"]),
                "palette_added_bytes": str(stats["palette_added_bytes"]),
                "palette_exact_bytes": str(stats["palette_exact_bytes"]),
                "palette_false_bytes": str(stats["palette_false_bytes"]),
                "skipped_known_bytes": str(stats["skipped_known_bytes"]),
                "skipped_rejected_bytes": str(stats["skipped_rejected_bytes"]),
                "total_clean_bytes": str(total_clean),
                "rejected_false_bytes": str(rejected_false),
                "remaining_unresolved_bytes": str(max(0, fixture_bytes - total_clean - rejected_false)),
                "decoded_path": decoded_path.as_posix(),
                "known_mask_path": known_mask_path.as_posix(),
                "palette_mask_path": palette_mask_path.as_posix(),
                "native_preview_path": native_preview_path.as_posix(),
                "fullhd_preview_path": fullhd_preview_path.as_posix(),
                "fullhd_width": str(fullhd_width),
                "fullhd_height": str(fullhd_height),
                "issues": ";".join(fixture_issues),
            }
        )

    palette_added = sum(int_field(row, "palette_added_bytes") for row in output_fixture_rows)
    palette_false = sum(int_field(row, "palette_false_bytes") for row in output_fixture_rows)
    summary = {
        "scope": "total",
        "fixture_rows": str(len(output_fixture_rows)),
        "value_rows": str(sum(len(rows) for rows in target_groups.values())),
        "promoted_rows": str(sum(1 for row in promotion_rows if int_field(row, "palette_added_bytes") > 0)),
        "base_clean_bytes": str(sum(int_field(row, "base_clean_bytes") for row in output_fixture_rows)),
        "palette_candidate_bytes": str(sum(int_field(row, "palette_candidate_bytes") for row in output_fixture_rows)),
        "palette_added_bytes": str(palette_added),
        "palette_exact_bytes": str(sum(int_field(row, "palette_exact_bytes") for row in output_fixture_rows)),
        "palette_false_bytes": str(palette_false),
        "skipped_known_bytes": str(sum(int_field(row, "skipped_known_bytes") for row in output_fixture_rows)),
        "skipped_rejected_bytes": str(sum(int_field(row, "skipped_rejected_bytes") for row in output_fixture_rows)),
        "total_clean_bytes": str(sum(int_field(row, "total_clean_bytes") for row in output_fixture_rows)),
        "rejected_false_bytes": str(sum(int_field(row, "rejected_false_bytes") for row in output_fixture_rows)),
        "remaining_unresolved_bytes": str(sum(int_field(row, "remaining_unresolved_bytes") for row in output_fixture_rows)),
        "native_previews": str(sum(1 for row in output_fixture_rows if row.get("native_preview_path"))),
        "fullhd_previews": str(
            sum(
                1
                for row in output_fixture_rows
                if (row.get("fullhd_width"), row.get("fullhd_height")) == (str(TARGET_SIZE[0]), str(TARGET_SIZE[1]))
            )
        ),
        "promotion_ready_bytes": str(palette_added if issue_rows == 0 and palette_false == 0 else 0),
        "issue_rows": str(issue_rows),
        "review_verdict": (
            "frontier80_clean_nonzero_palette_walk_low_tail_guard_fixture_replay_ready"
            if issue_rows == 0 and palette_false == 0 and palette_added > 0
            else "frontier80_clean_nonzero_palette_walk_low_tail_guard_fixture_replay_weak"
        ),
        "next_probe": (
            "rerun Frontier80 clean-gap queue after palette-walk fixture replay"
            if issue_rows == 0 and palette_false == 0 and palette_added > 0
            else "review palette-walk fixture promotion issues"
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
:root {{
  color-scheme: dark;
  --bg: #101417;
  --panel: #171f22;
  --line: #31424a;
  --text: #edf5f4;
  --muted: #9dafb5;
  --accent: #77d3b1;
  --warn: #f0c36a;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; min-height: 100vh; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
.wrap {{ width: min(1680px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12191b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 720; letter-spacing: 0; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 22px; font-weight: 760; line-height: 1.05; margin-top: 4px; }}
.warn {{ color: var(--warn); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1320px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Promotes raw palette-walk bytes from the low-tail guarded value producer into fixture buffers.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Added bytes</div><div class="value">{html.escape(summary['palette_added_bytes'])}</div></div>
    <div class="stat"><div class="label">Exact bytes</div><div class="value">{html.escape(summary['palette_exact_bytes'])}/{html.escape(summary['palette_candidate_bytes'])}</div></div>
    <div class="stat"><div class="label">False bytes</div><div class="value warn">{html.escape(summary['palette_false_bytes'])}</div></div>
    <div class="stat"><div class="label">Promotion ready</div><div class="value">{html.escape(summary['promotion_ready_bytes'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="sub">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</div></section>
  <section class="panel"><h2>Fixtures</h2>{render_table(fixture_rows, FIXTURE_FIELDNAMES)}</section>
  <section class="panel"><h2>Promotions</h2>{render_table(promotion_rows, PROMOTION_FIELDNAMES)}</section>
</main>
<script type="application/json" id="palette-walk-low-tail-fixture-replay-data">{data_json}</script>
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
    parser.add_argument("--value-runs", type=Path, default=DEFAULT_VALUE_RUNS)
    parser.add_argument("--value-rows", type=Path, default=DEFAULT_VALUE_ROWS)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Clean Nonzero Palette Walk Low-Tail Guard Fixture Replay",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, fixture_rows, promotion_rows = build_rows(
        output_dir=args.output,
        fixture_rows=read_csv(args.fixtures),
        frontier_rows=read_csv(args.frontiers),
        base_fixture_rows=read_csv(args.base_fixtures),
        clean_decision_rows=read_csv(args.clean_decisions),
        value_run_rows=read_csv(args.value_runs),
        value_rows=read_csv(args.value_rows),
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "fixtures.csv", FIXTURE_FIELDNAMES, fixture_rows)
    write_csv(args.output / "promotions.csv", PROMOTION_FIELDNAMES, promotion_rows)
    (args.output / "index.html").write_text(build_html(summary, fixture_rows, promotion_rows, args.output, args.title))
    print(f"Promoted rows: {summary['promoted_rows']}/{summary['value_rows']}")
    print(f"Added palette bytes: {summary['palette_added_bytes']}")
    print(f"False bytes: {summary['palette_false_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
