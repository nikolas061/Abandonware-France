#!/usr/bin/env python3
"""Export Lands of Lore II still image assets as Full HD PNG images."""

from __future__ import annotations

import argparse
import csv
import io
import re
import struct
from pathlib import Path

from PIL import Image


PCX_SIGNATURES = {b"\x0a\x05\x01\x08", b"\x0a\x00\x01\x08"}
TARGET_SIZE = (1920, 1080)
RT_CURSOR = 1
RT_BITMAP = 2
RT_ICON = 3
RT_GROUP_CURSOR = 12
RT_GROUP_ICON = 14


def read_entries(path: Path) -> tuple[int, list[tuple[int, int, int]]]:
    data = path.read_bytes()
    if len(data) < 6:
        raise ValueError(f"{path}: too small to be a MIX archive")

    count, body_size = struct.unpack_from("<HI", data, 0)
    table_end = 6 + count * 12
    if table_end > len(data):
        raise ValueError(f"{path}: invalid MIX table")

    entries: list[tuple[int, int, int]] = []
    max_end = 0
    for index in range(count):
        file_id, offset, size = struct.unpack_from("<III", data, 6 + index * 12)
        entries.append((file_id, offset, size))
        max_end = max(max_end, offset + size)

    if max_end > body_size:
        raise ValueError(f"{path}: entry table exceeds declared body size")

    return table_end, entries


def is_pcx(data: bytes) -> bool:
    return data[:4] in PCX_SIGNATURES


def scaled_rect(source: tuple[int, int], target: tuple[int, int], fit: str) -> tuple[int, int]:
    source_w, source_h = source
    target_w, target_h = target

    if fit == "stretch":
        return target

    scale_fn = max if fit == "cover" else min
    scale = scale_fn(target_w / source_w, target_h / source_h)
    return max(1, round(source_w * scale)), max(1, round(source_h * scale))


def make_fullhd(
    image: Image.Image,
    target: tuple[int, int],
    fit: str,
    resample: Image.Resampling,
    background: tuple[int, int, int],
) -> Image.Image:
    has_alpha = image.mode in {"RGBA", "LA"} or "transparency" in image.info
    source = image.convert("RGBA" if has_alpha else "RGB")
    target_w, target_h = target
    scaled_w, scaled_h = scaled_rect(source.size, target, fit)
    scaled = source.resize((scaled_w, scaled_h), resample=resample)

    if fit == "stretch":
        return scaled

    left = (target_w - scaled_w) // 2
    top = (target_h - scaled_h) // 2

    if fit == "cover":
        crop_left = max(0, -left)
        crop_top = max(0, -top)
        return scaled.crop((crop_left, crop_top, crop_left + target_w, crop_top + target_h))

    canvas = Image.new("RGBA" if has_alpha else "RGB", target, (*background, 0) if has_alpha else background)
    canvas.paste(scaled, (left, top))
    return canvas


def parse_background(value: str) -> tuple[int, int, int]:
    raw = value.strip()
    if raw.startswith("#"):
        raw = raw[1:]
    if len(raw) != 6:
        raise argparse.ArgumentTypeError("background must be a 6-digit hex color")
    try:
        return tuple(int(raw[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("background must be a 6-digit hex color") from exc


def export_archive(
    archive: Path,
    output_dir: Path,
    target: tuple[int, int],
    fit: str,
    resample: Image.Resampling,
    background: tuple[int, int, int],
) -> list[dict[str, str]]:
    data = archive.read_bytes()
    table_end, entries = read_entries(archive)
    archive_dir = output_dir / archive.stem
    archive_rows: list[dict[str, str]] = []

    for index, (file_id, offset, size) in enumerate(entries):
        payload = data[table_end + offset : table_end + offset + size]
        if not is_pcx(payload):
            continue

        image = Image.open(io.BytesIO(payload))
        image.load()
        rendered = make_fullhd(image, target, fit, resample, background)

        archive_dir.mkdir(parents=True, exist_ok=True)
        source_w, source_h = image.size
        name = f"{index:04d}_{file_id:08x}_{source_w}x{source_h}_fullhd.png"
        output_path = archive_dir / name
        rendered.save(output_path, "PNG", optimize=True)

        archive_rows.append(
            {
                "source_type": "mix_pcx",
                "source_path": str(archive),
                "archive": archive.name,
                "index": f"{index:04d}",
                "file_id": f"{file_id:08x}",
                "source_size": str(size),
                "source_width": str(source_w),
                "source_height": str(source_h),
                "output_width": str(target[0]),
                "output_height": str(target[1]),
                "fit": fit,
                "output_path": str(output_path),
            }
        )

    return archive_rows


def safe_stem(path: Path) -> str:
    stem = path.with_suffix("").as_posix()
    return re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("_")


def output_row(
    source_type: str,
    source_path: Path,
    source_size: int,
    source_width: int,
    source_height: int,
    target: tuple[int, int],
    fit: str,
    output_path: Path,
    archive: str = "",
    index: str = "",
    file_id: str = "",
) -> dict[str, str]:
    return {
        "source_type": source_type,
        "source_path": str(source_path),
        "archive": archive,
        "index": index,
        "file_id": file_id,
        "source_size": str(source_size),
        "source_width": str(source_width),
        "source_height": str(source_height),
        "output_width": str(target[0]),
        "output_height": str(target[1]),
        "fit": fit,
        "output_path": str(output_path),
    }


def export_direct_image(
    path: Path,
    output_dir: Path,
    target: tuple[int, int],
    fit: str,
    resample: Image.Resampling,
    background: tuple[int, int, int],
) -> dict[str, str]:
    with Image.open(path) as image:
        image.load()
        rendered = make_fullhd(image, target, fit, resample, background)
        source_w, source_h = image.size

    direct_dir = output_dir / "DIRECT"
    direct_dir.mkdir(parents=True, exist_ok=True)
    output_path = direct_dir / f"{safe_stem(path)}_{source_w}x{source_h}_fullhd.png"
    rendered.save(output_path, "PNG", optimize=True)

    return output_row("direct_image", path, path.stat().st_size, source_w, source_h, target, fit, output_path)


def read_u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def read_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def read_i32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<i", data, offset)[0]


def parse_pe_resources(path: Path) -> dict[int, list[dict[str, object]]]:
    data = path.read_bytes()
    if len(data) < 0x40 or data[:2] != b"MZ":
        return {}

    pe_offset = read_u32(data, 0x3C)
    if pe_offset + 24 > len(data) or data[pe_offset : pe_offset + 4] != b"PE\0\0":
        return {}

    section_count = read_u16(data, pe_offset + 6)
    optional_size = read_u16(data, pe_offset + 20)
    optional_offset = pe_offset + 24
    if optional_offset + optional_size > len(data):
        return {}

    magic = read_u16(data, optional_offset)
    data_dirs_offset = optional_offset + (112 if magic == 0x20B else 96)
    if data_dirs_offset + 8 * 3 > len(data):
        return {}

    resource_rva = read_u32(data, data_dirs_offset + 8 * 2)
    resource_size = read_u32(data, data_dirs_offset + 8 * 2 + 4)
    if not resource_rva or not resource_size:
        return {}

    sections = []
    section_offset = optional_offset + optional_size
    for index in range(section_count):
        offset = section_offset + index * 40
        if offset + 40 > len(data):
            break
        virtual_size = read_u32(data, offset + 8)
        virtual_address = read_u32(data, offset + 12)
        raw_size = read_u32(data, offset + 16)
        raw_pointer = read_u32(data, offset + 20)
        sections.append((virtual_address, max(virtual_size, raw_size), raw_pointer, raw_size))

    def rva_to_offset(rva: int) -> int | None:
        for virtual_address, size, raw_pointer, raw_size in sections:
            if virtual_address <= rva < virtual_address + size:
                file_offset = raw_pointer + (rva - virtual_address)
                if file_offset < raw_pointer + raw_size and file_offset < len(data):
                    return file_offset
        return None

    resource_offset = rva_to_offset(resource_rva)
    if resource_offset is None:
        return {}

    resources: dict[int, list[dict[str, object]]] = {}

    def resource_name(entry_value: int) -> int | str:
        if entry_value & 0x80000000:
            name_offset = resource_offset + (entry_value & 0x7FFFFFFF)
            if name_offset + 2 > len(data):
                return f"name_{entry_value & 0x7FFFFFFF:x}"
            length = read_u16(data, name_offset)
            raw = data[name_offset + 2 : name_offset + 2 + length * 2]
            return raw.decode("utf-16le", errors="replace")
        return entry_value & 0xFFFF

    def walk(directory_offset: int, levels: list[int | str]) -> None:
        absolute = resource_offset + directory_offset
        if absolute + 16 > len(data):
            return
        named_count = read_u16(data, absolute + 12)
        id_count = read_u16(data, absolute + 14)
        entry_count = named_count + id_count

        for index in range(entry_count):
            entry_offset = absolute + 16 + index * 8
            if entry_offset + 8 > len(data):
                return

            name = resource_name(read_u32(data, entry_offset))
            value = read_u32(data, entry_offset + 4)
            if value & 0x80000000:
                walk(value & 0x7FFFFFFF, [*levels, name])
                continue

            data_entry_offset = resource_offset + value
            if data_entry_offset + 16 > len(data):
                continue
            data_rva = read_u32(data, data_entry_offset)
            size = read_u32(data, data_entry_offset + 4)
            payload_offset = rva_to_offset(data_rva)
            if payload_offset is None or payload_offset + size > len(data):
                continue

            resource_type = levels[0] if levels else name
            if not isinstance(resource_type, int):
                continue
            resource_id = levels[1] if len(levels) > 1 else name
            language = levels[2] if len(levels) > 2 else ""
            resources.setdefault(resource_type, []).append(
                {
                    "id": resource_id,
                    "language": language,
                    "payload": data[payload_offset : payload_offset + size],
                    "size": size,
                }
            )

    walk(0, [])
    return resources


def icon_member_to_ico(width: int, height: int, color_count: int, planes: int, bit_count: int, payload: bytes) -> bytes:
    header_size = 6 + 16
    return b"".join(
        [
            struct.pack("<HHH", 0, 1, 1),
            struct.pack(
                "<BBBBHHII",
                0 if width >= 256 else width,
                0 if height >= 256 else height,
                color_count,
                0,
                planes,
                bit_count,
                len(payload),
                header_size,
            ),
            payload,
        ]
    )


def dib_to_bmp(payload: bytes) -> bytes:
    if len(payload) < 16:
        raise ValueError("DIB payload is too small")

    header_size = read_u32(payload, 0)
    if header_size == 12:
        bit_count = read_u16(payload, 10)
        colors_used = 0
        palette_entry_size = 3
    elif header_size >= 40 and len(payload) >= 36:
        bit_count = read_u16(payload, 14)
        colors_used = read_u32(payload, 32)
        palette_entry_size = 4
    else:
        raise ValueError("unsupported DIB header")

    palette_entries = colors_used
    if palette_entries == 0 and bit_count <= 8:
        palette_entries = 1 << bit_count

    pixel_offset = 14 + header_size + palette_entries * palette_entry_size
    file_size = 14 + len(payload)
    return b"".join(
        [
            b"BM",
            struct.pack("<IHHI", file_size, 0, 0, pixel_offset),
            payload,
        ]
    )


def export_rendered_image(
    image: Image.Image,
    output_path: Path,
    target: tuple[int, int],
    fit: str,
    resample: Image.Resampling,
    background: tuple[int, int, int],
) -> tuple[int, int]:
    image.load()
    rendered = make_fullhd(image, target, fit, resample, background)
    source_w, source_h = image.size
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rendered.save(output_path, "PNG", optimize=True)
    return source_w, source_h


def export_pe_resources(
    path: Path,
    output_dir: Path,
    target: tuple[int, int],
    fit: str,
    resample: Image.Resampling,
    background: tuple[int, int, int],
) -> list[dict[str, str]]:
    resources = parse_pe_resources(path)
    rows: list[dict[str, str]] = []
    if not resources:
        return rows

    pe_dir = output_dir / "PE" / safe_stem(path)
    icon_payloads = {resource["id"]: resource["payload"] for resource in resources.get(RT_ICON, [])}

    for group in resources.get(RT_GROUP_ICON, []):
        payload = group["payload"]
        if not isinstance(payload, bytes) or len(payload) < 6:
            continue
        reserved, icon_type, count = struct.unpack_from("<HHH", payload, 0)
        if reserved != 0 or icon_type != 1:
            continue

        for member_index in range(count):
            entry_offset = 6 + member_index * 14
            if entry_offset + 14 > len(payload):
                break
            width, height, color_count, _reserved, planes, bit_count, bytes_in_res, icon_id = struct.unpack_from(
                "<BBBBHHIH", payload, entry_offset
            )
            icon_payload = icon_payloads.get(icon_id)
            if not isinstance(icon_payload, bytes) or len(icon_payload) < bytes_in_res:
                continue

            ico = icon_member_to_ico(
                256 if width == 0 else width,
                256 if height == 0 else height,
                color_count,
                planes,
                bit_count,
                icon_payload,
            )
            try:
                with Image.open(io.BytesIO(ico)) as image:
                    stem = safe_stem(path)
                    output_path = (
                        pe_dir
                        / f"{stem}_group{group['id']}_member{member_index:02d}_icon{icon_id}_fullhd.png"
                    )
                    source_w, source_h = export_rendered_image(
                        image, output_path, target, fit, resample, background
                    )
            except Exception:
                continue

            rows.append(
                output_row(
                    "pe_icon",
                    path,
                    len(icon_payload),
                    source_w,
                    source_h,
                    target,
                    fit,
                    output_path,
                    index=f"group:{group['id']}/member:{member_index:02d}",
                    file_id=str(icon_id),
                )
            )

    for bitmap in resources.get(RT_BITMAP, []):
        payload = bitmap["payload"]
        if not isinstance(payload, bytes):
            continue
        try:
            with Image.open(io.BytesIO(dib_to_bmp(payload))) as image:
                stem = safe_stem(path)
                output_path = pe_dir / f"{stem}_bitmap{bitmap['id']}_fullhd.png"
                source_w, source_h = export_rendered_image(image, output_path, target, fit, resample, background)
        except Exception:
            continue

        rows.append(
            output_row(
                "pe_bitmap",
                path,
                len(payload),
                source_w,
                source_h,
                target,
                fit,
                output_path,
                index=f"bitmap:{bitmap['id']}",
                file_id=str(bitmap["id"]),
            )
        )

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract Lands of Lore II still images and upscale them to Full HD PNGs."
    )
    parser.add_argument("archives", nargs="*", type=Path)
    parser.add_argument("--direct-images", nargs="*", type=Path, default=[])
    parser.add_argument("--pe-resources", nargs="*", type=Path, default=[])
    parser.add_argument("-o", "--output", type=Path, default=Path("output/fullhd_images"))
    parser.add_argument("--width", type=int, default=TARGET_SIZE[0])
    parser.add_argument("--height", type=int, default=TARGET_SIZE[1])
    parser.add_argument("--fit", choices=("contain", "cover", "stretch"), default="contain")
    parser.add_argument("--background", type=parse_background, default=(0, 0, 0))
    parser.add_argument(
        "--filter",
        choices=("nearest", "bilinear", "bicubic", "lanczos"),
        default="lanczos",
        help="Resize filter used for the exported PNGs.",
    )
    args = parser.parse_args()

    if args.width < 1 or args.height < 1:
        raise SystemExit("width and height must be positive")
    if not args.archives and not args.direct_images and not args.pe_resources:
        raise SystemExit("provide at least one MIX archive, --direct-images path, or --pe-resources path")

    filters = {
        "nearest": Image.Resampling.NEAREST,
        "bilinear": Image.Resampling.BILINEAR,
        "bicubic": Image.Resampling.BICUBIC,
        "lanczos": Image.Resampling.LANCZOS,
    }

    args.output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    for archive in args.archives:
        rows.extend(
            export_archive(
                archive,
                args.output,
                (args.width, args.height),
                args.fit,
                filters[args.filter],
                args.background,
            )
        )
    for image_path in args.direct_images:
        rows.append(
            export_direct_image(
                image_path,
                args.output,
                (args.width, args.height),
                args.fit,
                filters[args.filter],
                args.background,
            )
        )
    for pe_path in args.pe_resources:
        rows.extend(
            export_pe_resources(
                pe_path,
                args.output,
                (args.width, args.height),
                args.fit,
                filters[args.filter],
                args.background,
            )
        )

    manifest = args.output / "manifest.csv"
    fieldnames = [
        "source_type",
        "source_path",
        "archive",
        "index",
        "file_id",
        "source_size",
        "source_width",
        "source_height",
        "output_width",
        "output_height",
        "fit",
        "output_path",
    ]
    with manifest.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    archive_count = len({row["archive"] for row in rows if row["archive"]})
    direct_count = sum(1 for row in rows if row["source_type"] == "direct_image")
    pe_bitmap_count = sum(1 for row in rows if row["source_type"] == "pe_bitmap")
    pe_icon_count = sum(1 for row in rows if row["source_type"] == "pe_icon")
    pcx_count = sum(1 for row in rows if row["source_type"] == "mix_pcx")
    print(f"Exported {pcx_count} PCX images from {archive_count} archives to {args.output}")
    print(f"Exported {direct_count} direct images to {args.output}")
    print(f"Exported {pe_icon_count} PE icons and {pe_bitmap_count} PE bitmaps to {args.output}")
    print(f"Manifest: {manifest}")


if __name__ == "__main__":
    main()
