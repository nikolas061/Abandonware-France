#!/usr/bin/env python3
"""Extract candidate Lands of Lore II textures from CDCACHE.MIX descriptors."""

from __future__ import annotations

import argparse
import csv
import re
import struct
from pathlib import Path

from PIL import Image


TARGET_SIZE = (1920, 1080)
DEFAULT_CHUNK_SIZE = 0x1000
DEFAULT_RECORD_STRIDE = 0x1039
DEFAULT_TILE_SIZE = 64


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


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "unnamed"


def parse_int(value: str) -> int:
    return int(value, 0)


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
        return [min(255, value * 4) for value in raw], source
    return list(raw), source


def apply_palette(image: Image.Image, palette: list[int] | None) -> Image.Image:
    if not palette:
        return image
    indexed = image if image.mode == "P" else image.convert("P")
    indexed.putpalette(palette)
    return indexed


def make_image(
    pixels: bytes,
    width: int,
    height: int,
    palette: list[int] | None,
    *,
    rgba: bool,
    transparent_index: int,
) -> Image.Image:
    indexed = apply_palette(Image.frombytes("P", (width, height), pixels), palette)
    if not rgba:
        return indexed

    image = indexed.convert("RGBA")
    alpha = Image.frombytes(
        "L",
        (width, height),
        bytes(0 if value == transparent_index else 255 for value in pixels),
    )
    image.putalpha(alpha)
    return image


def make_fullhd(image: Image.Image, target: tuple[int, int]) -> Image.Image:
    has_alpha = image.mode in {"RGBA", "LA"} or "transparency" in image.info
    source = image.convert("RGBA" if has_alpha else "RGB")
    target_w, target_h = target
    scale = min(target_w / source.width, target_h / source.height)
    scaled_w = max(1, round(source.width * scale))
    scaled_h = max(1, round(source.height * scale))
    scaled = source.resize((scaled_w, scaled_h), Image.Resampling.NEAREST)
    origin = ((target_w - scaled_w) // 2, (target_h - scaled_h) // 2)
    if has_alpha:
        canvas = Image.new("RGBA", target, (0, 0, 0, 0))
        canvas.alpha_composite(scaled, origin)
    else:
        canvas = Image.new("RGB", target, (0, 0, 0))
        canvas.paste(scaled, origin)
    return canvas


def collect_pixels(
    data: bytes,
    start: int,
    size: int,
    mode: str,
    chunk_size: int,
    record_stride: int,
    width: int,
    height: int,
    tile_size: int,
) -> bytes:
    if mode == "contiguous":
        end = start + size
        return data[start:end] if 0 <= start <= end <= len(data) else b""

    if mode == "tiled":
        if tile_size <= 0 or width <= 0 or height <= 0:
            return b""
        tile_bytes = tile_size * tile_size
        if tile_bytes > chunk_size:
            return b""

        pixels = bytearray(size)
        tiles_across = (width + tile_size - 1) // tile_size
        tiles_down = (height + tile_size - 1) // tile_size
        for tile_index in range(tiles_across * tiles_down):
            tile_offset = start + tile_index * record_stride
            if tile_offset < 0 or tile_offset + tile_bytes > len(data):
                return b""
            tile = data[tile_offset : tile_offset + tile_bytes]
            tile_x = (tile_index % tiles_across) * tile_size
            tile_y = (tile_index // tiles_across) * tile_size
            copy_width = min(tile_size, width - tile_x)
            copy_height = min(tile_size, height - tile_y)
            if copy_width <= 0 or copy_height <= 0:
                continue
            for y in range(copy_height):
                source_start = y * tile_size
                dest_start = (tile_y + y) * width + tile_x
                pixels[dest_start : dest_start + copy_width] = tile[
                    source_start : source_start + copy_width
                ]
        return bytes(pixels)

    pixels = bytearray()
    offset = start
    while len(pixels) < size and 0 <= offset < len(data):
        take = min(chunk_size, size - len(pixels))
        if offset + take > len(data):
            return b""
        pixels.extend(data[offset : offset + take])
        offset += record_stride
    return bytes(pixels) if len(pixels) == size else b""


def content_bbox(
    pixels: bytes,
    width: int,
    height: int,
    transparent_index: int,
) -> tuple[int, int, int, int] | None:
    left = width
    top = height
    right = -1
    bottom = -1
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


def load_descriptor_rows(path: Path, matched_only: bool) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    if matched_only:
        rows = [row for row in rows if row["matched_texture_archives"]]
    return rows


def write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "pcx_name",
        "base_name",
        "matched_texture_archives",
        "marker_word",
        "origin_x",
        "origin_y",
        "width",
        "height",
        "scale",
        "cache_index",
        "decode_mode",
        "chunk_size",
        "record_stride",
        "tile_size",
        "data_offset_hex",
        "data_size_guess",
        "content_bbox",
        "visible_pixel_ratio",
        "palette_source",
        "image_mode",
        "native_path",
        "fullhd_path",
        "crop_native_path",
        "crop_fullhd_path",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_tile_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = [
        "pcx_name",
        "base_name",
        "matched_texture_archives",
        "cache_index",
        "tile_index",
        "tile_x",
        "tile_y",
        "tile_width",
        "tile_height",
        "tile_size",
        "record_stride",
        "tile_data_offset_hex",
        "content_bbox",
        "visible_pixel_ratio",
        "palette_source",
        "image_mode",
        "native_path",
        "fullhd_path",
        "crop_native_path",
        "crop_fullhd_path",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract paletted PNG candidates from CDCACHE.MIX descriptor rows.",
    )
    parser.add_argument("--cache", type=Path, default=Path("C/LOLG/CDCACHE.MIX"))
    parser.add_argument(
        "--descriptors",
        type=Path,
        default=Path("output/texture_report/cdcache_descriptors.csv"),
    )
    parser.add_argument("-o", "--output", type=Path, default=Path("output/cdcache_textures"))
    parser.add_argument("--palette", default="C/LOLG/LOCAL.MIX:94")
    parser.add_argument("--all", action="store_true", help="Export every descriptor, not only .tex matches.")
    parser.add_argument(
        "--decode-mode",
        choices=("contiguous", "strided", "tiled", "both", "all-modes"),
        default="tiled",
        help="Read pixels continuously, as 4K cache chunks, or as 64x64 tiled chunks.",
    )
    parser.add_argument("--chunk-size", type=parse_int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--record-stride", type=parse_int, default=DEFAULT_RECORD_STRIDE)
    parser.add_argument("--tile-size", type=parse_int, default=DEFAULT_TILE_SIZE)
    parser.add_argument("--content-crop", action="store_true")
    parser.add_argument("--transparent-index", type=parse_int, default=0)
    parser.add_argument("--export-tiles", action="store_true")
    parser.add_argument("--include-empty-tiles", action="store_true")
    parser.add_argument(
        "--rgba",
        action="store_true",
        help="Write RGBA PNGs with transparent-index pixels exported as alpha 0.",
    )
    parser.add_argument("--fullhd", action="store_true")
    args = parser.parse_args()

    data = args.cache.read_bytes()
    palette, palette_source = load_palette(args.palette)
    rows = load_descriptor_rows(args.descriptors, matched_only=not args.all)

    args.output.mkdir(parents=True, exist_ok=True)
    native_dir = args.output / "native"
    fullhd_dir = args.output / "fullhd"
    crop_native_dir = args.output / "crop_native"
    crop_fullhd_dir = args.output / "crop_fullhd"
    tile_native_dir = args.output / "tiles_native"
    tile_fullhd_dir = args.output / "tiles_fullhd"
    tile_crop_native_dir = args.output / "tiles_crop_native"
    tile_crop_fullhd_dir = args.output / "tiles_crop_fullhd"
    native_dir.mkdir(parents=True, exist_ok=True)
    if args.fullhd:
        fullhd_dir.mkdir(parents=True, exist_ok=True)
    if args.content_crop:
        crop_native_dir.mkdir(parents=True, exist_ok=True)
        if args.fullhd:
            crop_fullhd_dir.mkdir(parents=True, exist_ok=True)
    if args.export_tiles:
        tile_native_dir.mkdir(parents=True, exist_ok=True)
        if args.fullhd:
            tile_fullhd_dir.mkdir(parents=True, exist_ok=True)
        if args.content_crop:
            tile_crop_native_dir.mkdir(parents=True, exist_ok=True)
            if args.fullhd:
                tile_crop_fullhd_dir.mkdir(parents=True, exist_ok=True)

    manifest_rows: list[dict[str, str]] = []
    tile_manifest_rows: list[dict[str, str]] = []
    image_suffix = "_rgba" if args.rgba else ("_pal" if palette else "")
    image_mode = "RGBA" if args.rgba else "P"
    if args.decode_mode == "both":
        modes = ("contiguous", "strided")
    elif args.decode_mode == "all-modes":
        modes = ("contiguous", "strided", "tiled")
    else:
        modes = (args.decode_mode,)
    for row in rows:
        width = int(row["width"])
        height = int(row["height"])
        data_offset = int(row["data_offset"])
        size = width * height
        if width <= 0 or height <= 0 or data_offset < 0:
            continue

        for mode in modes:
            pixels = collect_pixels(
                data,
                data_offset,
                size,
                mode,
                args.chunk_size,
                args.record_stride,
                width,
                height,
                args.tile_size,
            )
            if len(pixels) != size:
                continue

            image = make_image(
                pixels,
                width,
                height,
                palette,
                rgba=args.rgba,
                transparent_index=args.transparent_index,
            )
            stem = (
                f"{safe_name(row['base_name'])}_idx{int(row['cache_index']):04d}"
                f"_off{data_offset:08x}_{width}x{height}_{mode}"
            )
            native_path = native_dir / f"{stem}{image_suffix}.png"
            image.save(native_path, "PNG")

            fullhd_path = ""
            if args.fullhd:
                target = make_fullhd(image, TARGET_SIZE)
                fullhd_path = str(fullhd_dir / f"{stem}{image_suffix}_fullhd.png")
                target.save(fullhd_path, "PNG")

            bbox = content_bbox(pixels, width, height, args.transparent_index)
            bbox_text = ",".join(str(value) for value in bbox) if bbox else ""
            visible_pixels = sum(1 for value in pixels if value != args.transparent_index)
            visible_pixel_ratio = f"{visible_pixels / len(pixels):.6f}" if pixels else ""
            crop_native_path = ""
            crop_fullhd_path = ""
            if args.content_crop and bbox:
                crop = image.crop(bbox)
                crop_native = crop_native_dir / f"{stem}{image_suffix}_crop.png"
                crop.save(crop_native, "PNG")
                crop_native_path = str(crop_native)
                if args.fullhd:
                    crop_target = make_fullhd(crop, TARGET_SIZE)
                    crop_fullhd = (
                        crop_fullhd_dir
                        / f"{stem}{image_suffix}_crop_fullhd.png"
                    )
                    crop_target.save(crop_fullhd, "PNG")
                    crop_fullhd_path = str(crop_fullhd)

            manifest_rows.append(
                {
                    "pcx_name": row["pcx_name"],
                    "base_name": row["base_name"],
                    "matched_texture_archives": row["matched_texture_archives"],
                    "marker_word": row["marker_word"],
                    "origin_x": row["origin_x"],
                    "origin_y": row["origin_y"],
                    "width": row["width"],
                    "height": row["height"],
                    "scale": row["scale"],
                    "cache_index": row["cache_index"],
                    "decode_mode": mode,
                    "chunk_size": f"0x{args.chunk_size:x}",
                    "record_stride": f"0x{args.record_stride:x}",
                    "tile_size": f"0x{args.tile_size:x}",
                    "data_offset_hex": row["data_offset_hex"],
                    "data_size_guess": row["data_size_guess"],
                    "content_bbox": bbox_text,
                    "visible_pixel_ratio": visible_pixel_ratio,
                    "palette_source": palette_source,
                    "image_mode": image_mode,
                    "native_path": str(native_path),
                    "fullhd_path": fullhd_path,
                    "crop_native_path": crop_native_path,
                    "crop_fullhd_path": crop_fullhd_path,
                }
            )

        if args.export_tiles and args.tile_size > 0:
            tiles_across = (width + args.tile_size - 1) // args.tile_size
            tiles_down = (height + args.tile_size - 1) // args.tile_size
            tile_bytes = args.tile_size * args.tile_size
            if tile_bytes <= args.chunk_size:
                for tile_index in range(tiles_across * tiles_down):
                    tile_offset = data_offset + tile_index * args.record_stride
                    if tile_offset < 0 or tile_offset + tile_bytes > len(data):
                        continue
                    tile_x = (tile_index % tiles_across) * args.tile_size
                    tile_y = (tile_index // tiles_across) * args.tile_size
                    tile_width = min(args.tile_size, width - tile_x)
                    tile_height = min(args.tile_size, height - tile_y)
                    if tile_width <= 0 or tile_height <= 0:
                        continue

                    raw_tile = data[tile_offset : tile_offset + tile_bytes]
                    tile_pixels = bytearray(tile_width * tile_height)
                    for y in range(tile_height):
                        source_start = y * args.tile_size
                        dest_start = y * tile_width
                        tile_pixels[dest_start : dest_start + tile_width] = raw_tile[
                            source_start : source_start + tile_width
                        ]

                    tile_bbox = content_bbox(
                        tile_pixels,
                        tile_width,
                        tile_height,
                        args.transparent_index,
                    )
                    if tile_bbox is None and not args.include_empty_tiles:
                        continue

                    tile_visible_pixels = sum(
                        1 for value in tile_pixels if value != args.transparent_index
                    )
                    tile_visible_ratio = (
                        f"{tile_visible_pixels / len(tile_pixels):.6f}"
                        if tile_pixels
                        else ""
                    )
                    tile_image = make_image(
                        bytes(tile_pixels),
                        tile_width,
                        tile_height,
                        palette,
                        rgba=args.rgba,
                        transparent_index=args.transparent_index,
                    )
                    base_stem = (
                        f"{safe_name(row['base_name'])}_idx{int(row['cache_index']):04d}"
                        f"_tile{tile_index:04d}_x{tile_x:04d}_y{tile_y:04d}"
                        f"_{tile_width}x{tile_height}"
                    )
                    tile_native = (
                        tile_native_dir
                        / f"{base_stem}{image_suffix}.png"
                    )
                    tile_image.save(tile_native, "PNG")

                    tile_fullhd_path = ""
                    if args.fullhd:
                        tile_fullhd = make_fullhd(tile_image, TARGET_SIZE)
                        tile_fullhd_path = str(
                            tile_fullhd_dir
                            / f"{base_stem}{image_suffix}_fullhd.png"
                        )
                        tile_fullhd.save(tile_fullhd_path, "PNG")

                    tile_crop_native_path = ""
                    tile_crop_fullhd_path = ""
                    if args.content_crop and tile_bbox:
                        tile_crop = tile_image.crop(tile_bbox)
                        tile_crop_native = (
                            tile_crop_native_dir
                            / f"{base_stem}{image_suffix}_crop.png"
                        )
                        tile_crop.save(tile_crop_native, "PNG")
                        tile_crop_native_path = str(tile_crop_native)
                        if args.fullhd:
                            tile_crop_fullhd = make_fullhd(tile_crop, TARGET_SIZE)
                            tile_crop_fullhd_path = str(
                                tile_crop_fullhd_dir
                                / f"{base_stem}{image_suffix}_crop_fullhd.png"
                            )
                            tile_crop_fullhd.save(tile_crop_fullhd_path, "PNG")

                    tile_manifest_rows.append(
                        {
                            "pcx_name": row["pcx_name"],
                            "base_name": row["base_name"],
                            "matched_texture_archives": row["matched_texture_archives"],
                            "cache_index": row["cache_index"],
                            "tile_index": str(tile_index),
                            "tile_x": str(tile_x),
                            "tile_y": str(tile_y),
                            "tile_width": str(tile_width),
                            "tile_height": str(tile_height),
                            "tile_size": f"0x{args.tile_size:x}",
                            "record_stride": f"0x{args.record_stride:x}",
                            "tile_data_offset_hex": f"0x{tile_offset:08x}",
                            "content_bbox": (
                                ",".join(str(value) for value in tile_bbox)
                                if tile_bbox
                                else ""
                            ),
                            "visible_pixel_ratio": tile_visible_ratio,
                            "palette_source": palette_source,
                            "image_mode": image_mode,
                            "native_path": str(tile_native),
                            "fullhd_path": tile_fullhd_path,
                            "crop_native_path": tile_crop_native_path,
                            "crop_fullhd_path": tile_crop_fullhd_path,
                        }
                    )

    manifest = args.output / "manifest.csv"
    write_manifest(manifest, manifest_rows)
    if args.export_tiles:
        write_tile_manifest(args.output / "tiles_manifest.csv", tile_manifest_rows)
    print(f"Extracted {len(manifest_rows)} CDCACHE texture candidates")
    print(f"Manifest: {manifest}")
    print(f"Native PNGs: {native_dir}")
    if args.fullhd:
        print(f"Full HD PNGs: {fullhd_dir}")
    if args.content_crop:
        print(f"Cropped native PNGs: {crop_native_dir}")
        if args.fullhd:
            print(f"Cropped Full HD PNGs: {crop_fullhd_dir}")
    if args.export_tiles:
        print(f"Extracted {len(tile_manifest_rows)} CDCACHE tile candidates")
        print(f"Tile manifest: {args.output / 'tiles_manifest.csv'}")
        print(f"Tile native PNGs: {tile_native_dir}")
        if args.fullhd:
            print(f"Tile Full HD PNGs: {tile_fullhd_dir}")


if __name__ == "__main__":
    main()
