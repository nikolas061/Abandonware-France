#!/usr/bin/env python3
"""Probe common RLE families against .tex gap windows."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from pathlib import Path

from lolg_tex_gap_opcode_probe import (
    comparison_lookup,
    int_value,
    load_indexed_pixels,
    read_mix_entry,
    read_rows,
    relative_href,
    write_csv,
)


DEFAULT_OUTPUT = Path("output/tex_gap_rle_probe")
DEFAULT_FRONTIERS = Path("output/tex_gap_frontier_report/frontiers.csv")
DEFAULT_COMPARISONS = Path("output/tex_exact_cdcache_compare/comparisons.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "textures",
    "frontiers",
    "variants",
    "tested_pairs",
    "full_match_rows",
    "frontiers_with_full_match",
    "frontiers_with_prefix",
    "best_prefix_bytes",
    "best_prefix_variant",
    "best_prefix_frontier_id",
    "best_prefix_pcx",
    "issue_rows",
]

HYPOTHESIS_FIELDNAMES = [
    "variant",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "frontier_type",
    "pixel_gap",
    "segment_gap_bytes",
    "segment_gap_ratio",
    "consumed_bytes",
    "produced_bytes",
    "prefix_bytes",
    "prefix_ratio",
    "full_match",
    "segment_head_hex",
    "output_head_hex",
    "expected_head_hex",
    "decoder_notes",
    "issues",
]

BEST_FIELDNAMES = [
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "frontier_type",
    "pixel_gap",
    "segment_gap_bytes",
    "best_variant",
    "best_prefix_bytes",
    "best_prefix_ratio",
    "full_match",
    "issues",
]


def decode_pcx_rle(data: bytes, limit: int) -> tuple[bytes, int, list[str]]:
    output: list[int] = []
    index = 0
    issues: list[str] = []
    while index < len(data) and len(output) < limit:
        value = data[index]
        index += 1
        if value >= 0xC0:
            if index >= len(data):
                issues.append("truncated_pcx_rle_packet")
                break
            count = value & 0x3F
            output.extend([data[index]] * count)
            index += 1
        else:
            output.append(value)
    return bytes(output), index, issues


def decode_packbits(data: bytes, limit: int) -> tuple[bytes, int, list[str]]:
    output: list[int] = []
    index = 0
    issues: list[str] = []
    while index < len(data) and len(output) < limit:
        control = data[index]
        index += 1
        if control <= 127:
            count = control + 1
            if index + count > len(data):
                issues.append("truncated_packbits_literal")
            output.extend(data[index : index + count])
            index += count
        elif control >= 129:
            if index >= len(data):
                issues.append("truncated_packbits_repeat")
                break
            output.extend([data[index]] * (257 - control))
            index += 1
    return bytes(output), index, issues


def decode_packbits_inverse(data: bytes, limit: int) -> tuple[bytes, int, list[str]]:
    output: list[int] = []
    index = 0
    issues: list[str] = []
    while index < len(data) and len(output) < limit:
        control = data[index]
        index += 1
        if control <= 127:
            if index >= len(data):
                issues.append("truncated_inverse_repeat")
                break
            output.extend([data[index]] * (control + 1))
            index += 1
        elif control >= 129:
            count = 257 - control
            if index + count > len(data):
                issues.append("truncated_inverse_literal")
            output.extend(data[index : index + count])
            index += count
    return bytes(output), index, issues


def decode_hibit_literal(data: bytes, limit: int) -> tuple[bytes, int, list[str]]:
    output: list[int] = []
    index = 0
    issues: list[str] = []
    while index < len(data) and len(output) < limit:
        control = data[index]
        index += 1
        if control & 0x80:
            count = (control & 0x7F) + 1
            if index + count > len(data):
                issues.append("truncated_hibit_literal")
            output.extend(data[index : index + count])
            index += count
        else:
            if index >= len(data):
                issues.append("truncated_hibit_repeat")
                break
            output.extend([data[index]] * (control + 1))
            index += 1
    return bytes(output), index, issues


def decode_hibit_repeat(data: bytes, limit: int) -> tuple[bytes, int, list[str]]:
    output: list[int] = []
    index = 0
    issues: list[str] = []
    while index < len(data) and len(output) < limit:
        control = data[index]
        index += 1
        if control & 0x80:
            if index >= len(data):
                issues.append("truncated_hibit_repeat")
                break
            output.extend([data[index]] * ((control & 0x7F) + 1))
            index += 1
        else:
            count = control + 1
            if index + count > len(data):
                issues.append("truncated_hibit_literal")
            output.extend(data[index : index + count])
            index += count
    return bytes(output), index, issues


def decode_count_value(data: bytes, limit: int, addend: int) -> tuple[bytes, int, list[str]]:
    output: list[int] = []
    index = 0
    issues: list[str] = []
    while index + 1 < len(data) and len(output) < limit:
        count = data[index] + addend
        value = data[index + 1]
        index += 2
        output.extend([value] * count)
    if index < len(data) and len(output) < limit:
        issues.append("trailing_unpaired_count_value_byte")
    return bytes(output), index, issues


VARIANTS = {
    "pcx_rle": decode_pcx_rle,
    "packbits": decode_packbits,
    "packbits_inverse": decode_packbits_inverse,
    "hibit_literal": decode_hibit_literal,
    "hibit_repeat": decode_hibit_repeat,
    "count_value": lambda data, limit: decode_count_value(data, limit, 0),
    "count1_value": lambda data, limit: decode_count_value(data, limit, 1),
}


def common_prefix(left: bytes, right: bytes) -> int:
    limit = min(len(left), len(right))
    count = 0
    while count < limit and left[count] == right[count]:
        count += 1
    return count


def load_segment(
    archive_text: str,
    comparison: dict[str, str],
    payload_cache: dict[Path, bytes],
) -> tuple[bytes, list[str]]:
    issues: list[str] = []
    archive = Path(archive_text)
    if archive not in payload_cache:
        try:
            _file_id, payload_cache[archive] = read_mix_entry(archive, 2)
        except Exception as exc:
            payload_cache[archive] = b""
            issues.append(f"archive_read_failed:{exc}")
    payload = payload_cache[archive]
    body_offset = int(comparison.get("texture_body_offset") or 0)
    segment_size = int(comparison.get("texture_segment_size") or 0)
    segment = payload[body_offset : body_offset + segment_size]
    if len(segment) != segment_size:
        issues.append("segment_size_mismatch")
    return segment, issues


def build_rows(
    frontiers: Path,
    comparisons: Path,
    *,
    context_bytes: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    frontier_rows = read_rows(frontiers)
    comparison_rows = read_rows(comparisons)
    comparisons_by_key = comparison_lookup(comparison_rows)
    payload_cache: dict[Path, bytes] = {}
    reference_cache: dict[tuple[str, str], bytes] = {}
    hypothesis_rows: list[dict[str, str]] = []
    best_by_frontier: dict[tuple[str, str, str], dict[str, str]] = {}

    for frontier in frontier_rows:
        if frontier.get("issues") or frontier.get("segment_relation") != "forward":
            continue
        segment_gap_bytes = int_value(frontier, "segment_gap_bytes")
        pixel_gap = int_value(frontier, "pixel_gap")
        if segment_gap_bytes <= 0 or pixel_gap <= 0:
            continue

        issues: list[str] = []
        key = (frontier.get("archive", ""), frontier.get("pcx_name", ""))
        comparison = comparisons_by_key.get(key)
        if not comparison:
            issues.append("missing_comparison_row")
            segment = b""
            reference_pixels = b""
        else:
            segment, segment_issues = load_segment(frontier.get("archive", ""), comparison, payload_cache)
            issues.extend(segment_issues)
            native_path = Path(comparison.get("cdcache_native_path", ""))
            if key not in reference_cache:
                try:
                    pixels, _width, _height = load_indexed_pixels(native_path)
                    reference_cache[key] = pixels
                except Exception as exc:
                    reference_cache[key] = b""
                    issues.append(f"reference_read_failed:{exc}")
            reference_pixels = reference_cache[key]

        segment_start = int_value(frontier, "segment_gap_start")
        gap_start = int_value(frontier, "gap_start")
        gap_end = int_value(frontier, "gap_end")
        segment_gap = segment[segment_start : segment_start + segment_gap_bytes]
        reference_gap = reference_pixels[gap_start : gap_end + 1]
        if len(segment_gap) != segment_gap_bytes:
            issues.append("segment_gap_truncated")
        if len(reference_gap) != pixel_gap:
            issues.append("reference_gap_truncated")

        best_row: dict[str, str] | None = None
        frontier_key = (frontier.get("archive", ""), frontier.get("pcx_name", ""), frontier.get("frontier_id", ""))
        for variant_name, decoder in VARIANTS.items():
            output, consumed, decode_issues = decoder(segment_gap, pixel_gap)
            row_issues = list(issues)
            prefix = common_prefix(output, reference_gap)
            full_match = len(output) >= len(reference_gap) and output[: len(reference_gap)] == reference_gap
            row = {
                "variant": variant_name,
                "archive": frontier.get("archive", ""),
                "archive_tag": frontier.get("archive_tag", ""),
                "pcx_name": frontier.get("pcx_name", ""),
                "frontier_id": frontier.get("frontier_id", ""),
                "frontier_type": frontier.get("frontier_type", ""),
                "pixel_gap": str(pixel_gap),
                "segment_gap_bytes": str(segment_gap_bytes),
                "segment_gap_ratio": frontier.get("segment_gap_ratio", ""),
                "consumed_bytes": str(consumed),
                "produced_bytes": str(len(output)),
                "prefix_bytes": str(prefix),
                "prefix_ratio": f"{(prefix / pixel_gap):.6f}" if pixel_gap else "0.000000",
                "full_match": "yes" if full_match else "no",
                "segment_head_hex": segment_gap[:context_bytes].hex(),
                "output_head_hex": output[:context_bytes].hex(),
                "expected_head_hex": reference_gap[:context_bytes].hex(),
                "decoder_notes": ";".join(decode_issues),
                "issues": ";".join(row_issues),
            }
            hypothesis_rows.append(row)
            if best_row is None or (
                prefix,
                1 if full_match else 0,
                -len(row_issues),
            ) > (
                int_value(best_row, "prefix_bytes"),
                1 if best_row.get("full_match") == "yes" else 0,
                -len([part for part in best_row.get("issues", "").split(";") if part]),
            ):
                best_row = row
        if best_row is not None:
            best_by_frontier[frontier_key] = {
                "archive": best_row.get("archive", ""),
                "archive_tag": best_row.get("archive_tag", ""),
                "pcx_name": best_row.get("pcx_name", ""),
                "frontier_id": best_row.get("frontier_id", ""),
                "frontier_type": best_row.get("frontier_type", ""),
                "pixel_gap": best_row.get("pixel_gap", ""),
                "segment_gap_bytes": best_row.get("segment_gap_bytes", ""),
                "best_variant": best_row.get("variant", ""),
                "best_prefix_bytes": best_row.get("prefix_bytes", ""),
                "best_prefix_ratio": best_row.get("prefix_ratio", ""),
                "full_match": best_row.get("full_match", ""),
                "issues": best_row.get("issues", ""),
            }

    hypothesis_rows.sort(
        key=lambda row: (
            row.get("variant", ""),
            -int_value(row, "prefix_bytes"),
            row.get("pcx_name", ""),
            int_value(row, "frontier_id"),
        )
    )
    best_rows = sorted(
        best_by_frontier.values(),
        key=lambda row: (
            -int_value(row, "best_prefix_bytes"),
            row.get("pcx_name", ""),
            int_value(row, "frontier_id"),
        ),
    )
    return hypothesis_rows, best_rows


def summary_row(hypothesis_rows: list[dict[str, str]], best_rows: list[dict[str, str]]) -> dict[str, str]:
    best = max(hypothesis_rows, key=lambda row: int_value(row, "prefix_bytes")) if hypothesis_rows else {}
    full_rows = [row for row in hypothesis_rows if row.get("full_match") == "yes"]
    issue_rows = sum(1 for row in hypothesis_rows if row.get("issues"))
    return {
        "scope": "total",
        "textures": str(len({(row.get("archive", ""), row.get("pcx_name", "")) for row in best_rows})),
        "frontiers": str(len(best_rows)),
        "variants": str(len(VARIANTS)),
        "tested_pairs": str(len(hypothesis_rows)),
        "full_match_rows": str(len(full_rows)),
        "frontiers_with_full_match": str(
            len({(row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", "")) for row in full_rows})
        ),
        "frontiers_with_prefix": str(sum(1 for row in best_rows if int_value(row, "best_prefix_bytes") > 0)),
        "best_prefix_bytes": str(int_value(best, "prefix_bytes")),
        "best_prefix_variant": best.get("variant", ""),
        "best_prefix_frontier_id": best.get("frontier_id", ""),
        "best_prefix_pcx": best.get("pcx_name", ""),
        "issue_rows": str(issue_rows),
    }


def render_hypothesis_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('variant', ''))}</td>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('pixel_gap', ''))}</td>"
        f"<td>{html.escape(row.get('segment_gap_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('consumed_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('produced_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('prefix_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('full_match', ''))}</td>"
        f"<td><code>{html.escape(row.get('output_head_hex', ''))}</code></td>"
        f"<td><code>{html.escape(row.get('expected_head_hex', ''))}</code></td>"
        f"<td>{html.escape(row.get('decoder_notes', ''))}</td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def render_best_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_type', ''))}</td>"
        f"<td>{html.escape(row.get('pixel_gap', ''))}</td>"
        f"<td>{html.escape(row.get('segment_gap_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('best_variant', ''))}</td>"
        f"<td>{html.escape(row.get('best_prefix_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('full_match', ''))}</td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def build_html(
    summary: dict[str, str],
    hypothesis_rows: list[dict[str, str]],
    best_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "hypotheses": hypothesis_rows, "bestByFrontier": best_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("hypotheses.csv", output_dir / "hypotheses.csv"),
            ("best_by_frontier.csv", output_dir / "best_by_frontier.csv"),
        )
    )
    hypothesis_table = "\n".join(render_hypothesis_row(row) for row in hypothesis_rows[:240])
    best_table = "\n".join(render_best_row(row) for row in best_rows)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{
  color-scheme: dark;
  --bg: #101316;
  --panel: #171d22;
  --line: #2f3942;
  --text: #edf3f6;
  --muted: #9caab3;
  --accent: #74d3ae;
  --ok: #78d98f;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.wrap {{ width: min(1600px, calc(100vw - 28px)); margin: 0 auto; }}
header {{
  border-bottom: 1px solid var(--line);
  background: #12171b;
  padding: 18px 0 14px;
}}
h1 {{ margin: 0; font-size: 21px; font-weight: 700; letter-spacing: 0; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
}}
.stat, .panel {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  padding: 10px;
}}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 24px; font-weight: 750; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1120px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 10px; }}
code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Tests PCX RLE, PackBits et variantes high-bit/count-value sur les gaps .tex.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Tested pairs</div><div class="value">{html.escape(summary['tested_pairs'])}</div></div>
    <div class="stat"><div class="label">Full matches</div><div class="value">{html.escape(summary['full_match_rows'])}</div></div>
    <div class="stat"><div class="label">Best prefix</div><div class="value">{html.escape(summary['best_prefix_bytes'])}</div></div>
    <div class="stat"><div class="label">Variants</div><div class="value">{html.escape(summary['variants'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel">
    <h2>Best by frontier</h2>
    <table>
      <thead><tr><th>PCX</th><th>Frontier</th><th>Type</th><th>Pixel gap</th><th>Segment bytes</th><th>Best variant</th><th>Prefix</th><th>Full</th><th>Issues</th></tr></thead>
      <tbody>{best_table}</tbody>
    </table>
  </section>
  <section class="panel">
    <h2>Hypotheses</h2>
    <table>
      <thead><tr><th>Variant</th><th>PCX</th><th>Frontier</th><th>Pixel gap</th><th>Segment bytes</th><th>Consumed</th><th>Produced</th><th>Prefix</th><th>Full</th><th>Output head</th><th>Expected head</th><th>Decoder notes</th><th>Issues</th></tr></thead>
      <tbody>{hypothesis_table}</tbody>
    </table>
  </section>
</main>
<script>
const TEX_GAP_RLE_PROBE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    frontiers: Path,
    comparisons: Path,
    *,
    context_bytes: int,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    hypothesis_rows, best_rows = build_rows(frontiers, comparisons, context_bytes=context_bytes)
    summary = summary_row(hypothesis_rows, best_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "hypotheses.csv", HYPOTHESIS_FIELDNAMES, hypothesis_rows)
    write_csv(output_dir / "best_by_frontier.csv", BEST_FIELDNAMES, best_rows)
    (output_dir / "index.html").write_text(build_html(summary, hypothesis_rows, best_rows, output_dir, title))
    return summary, hypothesis_rows, best_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe common RLE families against .tex gap windows.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frontiers", type=Path, default=DEFAULT_FRONTIERS)
    parser.add_argument("--comparisons", type=Path, default=DEFAULT_COMPARISONS)
    parser.add_argument("--context-bytes", type=int, default=32)
    parser.add_argument("--title", default="Lands of Lore II .tex Gap RLE Probe")
    args = parser.parse_args()

    summary, _hypothesis_rows, _best_rows = write_report(
        args.output,
        args.frontiers,
        args.comparisons,
        context_bytes=args.context_bytes,
        title=args.title,
    )
    print(f"Tested pairs: {summary['tested_pairs']}")
    print(f"Full match rows: {summary['full_match_rows']}")
    print(f"Best prefix bytes: {summary['best_prefix_bytes']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
