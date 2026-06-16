#!/usr/bin/env python3
"""Probe .tex gap windows for raw replay and opcode/control-byte evidence."""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
import os
import struct
from collections import Counter
from pathlib import Path

from PIL import Image


DEFAULT_OUTPUT = Path("output/tex_gap_opcode_probe")
DEFAULT_FRONTIERS = Path("output/tex_gap_frontier_report/frontiers.csv")
DEFAULT_COMPARISONS = Path("output/tex_exact_cdcache_compare/comparisons.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "textures",
    "frontiers",
    "probe_rows",
    "forward_windows",
    "exact_raw_replay_rows",
    "raw_prefix_probe_rows",
    "best_prefix_bytes",
    "best_prefix_frontier_id",
    "best_prefix_pcx",
    "compressed_windows",
    "expanded_windows",
    "opcode_groups",
    "issue_rows",
]

PROBE_FIELDNAMES = [
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "frontier_type",
    "gap_start",
    "gap_end",
    "pixel_gap",
    "segment_gap_start",
    "segment_gap_end",
    "segment_gap_bytes",
    "segment_gap_ratio",
    "segment_relation",
    "opcode0_hex",
    "opcode1_hex",
    "opcode2_hex",
    "opcode3_hex",
    "head4_hex",
    "segment_gap_entropy",
    "expected_gap_entropy",
    "expected_zero_ratio",
    "best_raw_skip",
    "best_raw_prefix_bytes",
    "best_raw_prefix_ratio",
    "raw_exact_skip",
    "raw_exact_pixels",
    "expected_head_hex",
    "segment_head_hex",
    "segment_after_best_skip_hex",
    "probe_class",
    "issues",
]

OPCODE_FIELDNAMES = [
    "opcode0_hex",
    "rows",
    "textures",
    "pixel_gap_total",
    "segment_gap_bytes_total",
    "avg_segment_gap_ratio",
    "exact_raw_replay_rows",
    "best_prefix_bytes",
    "compressed_windows",
    "expanded_windows",
    "sample_pcx",
    "sample_frontier_id",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, str], field: str) -> int:
    raw = row.get(field, "")
    return int(raw) if raw else 0


def float_value(row: dict[str, str], field: str) -> float:
    raw = row.get(field, "")
    return float(raw) if raw else 0.0


def byte_hex(data: bytes, index: int) -> str:
    return f"0x{data[index]:02x}" if index < len(data) else ""


def entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    total = len(data)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def zero_ratio(data: bytes) -> float:
    return (data.count(0) / len(data)) if data else 0.0


def read_mix_entry(path: Path, index: int) -> tuple[int, bytes]:
    data = path.read_bytes()
    if len(data) < 6:
        raise ValueError(f"{path}: too small to be a MIX archive")
    count, body_size = struct.unpack_from("<HI", data, 0)
    table_end = 6 + count * 12
    if index < 0 or index >= count or table_end > len(data):
        raise ValueError(f"{path}: invalid MIX entry index {index}")
    file_id, offset, size = struct.unpack_from("<III", data, 6 + index * 12)
    if offset + size > body_size:
        raise ValueError(f"{path}: entry {index} exceeds declared body size")
    return file_id, data[table_end + offset : table_end + offset + size]


def comparison_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    output = {}
    for row in rows:
        key = (row.get("archive", ""), row.get("pcx_name", ""))
        if key[0] and key[1]:
            output[key] = row
    return output


def load_indexed_pixels(path: Path) -> tuple[bytes, int, int]:
    with Image.open(path) as image:
        indexed = image if image.mode in {"1", "L", "P"} else image.convert("P")
        return indexed.tobytes(), indexed.width, indexed.height


def raw_probe(
    segment_gap: bytes,
    reference_gap: bytes,
    *,
    max_skip: int,
) -> tuple[int, int, int]:
    best_skip = 0
    best_prefix = 0
    raw_exact_skip = -1
    skip_limit = min(max_skip, max(0, len(segment_gap) - 1))
    for skip in range(skip_limit + 1):
        limit = min(len(segment_gap) - skip, len(reference_gap))
        prefix = 0
        while prefix < limit and segment_gap[skip + prefix] == reference_gap[prefix]:
            prefix += 1
        if prefix > best_prefix:
            best_prefix = prefix
            best_skip = skip
        if (
            raw_exact_skip < 0
            and len(reference_gap) > 0
            and len(segment_gap) - skip >= len(reference_gap)
            and segment_gap[skip : skip + len(reference_gap)] == reference_gap
        ):
            raw_exact_skip = skip
    return best_skip, best_prefix, raw_exact_skip


def classify_probe(
    *,
    exact_pixels: int,
    best_prefix: int,
    pixel_gap: int,
    segment_gap_bytes: int,
) -> str:
    if exact_pixels:
        return "exact_raw_replay"
    if best_prefix >= 8:
        return "literal_fragment"
    if best_prefix >= 3:
        return "short_literal_echo"
    if segment_gap_bytes < pixel_gap:
        return "compressed_or_transform_required"
    if segment_gap_bytes > pixel_gap * 4:
        return "expanded_control_window"
    return "control_or_palette_transform"


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


def build_probe_rows(
    frontiers: Path,
    comparisons: Path,
    *,
    max_skip: int,
    context_bytes: int,
) -> list[dict[str, str]]:
    frontier_rows = read_rows(frontiers)
    comparison_rows = read_rows(comparisons)
    comparisons_by_key = comparison_lookup(comparison_rows)
    payload_cache: dict[Path, bytes] = {}
    reference_cache: dict[tuple[str, str], bytes] = {}
    rows: list[dict[str, str]] = []

    for frontier in frontier_rows:
        issues: list[str] = []
        if frontier.get("issues"):
            issues.append("source_frontier_has_issues")
        if frontier.get("segment_relation") != "forward":
            continue
        segment_gap_bytes = int_value(frontier, "segment_gap_bytes")
        pixel_gap = int_value(frontier, "pixel_gap")
        if segment_gap_bytes <= 0 or pixel_gap <= 0:
            continue

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

        best_skip, best_prefix, raw_exact_skip = raw_probe(
            segment_gap,
            reference_gap,
            max_skip=max_skip,
        )
        raw_exact_pixels = pixel_gap if raw_exact_skip >= 0 else 0
        probe_class = classify_probe(
            exact_pixels=raw_exact_pixels,
            best_prefix=best_prefix,
            pixel_gap=pixel_gap,
            segment_gap_bytes=segment_gap_bytes,
        )
        rows.append(
            {
                "archive": frontier.get("archive", ""),
                "archive_tag": frontier.get("archive_tag", ""),
                "pcx_name": frontier.get("pcx_name", ""),
                "frontier_id": frontier.get("frontier_id", ""),
                "frontier_type": frontier.get("frontier_type", ""),
                "gap_start": frontier.get("gap_start", ""),
                "gap_end": frontier.get("gap_end", ""),
                "pixel_gap": str(pixel_gap),
                "segment_gap_start": frontier.get("segment_gap_start", ""),
                "segment_gap_end": frontier.get("segment_gap_end", ""),
                "segment_gap_bytes": str(segment_gap_bytes),
                "segment_gap_ratio": frontier.get("segment_gap_ratio", ""),
                "segment_relation": frontier.get("segment_relation", ""),
                "opcode0_hex": byte_hex(segment_gap, 0),
                "opcode1_hex": byte_hex(segment_gap, 1),
                "opcode2_hex": byte_hex(segment_gap, 2),
                "opcode3_hex": byte_hex(segment_gap, 3),
                "head4_hex": segment_gap[:4].hex(),
                "segment_gap_entropy": f"{entropy(segment_gap):.4f}",
                "expected_gap_entropy": f"{entropy(reference_gap):.4f}",
                "expected_zero_ratio": f"{zero_ratio(reference_gap):.4f}",
                "best_raw_skip": str(best_skip),
                "best_raw_prefix_bytes": str(best_prefix),
                "best_raw_prefix_ratio": f"{(best_prefix / pixel_gap):.6f}" if pixel_gap else "0.000000",
                "raw_exact_skip": str(raw_exact_skip) if raw_exact_skip >= 0 else "",
                "raw_exact_pixels": str(raw_exact_pixels),
                "expected_head_hex": reference_gap[:context_bytes].hex(),
                "segment_head_hex": segment_gap[:context_bytes].hex(),
                "segment_after_best_skip_hex": segment_gap[best_skip : best_skip + context_bytes].hex(),
                "probe_class": probe_class,
                "issues": ";".join(issues),
            }
        )

    rows.sort(
        key=lambda row: (
            row.get("probe_class", ""),
            -int_value(row, "best_raw_prefix_bytes"),
            -int_value(row, "pixel_gap"),
            row.get("pcx_name", ""),
        )
    )
    return rows


def build_opcode_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        opcode = row.get("opcode0_hex", "") or "empty"
        grouped.setdefault(opcode, []).append(row)

    output: list[dict[str, str]] = []
    for opcode, group in grouped.items():
        pixel_gap_total = sum(int_value(row, "pixel_gap") for row in group)
        segment_gap_total = sum(int_value(row, "segment_gap_bytes") for row in group)
        ratios = [float_value(row, "segment_gap_ratio") for row in group if row.get("segment_gap_ratio")]
        exact_rows = sum(1 for row in group if int_value(row, "raw_exact_pixels") > 0)
        compressed = sum(
            1 for row in group if int_value(row, "segment_gap_bytes") < int_value(row, "pixel_gap")
        )
        expanded = sum(
            1 for row in group if int_value(row, "segment_gap_bytes") > int_value(row, "pixel_gap") * 4
        )
        sample = max(group, key=lambda row: int_value(row, "best_raw_prefix_bytes"))
        output.append(
            {
                "opcode0_hex": opcode,
                "rows": str(len(group)),
                "textures": str(len({(row.get("archive", ""), row.get("pcx_name", "")) for row in group})),
                "pixel_gap_total": str(pixel_gap_total),
                "segment_gap_bytes_total": str(segment_gap_total),
                "avg_segment_gap_ratio": f"{(sum(ratios) / len(ratios)):.6f}" if ratios else "0.000000",
                "exact_raw_replay_rows": str(exact_rows),
                "best_prefix_bytes": str(int_value(sample, "best_raw_prefix_bytes")),
                "compressed_windows": str(compressed),
                "expanded_windows": str(expanded),
                "sample_pcx": sample.get("pcx_name", ""),
                "sample_frontier_id": sample.get("frontier_id", ""),
            }
        )
    output.sort(key=lambda row: (-int_value(row, "rows"), row.get("opcode0_hex", "")))
    return output


def summary_row(rows: list[dict[str, str]], opcode_rows: list[dict[str, str]]) -> dict[str, str]:
    best = max(rows, key=lambda row: int_value(row, "best_raw_prefix_bytes")) if rows else {}
    issue_rows = sum(1 for row in rows if row.get("issues"))
    exact_rows = sum(1 for row in rows if int_value(row, "raw_exact_pixels") > 0)
    prefix_rows = sum(1 for row in rows if int_value(row, "best_raw_prefix_bytes") > 0)
    compressed = sum(1 for row in rows if int_value(row, "segment_gap_bytes") < int_value(row, "pixel_gap"))
    expanded = sum(
        1 for row in rows if int_value(row, "segment_gap_bytes") > int_value(row, "pixel_gap") * 4
    )
    return {
        "scope": "total",
        "textures": str(len({(row.get("archive", ""), row.get("pcx_name", "")) for row in rows})),
        "frontiers": str(len({row.get("frontier_id", "") for row in rows if row.get("frontier_id")})),
        "probe_rows": str(len(rows)),
        "forward_windows": str(len(rows)),
        "exact_raw_replay_rows": str(exact_rows),
        "raw_prefix_probe_rows": str(prefix_rows),
        "best_prefix_bytes": str(int_value(best, "best_raw_prefix_bytes")),
        "best_prefix_frontier_id": best.get("frontier_id", ""),
        "best_prefix_pcx": best.get("pcx_name", ""),
        "compressed_windows": str(compressed),
        "expanded_windows": str(expanded),
        "opcode_groups": str(len(opcode_rows)),
        "issue_rows": str(issue_rows),
    }


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def render_probe_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_id', ''))}</td>"
        f"<td>{html.escape(row.get('frontier_type', ''))}</td>"
        f"<td>{html.escape(row.get('probe_class', ''))}</td>"
        f"<td>{html.escape(row.get('pixel_gap', ''))}</td>"
        f"<td>{html.escape(row.get('segment_gap_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('segment_gap_ratio', ''))}</td>"
        f"<td>{html.escape(row.get('opcode0_hex', ''))}</td>"
        f"<td>{html.escape(row.get('best_raw_skip', ''))}</td>"
        f"<td>{html.escape(row.get('best_raw_prefix_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('raw_exact_skip', ''))}</td>"
        f"<td><code>{html.escape(row.get('segment_after_best_skip_hex', ''))}</code></td>"
        f"<td><code>{html.escape(row.get('expected_head_hex', ''))}</code></td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def render_opcode_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('opcode0_hex', ''))}</td>"
        f"<td>{html.escape(row.get('rows', ''))}</td>"
        f"<td>{html.escape(row.get('textures', ''))}</td>"
        f"<td>{html.escape(row.get('pixel_gap_total', ''))}</td>"
        f"<td>{html.escape(row.get('segment_gap_bytes_total', ''))}</td>"
        f"<td>{html.escape(row.get('avg_segment_gap_ratio', ''))}</td>"
        f"<td>{html.escape(row.get('best_prefix_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('sample_pcx', ''))} #{html.escape(row.get('sample_frontier_id', ''))}</td>"
        "</tr>"
    )


def build_html(
    summary: dict[str, str],
    rows: list[dict[str, str]],
    opcode_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "probeRows": rows, "opcodeRows": opcode_rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("probe.csv", output_dir / "probe.csv"),
            ("opcode_stats.csv", output_dir / "opcode_stats.csv"),
        )
    )
    probe_table = "\n".join(render_probe_row(row) for row in rows)
    opcode_table = "\n".join(render_opcode_row(row) for row in opcode_rows)
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
table {{ width: 100%; border-collapse: collapse; min-width: 1180px; }}
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
    <div class="sub">Probe strict des gaps .tex: replay brut, fragments litteraux, et regroupement par byte de controle.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Probe rows</div><div class="value">{html.escape(summary['probe_rows'])}</div></div>
    <div class="stat"><div class="label">Exact raw replay</div><div class="value">{html.escape(summary['exact_raw_replay_rows'])}</div></div>
    <div class="stat"><div class="label">Best prefix</div><div class="value">{html.escape(summary['best_prefix_bytes'])}</div></div>
    <div class="stat"><div class="label">Opcode groups</div><div class="value">{html.escape(summary['opcode_groups'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel">
    <h2>Opcode stats</h2>
    <table>
      <thead><tr><th>Opcode0</th><th>Rows</th><th>Textures</th><th>Pixel gap total</th><th>Segment bytes total</th><th>Avg ratio</th><th>Best prefix</th><th>Sample</th></tr></thead>
      <tbody>{opcode_table}</tbody>
    </table>
  </section>
  <section class="panel">
    <h2>Probe rows</h2>
    <table>
      <thead><tr><th>PCX</th><th>Frontier</th><th>Type</th><th>Class</th><th>Pixel gap</th><th>Segment bytes</th><th>Ratio</th><th>Opcode0</th><th>Best skip</th><th>Prefix</th><th>Exact skip</th><th>Segment at best skip</th><th>Expected head</th><th>Issues</th></tr></thead>
      <tbody>{probe_table}</tbody>
    </table>
  </section>
</main>
<script>
const TEX_GAP_OPCODE_PROBE = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    frontiers: Path,
    comparisons: Path,
    *,
    max_skip: int,
    context_bytes: int,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = build_probe_rows(
        frontiers,
        comparisons,
        max_skip=max_skip,
        context_bytes=context_bytes,
    )
    opcode_rows = build_opcode_rows(rows)
    summary = summary_row(rows, opcode_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "probe.csv", PROBE_FIELDNAMES, rows)
    write_csv(output_dir / "opcode_stats.csv", OPCODE_FIELDNAMES, opcode_rows)
    (output_dir / "index.html").write_text(build_html(summary, rows, opcode_rows, output_dir, title))
    return summary, rows, opcode_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe .tex gap windows for opcode evidence.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--frontiers", type=Path, default=DEFAULT_FRONTIERS)
    parser.add_argument("--comparisons", type=Path, default=DEFAULT_COMPARISONS)
    parser.add_argument("--max-skip", type=int, default=64)
    parser.add_argument("--context-bytes", type=int, default=32)
    parser.add_argument("--title", default="Lands of Lore II .tex Gap Opcode Probe")
    args = parser.parse_args()

    summary, _rows, _opcode_rows = write_report(
        args.output,
        args.frontiers,
        args.comparisons,
        max_skip=args.max_skip,
        context_bytes=args.context_bytes,
        title=args.title,
    )
    print(f"Probe rows: {summary['probe_rows']}")
    print(f"Exact raw replay rows: {summary['exact_raw_replay_rows']}")
    print(f"Best prefix bytes: {summary['best_prefix_bytes']}")
    print(f"Opcode groups: {summary['opcode_groups']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
