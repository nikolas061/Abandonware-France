#!/usr/bin/env python3
"""Build alias candidates from raw CDCACHE probes for missing .tex names."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
import struct
from pathlib import Path


DEFAULT_OUTPUT = Path("output/cdcache_alias_candidates")
DEFAULT_CACHE = Path("C/LOLG/CDCACHE.MIX")
DEFAULT_PROBE = Path("output/cdcache_raw_reference_probe/raw_reference_probe.csv")
DEFAULT_DESCRIPTORS = Path("output/texture_report/cdcache_descriptors.csv")
DEFAULT_PACK_MANIFEST = Path("output/cdcache_hd_asset_pack/manifest.csv")

DESCRIPTOR_FIELDNAMES = [
    "cache_path",
    "name_offset",
    "name_offset_hex",
    "pcx_name",
    "base_name",
    "matched_texture_archives",
    "descriptor_offset",
    "descriptor_offset_hex",
    "descriptor_padding",
    "marker_word",
    "origin_x",
    "origin_y",
    "width",
    "height",
    "scale",
    "cache_index",
    "unknown_dword",
    "tail_word0",
    "tail_word1",
    "data_offset",
    "data_offset_hex",
    "data_size_guess",
    "data_end_guess",
    "data_fits",
    "data_head_hex",
    "data_head_zero_ratio",
    "data_unique_values",
    "data_zero_ratio",
    "content_bbox",
    "content_width",
    "content_height",
    "content_area_ratio",
    "next_descriptor_offset",
    "next_descriptor_offset_hex",
    "next_descriptor_distance",
    "gap_to_next_descriptor",
    "data_crosses_next_descriptor",
]

SUMMARY_FIELDNAMES = [
    "scope",
    "alias_rows",
    "unique_missing_pcx",
    "existing_descriptor_aliases",
    "synthetic_descriptor_aliases",
    "aliases_with_pack_fullhd",
    "synthetic_descriptor_rows",
    "issue_rows",
]

ALIAS_FIELDNAMES = [
    "archive",
    "archive_tag",
    "missing_pcx_name",
    "raw_pcx_name",
    "alias_kind",
    "candidate_pcx_name",
    "candidate_base_name",
    "descriptor_offset_hex",
    "marker_word",
    "origin_x",
    "origin_y",
    "width",
    "height",
    "scale",
    "cache_index",
    "data_offset_hex",
    "pack_fullhd_path",
    "pack_path",
    "synthetic_descriptor",
    "issues",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def normalize_pcx(name: str) -> str:
    return Path(name.replace("\\", "/")).name.lower()


def archive_tag(path_text: str) -> str:
    return Path(path_text).stem.upper() if path_text else "UNKNOWN"


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "unnamed"


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def parse_candidate(value: str) -> dict[str, str] | None:
    if not value:
        return None
    first = value.split(";", 1)[0]
    match = re.match(
        r"(?P<offset>0x[0-9a-fA-F]+):(?P<marker>[0-9a-fA-F]{4}):"
        r"(?P<origin_x>\d+),(?P<origin_y>\d+):(?P<width>\d+)x(?P<height>\d+):"
        r"scale(?P<scale>\d+):idx(?P<cache_index>\d+):pad(?P<padding>-?\d+)",
        first,
    )
    return match.groupdict() if match else None


def descriptor_by_offset(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row["descriptor_offset_hex"].lower(): row for row in rows}


def pack_by_descriptor_key(rows: list[dict[str, str]]) -> dict[tuple[str, str, str, str], dict[str, str]]:
    output: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for row in rows:
        if row.get("asset_kind") != "descriptor":
            continue
        key = (
            row.get("base_name", "").lower(),
            row.get("cache_index", ""),
            row.get("native_width", ""),
            row.get("native_height", ""),
        )
        output[key] = row
    return output


def content_bbox(pixels: bytes, width: int, height: int, transparent_index: int = 0) -> tuple[int, int, int, int] | None:
    left = width
    top = height
    right = -1
    bottom = -1
    if len(pixels) < width * height:
        return None
    for y in range(height):
        row_start = y * width
        row = pixels[row_start : row_start + width]
        for x, value in enumerate(row):
            if value == transparent_index:
                continue
            if x < left:
                left = x
            if x > right:
                right = x
            if y < top:
                top = y
            if y > bottom:
                bottom = y
    if right < left or bottom < top:
        return None
    return left, top, right + 1, bottom + 1


def synthetic_descriptor_row(
    cache: Path,
    data: bytes,
    probe: dict[str, str],
    candidate: dict[str, str],
) -> dict[str, str]:
    descriptor_offset = int(candidate["offset"], 0)
    marker_word, origin_x, origin_y, width, height, scale, cache_index = struct.unpack_from(
        "<HHHHHHH",
        data,
        descriptor_offset,
    )
    unknown_dword = struct.unpack_from("<I", data, descriptor_offset + 14)[0]
    tail_word0, tail_word1 = struct.unpack_from("<HH", data, descriptor_offset + 18)
    data_offset = descriptor_offset + 22
    data_size_guess = width * height
    data_end = data_offset + data_size_guess
    sample = data[data_offset : min(len(data), data_offset + min(data_size_guess, 4096))]
    pixels = data[data_offset:data_end] if data_end <= len(data) else b""
    bbox = content_bbox(pixels, width, height)
    if bbox:
        left, top, right, bottom = bbox
        content_width = right - left
        content_height = bottom - top
        content_bbox_text = f"{left},{top},{right},{bottom}"
        content_area_ratio = f"{(content_width * content_height) / (width * height):.6f}"
    else:
        content_width = 0
        content_height = 0
        content_bbox_text = ""
        content_area_ratio = "0.000000" if width and height else ""
    return {
        "cache_path": str(cache),
        "name_offset": probe["name_offset"],
        "name_offset_hex": probe["name_offset_hex"],
        "pcx_name": probe["missing_pcx_name"] if "missing_pcx_name" in probe else probe["normalized_pcx_name"],
        "base_name": normalize_pcx(probe["normalized_pcx_name"]),
        "matched_texture_archives": probe["archive"],
        "descriptor_offset": str(descriptor_offset),
        "descriptor_offset_hex": f"0x{descriptor_offset:08x}",
        "descriptor_padding": candidate["padding"],
        "marker_word": f"{marker_word:04x}",
        "origin_x": str(origin_x),
        "origin_y": str(origin_y),
        "width": str(width),
        "height": str(height),
        "scale": str(scale),
        "cache_index": str(cache_index),
        "unknown_dword": f"{unknown_dword:08x}",
        "tail_word0": f"{tail_word0:04x}",
        "tail_word1": f"{tail_word1:04x}",
        "data_offset": str(data_offset),
        "data_offset_hex": f"0x{data_offset:08x}",
        "data_size_guess": str(data_size_guess),
        "data_end_guess": str(data_end),
        "data_fits": str(data_end <= len(data)),
        "data_head_hex": data[data_offset : data_offset + 64].hex(),
        "data_head_zero_ratio": f"{sample.count(0) / len(sample):.6f}" if sample else "",
        "data_unique_values": str(len(set(pixels))) if pixels else "",
        "data_zero_ratio": f"{pixels.count(0) / len(pixels):.6f}" if pixels else "",
        "content_bbox": content_bbox_text,
        "content_width": str(content_width),
        "content_height": str(content_height),
        "content_area_ratio": content_area_ratio,
        "next_descriptor_offset": "",
        "next_descriptor_offset_hex": "",
        "next_descriptor_distance": "",
        "gap_to_next_descriptor": "",
        "data_crosses_next_descriptor": "",
    }


def build_alias_rows(
    cache: Path,
    probe_rows: list[dict[str, str]],
    descriptors: list[dict[str, str]],
    pack_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    data = cache.read_bytes()
    descriptors_by_offset = descriptor_by_offset(descriptors)
    pack_by_key = pack_by_descriptor_key(pack_rows)
    alias_rows: list[dict[str, str]] = []
    synthetic_rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for probe in probe_rows:
        candidate = parse_candidate(probe.get("descriptor_candidates", ""))
        if candidate is None:
            continue
        archive = probe["archive"]
        missing = probe["normalized_pcx_name"]
        descriptor_offset_hex = candidate["offset"].lower()
        key = (archive, missing, descriptor_offset_hex)
        if key in seen:
            continue
        seen.add(key)
        descriptor = descriptors_by_offset.get(descriptor_offset_hex)
        synthetic = descriptor is None
        if synthetic:
            descriptor = synthetic_descriptor_row(cache, data, probe, candidate)
            synthetic_rows.append(descriptor)

        pack_key = (
            descriptor.get("base_name", "").lower(),
            descriptor.get("cache_index", ""),
            descriptor.get("width", ""),
            descriptor.get("height", ""),
        )
        pack = pack_by_key.get(pack_key, {})
        issues: list[str] = []
        if not synthetic and not pack:
            issues.append("existing_descriptor_missing_pack_asset")
        if synthetic and descriptor.get("data_fits") != "True":
            issues.append("synthetic_descriptor_data_out_of_range")
        alias_rows.append(
            {
                "archive": archive,
                "archive_tag": probe.get("archive_tag", "") or archive_tag(archive),
                "missing_pcx_name": missing,
                "raw_pcx_name": probe.get("raw_pcx_name", ""),
                "alias_kind": "synthetic_descriptor" if synthetic else "existing_descriptor",
                "candidate_pcx_name": descriptor.get("pcx_name", ""),
                "candidate_base_name": descriptor.get("base_name", ""),
                "descriptor_offset_hex": descriptor.get("descriptor_offset_hex", ""),
                "marker_word": descriptor.get("marker_word", ""),
                "origin_x": descriptor.get("origin_x", ""),
                "origin_y": descriptor.get("origin_y", ""),
                "width": descriptor.get("width", ""),
                "height": descriptor.get("height", ""),
                "scale": descriptor.get("scale", ""),
                "cache_index": descriptor.get("cache_index", ""),
                "data_offset_hex": descriptor.get("data_offset_hex", ""),
                "pack_fullhd_path": pack.get("source_fullhd_path", ""),
                "pack_path": pack.get("all_pack_path", ""),
                "synthetic_descriptor": "yes" if synthetic else "no",
                "issues": ";".join(issues),
            }
        )
    return alias_rows, synthetic_rows


def summary_row(alias_rows: list[dict[str, str]], synthetic_rows: list[dict[str, str]]) -> dict[str, str]:
    return {
        "scope": "total",
        "alias_rows": str(len(alias_rows)),
        "unique_missing_pcx": str(len({row["missing_pcx_name"] for row in alias_rows})),
        "existing_descriptor_aliases": str(
            sum(1 for row in alias_rows if row["alias_kind"] == "existing_descriptor")
        ),
        "synthetic_descriptor_aliases": str(
            sum(1 for row in alias_rows if row["alias_kind"] == "synthetic_descriptor")
        ),
        "aliases_with_pack_fullhd": str(sum(1 for row in alias_rows if row["pack_fullhd_path"])),
        "synthetic_descriptor_rows": str(len(synthetic_rows)),
        "issue_rows": str(sum(1 for row in alias_rows if row["issues"])),
    }


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def render_table(rows: list[dict[str, str]], columns: list[str]) -> str:
    head = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(row.get(column, ''))}</td>" for column in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_html(
    summary: dict[str, str],
    aliases: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "aliases": aliases}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("alias_candidates.csv", output_dir / "alias_candidates.csv"),
            ("synthetic_descriptors.csv", output_dir / "synthetic_descriptors.csv"),
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
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
}}
.stat {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  padding: 10px;
}}
.label {{ color: var(--muted); }}
.value {{ font-size: 24px; font-weight: 750; line-height: 1.05; margin-top: 4px; }}
.ok {{ color: var(--ok); }}
.panel {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  padding: 12px;
  overflow-x: auto;
}}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
table {{ width: 100%; min-width: 1280px; border-collapse: collapse; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
td {{ overflow-wrap: anywhere; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 10px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Alias</div><div class="value">{html.escape(summary['alias_rows'])}</div></div>
    <div class="stat"><div class="label">Noms uniques</div><div class="value">{html.escape(summary['unique_missing_pcx'])}</div></div>
    <div class="stat"><div class="label">Descriptors existants</div><div class="value">{html.escape(summary['existing_descriptor_aliases'])}</div></div>
    <div class="stat"><div class="label">Descriptors synthetiques</div><div class="value">{html.escape(summary['synthetic_descriptor_aliases'])}</div></div>
    <div class="stat"><div class="label">Issues</div><div class="value ok">{html.escape(summary['issue_rows'])}</div></div>
  </section>
  <section class="panel">
    <h2>Fichiers</h2>
    <div>{links}</div>
  </section>
  <section class="panel">
    <h2>Synthese</h2>
    {render_table([summary], SUMMARY_FIELDNAMES)}
  </section>
  <section class="panel">
    <h2>Alias candidats</h2>
    {render_table(aliases, ALIAS_FIELDNAMES)}
  </section>
</main>
<script>
const CDCACHE_ALIAS_CANDIDATES = {data_json};
</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    cache: Path,
    probe: Path,
    descriptors: Path,
    pack_manifest: Path,
    title: str,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    aliases, synthetic_rows = build_alias_rows(
        cache,
        read_rows(probe),
        read_rows(descriptors),
        read_rows(pack_manifest),
    )
    summary = summary_row(aliases, synthetic_rows)
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "alias_candidates.csv", ALIAS_FIELDNAMES, aliases)
    write_csv(output_dir / "synthetic_descriptors.csv", DESCRIPTOR_FIELDNAMES, synthetic_rows)
    (output_dir / "index.html").write_text(build_html(summary, aliases, output_dir, title))
    return summary, aliases, synthetic_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Build CDCACHE alias candidates for missing .tex names.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--probe", type=Path, default=DEFAULT_PROBE)
    parser.add_argument("--descriptors", type=Path, default=DEFAULT_DESCRIPTORS)
    parser.add_argument("--pack-manifest", type=Path, default=DEFAULT_PACK_MANIFEST)
    parser.add_argument("--title", default="Lands of Lore II CDCACHE Alias Candidates")
    args = parser.parse_args()

    summary, _aliases, _synthetic = write_report(
        args.output,
        args.cache,
        args.probe,
        args.descriptors,
        args.pack_manifest,
        args.title,
    )
    print(f"Alias rows: {summary['alias_rows']}")
    print(f"Unique missing PCX: {summary['unique_missing_pcx']}")
    print(f"Existing/synthetic aliases: {summary['existing_descriptor_aliases']}/{summary['synthetic_descriptor_aliases']}")
    print(f"Aliases with pack Full HD: {summary['aliases_with_pack_fullhd']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"HTML: {args.output / 'index.html'}")
    if summary["issue_rows"] != "0":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
