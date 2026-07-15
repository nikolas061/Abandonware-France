#!/usr/bin/env python3
import argparse
import struct
from pathlib import Path

from PIL import Image

from westwood_codecs import lcw_decompress


def read_palette(path):
    data = path.read_bytes()
    if len(data) < 768:
        raise ValueError(f"{path} is too small for a 256-color palette")
    colors = []
    for i in range(256):
        r, g, b = data[i * 3 : i * 3 + 3]
        # Westwood palettes normally store 6-bit VGA values.
        if max(r, g, b) <= 63:
            r, g, b = r * 255 // 63, g * 255 // 63, b * 255 // 63
        colors.append((r, g, b, 255))
    colors[0] = (0, 0, 0, 0)
    return colors


def parse_offsets(data):
    if len(data) < 10:
        return None
    frame_count = struct.unpack_from("<H", data, 0)[0]
    if frame_count < 1 or frame_count > 4096:
        return None

    # Dune II v1.07 uses UINT32 offsets relative to the start of the offset array.
    table_end_32 = 2 + 4 * (frame_count + 1)
    if table_end_32 <= len(data):
        offsets = [
            struct.unpack_from("<I", data, 2 + i * 4)[0] + 2
            for i in range(frame_count + 1)
        ]
        if offsets[0] == table_end_32 and offsets[-1] <= len(data):
            return offsets

    # Older files use UINT16 absolute offsets. Keep this as a fallback.
    table_end_16 = 2 + 2 * (frame_count + 1)
    if table_end_16 <= len(data):
        offsets = [
            struct.unpack_from("<H", data, 2 + i * 2)[0]
            for i in range(frame_count + 1)
        ]
        if min(offsets) >= table_end_16 and max(offsets) <= len(data):
            return offsets

    return None


def decode_frame(chunk):
    if len(chunk) < 10:
        raise ValueError("frame is too small")

    flags = struct.unpack_from("<H", chunk, 0)[0]
    slices = chunk[2]
    width = struct.unpack_from("<H", chunk, 3)[0]
    height = chunk[5]
    declared_size = struct.unpack_from("<H", chunk, 6)[0]
    zero_compressed_size = struct.unpack_from("<H", chunk, 8)[0]

    if width == 0 or height == 0:
        raise ValueError("frame has zero dimensions")
    if declared_size and declared_size != len(chunk):
        # Not fatal, but it usually means this is not the simple LOLG SHP variant.
        pass
    if slices != height:
        raise ValueError(f"slice count {slices} != height {height}")

    has_remap = bool(flags & 0x01)
    no_lcw = bool(flags & 0x02)
    custom_remap_size = bool(flags & 0x04)

    cursor = 10
    remap = None
    if has_remap:
        remap_size = 16
        if custom_remap_size:
            remap_size = chunk[cursor]
            cursor += 1
        remap = chunk[cursor : cursor + remap_size]
        cursor += remap_size

    zero_stream = chunk[cursor:]
    if no_lcw:
        if zero_compressed_size and len(zero_stream) < zero_compressed_size:
            raise ValueError("truncated RLE-Zero stream")
        zero_stream = zero_stream[:zero_compressed_size]
    else:
        zero_stream = lcw_decompress(zero_stream, zero_compressed_size)

    pixels = [0] * (width * height)
    i = 0

    for row in range(height):
        pos = row * width
        row_end = pos + width
        while i < len(zero_stream) and pos < row_end:
            value = zero_stream[i]
            i += 1
            if value == 0 and i < len(zero_stream):
                pos = min(row_end, pos + zero_stream[i])
                i += 1
            else:
                if remap is not None and value < len(remap):
                    value = remap[value]
                pixels[pos] = value
                pos += 1

    return {
        "width": width,
        "height": height,
        "pixels": pixels,
        "filled": len(pixels),
    }


def image_from_frame(frame, palette, scale, resample):
    image = Image.new("RGBA", (frame["width"], frame["height"]))
    rgba = [palette[index] for index in frame["pixels"]]
    image.putdata(rgba)
    if scale > 1:
        image = image.resize(
            (image.width * scale, image.height * scale),
            Image.Resampling[resample.upper()],
        )
    return image


def export_shp(path, out_root, palette, scale, resample):
    data = path.read_bytes()
    offsets = parse_offsets(data)
    if not offsets:
        return 0, "unsupported offset table"

    exported = 0
    rel_out = out_root / path.parent.name / path.stem
    rel_out.mkdir(parents=True, exist_ok=True)

    sorted_offsets = sorted(set(offsets))
    endings = {}
    for pos, start in enumerate(sorted_offsets):
        endings[start] = sorted_offsets[pos + 1] if pos + 1 < len(sorted_offsets) else len(data)

    for index, start in enumerate(offsets[:-1]):
        end = endings.get(start)
        if not end or start >= end:
            print(f"skip {path} frame {index:03d}: invalid frame bounds")
            continue
        try:
            frame = decode_frame(data[start:end])
            image = image_from_frame(frame, palette, scale, resample)
        except Exception as exc:
            print(f"skip {path} frame {index:03d}: {exc}")
            continue
        image.save(rel_out / f"frame_{index:03d}.png")
        exported += 1
    return exported, None


def main():
    parser = argparse.ArgumentParser(description="Export simple LOLG SHP sprites to PNG.")
    parser.add_argument(
        "source",
        nargs="?",
        type=Path,
        default=Path("extracted"),
        help="directory containing extracted SHP files",
    )
    parser.add_argument(
        "-p",
        "--palette",
        type=Path,
        default=Path("extracted/LOCAL/7231c8f9.pal"),
        help="768-byte base palette",
    )
    parser.add_argument(
        "-o", "--out", type=Path, default=Path("hd_shp"), help="output directory"
    )
    parser.add_argument("-s", "--scale", type=int, default=4, help="integer scale")
    parser.add_argument(
        "-r",
        "--resample",
        choices=["nearest", "box", "bilinear", "bicubic", "lanczos"],
        default="nearest",
        help="sprite resampling filter",
    )
    args = parser.parse_args()

    palette = read_palette(args.palette)
    files = sorted(args.source.rglob("*.shp"))
    total = 0
    skipped = 0
    for path in files:
        count, reason = export_shp(path, args.out, palette, args.scale, args.resample)
        if reason:
            skipped += 1
            print(f"skip {path}: {reason}")
        elif count:
            total += count
            print(f"{path}: exported {count} frame(s)")
    print(f"exported {total} SHP frame(s), skipped {skipped} unsupported SHP file(s)")


if __name__ == "__main__":
    main()
