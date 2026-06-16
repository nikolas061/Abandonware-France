#!/usr/bin/env python3
"""Extract byte-exact .tex/CDCACHE run fixtures from clustered direct matches."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import struct
from pathlib import Path

from PIL import Image


DEFAULT_OUTPUT = Path("output/tex_decoder_run_corpus")
DEFAULT_CLUSTERS = Path("output/tex_exact_chunk_clusters/clusters.csv")
DEFAULT_COMPARISONS = Path("output/tex_exact_cdcache_compare/comparisons.csv")

SUMMARY_FIELDNAMES = [
    "scope",
    "clusters",
    "extracted_runs",
    "byte_exact_runs",
    "byte_mismatch_runs",
    "total_exact_bytes",
    "longest_exact_bytes",
    "unique_pcx",
    "issue_rows",
]

RUN_FIELDNAMES = [
    "archive",
    "archive_tag",
    "pcx_name",
    "cluster_id",
    "cluster_class",
    "chunk_size",
    "pixel_start",
    "pixel_start_hex",
    "segment_start",
    "segment_start_hex",
    "run_bytes",
    "byte_equal",
    "segment_bin_path",
    "pixel_bin_path",
    "run_hex_prefix",
    "issues",
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


def load_pixel_bytes(path: Path) -> bytes:
    with Image.open(path) as image:
        if image.mode not in {"1", "L", "P"}:
            image = image.convert("L")
        return image.tobytes()


def comparison_lookup(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    output = {}
    for row in rows:
        key = (row.get("archive", ""), row.get("pcx_name", ""))
        if key[0] and key[1]:
            output[key] = row
    return output


def safe_stem(*parts: str) -> str:
    raw = "_".join(part for part in parts if part)
    return "".join(char if char.isalnum() or char in "-_." else "_" for char in raw).strip("_")


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def extract_rows(clusters: Path, comparisons: Path, output_dir: Path) -> list[dict[str, str]]:
    cluster_rows = read_rows(clusters)
    comparison_rows = read_rows(comparisons)
    comparisons_by_key = comparison_lookup(comparison_rows)
    payload_cache: dict[Path, bytes] = {}
    pixel_cache: dict[Path, bytes] = {}
    run_dir = output_dir / "runs"
    run_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []

    for cluster in cluster_rows:
        if cluster.get("issues"):
            continue
        archive_text = cluster.get("archive", "")
        pcx_name = cluster.get("pcx_name", "")
        archive = Path(archive_text)
        key = (archive_text, pcx_name)
        issues: list[str] = []
        comparison = comparisons_by_key.get(key, {})
        body_offset = int(comparison.get("texture_body_offset") or 0)
        segment_size = int(comparison.get("texture_segment_size") or 0)
        native_path = Path(comparison.get("cdcache_native_path", ""))
        pixel_start = int_value(cluster, "pixel_start")
        segment_start = int_value(cluster, "segment_start")
        run_bytes = int_value(cluster, "pixel_span_bytes")
        if run_bytes <= 0:
            run_bytes = int_value(cluster, "segment_span_bytes")

        if archive not in payload_cache:
            try:
                _file_id, payload_cache[archive] = read_mix_entry(archive, 2)
            except Exception as exc:
                payload_cache[archive] = b""
                issues.append(f"archive_read_failed:{exc}")
        payload = payload_cache[archive]
        texture_segment = payload[body_offset : body_offset + segment_size]
        if len(texture_segment) != segment_size:
            issues.append("segment_size_mismatch")
        segment_run = texture_segment[segment_start : segment_start + run_bytes]
        if len(segment_run) != run_bytes:
            issues.append("segment_run_truncated")

        if not native_path.exists():
            pixels = b""
            issues.append("missing_cdcache_native_path")
        else:
            if native_path not in pixel_cache:
                try:
                    pixel_cache[native_path] = load_pixel_bytes(native_path)
                except Exception as exc:
                    pixel_cache[native_path] = b""
                    issues.append(f"cdcache_image_read_failed:{exc}")
            pixels = pixel_cache[native_path]
        pixel_run = pixels[pixel_start : pixel_start + run_bytes]
        if len(pixel_run) != run_bytes:
            issues.append("pixel_run_truncated")

        byte_equal = bool(segment_run and pixel_run and segment_run == pixel_run)
        if segment_run and pixel_run and not byte_equal:
            issues.append("run_bytes_mismatch")

        stem = safe_stem(Path(archive_text).stem, pcx_name, f"cluster{cluster.get('cluster_id', '')}")
        segment_path = run_dir / f"{stem}_segment.bin"
        pixel_path = run_dir / f"{stem}_pixels.bin"
        if segment_run:
            segment_path.write_bytes(segment_run)
        if pixel_run:
            pixel_path.write_bytes(pixel_run)

        rows.append(
            {
                "archive": archive_text,
                "archive_tag": Path(archive_text).stem.upper(),
                "pcx_name": pcx_name,
                "cluster_id": cluster.get("cluster_id", ""),
                "cluster_class": cluster.get("cluster_class", ""),
                "chunk_size": cluster.get("chunk_size", ""),
                "pixel_start": str(pixel_start),
                "pixel_start_hex": f"0x{pixel_start:08x}",
                "segment_start": str(segment_start),
                "segment_start_hex": f"0x{segment_start:08x}",
                "run_bytes": str(run_bytes),
                "byte_equal": "1" if byte_equal else "0",
                "segment_bin_path": segment_path.as_posix() if segment_run else "",
                "pixel_bin_path": pixel_path.as_posix() if pixel_run else "",
                "run_hex_prefix": segment_run[:32].hex(),
                "issues": ";".join(issues),
            }
        )
    return rows


def summary_row(cluster_rows: list[dict[str, str]], rows: list[dict[str, str]]) -> dict[str, str]:
    issue_rows = [row for row in rows if row.get("issues")]
    exact_rows = [row for row in rows if row.get("byte_equal") == "1" and not row.get("issues")]
    mismatch_rows = [row for row in rows if "run_bytes_mismatch" in row.get("issues", "")]
    return {
        "scope": "total",
        "clusters": str(sum(1 for row in cluster_rows if not row.get("issues"))),
        "extracted_runs": str(len(rows)),
        "byte_exact_runs": str(len(exact_rows)),
        "byte_mismatch_runs": str(len(mismatch_rows)),
        "total_exact_bytes": str(sum(int_value(row, "run_bytes") for row in exact_rows)),
        "longest_exact_bytes": str(max((int_value(row, "run_bytes") for row in exact_rows), default=0)),
        "unique_pcx": str(len({row.get("pcx_name", "") for row in rows if row.get("pcx_name")})),
        "issue_rows": str(len(issue_rows)),
    }


def render_row(row: dict[str, str], output_dir: Path) -> str:
    segment_href = html.escape(relative_href(row.get("segment_bin_path", ""), output_dir))
    pixel_href = html.escape(relative_href(row.get("pixel_bin_path", ""), output_dir))
    return (
        "<tr>"
        f"<td>{html.escape(row.get('pcx_name', ''))}</td>"
        f"<td>{html.escape(row.get('cluster_id', ''))}</td>"
        f"<td>{html.escape(row.get('cluster_class', ''))}</td>"
        f"<td>{html.escape(row.get('run_bytes', ''))}</td>"
        f"<td>{html.escape(row.get('byte_equal', ''))}</td>"
        f"<td>{html.escape(row.get('pixel_start_hex', ''))}</td>"
        f"<td>{html.escape(row.get('segment_start_hex', ''))}</td>"
        f"<td><a href=\"{segment_href}\">segment</a> <a href=\"{pixel_href}\">pixels</a></td>"
        f"<td><code>{html.escape(row.get('run_hex_prefix', ''))}</code></td>"
        f"<td>{html.escape(row.get('issues', ''))}</td>"
        "</tr>"
    )


def build_html(
    summary: dict[str, str],
    rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "runs": rows}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("runs.csv", output_dir / "runs.csv"),
            ("runs/", output_dir / "runs"),
        )
    )
    table_rows = "\n".join(render_row(row, output_dir) for row in rows)
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
table {{ width: 100%; border-collapse: collapse; min-width: 1100px; }}
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
    <div class="sub">Corpus binaire des runs .tex deja prouves par les clusters CDCACHE.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Runs</div><div class="value">{html.escape(summary['extracted_runs'])}</div></div>
    <div class="stat"><div class="label">Byte exact</div><div class="value">{html.escape(summary['byte_exact_runs'])}</div></div>
    <div class="stat"><div class="label">Octets exacts</div><div class="value">{html.escape(summary['total_exact_bytes'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div></section>
  <section class="panel">
    <table>
      <thead><tr><th>PCX</th><th>Cluster</th><th>Class</th><th>Bytes</th><th>Exact</th><th>Pixel</th><th>Segment</th><th>Bins</th><th>Prefix</th><th>Issues</th></tr></thead>
      <tbody>{table_rows}</tbody>
    </table>
  </section>
</main>
<script>
const TEX_DECODER_RUN_CORPUS = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    clusters: Path,
    comparisons: Path,
    *,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cluster_rows = read_rows(clusters)
    rows = extract_rows(clusters, comparisons, output_dir)
    summary = summary_row(cluster_rows, rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "runs.csv", RUN_FIELDNAMES, rows)
    (output_dir / "index.html").write_text(build_html(summary, rows, output_dir, title))
    return summary, rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract byte-exact .tex decoder run corpus.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--clusters", type=Path, default=DEFAULT_CLUSTERS)
    parser.add_argument("--comparisons", type=Path, default=DEFAULT_COMPARISONS)
    parser.add_argument("--title", default="Lands of Lore II .tex Decoder Run Corpus")
    args = parser.parse_args()

    summary, _rows = write_report(
        args.output,
        args.clusters,
        args.comparisons,
        title=args.title,
    )
    print(f"Runs: {summary['extracted_runs']}")
    print(f"Byte-exact runs: {summary['byte_exact_runs']}")
    print(f"Total exact bytes: {summary['total_exact_bytes']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
