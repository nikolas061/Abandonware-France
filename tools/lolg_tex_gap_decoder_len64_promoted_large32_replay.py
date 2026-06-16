#!/usr/bin/env python3
"""Replay false-free large32 selector targets on top of len64-promoted buffers."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
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
    fixture_key,
    fixture_sort_key,
    frontier_lookup,
    load_bytes,
    render_preview,
    safe_stem,
)
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_large32_replay")
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_FRONTIERS = Path("output/tex_gap_frontier_report/frontiers.csv")
DEFAULT_BASE_FIXTURES = Path("output/tex_gap_decoder_len64_promoted_replay/fixtures.csv")
DEFAULT_CLEAN_DECISIONS = Path("output/tex_gap_decoder_clean_replay/decisions.csv")
DEFAULT_SELECTOR_TARGETS = Path("output/tex_gap_decoder_len64_promoted_large32_selector_probe/targets.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "fixture_rows",
    "target_rows",
    "promoted_target_rows",
    "base_clean_bytes",
    "selector_added_bytes",
    "selector_exact_bytes",
    "selector_false_bytes",
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
    "selector_target_rows",
    "selector_added_bytes",
    "selector_exact_bytes",
    "selector_false_bytes",
    "total_clean_bytes",
    "rejected_false_bytes",
    "remaining_unresolved_bytes",
    "decoded_path",
    "known_mask_path",
    "selector_mask_path",
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
    "run_index",
    "op_index",
    "expected_start",
    "expected_end",
    "length",
    "signature",
    "greedy_selector",
    "base_known_overlap_bytes",
    "rejected_overlap_bytes",
    "selector_added_bytes",
    "selector_exact_bytes",
    "selector_false_bytes",
    "issues",
]


def bounded_range(row: dict[str, str], size: int) -> tuple[int, int]:
    start = max(0, min(int_value(row, "start"), size))
    end = max(start, min(int_value(row, "end"), size))
    return start, end


def targets_by_fixture(target_rows: list[dict[str, str]]) -> dict[tuple[str, str, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in target_rows:
        if row.get("greedy_selector"):
            grouped[fixture_key(row)].append(row)
    return grouped


def build_rows(
    *,
    output_dir: Path,
    fixture_rows: list[dict[str, str]],
    frontier_rows: list[dict[str, str]],
    base_fixture_rows: list[dict[str, str]],
    clean_decision_rows: list[dict[str, str]],
    selector_target_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    manifest_by_key = {fixture_key(row): row for row in fixture_rows}
    frontiers = frontier_lookup(frontier_rows)
    rejected_by_fixture = rejected_ranges(clean_decision_rows)
    target_groups = targets_by_fixture(selector_target_rows)

    fixture_output_dir = output_dir / "fixtures"
    native_preview_dir = output_dir / "native"
    fullhd_preview_dir = output_dir / "fullhd"
    fixture_output_dir.mkdir(parents=True, exist_ok=True)
    native_preview_dir.mkdir(parents=True, exist_ok=True)
    fullhd_preview_dir.mkdir(parents=True, exist_ok=True)

    output_fixture_rows: list[dict[str, str]] = []
    promotion_rows: list[dict[str, str]] = []
    issue_rows = 0

    for base_fixture in sorted(base_fixture_rows, key=lambda row: fixture_sort_key(fixture_key(row))):
        key = fixture_key(base_fixture)
        manifest = manifest_by_key.get(key, {})
        fixture_issues: list[str] = []
        expected = load_bytes(manifest.get("expected_gap_path", ""), fixture_issues, "expected")
        decoded = bytearray(load_bytes(base_fixture.get("decoded_path", ""), fixture_issues, "decoded"))
        known_mask = bytearray(load_bytes(base_fixture.get("known_mask_path", ""), fixture_issues, "known_mask"))
        accepted_mask = bytearray(known_mask)
        if len(decoded) != len(expected):
            fixture_issues.append("decoded_size_mismatch")
            decoded = decoded[: len(expected)] + bytearray(max(0, len(expected) - len(decoded)))
        if len(known_mask) != len(expected):
            fixture_issues.append("known_mask_size_mismatch")
            known_mask = known_mask[: len(expected)] + bytearray(max(0, len(expected) - len(known_mask)))
        if len(accepted_mask) != len(expected):
            accepted_mask = accepted_mask[: len(expected)] + bytearray(max(0, len(expected) - len(accepted_mask)))

        rejected_mask = bytearray(len(expected))
        for start, end in rejected_by_fixture.get(key, []):
            bounded_start = max(0, min(start, len(expected)))
            bounded_end = max(bounded_start, min(end, len(expected)))
            rejected_mask[bounded_start:bounded_end] = b"\xff" * (bounded_end - bounded_start)

        selector_mask = bytearray(len(expected))
        stats = {
            "selector_target_rows": 0,
            "selector_added_bytes": 0,
            "selector_exact_bytes": 0,
            "selector_false_bytes": 0,
        }

        for target in sorted(target_groups.get(key, []), key=lambda row: (int_value(row, "start"), int_value(row, "op_index"))):
            target_issues: list[str] = []
            start, end = bounded_range(target, len(expected))
            target_length = int_value(target, "length")
            expected_slice = expected[start:end]
            base_overlap = overlap_bytes(known_mask, start, end)
            rejected_overlap = overlap_bytes(rejected_mask, start, end)
            false_bytes = sum(1 for value in expected_slice if value != 0)
            exact_bytes = len(expected_slice) - false_bytes
            if target.get("length_bucket") != "large32":
                target_issues.append("target_not_large32")
            if target.get("signature") != "internal|large32|left_nonzero|right_nonzero":
                target_issues.append("target_signature_mismatch")
            if end - start != target_length:
                target_issues.append("target_range_length_mismatch")
            if not target.get("greedy_selector"):
                target_issues.append("missing_greedy_selector")
            if base_overlap:
                target_issues.append("base_known_overlap")
            if rejected_overlap:
                target_issues.append("rejected_overlap")
            if false_bytes:
                target_issues.append("selector_would_write_false_bytes")

            if not target_issues:
                decoded[start:end] = b"\x00" * (end - start)
                known_mask[start:end] = b"\xff" * (end - start)
                accepted_mask[start:end] = b"\xff" * (end - start)
                selector_mask[start:end] = b"\xff" * (end - start)
                stats["selector_added_bytes"] += end - start
                stats["selector_exact_bytes"] += exact_bytes
                stats["selector_false_bytes"] += false_bytes
            else:
                issue_rows += 1
            stats["selector_target_rows"] += 1

            promotion_rows.append(
                {
                    "rank": target.get("rank", ""),
                    "archive": target.get("archive", ""),
                    "archive_tag": target.get("archive_tag", ""),
                    "pcx_name": target.get("pcx_name", ""),
                    "frontier_id": target.get("frontier_id", ""),
                    "span_index": target.get("span_index", ""),
                    "run_index": target.get("run_index", ""),
                    "op_index": target.get("op_index", ""),
                    "expected_start": str(start),
                    "expected_end": str(end),
                    "length": str(target_length),
                    "signature": target.get("signature", ""),
                    "greedy_selector": target.get("greedy_selector", ""),
                    "base_known_overlap_bytes": str(base_overlap),
                    "rejected_overlap_bytes": str(rejected_overlap),
                    "selector_added_bytes": str(0 if target_issues else end - start),
                    "selector_exact_bytes": str(0 if target_issues else exact_bytes),
                    "selector_false_bytes": str(false_bytes),
                    "issues": ";".join(target_issues),
                }
            )

        if fixture_issues:
            issue_rows += 1
        stem = safe_stem(
            f"rank{int(key[0]):03d}" if key[0].isdigit() else f"rank{key[0]}",
            key[1],
            f"frontier{key[2]}",
        )
        decoded_path = fixture_output_dir / f"{stem}_decoded_large32_promoted.bin"
        known_mask_path = fixture_output_dir / f"{stem}_known_mask.bin"
        selector_mask_path = fixture_output_dir / f"{stem}_selector_mask.bin"
        decoded_path.write_bytes(decoded)
        known_mask_path.write_bytes(known_mask)
        selector_mask_path.write_bytes(selector_mask)
        native_preview_path = native_preview_dir / f"{stem}_large32_promoted.png"
        fullhd_preview_path = fullhd_preview_dir / f"{stem}_large32_promoted_fullhd.png"
        fullhd_width, fullhd_height = render_preview(
            expected=expected,
            decoded=bytes(decoded),
            known_mask=bytes(known_mask),
            risk_mask=bytes(accepted_mask),
            frontier=frontiers.get((manifest.get("archive", ""), key[1], key[2]), {}),
            native_path=native_preview_path,
            fullhd_path=fullhd_preview_path,
        )

        base_clean = int_value(base_fixture, "total_clean_bytes")
        rejected_false = int_value(base_fixture, "rejected_false_bytes")
        total_clean = count_mask(known_mask)
        fixture_bytes = len(expected)
        output_fixture_rows.append(
            {
                "rank": key[0],
                "archive": manifest.get("archive", base_fixture.get("archive", "")),
                "archive_tag": manifest.get("archive_tag", base_fixture.get("archive_tag", "")),
                "pcx_name": key[1],
                "frontier_id": key[2],
                "fixture_bytes": str(fixture_bytes),
                "base_clean_bytes": str(base_clean),
                "selector_target_rows": str(stats["selector_target_rows"]),
                "selector_added_bytes": str(stats["selector_added_bytes"]),
                "selector_exact_bytes": str(stats["selector_exact_bytes"]),
                "selector_false_bytes": str(stats["selector_false_bytes"]),
                "total_clean_bytes": str(total_clean),
                "rejected_false_bytes": str(rejected_false),
                "remaining_unresolved_bytes": str(max(0, fixture_bytes - total_clean - rejected_false)),
                "decoded_path": decoded_path.as_posix(),
                "known_mask_path": known_mask_path.as_posix(),
                "selector_mask_path": selector_mask_path.as_posix(),
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
        "target_rows": str(sum(int_value(row, "selector_target_rows") for row in output_fixture_rows)),
        "promoted_target_rows": str(sum(1 for row in promotion_rows if int_value(row, "selector_added_bytes"))),
        "base_clean_bytes": str(sum(int_value(row, "base_clean_bytes") for row in output_fixture_rows)),
        "selector_added_bytes": str(sum(int_value(row, "selector_added_bytes") for row in output_fixture_rows)),
        "selector_exact_bytes": str(sum(int_value(row, "selector_exact_bytes") for row in output_fixture_rows)),
        "selector_false_bytes": str(sum(int_value(row, "selector_false_bytes") for row in output_fixture_rows)),
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
    <div class="muted">+{html.escape(row.get('selector_added_bytes', ''))} large32 - {html.escape(row.get('remaining_unresolved_bytes', ''))} unresolved</div>
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
.panel {{ overflow-x: auto; }}
.preview {{ display: block; aspect-ratio: 16 / 9; background: #07090a; border-bottom: 1px solid var(--line); overflow: hidden; }}
.preview img {{ width: 100%; height: 100%; object-fit: contain; image-rendering: pixelated; }}
.card-body {{ padding: 10px; display: grid; gap: 6px; }}
.card-title {{ font-weight: 700; }}
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
    <div class="sub">Applies false-free large32 selector targets on top of the len64-promoted replay.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Added large32 bytes</div><div class="value ok">{summary['selector_added_bytes']}</div></div>
    <div class="stat"><div class="label">Total clean bytes</div><div class="value">{summary['total_clean_bytes']}</div></div>
    <div class="stat"><div class="label">False bytes</div><div class="value">{summary['selector_false_bytes']}</div></div>
    <div class="stat"><div class="label">Remaining unresolved</div><div class="value">{summary['remaining_unresolved_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="cards">{cards}</section>
  <section class="panel"><h2>Fixtures</h2>{render_table(fixture_rows, FIXTURE_FIELDNAMES)}</section>
  <section class="panel"><h2>Promotions</h2>{render_table(promotion_rows, PROMOTION_FIELDNAMES)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_REPLAY = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replay false-free large32 selector targets over len64-promoted .tex buffers."
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--frontiers", type=Path, default=DEFAULT_FRONTIERS)
    parser.add_argument("--base-fixtures", type=Path, default=DEFAULT_BASE_FIXTURES)
    parser.add_argument("--clean-decisions", type=Path, default=DEFAULT_CLEAN_DECISIONS)
    parser.add_argument("--selector-targets", type=Path, default=DEFAULT_SELECTOR_TARGETS)
    parser.add_argument("--title", default="Lands of Lore II .tex Len64 Promoted Large32 Replay")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, fixture_rows, promotion_rows = build_rows(
        output_dir=args.output,
        fixture_rows=read_csv(args.fixtures),
        frontier_rows=read_csv(args.frontiers),
        base_fixture_rows=read_csv(args.base_fixtures),
        clean_decision_rows=read_csv(args.clean_decisions),
        selector_target_rows=read_csv(args.selector_targets),
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "fixtures.csv", FIXTURE_FIELDNAMES, fixture_rows)
    write_csv(args.output / "promotions.csv", PROMOTION_FIELDNAMES, promotion_rows)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, fixture_rows, promotion_rows, args.output, args.title))

    print(f"Promoted targets: {summary['promoted_target_rows']}/{summary['target_rows']}")
    print(f"Added large32 bytes: {summary['selector_added_bytes']}")
    print(f"Remaining unresolved bytes: {summary['remaining_unresolved_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
