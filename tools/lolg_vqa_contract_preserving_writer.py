#!/usr/bin/env python3
"""Write a WVQA replacement while preserving the original frame chunk contract."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import struct
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lolg_vqa_decode as vqa  # noqa: E402
import lolg_vqa_fullhd_replacement_writer as writer  # noqa: E402
import lolg_vqa_native_exact_fixture_writer as native_exact  # noqa: E402
import lolg_vqa_runtime_compat_audit as compat_audit  # noqa: E402
from westwood_codecs import (  # noqa: E402
    lcw_compress,
    lcw_compress_extended,
    lcw_compress_literal,
    lcw_compress_vqa_extended,
    lcw_compress_windowed_pointer,
    lcw_decompress,
)


DEFAULT_OUTPUT = Path("output/vqa_contract_preserving_writer")
SUMMARY_FIELDS = [
    "status",
    "source_mix",
    "entry_index",
    "file_id",
    "native_exact_status",
    "source_dir",
    "output_payload",
    "output_mix",
    "decoded_dir",
    "width",
    "height",
    "frames",
    "validated_frames",
    "payload_bytes",
    "payload_sha256",
    "codebook_vectors",
    "base_codebook_vectors",
    "final_codebook_vectors",
    "cbpz_update_vectors",
    "global_unique_vectors",
    "exact_blocks",
    "fallback_blocks",
    "exact_block_ratio",
    "changed_pixels",
    "changed_pixel_ratio",
    "max_cbfz_size",
    "max_vptz_size",
    "frame_shapes",
    "runtime_compat_status",
    "runtime_compat_report",
    "issues",
    "next_step",
]
FRAME_FIELDS = [
    "frame",
    "source_png",
    "decoded_png",
    "shape",
    "exact_blocks",
    "fallback_blocks",
    "changed_pixels",
    "pointer_lcw_size",
    "cbpz_update_vectors",
    "cbpz_lcw_size",
    "active_codebook_vectors",
    "validated",
    "issues",
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        csv_writer = csv.DictWriter(handle, fieldnames=fieldnames)
        csv_writer.writeheader()
        csv_writer.writerows(rows)


def read_mix(path: Path) -> tuple[bytes, list[tuple[int, int, int]], int]:
    data = path.read_bytes()
    if len(data) < 6:
        raise ValueError(f"{path}: too small to be MIX")
    count, body_size = struct.unpack_from("<HI", data, 0)
    table_end = 6 + count * 12
    if table_end + body_size > len(data):
        raise ValueError(f"{path}: MIX body exceeds file size")
    entries: list[tuple[int, int, int]] = []
    for index in range(count):
        file_id, offset, size = struct.unpack_from("<III", data, 6 + index * 12)
        if offset + size > body_size:
            raise ValueError(f"{path}: entry {index} exceeds MIX body")
        entries.append((file_id, offset, size))
    return data, entries, table_end


def entry_payload(data: bytes, table_end: int, entry: tuple[int, int, int]) -> bytes:
    _file_id, offset, size = entry
    return data[table_end + offset : table_end + offset + size]


def write_mix_with_payload(source_mix: Path, output_mix: Path, entry_index: int, payload: bytes) -> None:
    source_data, entries, table_end = read_mix(source_mix)
    payloads: dict[int, bytes] = {}
    for index, entry in enumerate(entries):
        payloads[index] = payload if index == entry_index else entry_payload(source_data, table_end, entry)

    physical_order = sorted(range(len(entries)), key=lambda index: entries[index][1])
    offsets: dict[int, int] = {}
    cursor = 0
    body_parts: list[bytes] = []
    for index in physical_order:
        offsets[index] = cursor
        body_parts.append(payloads[index])
        cursor += len(payloads[index])

    table = bytearray(struct.pack("<HI", len(entries), cursor))
    for index, entry in enumerate(entries):
        file_id, _offset, _size = entry
        table.extend(struct.pack("<III", file_id, offsets[index], len(payloads[index])))

    output_mix.parent.mkdir(parents=True, exist_ok=True)
    output_mix.write_bytes(bytes(table) + b"".join(body_parts))


def frame_paths(source_dir: Path, prefer_native: bool = False) -> list[Path]:
    if prefer_native:
        frames = sorted((source_dir / "frames_native").glob("frame_*.png"))
        if frames:
            return frames
    frames = sorted((source_dir / "frames_fullhd").glob("frame_*_fullhd.png"))
    if frames:
        return frames
    return sorted((source_dir / "frames_native").glob("frame_*.png"))


def palette_bytes(source_dir: Path) -> bytes:
    native = sorted((source_dir / "frames_native").glob("frame_*.png"))
    candidates = native or frame_paths(source_dir)
    if not candidates:
        raise ValueError(f"{source_dir}: no palette source frames")
    with Image.open(candidates[0]) as image:
        palette = image.convert("P").getpalette() or []
    if len(palette) < 768:
        palette.extend([0] * (768 - len(palette)))
    return bytes(palette[:768])


def image_to_indexed(path: Path, palette: bytes, target: tuple[int, int]) -> bytes:
    old_target = writer.TARGET_SIZE
    try:
        writer.TARGET_SIZE = target
        return writer.index_fullhd_image(path, palette)
    finally:
        writer.TARGET_SIZE = old_target


def frame_blocks(path: Path, palette: bytes, header: vqa.VqaHeader, target: tuple[int, int]) -> list[bytes]:
    indexed = image_to_indexed(path, palette, target)
    return writer.iter_blocks(indexed, target[0], target[1], header.block_width, header.block_height)


def build_global_codebook(
    frames: list[Path],
    palette: bytes,
    header: vqa.VqaHeader,
    target: tuple[int, int],
    progress_every: int,
    max_vectors: int | None = None,
) -> tuple[list[bytes], int]:
    vector_size = header.block_width * header.block_height
    max_entries = header.max_codebook_entries if max_vectors is None else min(header.max_codebook_entries, max_vectors)
    counts: Counter[bytes] = Counter()

    for index, path in enumerate(frames):
        if progress_every and (index == 0 or (index + 1) % progress_every == 0 or index + 1 == len(frames)):
            print(f"Scanning vectors: frame {index + 1}/{len(frames)}", flush=True)
        counts.update(frame_blocks(path, palette, header, target))

    codebook: list[bytes] = []
    seen: set[bytes] = set()
    for color in range(min(256, len(palette) // 3)):
        vector = bytes([color]) * vector_size
        codebook.append(vector)
        seen.add(vector)
        if len(codebook) >= max_entries:
            return codebook, len(counts)

    for vector, _count in counts.most_common():
        if vector in seen:
            continue
        codebook.append(vector)
        seen.add(vector)
        if len(codebook) >= max_entries:
            break
    return codebook, len(counts)


def decoded_lcw_or_stored(chunk: vqa.Chunk, expected_size: int | None = None) -> bytes:
    if not chunk.chunk_id.endswith("Z"):
        return chunk.payload
    try:
        return vqa.decode_lcw(
            chunk.payload,
            expected_size=expected_size,
            allow_signed_source=chunk.chunk_id in {"VPTZ", "VPT0"},
        )
    except Exception:
        if chunk.chunk_id in {"VPTZ", "VPT0"} and expected_size is not None:
            decoded, _status = vqa.decode_lcw_windowed_pointer(chunk.payload, expected_size)
            return decoded
        raise


def first_source_cbfz_codebook(source_vqfrs: list[vqa.Chunk], header: vqa.VqaHeader) -> list[bytes]:
    vector_size = header.block_width * header.block_height
    expected_size = header.max_codebook_entries * vector_size
    for source_vqfr in source_vqfrs:
        for subchunk in vqa.iter_chunks(source_vqfr.payload, 0):
            if subchunk.chunk_id in {"CBFZ", "CBF0"}:
                decoded = decoded_lcw_or_stored(subchunk, expected_size)
                vectors = [
                    decoded[offset : offset + vector_size]
                    for offset in range(0, len(decoded) - vector_size + 1, vector_size)
                ]
                return vectors[: header.max_codebook_entries]
    return []


def first_source_cbfz_vectors(source_vqfrs: list[vqa.Chunk], header: vqa.VqaHeader) -> int:
    vectors = first_source_cbfz_codebook(source_vqfrs, header)
    if vectors:
        return max(1, min(header.max_codebook_entries, len(vectors)))
    return header.max_codebook_entries


def source_cbpz_vector_budget(subchunk: vqa.Chunk, header: vqa.VqaHeader) -> int:
    vector_size = header.block_width * header.block_height
    try:
        decoded = decoded_lcw_or_stored(subchunk)
    except Exception:
        return header.max_codebook_entries
    vectors = len(decoded) // vector_size
    return vectors if vectors > 0 else header.max_codebook_entries


def encode_pointer(
    blocks: list[bytes],
    codebook_index: dict[bytes, int],
    vector_size: int,
) -> tuple[bytes, dict[str, int]]:
    pointer = bytearray()
    exact_blocks = 0
    fallback_blocks = 0
    changed_pixels = 0

    for vector in blocks:
        index = codebook_index.get(vector)
        if index is not None:
            exact_blocks += 1
        else:
            fallback_blocks += 1
            dominant = writer.dominant_index(vector)
            fallback = bytes([dominant]) * vector_size
            index = codebook_index.get(fallback, 0)
            changed_pixels += sum(1 for value in vector if value != dominant)
        pointer.extend(struct.pack("<H", index))

    return bytes(pointer), {
        "exact_blocks": exact_blocks,
        "fallback_blocks": fallback_blocks,
        "changed_pixels": changed_pixels,
    }


def shape_text(payload: bytes) -> str:
    return "+".join(chunk.chunk_id for chunk in vqa.iter_chunks(payload, 0))


def build_payload(
    source_payload: bytes,
    source_dir: Path,
    target: tuple[int, int],
    progress_every: int,
    compact: bool,
    extended_lcw: bool,
    adaptive_cbpz: bool,
    base_codebook_entries: int,
    max_codebook_entries: int,
    pad_initial_cbfz: bool,
    pad_cbpz_to_source_budget: bool,
    vqa_extended_lcw: bool,
    windowed_pointer_lcw: bool,
    prefer_native_frames: bool,
) -> tuple[bytes, dict[str, int], list[dict[str, str]]]:
    source_header, source_chunks = vqa.parse_vqa(source_payload)
    source_vqfrs = [chunk for chunk in source_chunks if chunk.chunk_id == "VQFR"]
    frames = frame_paths(source_dir, prefer_native_frames)
    if len(frames) != len(source_vqfrs):
        raise ValueError(f"{source_dir}: frames {len(frames)} != source VQFR {len(source_vqfrs)}")
    if target[0] % source_header.block_width or target[1] % source_header.block_height:
        raise ValueError("target size must be divisible by VQA block geometry")

    palette = palette_bytes(source_dir)
    if adaptive_cbpz:
        base_limit = base_codebook_entries or first_source_cbfz_vectors(source_vqfrs, source_header)
    else:
        base_limit = base_codebook_entries or source_header.max_codebook_entries
    codebook, global_unique_vectors = build_global_codebook(
        frames,
        palette,
        source_header,
        target,
        progress_every,
        max_vectors=base_limit,
    )
    vector_size = source_header.block_width * source_header.block_height
    active_codebook_limit = max_codebook_entries or source_header.max_codebook_entries
    active_codebook_limit = min(active_codebook_limit, source_header.max_codebook_entries)
    stored_base_codebook = list(codebook)
    if pad_initial_cbfz:
        source_base_codebook = first_source_cbfz_codebook(source_vqfrs, source_header)
        if len(stored_base_codebook) < len(source_base_codebook):
            stored_base_codebook.extend(
                source_base_codebook[len(stored_base_codebook) : source_header.max_codebook_entries]
            )
    if vqa_extended_lcw:
        codebook_compressor = lcw_compress_vqa_extended
    else:
        codebook_compressor = lcw_compress if compact or extended_lcw else lcw_compress_literal
    if windowed_pointer_lcw:
        pointer_compressor = lcw_compress_windowed_pointer
    else:
        if vqa_extended_lcw:
            pointer_compressor = lcw_compress_vqa_extended
        else:
            pointer_compressor = lcw_compress_extended if extended_lcw else codebook_compressor
    empty_cbpz = b"\x80"
    active_codebook: list[bytes] = list(stored_base_codebook)
    active_index: dict[bytes, int] = {vector: index for index, vector in enumerate(codebook)}

    vqfr_chunks: list[bytes] = []
    frame_rows: list[dict[str, str]] = []
    totals = Counter()
    totals["base_codebook_vectors"] = len(codebook)
    max_vptz_size = 0
    max_vqfr_size = 0
    max_cbfz_size = 0

    for frame_index, (source_vqfr, frame_path) in enumerate(zip(source_vqfrs, frames)):
        if progress_every and (
            frame_index == 0 or (frame_index + 1) % progress_every == 0 or frame_index + 1 == len(frames)
        ):
            print(f"Encoding contract frame {frame_index + 1}/{len(frames)}", flush=True)
        blocks = frame_blocks(frame_path, palette, source_header, target)

        parts: list[bytes] = []
        pointer_lcw = b""
        stats = {"exact_blocks": 0, "fallback_blocks": 0, "changed_pixels": 0}
        frame_cbpz_vectors = 0
        frame_cbpz_lcw_size = 0
        source_subchunks = vqa.iter_chunks(source_vqfr.payload, 0)
        for subchunk in source_subchunks:
            if subchunk.chunk_id in {"CBFZ", "CBF0"}:
                active_codebook = list(stored_base_codebook)
                active_index = {vector: index for index, vector in enumerate(codebook)}
                codebook_lcw = codebook_compressor(b"".join(active_codebook))
                max_cbfz_size = max(max_cbfz_size, len(codebook_lcw))
                parts.append(writer.chunk(subchunk.chunk_id, codebook_lcw))
            elif subchunk.chunk_id in {"CBPZ", "CBP0"}:
                update_vectors: list[bytes] = []
                source_budget = 0
                if adaptive_cbpz and len(active_codebook) < active_codebook_limit:
                    room = active_codebook_limit - len(active_codebook)
                    source_budget = source_cbpz_vector_budget(subchunk, source_header)
                    budget = min(room, source_budget)
                    if budget > 0:
                        missing = Counter(vector for vector in blocks if vector not in active_index)
                        for vector, _count in missing.most_common(budget):
                            active_index[vector] = len(active_codebook)
                            active_codebook.append(vector)
                            update_vectors.append(vector)
                        if not update_vectors and source_budget > 0 and len(subchunk.payload) > 1 and active_codebook:
                            active_codebook.append(active_codebook[0])
                            update_vectors.append(active_codebook[0])
                        if pad_cbpz_to_source_budget and active_codebook and source_budget > len(update_vectors):
                            pad_room = active_codebook_limit - len(active_codebook)
                            pad_count = min(pad_room, source_budget - len(update_vectors))
                            if pad_count > 0:
                                pad_vector = active_codebook[0]
                                active_codebook.extend([pad_vector] * pad_count)
                                update_vectors.extend([pad_vector] * pad_count)
                update_payload = b"".join(update_vectors)
                frame_cbpz_vectors += len(update_vectors)
                totals["cbpz_update_vectors"] += len(update_vectors)
                if subchunk.chunk_id.endswith("Z"):
                    cbpz_payload = codebook_compressor(update_payload) if update_payload else empty_cbpz
                else:
                    cbpz_payload = update_payload
                frame_cbpz_lcw_size += len(cbpz_payload)
                parts.append(writer.chunk(subchunk.chunk_id, cbpz_payload))
            elif subchunk.chunk_id == "CPL0":
                parts.append(writer.chunk("CPL0", palette))
            elif subchunk.chunk_id in {"VPTZ", "VPT0"}:
                pointer, stats = encode_pointer(blocks, active_index, vector_size)
                pointer_lcw = pointer_compressor(pointer)
                max_vptz_size = max(max_vptz_size, len(pointer_lcw))
                for key, value in stats.items():
                    totals[key] += value
                parts.append(writer.chunk(subchunk.chunk_id, pointer_lcw))
            else:
                parts.append(writer.chunk(subchunk.chunk_id, subchunk.payload))

        payload = b"".join(parts)
        max_vqfr_size = max(max_vqfr_size, len(payload))
        vqfr_chunks.append(writer.chunk("VQFR", payload))
        frame_rows.append(
            {
                "frame": str(frame_index),
                "source_png": str(frame_path),
                "decoded_png": "",
                "shape": shape_text(payload),
                "exact_blocks": str(stats["exact_blocks"]),
                "fallback_blocks": str(stats["fallback_blocks"]),
                "changed_pixels": str(stats["changed_pixels"]),
                "pointer_lcw_size": str(len(pointer_lcw)),
                "cbpz_update_vectors": str(frame_cbpz_vectors),
                "cbpz_lcw_size": str(frame_cbpz_lcw_size),
                "active_codebook_vectors": str(len(active_codebook)),
                "validated": "0",
                "issues": "",
            }
        )

    header_payload = writer.header_payload(
        source_header,
        target[0],
        target[1],
        len(frames),
        len(codebook_lcw),
        max_vptz_size,
    )
    output_chunks: list[bytes] = []
    frame_index = 0
    for source_chunk in source_chunks:
        if source_chunk.chunk_id == "VQHD":
            output_chunks.append(writer.chunk("VQHD", header_payload))
        elif source_chunk.chunk_id == "VQFR":
            output_chunks.append(vqfr_chunks[frame_index])
            frame_index += 1
        else:
            output_chunks.append(writer.chunk(source_chunk.chunk_id, source_chunk.payload))

    body = b"WVQA" + b"".join(output_chunks)
    totals["codebook_vectors"] = len(codebook)
    totals["final_codebook_vectors"] = len(active_codebook)
    totals["stored_base_codebook_vectors"] = len(stored_base_codebook)
    totals["global_unique_vectors"] = global_unique_vectors
    totals["max_cbfz_size"] = max_cbfz_size
    totals["max_vptz_size"] = max_vptz_size
    totals["max_vqfr_size"] = max_vqfr_size
    return b"FORM" + writer.be32(len(body)) + body, dict(totals), frame_rows


def decode_generated_subchunk(
    subchunk: vqa.Chunk,
    header: vqa.VqaHeader,
    common_pointer_lcw: bool,
    windowed_pointer_lcw: bool,
) -> bytes:
    if not subchunk.chunk_id.endswith("Z"):
        return subchunk.payload
    if windowed_pointer_lcw and subchunk.chunk_id in {"VPTZ", "VPT0"}:
        decoded, _status = vqa.decode_lcw_windowed_pointer(subchunk.payload, header.block_count * 2)
        return decoded
    if common_pointer_lcw and subchunk.chunk_id in {"VPTZ", "VPT0"}:
        return lcw_decompress(subchunk.payload, expected_size=header.block_count * 2)
    expected_size = None
    if subchunk.chunk_id in {"VPTZ", "VPT0"}:
        expected_size = header.block_count * 2
    elif subchunk.chunk_id in {"CBFZ", "CBF0"}:
        expected_size = header.max_codebook_entries * header.block_width * header.block_height
    return vqa.decode_lcw(
        subchunk.payload,
        expected_size=expected_size,
        allow_signed_source=subchunk.chunk_id in {"VPTZ", "VPT0"},
    )


def validate_payload_special_pointer(
    payload: bytes,
    output_dir: Path,
    frame_rows: list[dict[str, str]],
    common_pointer_lcw: bool,
    windowed_pointer_lcw: bool,
) -> int:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    frames_dir = output_dir / "frames_native"
    frames_dir.mkdir(parents=True, exist_ok=True)
    header, chunks = vqa.parse_vqa(payload)
    palette: bytes | None = None
    active_codebook: bytes | None = None
    rendered_frame: Image.Image | None = None
    validated = 0
    frame_index = 0

    for chunk_row in chunks:
        if chunk_row.chunk_id == "CPL0":
            palette = chunk_row.payload
            continue
        if chunk_row.chunk_id != "VQFR":
            continue

        pointer_payload: bytes | None = None
        for subchunk in vqa.iter_chunks(chunk_row.payload, 0):
            decoded = decode_generated_subchunk(subchunk, header, common_pointer_lcw, windowed_pointer_lcw)
            if subchunk.chunk_id == "CPL0":
                palette = decoded
            elif subchunk.chunk_id in {"CBFZ", "CBF0"}:
                active_codebook = decoded
            elif subchunk.chunk_id in {"CBPZ", "CBP0"}:
                result = vqa.apply_cbp_update(active_codebook, decoded, header)
                if result.codebook is not None:
                    active_codebook = result.codebook
            elif subchunk.chunk_id in {"VPTZ", "VPT0"}:
                pointer_payload = decoded

        if palette is None or len(palette) < 768 or active_codebook is None:
            frame_index += 1
            continue
        if rendered_frame is None:
            rendered_frame = Image.new("P", (header.width, header.height), color=0)
        rendered_frame.putpalette(list(palette[:768]))
        if pointer_payload is not None:
            vqa.render_vpt_frame(rendered_frame, pointer_payload, active_codebook, header, None)
        output_path = frames_dir / f"frame_{frame_index:04d}.png"
        rendered_frame.save(output_path, optimize=False)
        if frame_index < len(frame_rows):
            frame_rows[frame_index]["decoded_png"] = str(output_path)
            frame_rows[frame_index]["validated"] = "1"
        validated += 1
        frame_index += 1

    return validated


def validate_payload(
    payload: bytes,
    output_dir: Path,
    frame_rows: list[dict[str, str]],
    common_pointer_lcw: bool,
    windowed_pointer_lcw: bool,
) -> int:
    if common_pointer_lcw or windowed_pointer_lcw:
        return validate_payload_special_pointer(payload, output_dir, frame_rows, common_pointer_lcw, windowed_pointer_lcw)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    vqa.decode_frames(
        payload,
        output_dir,
        max_frames=None,
        dump_payloads=False,
        render_frames=True,
        fullhd=False,
        target=(1, 1),
        fit="stretch",
        resample=Image.Resampling.NEAREST,
        background=(0, 0, 0),
        experimental_window_lcw=True,
        transparent_index=None,
        png_optimize=False,
    )
    decoded = sorted((output_dir / "frames_native").glob("frame_*.png"))
    for row, path in zip(frame_rows, decoded):
        row["decoded_png"] = str(path)
        row["validated"] = "1"
    return len(decoded)


def ratio(numerator: int, denominator: int) -> str:
    return "0.000000" if denominator <= 0 else f"{numerator / denominator:.6f}"


def native_exact_preflight(source_payload: bytes) -> tuple[str, str]:
    try:
        rebuilt = native_exact.rebuild_form_wvqa(source_payload)
    except Exception as exc:  # noqa: BLE001 - returned as CSV issue context.
        return "gap", f"native_exact_rebuild_error:{type(exc).__name__}:{exc}"
    if rebuilt != source_payload:
        return "gap", "native_exact_payload_mismatch"
    return "pass", ""


def build(args: argparse.Namespace) -> dict[str, str]:
    source_data, entries, table_end = read_mix(args.source)
    if args.entry < 0 or args.entry >= len(entries):
        raise ValueError(f"entry {args.entry} outside 0..{len(entries) - 1}")
    file_id, _offset, _size = entries[args.entry]
    source_payload = entry_payload(source_data, table_end, entries[args.entry])
    native_exact_status, native_exact_issue = native_exact_preflight(source_payload)
    target = (args.width, args.height)
    payload, totals, frame_rows = build_payload(
        source_payload,
        args.source_dir,
        target,
        args.progress_every,
        args.compact_lcw,
        args.extended_lcw,
        args.adaptive_cbpz,
        args.base_codebook_entries,
        args.max_codebook_entries,
        args.pad_initial_cbfz,
        args.pad_cbpz_to_source_budget,
        args.vqa_extended_lcw,
        args.windowed_pointer_lcw,
        args.prefer_native_frames,
    )

    output_payload = args.output / "payloads" / args.source.stem / f"{file_id:08x}.vqa"
    output_mix = args.output / "mix" / args.source.name
    decoded_dir = args.output / "decoded"
    output_payload.parent.mkdir(parents=True, exist_ok=True)
    output_payload.write_bytes(payload)
    write_mix_with_payload(args.source, output_mix, args.entry, payload)
    validated = validate_payload(payload, decoded_dir, frame_rows, args.extended_lcw, args.windowed_pointer_lcw)

    audit_args = argparse.Namespace(
        original_label=f"{args.source}:{args.entry}",
        replacement_label=str(output_payload),
        allow_resolution_change=(args.width, args.height) != (vqa.parse_vqa(source_payload)[0].width, vqa.parse_vqa(source_payload)[0].height),
    )
    compat_summary, compat_frames = compat_audit.audit(source_payload, payload, audit_args)
    compat_dir = args.output / "runtime_compat"
    write_csv(compat_dir / "summary.csv", compat_audit.SUMMARY_FIELDS, [compat_summary])
    write_csv(compat_dir / "frames.csv", compat_audit.FRAME_FIELDS, compat_frames)

    frame_count = len(frame_rows)
    block_count = (target[0] // 4) * (target[1] // 4)
    exact_blocks = int(totals.get("exact_blocks", 0))
    fallback_blocks = int(totals.get("fallback_blocks", 0))
    changed_pixels = int(totals.get("changed_pixels", 0))
    issues: list[str] = []
    if native_exact_status != "pass":
        issues.append(native_exact_issue)
    if validated != frame_count:
        issues.append(f"validation_frames:{validated}/{frame_count}")
    if compat_summary.get("status") != "pass":
        issues.append("runtime_compat_gap")
    if int(totals.get("max_cbfz_size", 0)) > 0xFFFF:
        issues.append("max_cbfz_size_over_u16")
    if int(totals.get("max_vptz_size", 0)) > 0xFFFF:
        issues.append("max_vptz_size_over_u16")

    status = "pass" if not issues else "gap"
    summary = {
        "status": status,
        "source_mix": str(args.source),
        "entry_index": str(args.entry),
        "file_id": f"{file_id:08x}",
        "native_exact_status": native_exact_status,
        "source_dir": str(args.source_dir),
        "output_payload": str(output_payload),
        "output_mix": str(output_mix),
        "decoded_dir": str(decoded_dir),
        "width": str(args.width),
        "height": str(args.height),
        "frames": str(frame_count),
        "validated_frames": str(validated),
        "payload_bytes": str(len(payload)),
        "payload_sha256": sha256(payload),
        "codebook_vectors": str(totals.get("codebook_vectors", 0)),
        "base_codebook_vectors": str(totals.get("base_codebook_vectors", 0)),
        "final_codebook_vectors": str(totals.get("final_codebook_vectors", 0)),
        "cbpz_update_vectors": str(totals.get("cbpz_update_vectors", 0)),
        "global_unique_vectors": str(totals.get("global_unique_vectors", 0)),
        "exact_blocks": str(exact_blocks),
        "fallback_blocks": str(fallback_blocks),
        "exact_block_ratio": ratio(exact_blocks, exact_blocks + fallback_blocks),
        "changed_pixels": str(changed_pixels),
        "changed_pixel_ratio": ratio(changed_pixels, args.width * args.height * frame_count),
        "max_cbfz_size": str(totals.get("max_cbfz_size", 0)),
        "max_vptz_size": str(totals.get("max_vptz_size", 0)),
        "frame_shapes": compat_summary.get("replacement_frame_shapes", ""),
        "runtime_compat_status": compat_summary.get("status", ""),
        "runtime_compat_report": str(compat_dir / "summary.csv"),
        "issues": ";".join(issues),
        "next_step": (
            "runtime-test this contract-preserving HD payload"
            if (args.width, args.height) != (vqa.parse_vqa(source_payload)[0].width, vqa.parse_vqa(source_payload)[0].height)
            else "runtime-test this contract-preserving native payload before scaling to HD"
        ),
    }
    write_csv(args.output / "summary.csv", SUMMARY_FIELDS, [summary])
    write_csv(args.output / "frames.csv", FRAME_FIELDS, frame_rows)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (args.output / "header.json").write_text(
        json.dumps(asdict(vqa.parse_vqa(payload)[0]), indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("C/LOLG/LOCALLNG.MIX"))
    parser.add_argument("--entry", type=int, default=2)
    parser.add_argument("--source-dir", type=Path, default=Path("output/lolg95_locallng_safe_sidecar_640x400/decoded_source"))
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=400)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--compact-lcw", action="store_true")
    parser.add_argument("--extended-lcw", action="store_true", help="Use long LCW copy/fill commands for smaller VPTZ chunks.")
    parser.add_argument(
        "--vqa-extended-lcw",
        action="store_true",
        help="Use VQA common LCW extended command meanings: 0xFF fill, 0xFE long copy.",
    )
    parser.add_argument(
        "--windowed-pointer-lcw",
        action="store_true",
        help="Use original VQA 64K-window LCW commands for VPTZ chunks.",
    )
    parser.add_argument(
        "--prefer-native-frames",
        action="store_true",
        help="Use source_dir/frames_native even when source_dir/frames_fullhd also exists.",
    )
    parser.add_argument("--adaptive-cbpz", action="store_true", help="Use existing CBPZ chunks to append frame-local codebook vectors.")
    parser.add_argument(
        "--base-codebook-entries",
        type=int,
        default=0,
        help="Base CBFZ vector count for --adaptive-cbpz; default follows the first source CBFZ decoded size.",
    )
    parser.add_argument(
        "--max-codebook-entries",
        type=int,
        default=0,
        help="Maximum active codebook vectors after CBPZ updates; default follows the source VQA maximum.",
    )
    parser.add_argument(
        "--pad-initial-cbfz",
        action="store_true",
        help="Pad the first CBFZ with source codebook vectors while keeping pointer indices limited to the selected profile.",
    )
    parser.add_argument(
        "--pad-cbpz-to-source-budget",
        action="store_true",
        help="Pad adaptive CBPZ updates with unused duplicate vectors up to the original CBPZ vector budget.",
    )
    parser.add_argument("--progress-every", type=int, default=25)
    args = parser.parse_args()

    summary = build(args)
    print(f"VQA contract-preserving writer: {summary['status']}")
    print(f"Runtime compat: {summary['runtime_compat_status']}")
    print(f"Frames: {summary['validated_frames']}/{summary['frames']}")
    print(f"Exact blocks: {summary['exact_block_ratio']} changed pixels: {summary['changed_pixel_ratio']}")
    print(f"Summary: {args.output / 'summary.csv'}")
    if summary["issues"]:
        print(f"Issues: {summary['issues']}")


if __name__ == "__main__":
    main()
