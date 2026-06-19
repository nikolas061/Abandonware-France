#!/usr/bin/env python3
"""Render exploratory byte previews from Lands of Lore II texture payloads."""

from __future__ import annotations

import argparse
import csv
import math
import re
import struct
from pathlib import Path

from PIL import Image


TARGET_SIZE = (1920, 1080)


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


def parse_int_list(value: str) -> list[int]:
    items: list[int] = []
    for item in value.split(","):
        item = item.strip()
        if item:
            items.append(int(item, 0))
    return items


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "unnamed"


def make_fullhd(image: Image.Image, target: tuple[int, int]) -> Image.Image:
    source = image.convert("RGB")
    target_w, target_h = target
    scale = min(target_w / source.width, target_h / source.height)
    scaled_w = max(1, round(source.width * scale))
    scaled_h = max(1, round(source.height * scale))
    scaled = source.resize((scaled_w, scaled_h), Image.Resampling.NEAREST)
    canvas = Image.new("RGB", target, (0, 0, 0))
    canvas.paste(scaled, ((target_w - scaled_w) // 2, (target_h - scaled_h) // 2))
    return canvas


def render_grayscale(data: bytes, width: int, max_rows: int) -> Image.Image:
    if not data:
        data = b"\0"
    height = max(1, min(max_rows, math.ceil(len(data) / width)))
    pixel_count = width * height
    clipped = data[:pixel_count].ljust(pixel_count, b"\0")
    return Image.frombytes("L", (width, height), clipped)


def load_palette(spec: str) -> tuple[list[int] | None, str]:
    if not spec:
        return None, ""

    if ":" in spec:
        path_text, index_text = spec.rsplit(":", 1)
        _file_id, payload = read_mix_entry(Path(path_text), int(index_text, 0))
        source = spec
    else:
        payload = Path(spec).read_bytes()
        source = spec

    if len(payload) < 768:
        raise ValueError(f"{source}: palette payload is shorter than 768 bytes")

    raw = payload[:768]
    if max(raw) <= 63:
        values = [min(255, value * 4) for value in raw]
    else:
        values = list(raw)
    return values, source


def apply_palette(image: Image.Image, palette: list[int] | None) -> Image.Image:
    if not palette:
        return image
    indexed = image if image.mode == "P" else image.convert("P")
    indexed.putpalette(palette)
    return indexed


def load_probe_rows(report_dir: Path, names: set[str]) -> list[dict[str, str]]:
    links_path = report_dir / "material_texture_record_links.csv"
    segments_path = report_dir / "texture_segments.csv"

    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    if links_path.exists():
        with links_path.open(newline="") as handle:
            for row in csv.DictReader(handle):
                if not row.get("texture_body_offset"):
                    continue
                pcx_name = row["pcx_name"].lower()
                if names and pcx_name not in names:
                    continue
                key = (row["archive"], pcx_name, row["texture_body_offset"])
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "source": "material_texture_record_links",
                        "archive": row["archive"],
                        "pcx_name": row["pcx_name"],
                        "segment_index": row["texture_segment_index"],
                        "body_offset": row["texture_body_offset"],
                        "body_offset_hex": row["texture_body_offset_hex"],
                        "segment_size": row["texture_segment_size"],
                        "body_first_word": row["texture_body_first_word"],
                        "material_clean_text": row["material_clean_text"],
                        "record_size": row["record_size"],
                    }
                )

    if rows or not segments_path.exists():
        return rows

    with segments_path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row["reference_class"] == "prefix" or not row["body_offset"]:
                continue
            pcx_name = row["pcx_name"].rsplit("\\", 1)[-1].rsplit("/", 1)[-1].lower()
            if names and pcx_name not in names:
                continue
            rows.append(
                {
                    "source": "texture_segments",
                    "archive": row["archive"],
                    "pcx_name": row["pcx_name"],
                    "segment_index": row["segment_index"],
                    "body_offset": row["body_offset"],
                    "body_offset_hex": row["body_offset_hex"],
                    "segment_size": row["segment_size"],
                    "body_first_word": row["body_first_word"],
                    "material_clean_text": "",
                    "record_size": "",
                }
            )
    return rows


def load_profile_names(path: Path, priority: str) -> set[str]:
    names: set[str] = set()
    if not path.exists():
        return names
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            if priority and row.get("priority") != priority:
                continue
            name = row.get("normalized_pcx_name") or row.get("pcx_name")
            if name:
                names.add(Path(name.replace("\\", "/")).name.lower())
    return names


def write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "archive",
        "pcx_name",
        "material_clean_text",
        "segment_index",
        "body_offset",
        "body_offset_hex",
        "body_first_word",
        "segment_size",
        "skip",
        "width",
        "height",
        "sample_size",
        "record_size",
        "palette_source",
        "source",
        "native_path",
        "fullhd_path",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render exploratory grayscale previews from texture payload bytes.",
    )
    parser.add_argument("--report-dir", type=Path, default=Path("output/texture_report"))
    parser.add_argument("-o", "--output", type=Path, default=Path("output/tex_probe_render"))
    parser.add_argument("--names", default="", help="Comma-separated PCX basenames to render.")
    parser.add_argument(
        "--names-from-profile",
        type=Path,
        default=None,
        help="Optional remaining-reference profile CSV used to add PCX basenames.",
    )
    parser.add_argument(
        "--profile-priority",
        default="",
        help="When --names-from-profile is set, only include rows with this priority.",
    )
    parser.add_argument("--widths", default="64,128,256")
    parser.add_argument("--skips", default="0,4,8,12,16,24,32")
    parser.add_argument("--max-rows", type=int, default=512)
    parser.add_argument("--max-samples", type=int, default=16)
    parser.add_argument(
        "--palette",
        default="",
        help="Optional raw palette path, or MIX path plus entry index as path:index.",
    )
    parser.add_argument("--fullhd", action="store_true")
    args = parser.parse_args()

    names = {
        item.strip().lower()
        for item in args.names.split(",")
        if item.strip()
    }
    if args.names_from_profile is not None:
        names.update(load_profile_names(args.names_from_profile, args.profile_priority))
    widths = parse_int_list(args.widths)
    skips = parse_int_list(args.skips)
    probe_rows = load_probe_rows(args.report_dir, names)[: args.max_samples]
    palette, palette_source = load_palette(args.palette)

    args.output.mkdir(parents=True, exist_ok=True)
    payload_cache: dict[Path, bytes] = {}
    manifest_rows: list[dict[str, str]] = []
    for row in probe_rows:
        archive = Path(row["archive"])
        if archive not in payload_cache:
            _file_id, payload_cache[archive] = read_mix_entry(archive, 2)
        payload = payload_cache[archive]
        body_offset = int(row["body_offset"])
        segment_size = int(row["segment_size"]) if row["segment_size"] else 0
        sample_limit = min(segment_size, max(widths) * args.max_rows + max(skips))
        base = payload[body_offset : body_offset + sample_limit]

        archive_dir = args.output / archive.stem
        archive_dir.mkdir(parents=True, exist_ok=True)
        stem = safe_name(row["pcx_name"])
        for skip in skips:
            if skip >= len(base):
                continue
            for width in widths:
                sample = base[skip : skip + width * args.max_rows]
                image = apply_palette(
                    render_grayscale(sample, width, args.max_rows),
                    palette,
                )
                native_path = (
                    archive_dir
                    / f"{stem}_seg{row['segment_index']}_off{body_offset:08x}_skip{skip}_w{width}{'_pal' if palette else ''}.png"
                )
                image.save(native_path, "PNG")
                fullhd_path = ""
                if args.fullhd:
                    fullhd = make_fullhd(image, TARGET_SIZE)
                    fullhd_path = str(
                        native_path.with_name(native_path.stem + "_fullhd.png")
                    )
                    fullhd.save(fullhd_path, "PNG")
                manifest_rows.append(
                    {
                        "archive": row["archive"],
                        "pcx_name": row["pcx_name"],
                        "material_clean_text": row["material_clean_text"],
                        "segment_index": row["segment_index"],
                        "body_offset": row["body_offset"],
                        "body_offset_hex": row["body_offset_hex"],
                        "body_first_word": row["body_first_word"],
                        "segment_size": row["segment_size"],
                        "skip": str(skip),
                        "width": str(width),
                        "height": str(image.height),
                        "sample_size": str(len(sample)),
                        "record_size": row["record_size"],
                        "palette_source": palette_source,
                        "source": row["source"],
                        "native_path": str(native_path),
                        "fullhd_path": fullhd_path,
                    }
                )

    manifest_path = args.output / "manifest.csv"
    write_manifest(manifest_path, manifest_rows)
    print(f"Rendered {len(manifest_rows)} probe previews to {args.output}")
    print(f"Name filters: {len(names)}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
