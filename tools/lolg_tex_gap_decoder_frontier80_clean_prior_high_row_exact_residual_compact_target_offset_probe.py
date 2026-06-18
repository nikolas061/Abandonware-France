#!/usr/bin/env python3
"""Probe target-offset application for compact high-row residual corrections."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_exact_residual_compact_target_offset_probe"
)
DEFAULT_SELECTOR_ROWS = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_exact_residual_compact_promoted_replay/"
    "selector_rows.csv"
)
DEFAULT_FIXTURES = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_BASE_FIXTURES = Path(
    "output/tex_old_clean_byte_union_frontier80_tail_compact_token_transfer_guard_promoted_replay/fixtures.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "total_bytes",
    "target_offset_delta",
    "target_unknown_bytes",
    "target_known_bytes",
    "target_exact_bytes",
    "target_le2_bytes",
    "target_outlier_bytes",
    "top_delta",
    "top_delta_count",
    "delta_domain",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

ROW_FIELDNAMES = [
    "pair_id",
    "source_id",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "source_offset",
    "target_offset",
    "byte_index",
    "residual_value_hex",
    "target_expected_hex",
    "target_base_known",
    "target_base_decoded_hex",
    "target_delta",
    "target_exact",
    "target_le2",
    "target_outlier",
    "issues",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def archive_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def parse_hex_byte(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    try:
        return int(value, 16)
    except ValueError:
        return None


def hex_byte(value: int | None) -> str:
    return "" if value is None else f"0x{value & 0xFF:02x}"


def signed_delta(source: int, target: int) -> int:
    value = (target - source) & 0xFF
    return value if value < 128 else value - 256


def load_bytes(path_text: str) -> bytes:
    return Path(path_text).read_bytes() if path_text else b""


def build_rows(
    selector_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    base_fixture_rows: list[dict[str, str]],
    target_offset_delta: int,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    fixtures_by_key = {archive_key(row): row for row in fixture_rows}
    base_by_key = {archive_key(row): row for row in base_fixture_rows}
    loaded_expected: dict[tuple[str, str, str], bytes] = {}
    loaded_base: dict[tuple[str, str, str], tuple[bytes, bytes]] = {}

    output_rows: list[dict[str, str]] = []
    issue_rows = 0
    target_exact = 0
    target_le2 = 0
    target_unknown = 0
    target_known = 0
    deltas: list[int] = []

    for row in selector_rows:
        key = archive_key(row)
        row_issues: list[str] = []
        fixture = fixtures_by_key.get(key, {})
        base_fixture = base_by_key.get(key, {})
        source_offset = int_value(row, "source_offset")
        target_offset = source_offset + target_offset_delta
        residual_value = parse_hex_byte(row.get("residual_value_hex", ""))

        if not fixture:
            row_issues.append("missing_fixture")
            expected = b""
        else:
            if key not in loaded_expected:
                loaded_expected[key] = load_bytes(fixture.get("expected_gap_path", ""))
            expected = loaded_expected[key]
        if not base_fixture:
            row_issues.append("missing_base_fixture")
            decoded = b""
            known_mask = b""
        else:
            if key not in loaded_base:
                loaded_base[key] = (
                    load_bytes(base_fixture.get("decoded_path", "")),
                    load_bytes(base_fixture.get("known_mask_path", "")),
                )
            decoded, known_mask = loaded_base[key]

        if target_offset < 0 or target_offset >= len(expected):
            row_issues.append("target_offset_out_of_range")
            target_expected: int | None = None
        else:
            target_expected = expected[target_offset]
        if target_offset < 0 or target_offset >= len(known_mask):
            row_issues.append("target_mask_offset_out_of_range")
            base_known = False
        else:
            base_known = known_mask[target_offset] != 0
        if target_offset < 0 or target_offset >= len(decoded):
            base_decoded: int | None = None
        else:
            base_decoded = decoded[target_offset]
        if residual_value is None:
            row_issues.append("missing_residual_value")

        if residual_value is not None and target_expected is not None:
            delta = signed_delta(residual_value, target_expected)
            exact = delta == 0
            le2 = abs(delta) <= 2
            deltas.append(delta)
        else:
            delta = 0
            exact = False
            le2 = False

        target_exact += 1 if exact else 0
        target_le2 += 1 if le2 else 0
        target_known += 1 if base_known else 0
        target_unknown += 0 if base_known else 1
        if row_issues:
            issue_rows += 1

        output_rows.append(
            {
                "pair_id": row.get("pair_id", ""),
                "source_id": row.get("source_id", ""),
                "archive": row.get("archive", ""),
                "archive_tag": row.get("archive_tag", ""),
                "pcx_name": row.get("pcx_name", ""),
                "frontier_id": row.get("frontier_id", ""),
                "source_offset": str(source_offset),
                "target_offset": str(target_offset),
                "byte_index": row.get("byte_index", ""),
                "residual_value_hex": row.get("residual_value_hex", ""),
                "target_expected_hex": hex_byte(target_expected),
                "target_base_known": "1" if base_known else "0",
                "target_base_decoded_hex": hex_byte(base_decoded),
                "target_delta": str(delta),
                "target_exact": "1" if exact else "0",
                "target_le2": "1" if le2 else "0",
                "target_outlier": "1" if not le2 else "0",
                "issues": ";".join(row_issues),
            }
        )

    counts = Counter(deltas)
    top_delta, top_count = (0, 0)
    if counts:
        top_delta, top_count = sorted(counts.items(), key=lambda item: (-item[1], abs(item[0]), item[0]))[0]
    target_outliers = len(output_rows) - target_le2
    if issue_rows:
        verdict = "frontier80_prior_high_row_exact_residual_compact_target_offset_issues"
        next_probe = "fix compact target-offset probe input issues"
    elif target_le2 == len(output_rows) and output_rows:
        verdict = "frontier80_prior_high_row_exact_residual_compact_target_offset_ready"
        next_probe = "promote compact target-offset high-row residual replay"
    elif target_le2 > 0 and target_outliers > 0:
        verdict = "frontier80_prior_high_row_exact_residual_compact_target_offset_outliers"
        next_probe = "derive guarded target delta correction for compact high-row residual outliers"
    else:
        verdict = "frontier80_prior_high_row_exact_residual_compact_target_offset_weak"
        next_probe = "expand target-offset search for compact high-row residual corrections"

    summary = {
        "scope": "total",
        "total_bytes": str(len(output_rows)),
        "target_offset_delta": str(target_offset_delta),
        "target_unknown_bytes": str(target_unknown),
        "target_known_bytes": str(target_known),
        "target_exact_bytes": str(target_exact),
        "target_le2_bytes": str(target_le2),
        "target_outlier_bytes": str(target_outliers),
        "top_delta": str(top_delta),
        "top_delta_count": str(top_count),
        "delta_domain": ";".join(str(delta) for delta in sorted(counts)),
        "issue_rows": str(issue_rows),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }
    return summary, output_rows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(summary: dict[str, str], rows: list[dict[str, str]], output_dir: Path, title: str) -> str:
    data_json = json.dumps({"summary": summary, "rows": rows}, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("target_rows.csv", output_dir / "target_rows.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #111416; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 1500px; }}
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
  <div class="box"><div class="num">{summary['target_le2_bytes']}/{summary['total_bytes']}</div><div class="muted">target <=2 bytes</div></div>
  <div class="box"><div class="num">{summary['target_exact_bytes']}/{summary['total_bytes']}</div><div class="muted">target exact bytes</div></div>
  <div class="box"><div class="num">{summary['target_outlier_bytes']}</div><div class="muted">target outliers</div></div>
  <div class="box"><div class="num">{summary['target_unknown_bytes']}</div><div class="muted">target unknown bytes</div></div>
</div>
<p>{links}</p>
<p class="muted">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</p>
<div class="panel">{render_table(rows, ROW_FIELDNAMES)}</div>
<script type="application/json" id="compact-target-offset-data">{data_json}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selector-rows", type=Path, default=DEFAULT_SELECTOR_ROWS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--base-fixtures", type=Path, default=DEFAULT_BASE_FIXTURES)
    parser.add_argument("--target-offset-delta", type=int, default=32)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Prior High Row Exact Residual Compact Target Offset Probe",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, rows = build_rows(
        read_csv(args.selector_rows),
        read_csv(args.fixtures),
        read_csv(args.base_fixtures),
        args.target_offset_delta,
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "target_rows.csv", ROW_FIELDNAMES, rows)
    (args.output / "index.html").write_text(build_html(summary, rows, args.output, args.title), encoding="utf-8")
    print(f"Target <=2: {summary['target_le2_bytes']}/{summary['total_bytes']}")
    print(f"Target exact: {summary['target_exact_bytes']}/{summary['total_bytes']}")
    print(f"Target outliers: {summary['target_outlier_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
