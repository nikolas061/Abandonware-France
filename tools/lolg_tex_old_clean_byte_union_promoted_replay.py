#!/usr/bin/env python3
"""Promote clean bytes found in older .tex replay artifacts into the current replay."""

from __future__ import annotations

import argparse
import csv
import html
from pathlib import Path

from lolg_tex_gap_decoder_seed_replay import frontier_lookup, render_preview, safe_stem
from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_old_clean_byte_seed_union_promoted_replay")
DEFAULT_BASE_FIXTURES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_eleventh_terminal_source_byte_guard_after_terminal_root_source_byte_cascade_promoted/fixtures.csv"
)
DEFAULT_SOURCE_FIXTURES = Path("output/tex_gap_decoder_seed_replay/fixtures.csv")
DEFAULT_EXPECTED_MANIFEST = Path("output/tex_gap_rule_fixtures_expanded/manifest.csv")
DEFAULT_FRONTIERS = Path("output/tex_gap_frontier_report/frontiers.csv")
TARGET_SIZE = (1920, 1080)

SUMMARY_FIELDNAMES = [
    "scope",
    "base_fixtures",
    "source_fixtures",
    "fixture_rows",
    "promoted_rows",
    "base_clean_bytes",
    "source_candidate_bytes",
    "source_added_bytes",
    "source_exact_bytes",
    "source_false_bytes",
    "skipped_known_bytes",
    "total_clean_bytes",
    "rejected_false_bytes",
    "remaining_unresolved_bytes",
    "native_previews",
    "fullhd_previews",
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
    "source_candidate_bytes",
    "source_added_bytes",
    "source_exact_bytes",
    "source_false_bytes",
    "skipped_known_bytes",
    "skipped_rejected_bytes",
    "total_clean_bytes",
    "rejected_false_bytes",
    "remaining_unresolved_bytes",
    "decoded_path",
    "known_mask_path",
    "source_mask_path",
    "native_preview_path",
    "fullhd_preview_path",
    "fullhd_width",
    "fullhd_height",
    "issues",
]

BYTE_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "offset",
    "expected_hex",
    "source_hex",
    "promotion_ready",
    "issues",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        return list(csv.DictReader(handle))


def fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        row.get("archive_tag", "").strip(),
        row.get("pcx_name", "").strip(),
        row.get("frontier_id", "").strip(),
    )


def frontier_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        row.get("archive", "").strip(),
        row.get("pcx_name", "").strip(),
        row.get("frontier_id", "").strip(),
    )


def is_under(path: Path, parent: Path) -> bool:
    resolved = path.resolve(strict=False)
    resolved_parent = parent.resolve(strict=False)
    return resolved == resolved_parent or resolved_parent in resolved.parents


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    path = Path(path_text)
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve(strict=False)
    workspace = Path.cwd().resolve(strict=False)
    excluded_game_dir = workspace / "C" / "LOLG"
    if not is_under(path, workspace):
        issues.append(f"{label}:outside_workspace")
        return b""
    if is_under(path, excluded_game_dir):
        issues.append(f"{label}:excluded_game_path")
        return b""
    try:
        return path.read_bytes()
    except OSError as exc:
        issues.append(f"{label}:read_failed:{exc.__class__.__name__}")
        return b""


def clean_count(expected: bytes, decoded: bytes, mask: bytes) -> int:
    return sum(
        1
        for index in range(min(len(expected), len(decoded), len(mask)))
        if mask[index] and decoded[index] == expected[index]
    )


def load_expected(rows: list[dict[str, str]], issues: list[str]) -> dict[tuple[str, str, str], bytes]:
    expected: dict[tuple[str, str, str], bytes] = {}
    for row in rows:
        key = fixture_key(row)
        if not all(key):
            continue
        data = load_bytes(row.get("expected_gap_path", ""), issues, "expected")
        if data:
            expected[key] = data
    return expected


def build_rows(
    *,
    output_dir: Path,
    base_rows: list[dict[str, str]],
    source_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
    frontier_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    fixture_output_dir = output_dir / "fixtures"
    native_preview_dir = output_dir / "native"
    fullhd_preview_dir = output_dir / "fullhd"
    fixture_output_dir.mkdir(parents=True, exist_ok=True)
    native_preview_dir.mkdir(parents=True, exist_ok=True)
    fullhd_preview_dir.mkdir(parents=True, exist_ok=True)

    issue_rows = 0
    manifest_issues: list[str] = []
    expected_by_key = load_expected(manifest_rows, manifest_issues)
    source_by_key = {fixture_key(row): row for row in source_rows}
    frontiers = frontier_lookup(frontier_rows)

    output_fixture_rows: list[dict[str, str]] = []
    output_byte_rows: list[dict[str, str]] = []

    totals = {
        "base_clean_bytes": 0,
        "source_candidate_bytes": 0,
        "source_added_bytes": 0,
        "source_exact_bytes": 0,
        "source_false_bytes": 0,
        "skipped_known_bytes": 0,
        "skipped_rejected_bytes": 0,
        "total_clean_bytes": 0,
        "rejected_false_bytes": 0,
        "remaining_unresolved_bytes": 0,
    }

    for base_row in base_rows:
        key = fixture_key(base_row)
        fixture_issues: list[str] = []
        expected = expected_by_key.get(key, b"")
        if not expected:
            fixture_issues.append("missing_expected")
        source_row = source_by_key.get(key, {})
        if not source_row:
            fixture_issues.append("missing_source_fixture")

        base_decoded = bytearray(load_bytes(base_row.get("decoded_path", ""), fixture_issues, "base_decoded"))
        base_mask = bytearray(load_bytes(base_row.get("known_mask_path", ""), fixture_issues, "base_known_mask"))
        base_decoded_original = bytes(base_decoded)
        base_mask_original = bytes(base_mask)
        source_decoded = load_bytes(source_row.get("decoded_path", ""), fixture_issues, "source_decoded") if source_row else b""
        source_mask = load_bytes(source_row.get("known_mask_path", ""), fixture_issues, "source_known_mask") if source_row else b""

        fixture_bytes = len(expected)
        limit = min(len(expected), len(base_decoded), len(base_mask), len(source_decoded), len(source_mask))
        if fixture_bytes and limit != fixture_bytes:
            fixture_issues.append("length_mismatch")

        source_promoted_mask = bytearray(len(base_mask))
        source_candidate_bytes = 0
        source_added_bytes = 0
        source_exact_bytes = 0
        source_false_bytes = 0
        skipped_known_bytes = 0
        skipped_rejected_bytes = 0
        rejected_false_bytes = int_value(base_row, "rejected_false_bytes")

        for offset in range(limit):
            if not source_mask[offset]:
                continue
            if base_mask[offset]:
                skipped_known_bytes += 1
                continue
            source_candidate_bytes += 1
            if source_decoded[offset] != expected[offset]:
                source_false_bytes += 1
                continue
            source_exact_bytes += 1
            source_added_bytes += 1
            base_decoded[offset] = source_decoded[offset]
            base_mask[offset] = 1
            source_promoted_mask[offset] = 255
            output_byte_rows.append(
                {
                    "rank": base_row.get("rank", ""),
                    "archive": base_row.get("archive", ""),
                    "archive_tag": key[0],
                    "pcx_name": key[1],
                    "frontier_id": key[2],
                    "offset": str(offset),
                    "expected_hex": f"{expected[offset]:02x}",
                    "source_hex": f"{source_decoded[offset]:02x}",
                    "promotion_ready": "1",
                    "issues": "",
                }
            )

        base_clean_bytes = clean_count(expected, base_decoded_original, base_mask_original)
        total_clean_bytes = clean_count(expected, base_decoded, base_mask)
        remaining_unresolved = max(0, fixture_bytes - total_clean_bytes - rejected_false_bytes)

        stem = safe_stem(
            f"rank{int_value(base_row, 'rank'):03d}",
            key[1],
            f"frontier{key[2]}",
        )
        decoded_path = fixture_output_dir / f"{stem}_decoded_old_clean_union.bin"
        known_mask_path = fixture_output_dir / f"{stem}_known_mask.bin"
        source_mask_path = fixture_output_dir / f"{stem}_old_clean_union_mask.bin"
        native_preview_path = native_preview_dir / f"{stem}_old_clean_union.png"
        fullhd_preview_path = fullhd_preview_dir / f"{stem}_old_clean_union_fullhd.png"
        decoded_path.write_bytes(base_decoded)
        known_mask_path.write_bytes(base_mask)
        source_mask_path.write_bytes(source_promoted_mask)

        frontier = frontiers.get(frontier_key(base_row), {})
        if expected:
            render_preview(
                expected=expected,
                decoded=base_decoded,
                known_mask=base_mask,
                risk_mask=source_promoted_mask,
                frontier=frontier,
                native_path=native_preview_path,
                fullhd_path=fullhd_preview_path,
            )
            fullhd_width, fullhd_height = TARGET_SIZE
        else:
            fullhd_width, fullhd_height = 0, 0

        if fixture_issues:
            issue_rows += 1
        output_fixture_rows.append(
            {
                "rank": base_row.get("rank", ""),
                "archive": base_row.get("archive", ""),
                "archive_tag": key[0],
                "pcx_name": key[1],
                "frontier_id": key[2],
                "fixture_bytes": str(fixture_bytes),
                "base_clean_bytes": str(base_clean_bytes),
                "source_candidate_bytes": str(source_candidate_bytes),
                "source_added_bytes": str(source_added_bytes),
                "source_exact_bytes": str(source_exact_bytes),
                "source_false_bytes": str(source_false_bytes),
                "skipped_known_bytes": str(skipped_known_bytes),
                "skipped_rejected_bytes": str(skipped_rejected_bytes),
                "total_clean_bytes": str(total_clean_bytes),
                "rejected_false_bytes": str(rejected_false_bytes),
                "remaining_unresolved_bytes": str(remaining_unresolved),
                "decoded_path": decoded_path.as_posix(),
                "known_mask_path": known_mask_path.as_posix(),
                "source_mask_path": source_mask_path.as_posix(),
                "native_preview_path": native_preview_path.as_posix(),
                "fullhd_preview_path": fullhd_preview_path.as_posix(),
                "fullhd_width": str(fullhd_width),
                "fullhd_height": str(fullhd_height),
                "issues": ";".join(fixture_issues),
            }
        )

        totals["base_clean_bytes"] += base_clean_bytes
        totals["source_candidate_bytes"] += source_candidate_bytes
        totals["source_added_bytes"] += source_added_bytes
        totals["source_exact_bytes"] += source_exact_bytes
        totals["source_false_bytes"] += source_false_bytes
        totals["skipped_known_bytes"] += skipped_known_bytes
        totals["skipped_rejected_bytes"] += skipped_rejected_bytes
        totals["total_clean_bytes"] += total_clean_bytes
        totals["rejected_false_bytes"] += rejected_false_bytes
        totals["remaining_unresolved_bytes"] += remaining_unresolved

    summary = {
        "scope": "old_clean_seed_union_promoted_replay",
        "base_fixtures": DEFAULT_BASE_FIXTURES.as_posix(),
        "source_fixtures": DEFAULT_SOURCE_FIXTURES.as_posix(),
        "fixture_rows": str(len(output_fixture_rows)),
        "promoted_rows": str(sum(1 for row in output_fixture_rows if int_value(row, "source_added_bytes") > 0)),
        "base_clean_bytes": str(totals["base_clean_bytes"]),
        "source_candidate_bytes": str(totals["source_candidate_bytes"]),
        "source_added_bytes": str(totals["source_added_bytes"]),
        "source_exact_bytes": str(totals["source_exact_bytes"]),
        "source_false_bytes": str(totals["source_false_bytes"]),
        "skipped_known_bytes": str(totals["skipped_known_bytes"]),
        "total_clean_bytes": str(totals["total_clean_bytes"]),
        "rejected_false_bytes": str(totals["rejected_false_bytes"]),
        "remaining_unresolved_bytes": str(totals["remaining_unresolved_bytes"]),
        "native_previews": str(sum(1 for row in output_fixture_rows if row.get("native_preview_path"))),
        "fullhd_previews": str(sum(1 for row in output_fixture_rows if row.get("fullhd_preview_path"))),
        "promotion_ready_bytes": str(totals["source_added_bytes"] if totals["source_false_bytes"] == 0 else 0),
        "issue_rows": str(issue_rows + len(manifest_issues)),
    }
    return summary, output_fixture_rows, output_byte_rows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 160) -> str:
    body = []
    for row in rows[:limit]:
        body.append("<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>")
    return (
        "<table><thead><tr>"
        + "".join(f"<th>{html.escape(field)}</th>" for field in fields)
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table>"
    )


def render_preview_card(row: dict[str, str], output_dir: Path) -> str:
    image = html.escape(relative_href(row.get("fullhd_preview_path", ""), output_dir))
    title = html.escape(f"{row.get('pcx_name', '')} frontier {row.get('frontier_id', '')}")
    added = html.escape(row.get("source_added_bytes", "0"))
    return f"<figure><img src='{image}' alt='{title}'><figcaption>{title} +{added}</figcaption></figure>"


def write_html(output_dir: Path, summary: dict[str, str], fixture_rows: list[dict[str, str]], byte_rows: list[dict[str, str]]) -> None:
    promoted_rows = [row for row in fixture_rows if int_value(row, "source_added_bytes") > 0]
    preview_cards = "".join(render_preview_card(row, output_dir) for row in promoted_rows)
    page = f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>Lands of Lore II .tex Old Clean Union Replay</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; background: #f7f7f4; color: #222; }}
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; margin: 18px 0; }}
    .stat {{ background: #fff; border: 1px solid #ddd; padding: 10px; }}
    .label {{ color: #666; font-size: 12px; }}
    .value {{ font-size: 22px; font-weight: 700; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; }}
    figure {{ margin: 0; background: white; border: 1px solid #ddd; padding: 8px; }}
    img {{ width: 100%; display: block; image-rendering: pixelated; }}
    figcaption {{ margin-top: 6px; font-size: 13px; }}
    table {{ border-collapse: collapse; width: 100%; background: white; margin: 18px 0; }}
    th, td {{ border: 1px solid #ddd; padding: 6px 8px; font-size: 13px; text-align: left; }}
    th {{ background: #ecebe4; }}
  </style>
</head>
<body>
  <h1>Lands of Lore II .tex Old Clean Union Replay</h1>
  <div class="stats">
    <div class="stat"><div class="label">Base clean</div><div class="value">{html.escape(summary['base_clean_bytes'])}</div></div>
    <div class="stat"><div class="label">Added clean</div><div class="value">{html.escape(summary['source_added_bytes'])}</div></div>
    <div class="stat"><div class="label">Source false</div><div class="value">{html.escape(summary['source_false_bytes'])}</div></div>
    <div class="stat"><div class="label">Total clean</div><div class="value">{html.escape(summary['total_clean_bytes'])}</div></div>
    <div class="stat"><div class="label">Remaining</div><div class="value">{html.escape(summary['remaining_unresolved_bytes'])}</div></div>
  </div>
  <h2>Promoted Previews</h2>
  <div class="grid">{preview_cards}</div>
  <h2>Fixtures</h2>
  {render_table(fixture_rows, FIXTURE_FIELDNAMES)}
  <h2>Promoted Bytes</h2>
  {render_table(byte_rows, BYTE_FIELDNAMES)}
</body>
</html>
"""
    (output_dir / "index.html").write_text(page, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--base-fixtures", type=Path, default=DEFAULT_BASE_FIXTURES)
    parser.add_argument("--source-fixtures", type=Path, default=DEFAULT_SOURCE_FIXTURES)
    parser.add_argument("--expected-manifest", type=Path, default=DEFAULT_EXPECTED_MANIFEST)
    parser.add_argument("--frontiers", type=Path, default=DEFAULT_FRONTIERS)
    args = parser.parse_args()

    output_dir = args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    summary, fixture_rows, byte_rows = build_rows(
        output_dir=output_dir,
        base_rows=read_csv(args.base_fixtures),
        source_rows=read_csv(args.source_fixtures),
        manifest_rows=read_csv(args.expected_manifest),
        frontier_rows=read_csv(args.frontiers),
    )

    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "fixtures.csv", FIXTURE_FIELDNAMES, fixture_rows)
    write_csv(output_dir / "promoted_bytes.csv", BYTE_FIELDNAMES, byte_rows)
    write_html(output_dir, summary, fixture_rows, byte_rows)

    print(f"summary={output_dir / 'summary.csv'}")
    print(f"fixtures={output_dir / 'fixtures.csv'}")
    print(f"promoted_bytes={output_dir / 'promoted_bytes.csv'}")
    print(f"html={output_dir / 'index.html'}")
    print(
        "promoted="
        f"{summary['source_added_bytes']} "
        f"false={summary['source_false_bytes']} "
        f"total_clean={summary['total_clean_bytes']} "
        f"remaining={summary['remaining_unresolved_bytes']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
