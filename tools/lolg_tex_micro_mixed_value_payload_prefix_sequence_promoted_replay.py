#!/usr/bin/env python3
"""Promote guarded mixed-value prefix/sequence replay bytes into fixture buffers."""

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
from lolg_tex_micro_mixed_value_payload_prefix_sequence_replay import (
    DEFAULT_OUTPUT as DEFAULT_PREFIX_SEQUENCE_REPLAY_OUTPUT,
)


DEFAULT_OUTPUT = Path("output/tex_micro_mixed_value_payload_prefix_sequence_promoted_replay")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_FRONTIERS = Path("output/tex_gap_frontier_report/frontiers.csv")
DEFAULT_BASE_FIXTURES = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_fill_replay/fixtures.csv")
DEFAULT_CLEAN_DECISIONS = Path("output/tex_gap_decoder_clean_replay/decisions.csv")
DEFAULT_REPLAY_ROWS = DEFAULT_PREFIX_SEQUENCE_REPLAY_OUTPUT / "rows.csv"

SUMMARY_FIELDNAMES = [
    "scope",
    "fixture_rows",
    "replay_rows",
    "promoted_rows",
    "base_clean_bytes",
    "mixed_value_added_bytes",
    "mixed_value_exact_bytes",
    "mixed_value_false_bytes",
    "skipped_known_bytes",
    "skipped_rejected_bytes",
    "total_clean_bytes",
    "rejected_false_bytes",
    "remaining_unresolved_bytes",
    "native_previews",
    "fullhd_previews",
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
    "mixed_value_replay_rows",
    "mixed_value_added_bytes",
    "mixed_value_exact_bytes",
    "mixed_value_false_bytes",
    "skipped_known_bytes",
    "skipped_rejected_bytes",
    "total_clean_bytes",
    "rejected_false_bytes",
    "remaining_unresolved_bytes",
    "decoded_path",
    "known_mask_path",
    "mixed_value_mask_path",
    "native_preview_path",
    "fullhd_preview_path",
    "fullhd_width",
    "fullhd_height",
    "issues",
]

PROMOTION_FIELDNAMES = [
    "fixture_rank",
    "replay_rank",
    "stage",
    "row_index",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_index",
    "op_index",
    "absolute_offset",
    "relative_offset",
    "expected_byte",
    "predicted_byte",
    "base_known_overlap_bytes",
    "mixed_value_overlap_bytes",
    "rejected_overlap_bytes",
    "prerequisite_offsets",
    "prerequisites_available",
    "mixed_value_added_bytes",
    "mixed_value_exact_bytes",
    "mixed_value_false_bytes",
    "skipped_known_bytes",
    "skipped_rejected_bytes",
    "issues",
]

PROMOTABLE_VERDICTS = {"prefix_added", "sequence_added"}


def archive_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def parse_hex_byte(text: str, issues: list[str], label: str) -> int | None:
    if not text:
        issues.append(f"missing_{label}")
        return None
    try:
        value = int(text, 16)
    except ValueError:
        issues.append(f"invalid_{label}:{text}")
        return None
    if value < 0 or value > 0xFF:
        issues.append(f"{label}_out_of_range:{text}")
        return None
    return value


def byte_hex(data: bytes | bytearray, offset: int) -> str:
    if 0 <= offset < len(data):
        return f"{data[offset]:02x}"
    return "NA"


def grouped_replay_rows(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[archive_key(row)].append(row)
    for group in grouped.values():
        group.sort(key=lambda row: int_value(row, "rank"))
    return grouped


def row_known_or_added(known_mask: bytearray, mixed_value_mask: bytearray, offset: int) -> bool:
    return (
        0 <= offset < len(known_mask)
        and bool(known_mask[offset])
    ) or (
        0 <= offset < len(mixed_value_mask)
        and bool(mixed_value_mask[offset])
    )


def build_rows(
    *,
    output_dir: Path,
    fixture_rows: list[dict[str, str]],
    frontier_rows: list[dict[str, str]],
    base_fixture_rows: list[dict[str, str]],
    clean_decision_rows: list[dict[str, str]],
    replay_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    manifest_by_key = {archive_key(row): row for row in fixture_rows}
    fixture_rank_by_key = {archive_key(row): row.get("rank", "") for row in base_fixture_rows}
    frontiers = frontier_lookup(frontier_rows)
    rejected_by_fixture = rejected_ranges(clean_decision_rows)
    replay_groups = grouped_replay_rows(replay_rows)

    fixture_output_dir = output_dir / "fixtures"
    native_preview_dir = output_dir / "native"
    fullhd_preview_dir = output_dir / "fullhd"
    fixture_output_dir.mkdir(parents=True, exist_ok=True)
    native_preview_dir.mkdir(parents=True, exist_ok=True)
    fullhd_preview_dir.mkdir(parents=True, exist_ok=True)

    output_fixture_rows: list[dict[str, str]] = []
    promotion_rows: list[dict[str, str]] = []
    issue_rows = 0

    for base_fixture in sorted(
        base_fixture_rows,
        key=lambda row: fixture_sort_key((row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", ""))),
    ):
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

        rejected_key = (base_fixture.get("rank", ""), base_fixture.get("pcx_name", ""), base_fixture.get("frontier_id", ""))
        rejected_mask = bytearray(len(expected))
        for start, end in rejected_by_fixture.get(rejected_key, []):
            bounded_start = max(0, min(start, len(expected)))
            bounded_end = max(bounded_start, min(end, len(expected)))
            rejected_mask[bounded_start:bounded_end] = b"\xff" * (bounded_end - bounded_start)

        mixed_value_mask = bytearray(len(expected))
        stats: Counter[str] = Counter()
        for row in replay_groups.get(key, []):
            target_issues: list[str] = []
            offset = int_value(row, "absolute_offset")
            predicted = parse_hex_byte(row.get("predicted_byte", ""), target_issues, "predicted_byte")
            actual_expected = byte_hex(expected, offset)
            expected_value = None if actual_expected == "NA" else int(actual_expected, 16)
            base_overlap = overlap_bytes(known_mask, offset, offset + 1)
            mixed_overlap = overlap_bytes(mixed_value_mask, offset, offset + 1)
            rejected_overlap = overlap_bytes(rejected_mask, offset, offset + 1)
            prerequisite_offsets = [
                int(part) for part in row.get("prerequisites", "").split("|") if part
            ]
            prerequisites_available = all(
                row_known_or_added(known_mask, mixed_value_mask, prereq)
                for prereq in prerequisite_offsets
            )

            if row.get("verdict", "") not in PROMOTABLE_VERDICTS:
                target_issues.append("replay_row_not_promotable")
            if offset < 0 or offset >= len(expected):
                target_issues.append("offset_out_of_range")
            if predicted is not None and expected_value is not None and predicted != expected_value:
                target_issues.append("mixed_value_would_write_false_byte")
            if base_overlap and predicted is not None and offset < len(decoded) and decoded[offset] != predicted:
                target_issues.append("base_known_conflict")
            if mixed_overlap:
                target_issues.append("mixed_value_overlap")
            if row.get("stage") == "sequence" and not prerequisites_available:
                target_issues.append("missing_sequence_prerequisites")

            false_bytes = 1 if "mixed_value_would_write_false_byte" in target_issues else 0
            added_bytes = 0
            skipped_known = 0
            skipped_rejected = 0
            exact_bytes = 0
            if not target_issues:
                if base_overlap:
                    skipped_known = 1
                elif rejected_overlap:
                    skipped_rejected = 1
                elif predicted is not None:
                    decoded[offset] = predicted
                    known_mask[offset] = 0xFF
                    mixed_value_mask[offset] = 0xFF
                    added_bytes = 1
                    exact_bytes = 1
            else:
                issue_rows += 1

            stats["mixed_value_replay_rows"] += 1
            stats["mixed_value_added_bytes"] += added_bytes
            stats["mixed_value_exact_bytes"] += exact_bytes
            stats["mixed_value_false_bytes"] += false_bytes
            stats["skipped_known_bytes"] += skipped_known
            stats["skipped_rejected_bytes"] += skipped_rejected
            promotion_rows.append(
                {
                    "fixture_rank": fixture_rank_by_key.get(key, ""),
                    "replay_rank": row.get("rank", ""),
                    "stage": row.get("stage", ""),
                    "row_index": row.get("row_index", ""),
                    "archive": key[0],
                    "archive_tag": manifest.get("archive_tag", base_fixture.get("archive_tag", "")),
                    "pcx_name": key[1],
                    "frontier_id": key[2],
                    "span_index": row.get("span_index", ""),
                    "op_index": row.get("op_index", ""),
                    "absolute_offset": str(offset),
                    "relative_offset": row.get("relative_offset", ""),
                    "expected_byte": actual_expected,
                    "predicted_byte": row.get("predicted_byte", ""),
                    "base_known_overlap_bytes": str(base_overlap),
                    "mixed_value_overlap_bytes": str(mixed_overlap),
                    "rejected_overlap_bytes": str(rejected_overlap),
                    "prerequisite_offsets": "|".join(str(value) for value in prerequisite_offsets),
                    "prerequisites_available": "1" if prerequisites_available else "0",
                    "mixed_value_added_bytes": str(added_bytes),
                    "mixed_value_exact_bytes": str(exact_bytes),
                    "mixed_value_false_bytes": str(false_bytes),
                    "skipped_known_bytes": str(skipped_known),
                    "skipped_rejected_bytes": str(skipped_rejected),
                    "issues": ";".join(target_issues),
                }
            )

        if fixture_issues:
            issue_rows += 1
        stem = safe_stem(
            f"rank{int(base_fixture.get('rank', '0')):03d}" if base_fixture.get("rank", "").isdigit() else f"rank{base_fixture.get('rank', '')}",
            key[1],
            f"frontier{key[2]}",
        )
        decoded_path = fixture_output_dir / f"{stem}_decoded_mixed_value_prefix_sequence.bin"
        known_mask_path = fixture_output_dir / f"{stem}_known_mask.bin"
        mixed_value_mask_path = fixture_output_dir / f"{stem}_mixed_value_prefix_sequence_mask.bin"
        decoded_path.write_bytes(decoded)
        known_mask_path.write_bytes(known_mask)
        mixed_value_mask_path.write_bytes(mixed_value_mask)
        native_preview_path = native_preview_dir / f"{stem}_mixed_value_prefix_sequence.png"
        fullhd_preview_path = fullhd_preview_dir / f"{stem}_mixed_value_prefix_sequence_fullhd.png"
        fullhd_width, fullhd_height = render_preview(
            expected=expected,
            decoded=bytes(decoded),
            known_mask=bytes(known_mask),
            risk_mask=bytes(mixed_value_mask),
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
                "mixed_value_replay_rows": str(stats["mixed_value_replay_rows"]),
                "mixed_value_added_bytes": str(stats["mixed_value_added_bytes"]),
                "mixed_value_exact_bytes": str(stats["mixed_value_exact_bytes"]),
                "mixed_value_false_bytes": str(stats["mixed_value_false_bytes"]),
                "skipped_known_bytes": str(stats["skipped_known_bytes"]),
                "skipped_rejected_bytes": str(stats["skipped_rejected_bytes"]),
                "total_clean_bytes": str(total_clean),
                "rejected_false_bytes": str(rejected_false),
                "remaining_unresolved_bytes": str(max(0, fixture_bytes - total_clean - rejected_false)),
                "decoded_path": decoded_path.as_posix(),
                "known_mask_path": known_mask_path.as_posix(),
                "mixed_value_mask_path": mixed_value_mask_path.as_posix(),
                "native_preview_path": native_preview_path.as_posix(),
                "fullhd_preview_path": fullhd_preview_path.as_posix(),
                "fullhd_width": str(fullhd_width),
                "fullhd_height": str(fullhd_height),
                "issues": ";".join(fixture_issues),
            }
        )

    summary = {
        "scope": "total",
        "fixture_rows": str(len(output_fixture_rows)),
        "replay_rows": str(len(replay_rows)),
        "promoted_rows": str(sum(1 for row in promotion_rows if int_value(row, "mixed_value_added_bytes"))),
        "base_clean_bytes": str(sum(int_value(row, "base_clean_bytes") for row in output_fixture_rows)),
        "mixed_value_added_bytes": str(sum(int_value(row, "mixed_value_added_bytes") for row in output_fixture_rows)),
        "mixed_value_exact_bytes": str(sum(int_value(row, "mixed_value_exact_bytes") for row in output_fixture_rows)),
        "mixed_value_false_bytes": str(sum(int_value(row, "mixed_value_false_bytes") for row in output_fixture_rows)),
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
                if (row.get("fullhd_width"), row.get("fullhd_height"))
                == (str(TARGET_SIZE[0]), str(TARGET_SIZE[1]))
            )
        ),
        "issue_rows": str(issue_rows),
    }
    return summary, output_fixture_rows, promotion_rows


def render_preview_card(row: dict[str, str], output_dir: Path) -> str:
    image = html.escape(relative_href(row.get("fullhd_preview_path", ""), output_dir))
    return f"""
<article class="card">
  <a class="preview" href="{image}"><img src="{image}" loading="lazy" decoding="async" alt=""></a>
  <div class="card-body">
    <div class="card-title">#{html.escape(row.get('rank', ''))} {html.escape(row.get('pcx_name', ''))}</div>
    <div class="muted">+{html.escape(row.get('mixed_value_added_bytes', ''))} mixed-value - {html.escape(row.get('remaining_unresolved_bytes', ''))} unresolved</div>
    <a href="{image}">Full HD</a>
  </div>
</article>"""


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
    cards = "\n".join(render_preview_card(row, output_dir) for row in fixture_rows)
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
.wrap {{ width: min(1680px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12191b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 720; letter-spacing: 0; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }}
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 10px; }}
.stat, .panel, .card {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); }}
.stat, .panel {{ padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 22px; font-weight: 760; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.warn {{ color: var(--warn); }}
.panel {{ overflow-x: auto; }}
.preview {{ display: block; aspect-ratio: 16 / 9; background: #07090a; border-bottom: 1px solid var(--line); overflow: hidden; }}
.preview img {{ width: 100%; height: 100%; object-fit: contain; image-rendering: pixelated; }}
.card-body {{ padding: 10px; display: grid; gap: 6px; }}
.card-title {{ font-weight: 700; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1480px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Promotes guarded mixed-value prefix and sequence replay bytes over the tiny nonzero-fill buffers.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Added mixed-value bytes</div><div class="value ok">{summary['mixed_value_added_bytes']}</div></div>
    <div class="stat"><div class="label">Promoted rows</div><div class="value">{summary['promoted_rows']}/{summary['replay_rows']}</div></div>
    <div class="stat"><div class="label">False bytes</div><div class="value warn">{summary['mixed_value_false_bytes']}</div></div>
    <div class="stat"><div class="label">Remaining unresolved</div><div class="value">{summary['remaining_unresolved_bytes']}</div></div>
    <div class="stat"><div class="label">Issue rows</div><div class="value">{summary['issue_rows']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="cards">{cards}</section>
  <section class="panel"><h2>Fixtures</h2>{render_table(fixture_rows, FIXTURE_FIELDNAMES)}</section>
  <section class="panel"><h2>Promotions</h2>{render_table(promotion_rows, PROMOTION_FIELDNAMES)}</section>
</main>
<script>
const TEX_MICRO_MIXED_VALUE_PAYLOAD_PREFIX_SEQUENCE_PROMOTED_REPLAY = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Promote guarded mixed-value prefix/sequence replay bytes into fixture buffers."
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--frontiers", type=Path, default=DEFAULT_FRONTIERS)
    parser.add_argument("--base-fixtures", type=Path, default=DEFAULT_BASE_FIXTURES)
    parser.add_argument("--clean-decisions", type=Path, default=DEFAULT_CLEAN_DECISIONS)
    parser.add_argument("--replay-rows", type=Path, default=DEFAULT_REPLAY_ROWS)
    parser.add_argument("--title", default="Lands of Lore II .tex Mixed Value Prefix/Sequence Promoted Replay")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, fixture_rows, promotion_rows = build_rows(
        output_dir=args.output,
        fixture_rows=read_csv(args.fixtures),
        frontier_rows=read_csv(args.frontiers),
        base_fixture_rows=read_csv(args.base_fixtures),
        clean_decision_rows=read_csv(args.clean_decisions),
        replay_rows=read_csv(args.replay_rows),
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "fixtures.csv", FIXTURE_FIELDNAMES, fixture_rows)
    write_csv(args.output / "promotions.csv", PROMOTION_FIELDNAMES, promotion_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, fixture_rows, promotion_rows, args.output, args.title))

    print(f"Promoted rows: {summary['promoted_rows']}/{summary['replay_rows']}")
    print(f"Added mixed-value bytes: {summary['mixed_value_added_bytes']}")
    print(f"False bytes: {summary['mixed_value_false_bytes']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Remaining unresolved bytes: {summary['remaining_unresolved_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
