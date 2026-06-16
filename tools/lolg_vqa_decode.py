#!/usr/bin/env python3
"""Start a frame-by-frame Lands of Lore II / Westwood VQA decoder."""

from __future__ import annotations

import argparse
import csv
import json
import struct
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image

TARGET_SIZE = (1920, 1080)


def be32(data: bytes, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def le16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def read_mix_entry(path: Path, index: int) -> bytes:
    data = path.read_bytes()
    if len(data) < 6:
        raise ValueError(f"{path}: too small to be a MIX archive")

    count, body_size = struct.unpack_from("<HI", data, 0)
    if index < 0 or index >= count:
        raise ValueError(f"{path}: entry index {index} outside 0..{count - 1}")

    table_end = 6 + count * 12
    file_id, offset, size = struct.unpack_from("<III", data, 6 + index * 12)
    if offset + size > body_size:
        raise ValueError(f"{path}: entry {index} exceeds declared MIX body size")

    payload = data[table_end + offset : table_end + offset + size]
    if not payload.startswith(b"FORM"):
        raise ValueError(f"{path}: entry {index} ({file_id:08x}) is not a FORM/VQA payload")
    return payload


@dataclass
class Chunk:
    offset: int
    chunk_id: str
    size: int
    payload: bytes


@dataclass
class VqaHeader:
    version: int
    flags: int
    frame_count: int
    width: int
    height: int
    block_width: int
    block_height: int
    frame_rate: int
    unknown_13: int
    colors: int
    max_codebook_entries: int
    unknown_18: int
    unknown_20: int
    sample_rate: int
    audio_flags: int
    unknown_26: int
    unknown_28: int
    unknown_30: int
    unknown_32: int
    max_cbfz_size: int
    unknown_36: int
    max_vptz_size: int
    unknown_40: int

    @property
    def blocks_x(self) -> int:
        return self.width // self.block_width

    @property
    def blocks_y(self) -> int:
        return self.height // self.block_height

    @property
    def block_count(self) -> int:
        return self.blocks_x * self.blocks_y


@dataclass
class CodebookUpdate:
    status: str
    codebook: bytes | None
    applied_vectors: int = 0
    ignored_bytes: int = 0
    note: str = ""


@dataclass
class PointerRenderStats:
    drawn_blocks: int = 0
    skipped_blocks: int = 0
    missing_blocks: int = 0
    explicit_skip_blocks: int = 0
    out_of_range_blocks: int = 0
    unique_indices: int = 0
    min_index: int | None = None
    max_index: int | None = None


def iter_chunks(data: bytes, start: int, end: int | None = None) -> list[Chunk]:
    chunks: list[Chunk] = []
    end = len(data) if end is None else end
    pos = start

    while pos + 8 <= end:
        raw_id = data[pos : pos + 4]
        chunk_id = raw_id.decode("ascii", errors="replace")
        size = be32(data, pos + 4)
        payload_start = pos + 8
        payload_end = payload_start + size
        if payload_end > end:
            break

        chunks.append(Chunk(pos, chunk_id, size, data[payload_start:payload_end]))
        pos = payload_end + (size & 1)

    return chunks


def parse_vqhd(payload: bytes) -> VqaHeader:
    if len(payload) != 42:
        raise ValueError(f"VQHD header should be 42 bytes, got {len(payload)}")

    return VqaHeader(
        version=le16(payload, 0),
        flags=le16(payload, 2),
        frame_count=le16(payload, 4),
        width=le16(payload, 6),
        height=le16(payload, 8),
        block_width=payload[10],
        block_height=payload[11],
        frame_rate=payload[12],
        unknown_13=payload[13],
        colors=le16(payload, 14),
        max_codebook_entries=le16(payload, 16),
        unknown_18=le16(payload, 18),
        unknown_20=le16(payload, 20),
        sample_rate=le16(payload, 22),
        audio_flags=le16(payload, 24),
        unknown_26=le16(payload, 26),
        unknown_28=le16(payload, 28),
        unknown_30=le16(payload, 30),
        unknown_32=le16(payload, 32),
        max_cbfz_size=le16(payload, 34),
        unknown_36=le16(payload, 36),
        max_vptz_size=le16(payload, 38),
        unknown_40=le16(payload, 40),
    )


def lcw_copy(
    output: bytearray,
    start: int,
    count: int,
    expected_size: int | None = None,
    allow_signed_source: bool = False,
) -> None:
    if start < 0 or start >= len(output):
        if allow_signed_source and start >= 0x8000:
            signed_start = len(output) + start - 0x10000
            if 0 <= signed_start < len(output):
                start = signed_start
        if start < 0 or start >= len(output):
            raise ValueError(f"invalid LCW copy start {start} for output length {len(output)}")

    for _ in range(count):
        if expected_size is not None and len(output) >= expected_size:
            return
        output.append(output[start])
        start += 1


def lcw_literal(output: bytearray, payload: bytes, expected_size: int | None) -> None:
    if expected_size is None:
        output.extend(payload)
        return

    remaining = expected_size - len(output)
    if remaining > 0:
        output.extend(payload[:remaining])


def decode_lcw(
    payload: bytes,
    expected_size: int | None = None,
    allow_signed_source: bool = False,
) -> bytes:
    """Decode Westwood LCW/Format80 streams used by VQA *Z chunks.

    `expected_size` is used for chunks whose uncompressed size is known from
    the VQA header, notably `VPTZ`. Some game files use 16-bit absolute copy
    sources that are only valid when interpreted as signed offsets from the
    current output position; `allow_signed_source` enables that fallback only
    after the normal absolute source fails.
    """

    output = bytearray()
    pos = 0

    while pos < len(payload):
        if expected_size is not None and len(output) >= expected_size:
            break

        command = payload[pos]
        pos += 1

        if command == 0x80:
            break

        if command == 0xFF:
            if pos + 3 > len(payload):
                raise ValueError("truncated LCW fill command")
            count = payload[pos] | (payload[pos + 1] << 8)
            value = payload[pos + 2]
            pos += 3
            if expected_size is None:
                output.extend([value] * count)
            else:
                output.extend([value] * min(count, max(0, expected_size - len(output))))
            continue

        if command == 0xFE:
            if pos + 4 > len(payload):
                raise ValueError("truncated LCW long copy command")
            count = payload[pos] | (payload[pos + 1] << 8)
            source = payload[pos + 2] | (payload[pos + 3] << 8)
            pos += 4
            lcw_copy(output, source, count, expected_size, allow_signed_source)
            continue

        if (command & 0x80) == 0:
            if pos >= len(payload):
                raise ValueError("truncated LCW short relative copy command")
            count = ((command & 0x70) >> 4) + 3
            relative = ((command & 0x0F) << 8) | payload[pos]
            pos += 1
            lcw_copy(output, len(output) - relative, count, expected_size)
            continue

        if (command & 0x40) == 0:
            count = command & 0x3F
            if pos + count > len(payload):
                raise ValueError("truncated LCW literal command")
            lcw_literal(output, payload[pos : pos + count], expected_size)
            pos += count
            continue

        if pos + 2 > len(payload):
            raise ValueError("truncated LCW absolute copy command")
        count = (command & 0x3F) + 3
        source = payload[pos] | (payload[pos + 1] << 8)
        pos += 2
        lcw_copy(output, source, count, expected_size, allow_signed_source)

    return bytes(output)


def decode_lcw_legacy(payload: bytes) -> bytes:
    """Decode LCW streams with the original strict behavior."""

    output = bytearray()
    pos = 0

    while pos < len(payload):
        command = payload[pos]
        pos += 1

        if command == 0x80:
            break

        if command == 0xFF:
            if pos + 3 > len(payload):
                raise ValueError("truncated LCW fill command")
            count = payload[pos] | (payload[pos + 1] << 8)
            value = payload[pos + 2]
            pos += 3
            output.extend([value] * count)
            continue

        if command == 0xFE:
            if pos + 4 > len(payload):
                raise ValueError("truncated LCW long copy command")
            count = payload[pos] | (payload[pos + 1] << 8)
            source = payload[pos + 2] | (payload[pos + 3] << 8)
            pos += 4
            lcw_copy(output, source, count)
            continue

        if (command & 0x80) == 0:
            if pos >= len(payload):
                raise ValueError("truncated LCW short relative copy command")
            count = ((command & 0x70) >> 4) + 3
            relative = ((command & 0x0F) << 8) | payload[pos]
            pos += 1
            lcw_copy(output, len(output) - relative, count)
            continue

        if (command & 0x40) == 0:
            count = command & 0x3F
            if pos + count > len(payload):
                raise ValueError("truncated LCW literal command")
            output.extend(payload[pos : pos + count])
            pos += count
            continue

        if pos + 2 > len(payload):
            raise ValueError("truncated LCW absolute copy command")
        count = (command & 0x3F) + 3
        source = payload[pos] | (payload[pos + 1] << 8)
        pos += 2
        lcw_copy(output, source, count)

    return bytes(output)


def decode_lcw_inplace(
    payload: bytes,
    seed: bytes,
    expected_size: int,
    allow_signed_source: bool = False,
) -> bytes:
    """Decode an LCW delta stream into a pre-seeded destination buffer."""

    output = bytearray(seed[:expected_size])
    if len(output) < expected_size:
        output.extend([0] * (expected_size - len(output)))

    write_pos = 0
    pos = 0

    def write_byte(value: int) -> None:
        nonlocal write_pos
        if write_pos < expected_size:
            output[write_pos] = value
            write_pos += 1

    def copy_from(source: int, count: int) -> None:
        nonlocal write_pos
        if source < 0 or source >= expected_size:
            if allow_signed_source and source >= 0x8000:
                signed_source = write_pos + source - 0x10000
                if 0 <= signed_source < expected_size:
                    source = signed_source
        if source < 0 or source >= expected_size:
            raise ValueError(f"invalid LCW delta copy start {source} for output length {expected_size}")

        for _ in range(count):
            if write_pos >= expected_size:
                return
            output[write_pos] = output[source]
            write_pos += 1
            source += 1
            if source >= expected_size and write_pos < expected_size:
                raise ValueError(f"invalid LCW delta copy overrun {source} for output length {expected_size}")

    while pos < len(payload) and write_pos < expected_size:
        command = payload[pos]
        pos += 1

        if command == 0x80:
            break

        if command == 0xFF:
            if pos + 3 > len(payload):
                raise ValueError("truncated LCW fill command")
            count = payload[pos] | (payload[pos + 1] << 8)
            value = payload[pos + 2]
            pos += 3
            for _ in range(count):
                write_byte(value)
            continue

        if command == 0xFE:
            if pos + 4 > len(payload):
                raise ValueError("truncated LCW long copy command")
            count = payload[pos] | (payload[pos + 1] << 8)
            source = payload[pos + 2] | (payload[pos + 3] << 8)
            pos += 4
            copy_from(source, count)
            continue

        if (command & 0x80) == 0:
            if pos >= len(payload):
                raise ValueError("truncated LCW short relative copy command")
            count = ((command & 0x70) >> 4) + 3
            relative = ((command & 0x0F) << 8) | payload[pos]
            pos += 1
            copy_from(write_pos - relative, count)
            continue

        if (command & 0x40) == 0:
            count = command & 0x3F
            available = min(count, len(payload) - pos)
            for value in payload[pos : pos + available]:
                write_byte(value)
            pos += available
            continue

        if pos + 2 > len(payload):
            raise ValueError("truncated LCW absolute copy command")
        count = (command & 0x3F) + 3
        source = payload[pos] | (payload[pos + 1] << 8)
        pos += 2
        copy_from(source, count)

    return bytes(output)


def decode_lcw_windowed_pointer(
    payload: bytes,
    expected_size: int,
    base_address: int = 0x8200,
) -> tuple[bytes, str]:
    """Decode pointer LCW streams that address a 64K output window.

    Some compact `VPTZ` streams reference absolute sources around 0x8200 after
    writing only one byte. This experimental decoder treats output writes as a
    64K circular address space and accepts short tail forms seen in the game
    data. It is intentionally opt-in from the CLI.
    """

    memory = bytearray(65536)
    output = bytearray()
    pos = 0

    def write_byte(value: int) -> None:
        if len(output) >= expected_size:
            return
        memory[(base_address + len(output)) & 0xFFFF] = value
        output.append(value)

    def copy_from(source: int, count: int) -> None:
        for _ in range(count):
            if len(output) >= expected_size:
                return
            write_byte(memory[source & 0xFFFF])
            source = (source + 1) & 0xFFFF

    while pos < len(payload) and len(output) < expected_size:
        command = payload[pos]
        pos += 1

        if command == 0x80:
            return bytes(output), "lcw_window_end" if len(output) < expected_size else "lcw_window"

        if command == 0xFF:
            if pos < len(payload) and payload[pos] == 0x80 and pos + 1 == len(payload):
                return bytes(output), "lcw_window_ff80"
            if pos + 3 > len(payload):
                raise ValueError("truncated LCW fill command")
            count = payload[pos] | (payload[pos + 1] << 8)
            value = payload[pos + 2]
            pos += 3
            for _ in range(count):
                write_byte(value)
            continue

        if command == 0xFE:
            if pos + 4 > len(payload):
                raise ValueError("truncated LCW long copy command")
            count = payload[pos] | (payload[pos + 1] << 8)
            source = payload[pos + 2] | (payload[pos + 3] << 8)
            pos += 4
            copy_from(source, count)
            continue

        if (command & 0x80) == 0:
            if pos >= len(payload):
                raise ValueError("truncated LCW short relative copy command")
            count = ((command & 0x70) >> 4) + 3
            relative = ((command & 0x0F) << 8) | payload[pos]
            pos += 1
            copy_from((base_address + len(output) - relative) & 0xFFFF, count)
            continue

        if (command & 0x40) == 0:
            count = command & 0x3F
            available = min(count, len(payload) - pos)
            if available < count:
                for value in payload[pos : pos + available]:
                    write_byte(value)
                return bytes(output), "lcw_window_literal_tail"
            for value in payload[pos : pos + count]:
                write_byte(value)
            pos += count
            continue

        if pos + 2 > len(payload):
            return bytes(output), "lcw_window_abs_tail"
        count = (command & 0x3F) + 3
        source = payload[pos] | (payload[pos + 1] << 8)
        pos += 2
        copy_from(source, count)

    if len(output) >= expected_size:
        return bytes(output), "lcw_window"
    return bytes(output), "lcw_window_eof"


def parse_vqa(data: bytes) -> tuple[VqaHeader, list[Chunk]]:
    if len(data) < 12 or data[:4] != b"FORM" or data[8:12] != b"WVQA":
        raise ValueError("not a FORM/WVQA file")

    chunks = iter_chunks(data, 12, min(len(data), 8 + be32(data, 4)))
    header_chunk = next((chunk for chunk in chunks if chunk.chunk_id == "VQHD"), None)
    if header_chunk is None:
        raise ValueError("missing VQHD header")
    return parse_vqhd(header_chunk.payload), chunks


def render_palette(payload: bytes, output_path: Path) -> None:
    if len(payload) < 768:
        return
    swatch = 16
    image = Image.new("RGB", (16 * swatch, 16 * swatch))
    for index in range(256):
        r, g, b = payload[index * 3 : index * 3 + 3]
        color = (r, g, b)
        x0 = (index % 16) * swatch
        y0 = (index // 16) * swatch
        for y in range(y0, y0 + swatch):
            for x in range(x0, x0 + swatch):
                image.putpixel((x, y), color)
    image.save(output_path)


def render_pointer_map(payload: bytes, header: VqaHeader, output_path: Path) -> None:
    if len(payload) < header.block_count * 2:
        return
    image = Image.new("L", (header.blocks_x, header.blocks_y))
    for block in range(header.block_count):
        value = payload[block * 2] | (payload[block * 2 + 1] << 8)
        image.putpixel((block % header.blocks_x, block // header.blocks_x), value & 0xFF)
    image = image.resize((header.width, header.height), Image.Resampling.NEAREST)
    image.save(output_path)


def render_codebook(payload: bytes, header: VqaHeader, palette: bytes | None, output_path: Path) -> None:
    vector_size = header.block_width * header.block_height
    if vector_size <= 0 or len(payload) < vector_size:
        return

    vector_count = len(payload) // vector_size
    columns = 32
    rows = (vector_count + columns - 1) // columns
    image = Image.new("P", (columns * header.block_width, rows * header.block_height))
    if palette and len(palette) >= 768:
        image.putpalette(list(palette[:768]))

    for vector in range(vector_count):
        source = vector * vector_size
        tile_x = (vector % columns) * header.block_width
        tile_y = (vector // columns) * header.block_height
        for y in range(header.block_height):
            for x in range(header.block_width):
                image.putpixel((tile_x + x, tile_y + y), payload[source + y * header.block_width + x])

    image.save(output_path)


def apply_cbp_update(active_codebook: bytes | None, update: bytes, header: VqaHeader) -> CodebookUpdate:
    """Append vector-aligned CBP data to the active codebook.

    Lands of Lore II's first-frame `CBP*` chunks often contain extra vector
    data after a full `CBF*` codebook. Later `CBPZ` frames still need more
    reverse-engineering, so this intentionally handles only the safe append
    case and reports how much data was ignored.
    """

    if active_codebook is None:
        return CodebookUpdate("no_base", None, note="CBP update has no active codebook")

    vector_size = header.block_width * header.block_height
    if vector_size <= 0:
        return CodebookUpdate("invalid_vector_size", active_codebook)

    vector_bytes = (len(update) // vector_size) * vector_size
    ignored_bytes = len(update) - vector_bytes
    update_vectors = vector_bytes // vector_size
    if update_vectors == 0:
        return CodebookUpdate("empty", active_codebook, ignored_bytes=ignored_bytes)

    base_vectors = len(active_codebook) // vector_size
    capacity_vectors = header.max_codebook_entries or (base_vectors + update_vectors)
    if base_vectors >= capacity_vectors:
        return CodebookUpdate(
            "no_room",
            active_codebook,
            ignored_bytes=len(update),
            note=f"CBP update skipped: active codebook already has {base_vectors} vectors",
        )

    room_vectors = capacity_vectors - base_vectors
    applied_vectors = min(update_vectors, room_vectors)
    applied_bytes = applied_vectors * vector_size
    codebook = active_codebook + update[:applied_bytes]

    ignored_total = ignored_bytes + (vector_bytes - applied_bytes)
    if applied_vectors < update_vectors:
        return CodebookUpdate(
            "applied_truncated",
            codebook,
            applied_vectors,
            ignored_total,
            f"CBP appended {applied_vectors}/{update_vectors} vectors up to header capacity",
        )

    if ignored_bytes:
        return CodebookUpdate(
            "applied_unaligned",
            codebook,
            applied_vectors,
            ignored_bytes,
            f"CBP appended {applied_vectors} vectors and ignored {ignored_bytes} trailing bytes",
        )

    return CodebookUpdate("applied", codebook, applied_vectors)


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
    source = image.convert("RGB")
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

    canvas = Image.new("RGB", target, background)
    canvas.paste(scaled, (left, top))
    return canvas


def save_png(image: Image.Image, path: Path, optimize: bool) -> None:
    save_args: dict[str, int | bool] = {"optimize": optimize}
    if not optimize:
        save_args["compress_level"] = 1
    image.save(path, "PNG", **save_args)


def save_frame_outputs(
    frame: Image.Image,
    output_dir: Path,
    frame_index: int,
    fullhd: bool,
    target: tuple[int, int],
    fit: str,
    resample: Image.Resampling,
    background: tuple[int, int, int],
    png_optimize: bool,
) -> tuple[str, str]:
    native_dir = output_dir / "frames_native"
    native_dir.mkdir(parents=True, exist_ok=True)
    native_path = native_dir / f"frame_{frame_index:04d}.png"
    save_png(frame, native_path, png_optimize)

    fullhd_output = ""
    if fullhd:
        fullhd_dir = output_dir / "frames_fullhd"
        fullhd_dir.mkdir(parents=True, exist_ok=True)
        fullhd_path = fullhd_dir / f"frame_{frame_index:04d}_fullhd.png"
        fullhd_image = make_fullhd(frame, target, fit, resample, background)
        save_png(fullhd_image, fullhd_path, png_optimize)
        fullhd_output = str(fullhd_path)

    return str(native_path), fullhd_output


def nearest_palette_index(palette: bytes, color: tuple[int, int, int]) -> int:
    if len(palette) < 3:
        return 0

    best_index = 0
    best_distance: int | None = None
    limit = min(256, len(palette) // 3)
    target_r, target_g, target_b = color

    for index in range(limit):
        r, g, b = palette[index * 3 : index * 3 + 3]
        distance = (r - target_r) ** 2 + (g - target_g) ** 2 + (b - target_b) ** 2
        if best_distance is None or distance < best_distance:
            best_index = index
            best_distance = distance

    return best_index


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


def render_vpt_frame(
    frame: Image.Image,
    vpt_payload: bytes,
    codebook: bytes,
    header: VqaHeader,
    transparent_index: int | None,
) -> PointerRenderStats:
    vector_size = header.block_width * header.block_height
    if vector_size <= 0:
        return PointerRenderStats(missing_blocks=header.block_count)

    vector_count = len(codebook) // vector_size
    block_limit = min(header.block_count, len(vpt_payload) // 2)
    pixels = frame.load()
    drawn = 0
    skipped = 0
    out_of_range = 0
    indices: set[int] = set()
    min_index: int | None = None
    max_index: int | None = None

    for block in range(block_limit):
        value = vpt_payload[block * 2] | (vpt_payload[block * 2 + 1] << 8)
        if value >= vector_count:
            skipped += 1
            out_of_range += 1
            continue

        indices.add(value)
        min_index = value if min_index is None else min(min_index, value)
        max_index = value if max_index is None else max(max_index, value)
        drawn += 1
        source = value * vector_size
        target_x = (block % header.blocks_x) * header.block_width
        target_y = (block // header.blocks_x) * header.block_height

        for y in range(header.block_height):
            row = source + y * header.block_width
            for x in range(header.block_width):
                pixel = codebook[row + x]
                if transparent_index is not None and pixel == transparent_index:
                    continue
                pixels[target_x + x, target_y + y] = pixel

    missing = header.block_count - block_limit
    return PointerRenderStats(
        drawn_blocks=drawn,
        skipped_blocks=skipped,
        missing_blocks=missing,
        out_of_range_blocks=out_of_range,
        unique_indices=len(indices),
        min_index=min_index,
        max_index=max_index,
    )


def expand_vpr_pointers(payload: bytes, header: VqaHeader) -> list[int | None]:
    pointers: list[int | None] = []
    for offset in range(0, len(payload) - 1, 2):
        word = payload[offset] | (payload[offset + 1] << 8)
        if (word & 0xFF00) == 0xA000:
            pointers.extend([None] * (word & 0xFF))
        elif word == 0x8000:
            pointers.append(None)
        else:
            pointers.append(word & 0x0FFF)

        if len(pointers) >= header.block_count:
            return pointers[: header.block_count]

    return pointers


def render_vpr_frame(
    frame: Image.Image,
    payload: bytes,
    codebook: bytes,
    header: VqaHeader,
    transparent_index: int | None,
) -> PointerRenderStats:
    vector_size = header.block_width * header.block_height
    if vector_size <= 0:
        return PointerRenderStats(missing_blocks=header.block_count)

    vector_count = len(codebook) // vector_size
    pointers = expand_vpr_pointers(payload, header)
    pixels = frame.load()
    drawn = 0
    skipped = 0
    explicit_skip = 0
    out_of_range = 0
    indices: set[int] = set()
    min_index: int | None = None
    max_index: int | None = None

    for block, value in enumerate(pointers):
        if value is None:
            skipped += 1
            explicit_skip += 1
            continue

        if value >= vector_count:
            skipped += 1
            out_of_range += 1
            continue

        indices.add(value)
        min_index = value if min_index is None else min(min_index, value)
        max_index = value if max_index is None else max(max_index, value)
        drawn += 1
        source = value * vector_size
        target_x = (block % header.blocks_x) * header.block_width
        target_y = (block // header.blocks_x) * header.block_height

        for y in range(header.block_height):
            row = source + y * header.block_width
            for x in range(header.block_width):
                pixel = codebook[row + x]
                if transparent_index is not None and pixel == transparent_index:
                    continue
                pixels[target_x + x, target_y + y] = pixel

    missing = header.block_count - len(pointers)
    return PointerRenderStats(
        drawn_blocks=drawn,
        skipped_blocks=skipped,
        missing_blocks=missing,
        explicit_skip_blocks=explicit_skip,
        out_of_range_blocks=out_of_range,
        unique_indices=len(indices),
        min_index=min_index,
        max_index=max_index,
    )


def write_render_manifest(output_dir: Path, rows: list[dict[str, str]]) -> None:
    with (output_dir / "rendered_frames.csv").open("w", newline="") as handle:
        fieldnames = [
            "frame",
            "status",
            "width",
            "height",
            "codebook_vectors",
            "pointer_decode_chunk",
            "pointer_decode_status",
            "pointer_decode_source_size",
            "pointer_decode_expected_size",
            "pointer_decode_size",
            "pointer_decode_prefix",
            "pointer_decode_error",
            "pointer_chunk",
            "drawn_blocks",
            "skipped_blocks",
            "missing_blocks",
            "pointer_unique_indices",
            "pointer_min_index",
            "pointer_max_index",
            "pointer_explicit_skip_blocks",
            "pointer_out_of_range_blocks",
            "cbp_decode_status",
            "cbp_decoded_bytes",
            "cbp_decoded_vectors",
            "cbp_trailing_bytes",
            "cbp_decode_error",
            "partial_codebook_update",
            "codebook_update_vectors",
            "codebook_update_ignored_bytes",
            "native_output",
            "fullhd_output",
            "note",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def decode_frames(
    data: bytes,
    output_dir: Path,
    max_frames: int | None,
    dump_payloads: bool,
    render_frames: bool,
    fullhd: bool,
    target: tuple[int, int],
    fit: str,
    resample: Image.Resampling,
    background: tuple[int, int, int],
    experimental_window_lcw: bool,
    transparent_index: int | None,
    png_optimize: bool,
) -> None:
    header, chunks = parse_vqa(data)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "header.json").write_text(json.dumps(asdict(header), indent=2), encoding="utf-8")

    rows: list[dict[str, str]] = []
    render_rows: list[dict[str, str]] = []
    palette: bytes | None = None
    active_codebook: bytes | None = None
    previous_pointer: bytes | None = None
    rendered_frame: Image.Image | None = None
    frame_index = 0

    for chunk in chunks:
        if chunk.chunk_id == "CPL0":
            palette = chunk.payload

        if chunk.chunk_id != "VQFR":
            continue
        if max_frames is not None and frame_index >= max_frames:
            break

        frame_dir = output_dir / f"frame_{frame_index:04d}"
        frame_dir.mkdir(parents=True, exist_ok=True)
        frame_palette = palette
        decoded_subchunks: list[tuple[Chunk, bytes, str, str]] = []

        for subchunk in iter_chunks(chunk.payload, 0):
            decoded = subchunk.payload
            status = "stored"
            error = ""

            if subchunk.chunk_id.endswith("Z"):
                try:
                    expected_size = None
                    if subchunk.chunk_id in {"VPTZ", "VPT0"}:
                        expected_size = header.block_count * 2
                    elif subchunk.chunk_id in {"CBFZ", "CBF0"}:
                        expected_size = header.max_codebook_entries * header.block_width * header.block_height
                    is_pointer = subchunk.chunk_id in {"VPTZ", "VPT0"}
                    try:
                        decoded = decode_lcw(
                            subchunk.payload,
                            expected_size=expected_size,
                            allow_signed_source=is_pointer,
                        )
                        status = "lcw"
                    except Exception:
                        if subchunk.chunk_id in {"CBPZ", "CBP0"}:
                            vector_size = header.block_width * header.block_height
                            partial_size = (subchunk.size // vector_size) * vector_size
                            if partial_size <= 0:
                                raise
                            try:
                                decoded = decode_lcw(subchunk.payload, expected_size=partial_size)
                                status = "lcw_partial"
                            except Exception:
                                if not experimental_window_lcw:
                                    raise
                                decoded, status = decode_lcw_windowed_pointer(
                                    subchunk.payload,
                                    max(1, subchunk.size * 2),
                                )
                        elif experimental_window_lcw and subchunk.chunk_id in {"VPTZ", "VPT0"} and expected_size is not None:
                            decoded, status = decode_lcw_windowed_pointer(
                                subchunk.payload,
                                expected_size,
                            )
                        elif experimental_window_lcw and subchunk.chunk_id == "VPRZ":
                            decoded, status = decode_lcw_windowed_pointer(
                                subchunk.payload,
                                max(1, subchunk.size * 2),
                            )
                        elif not is_pointer or previous_pointer is None or expected_size is None:
                            raise
                        else:
                            decoded = decode_lcw_inplace(
                                subchunk.payload,
                                previous_pointer,
                                expected_size,
                                allow_signed_source=True,
                            )
                            status = "lcw_delta"
                except Exception as exc:
                    status = "lcw_error"
                    error = str(exc)

            if subchunk.chunk_id == "CPL0":
                frame_palette = decoded
                palette = decoded

            if status != "lcw_error" and subchunk.chunk_id in {"VPTZ", "VPT0"}:
                previous_pointer = decoded

            decoded_subchunks.append((subchunk, decoded, status, error))

        for subchunk, decoded, status, error in decoded_subchunks:
            if subchunk.chunk_id == "CPL0" and status != "lcw_error":
                render_palette(decoded, frame_dir / "palette.png")

            if dump_payloads:
                suffix = "bin" if status != "lcw_error" else "failed.bin"
                (frame_dir / f"{subchunk.chunk_id}.{suffix}").write_bytes(decoded)

            if status != "lcw_error" and subchunk.chunk_id in {"CBFZ", "CBPZ", "CBF0", "CBP0"}:
                render_codebook(decoded, header, frame_palette, frame_dir / f"{subchunk.chunk_id}_codebook.png")

            if status != "lcw_error" and subchunk.chunk_id in {"VPTZ", "VPT0"}:
                render_pointer_map(decoded, header, frame_dir / f"{subchunk.chunk_id}_pointer_map.png")

            rows.append(
                {
                    "frame": str(frame_index),
                    "chunk": subchunk.chunk_id,
                    "source_size": str(subchunk.size),
                    "decoded_size": str(len(decoded)),
                    "status": status,
                    "error": error,
                }
            )

        if render_frames:
            pointer_candidates = [
                (subchunk, decoded, status, error)
                for subchunk, decoded, status, error in decoded_subchunks
                if subchunk.chunk_id in {"VPTZ", "VPT0", "VPRZ", "VPTR"}
            ]
            pointer_chunk = next(
                (
                    (subchunk, decoded, status)
                    for subchunk, decoded, status, _error in pointer_candidates
                    if status != "lcw_error"
                ),
                None,
            )
            pointer_decode_chunk = ""
            pointer_decode_status = ""
            pointer_decode_source_size = ""
            pointer_decode_expected_size = ""
            pointer_decode_size = ""
            pointer_decode_prefix = ""
            pointer_decode_error = ""
            if pointer_candidates:
                pointer_subchunk, pointer_decoded, pointer_status, pointer_error = pointer_candidates[0]
                pointer_decode_chunk = pointer_subchunk.chunk_id
                pointer_decode_status = pointer_status
                pointer_decode_source_size = str(pointer_subchunk.size)
                if pointer_subchunk.chunk_id in {"VPTZ", "VPT0"}:
                    pointer_decode_expected_size = str(header.block_count * 2)
                elif pointer_subchunk.chunk_id == "VPRZ" and pointer_status.startswith("lcw_window"):
                    pointer_decode_expected_size = str(max(1, pointer_subchunk.size * 2))
                pointer_decode_size = str(len(pointer_decoded)) if pointer_status != "lcw_error" else ""
                pointer_decode_prefix = pointer_subchunk.payload[:8].hex()
                pointer_decode_error = pointer_error

            partial_updates = [
                (subchunk, decoded, status, error)
                for subchunk, decoded, status, error in decoded_subchunks
                if subchunk.chunk_id in {"CBPZ", "CBP0"}
            ]
            partial_update_status = "no"
            vector_size = header.block_width * header.block_height
            cbp_decode_status = "+".join(
                dict.fromkeys(status for _subchunk, _decoded, status, _error in partial_updates)
            )
            cbp_decoded_payloads = [
                decoded
                for _subchunk, decoded, status, _error in partial_updates
                if status != "lcw_error"
            ]
            cbp_decoded_bytes = sum(len(decoded) for decoded in cbp_decoded_payloads)
            if vector_size > 0:
                cbp_decoded_vectors = sum(len(decoded) // vector_size for decoded in cbp_decoded_payloads)
                cbp_trailing_bytes = sum(len(decoded) % vector_size for decoded in cbp_decoded_payloads)
            else:
                cbp_decoded_vectors = 0
                cbp_trailing_bytes = cbp_decoded_bytes
            partial_errors = [
                error
                for _subchunk, _decoded, status, error in partial_updates
                if status == "lcw_error" and error
            ]
            cbp_decode_error = " | ".join(dict.fromkeys(partial_errors))
            cbp_results: list[CodebookUpdate] = []
            cbp_window_decode = any(
                status.startswith("lcw_window")
                for _subchunk, _decoded, status, _error in partial_updates
            )

            for subchunk, decoded, status, _error in decoded_subchunks:
                if status != "lcw_error" and subchunk.chunk_id in {"CBFZ", "CBF0"}:
                    active_codebook = decoded
                elif status != "lcw_error" and subchunk.chunk_id in {"CBPZ", "CBP0"}:
                    result = apply_cbp_update(active_codebook, decoded, header)
                    if result.codebook is not None:
                        active_codebook = result.codebook
                    cbp_results.append(result)

            if partial_errors:
                partial_update_status = "decode_error"
            elif cbp_results:
                applied_results = [result for result in cbp_results if result.applied_vectors > 0]
                if applied_results and any(result.status == "applied_truncated" for result in applied_results):
                    partial_update_status = "applied_truncated"
                elif applied_results and any(result.status == "applied_unaligned" for result in applied_results):
                    partial_update_status = "applied_unaligned"
                elif applied_results:
                    partial_update_status = "applied"
                else:
                    partial_update_status = "+".join(dict.fromkeys(result.status for result in cbp_results))

            cbp_update_vectors = sum(result.applied_vectors for result in cbp_results)
            cbp_ignored_bytes = sum(result.ignored_bytes for result in cbp_results)
            partial_notes: list[str] = []
            if partial_errors:
                partial_notes.append(f"CBP partial codebook update failed: {partial_errors[0]}")
            if cbp_window_decode:
                partial_notes.append("CBP windowed LCW decode is experimental")
            partial_notes.extend(result.note for result in cbp_results if result.note)
            partial_note = "; ".join(partial_notes)

            status = "not_rendered"
            note = partial_note
            pointer_stats = PointerRenderStats()
            native_output = ""
            fullhd_output = ""
            codebook_vectors = 0
            pointer_name = ""
            if active_codebook is not None:
                codebook_vectors = len(active_codebook) // (header.block_width * header.block_height)

            if frame_palette and rendered_frame is None:
                rendered_frame = Image.new(
                    "P",
                    (header.width, header.height),
                    color=nearest_palette_index(frame_palette, background),
                )
                rendered_frame.putpalette(list(frame_palette[:768]))
            elif frame_palette and rendered_frame is not None:
                rendered_frame.putpalette(list(frame_palette[:768]))

            if active_codebook is None:
                status = "no_codebook"
            elif frame_palette is None or len(frame_palette) < 768:
                status = "no_palette"
            elif pointer_chunk is None:
                status = "held_frame"
                note = "; ".join(
                    item
                    for item in (note, "No pointer chunk; saved current frame buffer")
                    if item
                )
                if rendered_frame is not None:
                    native_output, fullhd_output = save_frame_outputs(
                        rendered_frame,
                        output_dir,
                        frame_index,
                        fullhd,
                        target,
                        fit,
                        resample,
                        background,
                        png_optimize,
                    )
                else:
                    status = "no_frame_buffer"
            elif rendered_frame is None:
                status = "no_frame_buffer"
            else:
                pointer_subchunk, pointer_payload, pointer_status = pointer_chunk
                pointer_name = pointer_subchunk.chunk_id
                if pointer_name in {"VPRZ", "VPTR"}:
                    pointer_stats = render_vpr_frame(
                        rendered_frame,
                        pointer_payload,
                        active_codebook,
                        header,
                        transparent_index,
                    )
                else:
                    pointer_stats = render_vpt_frame(
                        rendered_frame,
                        pointer_payload,
                        active_codebook,
                        header,
                        transparent_index,
                    )
                status = "rendered"
                if pointer_name in {"VPRZ", "VPTR"}:
                    note = "; ".join(
                        item
                        for item in (note, "VPR pointer expansion is experimental")
                        if item
                    )
                if pointer_status.startswith("lcw_window"):
                    note = "; ".join(
                        item
                        for item in (note, "Pointer windowed LCW decode is experimental")
                        if item
                    )
                if transparent_index is not None:
                    note = "; ".join(
                        item
                        for item in (note, f"Palette index {transparent_index} treated as transparent")
                        if item
                    )

                native_output, fullhd_output = save_frame_outputs(
                    rendered_frame,
                    output_dir,
                    frame_index,
                    fullhd,
                    target,
                    fit,
                    resample,
                    background,
                    png_optimize,
                )
            render_rows.append(
                {
                    "frame": str(frame_index),
                    "status": status,
                    "width": str(header.width),
                    "height": str(header.height),
                    "codebook_vectors": str(codebook_vectors),
                    "pointer_decode_chunk": pointer_decode_chunk,
                    "pointer_decode_status": pointer_decode_status,
                    "pointer_decode_source_size": pointer_decode_source_size,
                    "pointer_decode_expected_size": pointer_decode_expected_size,
                    "pointer_decode_size": pointer_decode_size,
                    "pointer_decode_prefix": pointer_decode_prefix,
                    "pointer_decode_error": pointer_decode_error,
                    "pointer_chunk": pointer_name,
                    "drawn_blocks": str(pointer_stats.drawn_blocks),
                    "skipped_blocks": str(pointer_stats.skipped_blocks),
                    "missing_blocks": str(pointer_stats.missing_blocks),
                    "pointer_unique_indices": str(pointer_stats.unique_indices),
                    "pointer_min_index": "" if pointer_stats.min_index is None else str(pointer_stats.min_index),
                    "pointer_max_index": "" if pointer_stats.max_index is None else str(pointer_stats.max_index),
                    "pointer_explicit_skip_blocks": str(pointer_stats.explicit_skip_blocks),
                    "pointer_out_of_range_blocks": str(pointer_stats.out_of_range_blocks),
                    "cbp_decode_status": cbp_decode_status,
                    "cbp_decoded_bytes": str(cbp_decoded_bytes),
                    "cbp_decoded_vectors": str(cbp_decoded_vectors),
                    "cbp_trailing_bytes": str(cbp_trailing_bytes),
                    "cbp_decode_error": cbp_decode_error,
                    "partial_codebook_update": partial_update_status,
                    "codebook_update_vectors": str(cbp_update_vectors),
                    "codebook_update_ignored_bytes": str(cbp_ignored_bytes),
                    "native_output": native_output,
                    "fullhd_output": fullhd_output,
                    "note": note,
                }
            )

        frame_index += 1

    with (output_dir / "frames.csv").open("w", newline="") as handle:
        fieldnames = ["frame", "chunk", "source_size", "decoded_size", "status", "error"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    if render_frames:
        write_render_manifest(output_dir, render_rows)

    print(f"Decoded {frame_index} frames to {output_dir}")


def print_info(data: bytes) -> None:
    header, chunks = parse_vqa(data)
    print(json.dumps(asdict(header), indent=2))

    frame_index = 0
    for chunk in chunks:
        if chunk.chunk_id == "VQFR":
            subchunks = ", ".join(f"{sub.chunk_id}:{sub.size}" for sub in iter_chunks(chunk.payload, 0))
            print(f"frame {frame_index:04d}: offset=0x{chunk.offset:08x} size={chunk.size} {subchunks}")
            frame_index += 1
        else:
            print(f"chunk {chunk.chunk_id}: offset=0x{chunk.offset:08x} size={chunk.size}")


def load_input(path: Path, entry: int | None) -> bytes:
    if entry is not None:
        return read_mix_entry(path, entry)
    return path.read_bytes()


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse and partially decode Westwood VQA files frame by frame.")
    parser.add_argument("input", type=Path, help="A VQA/FORM file, or a MIX archive when --entry is used.")
    parser.add_argument("--entry", type=int, help="MIX entry index to decode as VQA.")
    parser.add_argument("-o", "--output", type=Path, default=Path("output/vqa_decode"))
    parser.add_argument("--max-frames", type=int)
    parser.add_argument("--dump-payloads", action="store_true")
    parser.add_argument("--render-frames", action="store_true", help="Render native paletted PNG frames from VPT chunks.")
    parser.add_argument("--fullhd", action="store_true", help="Also export rendered frames as Full HD PNG images.")
    parser.add_argument("--width", type=int, default=TARGET_SIZE[0])
    parser.add_argument("--height", type=int, default=TARGET_SIZE[1])
    parser.add_argument("--fit", choices=("contain", "cover", "stretch"), default="contain")
    parser.add_argument("--background", type=parse_background, default=(0, 0, 0))
    parser.add_argument(
        "--transparent-index",
        type=int,
        help="Palette index to treat as transparent while drawing codebook vectors.",
    )
    parser.add_argument(
        "--filter",
        choices=("nearest", "bilinear", "bicubic", "lanczos"),
        default="nearest",
        help="Resize filter used for --fullhd frame exports.",
    )
    parser.add_argument(
        "--fast-png",
        action="store_true",
        help="Disable PNG optimization for faster bulk frame exports.",
    )
    parser.add_argument("--info", action="store_true", help="Only print VQA structure information.")
    parser.add_argument(
        "--experimental-window-lcw",
        action="store_true",
        help="Try the experimental 64K-window LCW fallback for compact VPT chunks.",
    )
    args = parser.parse_args()

    if args.width < 1 or args.height < 1:
        raise SystemExit("width and height must be positive")
    if args.transparent_index is not None and not 0 <= args.transparent_index <= 255:
        raise SystemExit("--transparent-index must be between 0 and 255")

    data = load_input(args.input, args.entry)

    if args.info:
        print_info(data)
        return

    filters = {
        "nearest": Image.Resampling.NEAREST,
        "bilinear": Image.Resampling.BILINEAR,
        "bicubic": Image.Resampling.BICUBIC,
        "lanczos": Image.Resampling.LANCZOS,
    }

    decode_frames(
        data,
        args.output,
        args.max_frames,
        args.dump_payloads,
        args.render_frames or args.fullhd,
        args.fullhd,
        (args.width, args.height),
        args.fit,
        filters[args.filter],
        args.background,
        args.experimental_window_lcw,
        args.transparent_index,
        not args.fast_png,
    )


if __name__ == "__main__":
    main()
