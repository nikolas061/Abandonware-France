#!/usr/bin/env python3
"""Write a first quantized Full HD WVQA replacement payload."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import shutil
import struct
from collections import Counter
from pathlib import Path

from PIL import Image

import lolg_vqa_decode as vqa
from westwood_codecs import lcw_compress_literal


DEFAULT_MANIFEST = Path("output/vqa_batch_window_lcw_transparent0_allframes/manifest.csv")
DEFAULT_FIXTURE_SUMMARY = Path("output/vqa_native_exact_fixture_writer/summary.csv")
DEFAULT_OUTPUT = Path("output/vqa_fullhd_replacement_writer")
DEFAULT_REPLACEMENTS = Path("replacements_vqa_fullhd")
DEFAULT_ARCHIVE_SEED_OUTPUT = Path("output/vqa_runtime_archive_seed_writer")
TARGET_SIZE = (1920, 1080)

SUMMARY_FIELDS = [
    "status",
    "archive",
    "index",
    "file_id",
    "source_dir",
    "replacement_payload",
    "decoded_dir",
    "frames",
    "validated_frames",
    "width",
    "height",
    "block_count",
    "max_codebook_entries",
    "max_vectors_used",
    "exact_blocks",
    "fallback_blocks",
    "exact_block_ratio",
    "changed_pixels",
    "changed_pixel_ratio",
    "payload_bytes",
    "payload_sha256",
    "runtime_replacement_path",
    "issues",
    "next_step",
]

REQUIREMENT_FIELDS = ["requirement", "status", "evidence", "next_step"]

FRAME_FIELDS = [
    "frame",
    "source_fullhd_png",
    "decoded_png",
    "unique_source_vectors",
    "codebook_vectors",
    "exact_blocks",
    "fallback_blocks",
    "changed_pixels",
    "codebook_lcw_size",
    "pointer_lcw_size",
    "validated",
    "issues",
]

_FRAME_ROWS_CACHE: dict[Path, list[dict[str, str]]] = {}
_FRAME_ROW_INDEX_CACHE: dict[Path, dict[str, list[dict[str, str]]]] = {}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def cached_frame_rows(output: Path) -> list[dict[str, str]]:
    path = output / "frames.csv"
    cached = _FRAME_ROWS_CACHE.get(path)
    if cached is None:
        cached = read_csv(path)
        _FRAME_ROWS_CACHE[path] = cached
    return cached


def cached_prefixed_frame_rows(output: Path, prefix: str) -> list[dict[str, str]]:
    path = output / "frames.csv"
    index = _FRAME_ROW_INDEX_CACHE.get(path)
    if index is None:
        index = {}
        for row in cached_frame_rows(output):
            text = row.get("frame", "")
            if ":" not in text:
                continue
            row_prefix, frame = text.split(":", 1)
            cached_row = dict(row)
            cached_row["frame"] = frame
            index.setdefault(row_prefix, []).append(cached_row)
        for rows in index.values():
            rows.sort(key=frame_row_number)
        _FRAME_ROW_INDEX_CACHE[path] = index
    return [dict(row) for row in index.get(prefix, [])]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, str], field: str) -> int:
    try:
        return int(row.get(field, "0") or 0)
    except ValueError:
        return 0


def be32(value: int) -> bytes:
    return struct.pack(">I", value)


def chunk(name: str, payload: bytes) -> bytes:
    data = name.encode("ascii") + be32(len(payload)) + payload
    if len(payload) & 1:
        data += b"\x00"
    return data


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def resolve_archive_path(path_text: str) -> Path:
    path = Path(path_text)
    candidates = [path, Path(path.name), Path("C") / "LOLG" / path.name, Path("backup_original_mix") / path.name]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return path


def replacement_path_for_entry(replacements: Path, row: dict[str, str]) -> Path:
    archive = row.get("archive", "")
    file_id = row.get("file_id", "").lower()
    return replacements / Path(archive).stem / f"{file_id}.vqa"


def excluded_archive(row: dict[str, str], excluded_stems: set[str]) -> bool:
    if not excluded_stems:
        return False
    return Path(row.get("archive", "")).stem.upper() in excluded_stems


def read_mix_entry(path: Path, index: int) -> bytes:
    data = path.read_bytes()
    count, body_size = struct.unpack_from("<HI", data, 0)
    if index < 0 or index >= count:
        raise ValueError(f"{path}: entry {index} outside 0..{count - 1}")
    table_end = 6 + count * 12
    _file_id, offset, size = struct.unpack_from("<III", data, 6 + index * 12)
    if offset + size > body_size:
        raise ValueError(f"{path}: entry {index} exceeds body")
    return data[table_end + offset : table_end + offset + size]


def header_payload(
    header: vqa.VqaHeader,
    width: int,
    height: int,
    frame_count: int,
    max_cbfz: int,
    max_vptz: int,
) -> bytes:
    return struct.pack(
        "<HHHHHBBBxHHHHHHHHHHHHHH",
        header.version,
        header.flags,
        frame_count,
        width,
        height,
        header.block_width,
        header.block_height,
        header.frame_rate,
        header.colors,
        header.max_codebook_entries,
        header.unknown_18,
        header.unknown_20,
        header.sample_rate,
        header.audio_flags,
        header.unknown_26,
        header.unknown_28,
        header.unknown_30,
        header.unknown_32,
        min(max_cbfz, 0xFFFF),
        header.unknown_36,
        min(max_vptz, 0xFFFF),
        header.unknown_40,
    )


def select_entry(args: argparse.Namespace) -> dict[str, str]:
    manifest_rows = read_csv(args.manifest)
    fixture_rows = read_csv(args.fixture_summary)
    if args.archive and args.index and args.file_id:
        for row in manifest_rows:
            if (
                row.get("archive") == args.archive
                and row.get("index") == args.index
                and row.get("file_id", "").lower() == args.file_id.lower()
            ):
                return row
        return {}
    if fixture_rows:
        fixture = fixture_rows[0]
        for row in manifest_rows:
            if (
                row.get("archive") == fixture.get("archive")
                and row.get("index") == fixture.get("index")
                and row.get("file_id") == fixture.get("file_id")
            ):
                return row
    for row in manifest_rows:
        if row.get("output_dir") and int_value(row, "fullhd_frames") > 0:
            return row
    return {}


def select_entries(args: argparse.Namespace) -> list[dict[str, str]]:
    excluded_stems = {stem.upper() for stem in args.exclude_archive_stem}
    if args.archive or args.index or args.file_id:
        entry = select_entry(args)
        if entry and args.missing_only and replacement_path_for_entry(args.replacements, entry).is_file():
            return []
        if entry and excluded_archive(entry, excluded_stems):
            return []
        return [entry] if entry else []

    limit = max(1, args.batch_limit)
    manifest_rows = read_csv(args.manifest)
    selected: list[dict[str, str]] = []
    selected_keys: set[tuple[str, str, str]] = set()

    fixture_entry = select_entry(args)
    if (
        fixture_entry
        and not excluded_archive(fixture_entry, excluded_stems)
        and (not args.missing_only or not replacement_path_for_entry(args.replacements, fixture_entry).is_file())
    ):
        key = (fixture_entry.get("archive", ""), fixture_entry.get("index", ""), fixture_entry.get("file_id", ""))
        selected.append(fixture_entry)
        selected_keys.add(key)

    candidates = [
        row
        for row in manifest_rows
        if row.get("output_dir") and int_value(row, "fullhd_frames") > 0
    ]
    if args.missing_only:
        candidates = [row for row in candidates if not replacement_path_for_entry(args.replacements, row).is_file()]
    if excluded_stems:
        candidates = [row for row in candidates if not excluded_archive(row, excluded_stems)]
    candidates.sort(
        key=lambda row: (
            int_value(row, "fullhd_frames"),
            int_value(row, "source_size"),
            int_value(row, "width") * int_value(row, "height"),
            row.get("archive", ""),
            row.get("index", ""),
        )
    )
    for row in candidates:
        if len(selected) >= limit:
            break
        key = (row.get("archive", ""), row.get("index", ""), row.get("file_id", ""))
        if key in selected_keys:
            continue
        selected.append(row)
        selected_keys.add(key)
    return selected


def frame_paths(source_dir: Path) -> list[Path]:
    return sorted((source_dir / "frames_fullhd").glob("frame_*_fullhd.png"))


def native_frame_paths(source_dir: Path) -> list[Path]:
    return sorted((source_dir / "frames_native").glob("frame_*.png"))


def frame_prefix(archive: str, index: int, file_id: str) -> str:
    return f"{Path(archive).stem}_{index:04d}_{file_id}"


def frame_row_number(row: dict[str, str]) -> int:
    text = row.get("frame", "")
    if ":" in text:
        text = text.split(":", 1)[1]
    try:
        return int(text)
    except ValueError:
        return -1


def reusable_frame_rows(
    output: Path,
    archive: str,
    index: int,
    file_id: str,
    expected_frames: list[Path],
    decoded_dir: Path,
    validate_images: bool,
) -> list[dict[str, str]]:
    prefix = frame_prefix(archive, index, file_id)
    matches = cached_prefixed_frame_rows(output, prefix)
    if len(matches) != len(expected_frames):
        return []
    for row, expected in zip(matches, expected_frames):
        if row.get("source_fullhd_png", "") != str(expected):
            return []
        if row.get("validated", "") != "1":
            return []
        if validate_images:
            decoded = Path(row.get("decoded_png", ""))
            if not decoded.is_file():
                return []
            with Image.open(decoded) as image:
                if image.size != TARGET_SIZE:
                    return []
    return matches


def reusable_unprefixed_frame_rows(
    output: Path,
    expected_frames: list[Path],
    validate_images: bool,
) -> list[dict[str, str]]:
    rows = [dict(row) for row in cached_frame_rows(output)]
    if len(rows) != len(expected_frames):
        return []
    rows.sort(key=frame_row_number)
    for row, expected in zip(rows, expected_frames):
        if row.get("source_fullhd_png", "") != str(expected):
            return []
        if row.get("validated", "") != "1":
            return []
        if validate_images:
            decoded = Path(row.get("decoded_png", ""))
            if not decoded.is_file():
                return []
            with Image.open(decoded) as image:
                if image.size != TARGET_SIZE:
                    return []
    return [dict(row) for row in rows]


def reusable_payload(
    report_payload: Path,
    replacement_path: Path,
) -> bytes:
    if not report_payload.is_file() or not replacement_path.is_file():
        return b""
    payload = report_payload.read_bytes()
    if payload != replacement_path.read_bytes():
        return b""
    return payload


def reusable_archive_seed(
    seed_output: Path,
    archive: str,
    index: int,
    file_id: str,
    expected_frames: list[Path],
    report_payload: Path,
    replacement_path: Path,
    validate_images: bool,
) -> tuple[bytes, list[dict[str, str]]]:
    seed_dir = seed_output / "targets" / frame_prefix(archive, index, file_id)
    seed_payload = seed_dir / "payloads" / Path(archive).stem / f"{file_id}.vqa"
    payload = reusable_payload(seed_payload, replacement_path)
    if not payload:
        return b"", []
    rows = reusable_unprefixed_frame_rows(seed_dir, expected_frames, validate_images)
    if not rows:
        return b"", []
    report_payload.parent.mkdir(parents=True, exist_ok=True)
    if not report_payload.exists() or report_payload.read_bytes() != payload:
        shutil.copyfile(seed_payload, report_payload)
    return payload, rows


def totals_from_frame_rows(
    source_payload: bytes,
    frame_rows: list[dict[str, str]],
) -> dict[str, int]:
    source_header, _chunks = vqa.parse_vqa(source_payload)
    return {
        "unique_source_vectors": sum(int_value(row, "unique_source_vectors") for row in frame_rows),
        "codebook_vectors": sum(int_value(row, "codebook_vectors") for row in frame_rows),
        "exact_blocks": sum(int_value(row, "exact_blocks") for row in frame_rows),
        "fallback_blocks": sum(int_value(row, "fallback_blocks") for row in frame_rows),
        "changed_pixels": sum(int_value(row, "changed_pixels") for row in frame_rows),
        "max_codebook_entries": source_header.max_codebook_entries,
    }


def palette_bytes(source_dir: Path) -> bytes:
    native_paths = native_frame_paths(source_dir)
    if not native_paths:
        raise ValueError(f"{source_dir}: missing native frame palette source")
    with Image.open(native_paths[0]) as image:
        palette = image.convert("P").getpalette() or []
    if len(palette) < 768:
        palette = palette + [0] * (768 - len(palette))
    return bytes(palette[:768])


def palette_index_lookup(palette: bytes) -> dict[tuple[int, int, int], int]:
    lookup: dict[tuple[int, int, int], int] = {}
    for index in range(min(256, len(palette) // 3)):
        color = tuple(palette[index * 3 : index * 3 + 3])
        lookup.setdefault(color, index)
    return lookup


def nearest_palette_index(palette: bytes, color: tuple[int, int, int]) -> int:
    best_index = 0
    best_distance: int | None = None
    limit = min(256, len(palette) // 3)
    for index in range(limit):
        r, g, b = palette[index * 3 : index * 3 + 3]
        distance = (r - color[0]) ** 2 + (g - color[1]) ** 2 + (b - color[2]) ** 2
        if best_distance is None or distance < best_distance:
            best_index = index
            best_distance = distance
    return best_index


def index_fullhd_image(path: Path, palette: bytes) -> bytes:
    lookup = palette_index_lookup(palette)
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        if rgb.size != TARGET_SIZE:
            raise ValueError(f"{path}: size {rgb.size}, expected {TARGET_SIZE}")
        data = rgb.tobytes()
    indexed = bytearray(len(data) // 3)
    cache: dict[tuple[int, int, int], int] = {}
    out = 0
    for pos in range(0, len(data), 3):
        color = (data[pos], data[pos + 1], data[pos + 2])
        index = cache.get(color)
        if index is None:
            index = lookup.get(color)
            if index is None:
                index = nearest_palette_index(palette, color)
            cache[color] = index
        indexed[out] = index
        out += 1
    return bytes(indexed)


def iter_blocks(indexed: bytes, width: int, height: int, block_width: int, block_height: int) -> list[bytes]:
    blocks: list[bytes] = []
    for y0 in range(0, height, block_height):
        for x0 in range(0, width, block_width):
            vector = bytearray()
            for y in range(block_height):
                start = (y0 + y) * width + x0
                vector.extend(indexed[start : start + block_width])
            blocks.append(bytes(vector))
    return blocks


def dominant_index(vector: bytes) -> int:
    counts = Counter(vector)
    return counts.most_common(1)[0][0]


def encode_quantized_frame(
    path: Path,
    palette: bytes,
    header: vqa.VqaHeader,
) -> tuple[bytes, bytes, dict[str, int]]:
    indexed = index_fullhd_image(path, palette)
    blocks = iter_blocks(indexed, TARGET_SIZE[0], TARGET_SIZE[1], header.block_width, header.block_height)
    source_counts = Counter(blocks)
    seen_colors = sorted(set(indexed))
    vector_size = header.block_width * header.block_height
    max_entries = max(1, header.max_codebook_entries)

    codebook: list[bytes] = []
    codebook_index: dict[bytes, int] = {}
    for color in seen_colors:
        vector = bytes([color]) * vector_size
        if vector not in codebook_index and len(codebook) < max_entries:
            codebook_index[vector] = len(codebook)
            codebook.append(vector)

    for vector, _count in source_counts.most_common():
        if vector in codebook_index:
            continue
        if len(codebook) >= max_entries:
            break
        codebook_index[vector] = len(codebook)
        codebook.append(vector)

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
            dominant = dominant_index(vector)
            fallback = bytes([dominant]) * vector_size
            index = codebook_index.get(fallback, 0)
            changed_pixels += sum(1 for value in vector if value != dominant)
        pointer.extend(struct.pack("<H", index))

    codebook_payload = b"".join(codebook)
    stats = {
        "unique_source_vectors": len(source_counts),
        "codebook_vectors": len(codebook),
        "exact_blocks": exact_blocks,
        "fallback_blocks": fallback_blocks,
        "changed_pixels": changed_pixels,
    }
    return codebook_payload, bytes(pointer), stats


def build_payload(
    source_payload: bytes,
    source_dir: Path,
    selected_frames: list[Path],
    frame_rows: list[dict[str, str]],
    progress_every: int = 0,
) -> tuple[bytes, dict[str, int]]:
    source_header, source_chunks = vqa.parse_vqa(source_payload)
    if source_header.block_width <= 0 or source_header.block_height <= 0:
        raise ValueError("invalid source block geometry")
    if TARGET_SIZE[0] % source_header.block_width or TARGET_SIZE[1] % source_header.block_height:
        raise ValueError("target size must be divisible by VQA block geometry")
    source_vqfr_count = sum(1 for chunk_row in source_chunks if chunk_row.chunk_id == "VQFR")
    if source_vqfr_count != len(selected_frames):
        raise ValueError(
            f"selected frame count {len(selected_frames)} does not match source VQFR count {source_vqfr_count}; "
            "refusing to write a runtime replacement with a changed frame contract"
        )

    palette = palette_bytes(source_dir)
    vqfr_chunks: list[bytes] = []
    totals = Counter()
    max_cbfz_size = 0
    max_vptz_size = 0

    for frame_index, path in enumerate(selected_frames):
        if progress_every and (
            frame_index == 0 or (frame_index + 1) % progress_every == 0 or frame_index + 1 == len(selected_frames)
        ):
            print(f"Encoding {source_dir.name}: frame {frame_index + 1}/{len(selected_frames)}", flush=True)
        codebook, pointer, stats = encode_quantized_frame(path, palette, source_header)
        codebook_lcw = lcw_compress_literal(codebook)
        pointer_lcw = lcw_compress_literal(pointer)
        max_cbfz_size = max(max_cbfz_size, len(codebook_lcw))
        max_vptz_size = max(max_vptz_size, len(pointer_lcw))
        for key, value in stats.items():
            totals[key] += value
        vqfr_chunks.append(
            chunk(
                "VQFR",
                b"".join(
                    [
                        chunk("CPL0", palette),
                        chunk("CBFZ", codebook_lcw),
                        chunk("VPTZ", pointer_lcw),
                    ]
                ),
            )
        )
        frame_rows.append(
            {
                "frame": str(frame_index),
                "source_fullhd_png": str(path),
                "decoded_png": "",
                "unique_source_vectors": str(stats["unique_source_vectors"]),
                "codebook_vectors": str(stats["codebook_vectors"]),
                "exact_blocks": str(stats["exact_blocks"]),
                "fallback_blocks": str(stats["fallback_blocks"]),
                "changed_pixels": str(stats["changed_pixels"]),
                "codebook_lcw_size": str(len(codebook_lcw)),
                "pointer_lcw_size": str(len(pointer_lcw)),
                "validated": "0",
                "issues": "",
            }
        )

    header = header_payload(source_header, TARGET_SIZE[0], TARGET_SIZE[1], len(selected_frames), max_cbfz_size, max_vptz_size)
    output_chunks: list[bytes] = []
    frame_index = 0
    for source_chunk in source_chunks:
        if source_chunk.chunk_id == "VQHD":
            output_chunks.append(chunk("VQHD", header))
        elif source_chunk.chunk_id == "VQFR":
            output_chunks.append(vqfr_chunks[frame_index])
            frame_index += 1
        else:
            output_chunks.append(chunk(source_chunk.chunk_id, source_chunk.payload))

    body = b"WVQA" + b"".join(output_chunks)
    totals["max_cbfz_size"] = max_cbfz_size
    totals["max_vptz_size"] = max_vptz_size
    totals["max_codebook_entries"] = source_header.max_codebook_entries
    return b"FORM" + be32(len(body)) + body, dict(totals)


def validate_payload(payload: bytes, decoded_dir: Path, frame_rows: list[dict[str, str]]) -> int:
    vqa.decode_frames(
        payload,
        decoded_dir,
        max_frames=None,
        dump_payloads=False,
        render_frames=True,
        fullhd=False,
        target=TARGET_SIZE,
        fit="contain",
        resample=Image.Resampling.NEAREST,
        background=(0, 0, 0),
        experimental_window_lcw=False,
        transparent_index=None,
        png_optimize=False,
    )
    validated = 0
    for row in frame_rows:
        source = Path(row["source_fullhd_png"])
        decoded = decoded_dir / "frames_native" / source.name.replace("_fullhd", "")
        row["decoded_png"] = str(decoded)
        if not decoded.exists():
            row["issues"] = "missing_decoded_frame"
            continue
        with Image.open(decoded) as image:
            if image.size != TARGET_SIZE:
                row["issues"] = f"decoded_size:{image.size[0]}x{image.size[1]}"
                continue
        row["validated"] = "1"
        validated += 1
    return validated


def ratio(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "0.000000"
    return f"{numerator / denominator:.6f}"


def build_reports(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    entries = select_entries(args)
    if len(entries) > 1:
        child_summaries: list[dict[str, str]] = []
        all_frames: list[dict[str, str]] = []
        all_issues: list[str] = []
        previous_batch_count = 0
        previous_summary: dict[str, str] = {}
        if not args.no_reuse_existing:
            previous_rows = read_csv(args.output / "summary.csv")
            previous_summary = previous_rows[0] if previous_rows else {}
            previous_archive = previous_summary.get("archive", "")
            if previous_summary.get("status") == "pass" and previous_archive.startswith("batch:"):
                try:
                    candidate_count = int(previous_archive.split(":", 1)[1])
                except ValueError:
                    candidate_count = 0
                previous_frames = read_csv(args.output / "frames.csv")
                if (
                    0 < candidate_count < len(entries)
                    and len(previous_frames) == int_value(previous_summary, "frames")
                    and int_value(previous_summary, "validated_frames") == int_value(previous_summary, "frames")
                ):
                    previous_batch_count = candidate_count
                    all_frames.extend(dict(row) for row in previous_frames)

        for entry in entries[previous_batch_count:]:
            child_args = argparse.Namespace(**vars(args))
            child_args.archive = entry.get("archive", "")
            child_args.index = entry.get("index", "")
            child_args.file_id = entry.get("file_id", "")
            child_args.batch_limit = 1
            child_summary, _child_requirements, child_frames = build_reports(child_args)
            child_summaries.append(child_summary)
            if child_summary.get("issues"):
                all_issues.append(
                    f"{Path(child_summary.get('archive', '')).stem}:"
                    f"{child_summary.get('index', '')}:"
                    f"{child_summary.get('file_id', '')}:"
                    f"{child_summary.get('issues', '')}"
                )
            frame_prefix = (
                f"{Path(child_summary.get('archive', '')).stem}_"
                f"{child_summary.get('index', '')}_"
                f"{child_summary.get('file_id', '')}"
            )
            for row in child_frames:
                merged = dict(row)
                merged["frame"] = f"{frame_prefix}:{row.get('frame', '')}"
                all_frames.append(merged)

        processed_entries = previous_batch_count + len(child_summaries)
        total_frames = int_value(previous_summary, "frames") + sum(int_value(row, "frames") for row in child_summaries)
        validated_frames = int_value(previous_summary, "validated_frames") + sum(
            int_value(row, "validated_frames") for row in child_summaries
        )
        exact_blocks = int_value(previous_summary, "exact_blocks") + sum(
            int_value(row, "exact_blocks") for row in child_summaries
        )
        fallback_blocks = int_value(previous_summary, "fallback_blocks") + sum(
            int_value(row, "fallback_blocks") for row in child_summaries
        )
        changed_pixels = int_value(previous_summary, "changed_pixels") + sum(
            int_value(row, "changed_pixels") for row in child_summaries
        )
        payload_bytes = int_value(previous_summary, "payload_bytes") + sum(
            int_value(row, "payload_bytes") for row in child_summaries
        )
        block_count = (TARGET_SIZE[0] // 4) * (TARGET_SIZE[1] // 4)
        total_blocks = block_count * total_frames
        total_pixels = TARGET_SIZE[0] * TARGET_SIZE[1] * total_frames
        max_vectors = max(
            [int_value(previous_summary, "max_vectors_used")]
            + [int_value(row, "max_vectors_used") for row in child_summaries],
            default=0,
        )
        max_codebook_entries = max(
            [int_value(previous_summary, "max_codebook_entries")]
            + [int_value(row, "max_codebook_entries") for row in child_summaries],
            default=0,
        )
        replacement_paths = [
            row.get("runtime_replacement_path", "")
            for row in child_summaries
            if row.get("runtime_replacement_path", "")
        ]
        replacement_file_count = previous_batch_count + len(replacement_paths)
        status = (
            "pass"
            if processed_entries == len(entries)
            and all(row.get("status") == "pass" for row in child_summaries)
            and validated_frames == total_frames
            and not all_issues
            else "gap"
        )
        summary = {
            "status": status,
            "archive": f"batch:{processed_entries}",
            "index": "",
            "file_id": "",
            "source_dir": str(args.manifest),
            "replacement_payload": str(args.output / "payloads"),
            "decoded_dir": str(args.output / "decoded"),
            "frames": str(total_frames),
            "validated_frames": str(validated_frames),
            "width": str(TARGET_SIZE[0]),
            "height": str(TARGET_SIZE[1]),
            "block_count": str(block_count),
            "max_codebook_entries": str(max_codebook_entries),
            "max_vectors_used": str(max_vectors),
            "exact_blocks": str(exact_blocks),
            "fallback_blocks": str(fallback_blocks),
            "exact_block_ratio": ratio(exact_blocks, total_blocks),
            "changed_pixels": str(changed_pixels),
            "changed_pixel_ratio": ratio(changed_pixels, total_pixels),
            "payload_bytes": str(payload_bytes),
            "payload_sha256": "",
            "runtime_replacement_path": str(args.replacements),
            "issues": ";".join(all_issues),
            "next_step": "continue expanding replacement coverage and improve quantizer quality",
        }
        requirements = [
            {
                "requirement": "fullhd_source_frames",
                "status": "pass" if total_frames else "gap",
                "evidence": f"entries={processed_entries};frames={total_frames};manifest={args.manifest}",
                "next_step": "keep all-frame Full HD exports current before encoding replacements",
            },
            {
                "requirement": "dominant_block_quantizer",
                "status": "pass" if status == "pass" and max_vectors <= max_codebook_entries else "gap",
                "evidence": (
                    f"max_vectors_used={max_vectors};max_codebook_entries={max_codebook_entries};"
                    f"exact_block_ratio={summary['exact_block_ratio']};"
                    f"changed_pixel_ratio={summary['changed_pixel_ratio']}"
                ),
                "next_step": "replace dominant-block fallback with nearest-vector or k-means refinement for better quality",
            },
            {
                "requirement": "wvqa_fullhd_payload",
                "status": "pass" if payload_bytes and not all_issues else "gap",
                "evidence": f"payloads={replacement_file_count};payload_bytes={payload_bytes}",
                "next_step": "decode-validate every produced payload before pack build consumes it",
            },
            {
                "requirement": "decode_validation",
                "status": "pass" if total_frames and validated_frames == total_frames else "gap",
                "evidence": f"validated_frames={validated_frames}/{total_frames};decoded_dir={args.output / 'decoded'}",
                "next_step": "compare decoded output against source Full HD frames and track visual error",
            },
            {
                "requirement": "runtime_replacement_file",
                "status": "pass" if replacement_file_count == processed_entries else "gap",
                "evidence": f"replacement_files={replacement_file_count}/{processed_entries};root={args.replacements}",
                "next_step": "rerun VQA repack readiness and runtime pack build",
            },
        ]
        return summary, requirements, all_frames

    entry = entries[0] if entries else {}
    frame_rows: list[dict[str, str]] = []
    requirements: list[dict[str, str]] = []
    issues: list[str] = []
    if not entry:
        issues.append("no_vqa_entry_selected")
        summary = {
            "status": "gap",
            "archive": "",
            "index": "",
            "file_id": "",
            "source_dir": "",
            "replacement_payload": "",
            "decoded_dir": "",
            "frames": "0",
            "validated_frames": "0",
            "width": str(TARGET_SIZE[0]),
            "height": str(TARGET_SIZE[1]),
            "block_count": "0",
            "max_codebook_entries": "0",
            "max_vectors_used": "0",
            "exact_blocks": "0",
            "fallback_blocks": "0",
            "exact_block_ratio": "0.000000",
            "changed_pixels": "0",
            "changed_pixel_ratio": "0.000000",
            "payload_bytes": "0",
            "payload_sha256": "",
            "runtime_replacement_path": "",
            "issues": ";".join(issues),
            "next_step": "regenerate VQA all-frame exports and native fixture summary",
        }
        return summary, requirements, frame_rows

    archive = entry.get("archive", "")
    index = int_value(entry, "index")
    file_id = entry.get("file_id", "").lower()
    source_dir = Path(entry.get("output_dir", ""))
    frames = frame_paths(source_dir)
    if args.max_frames:
        frames = frames[: args.max_frames]
    replacement_path = args.replacements / Path(archive).stem / f"{file_id}.vqa"
    report_payload = args.output / "payloads" / Path(archive).stem / f"{file_id}.vqa"
    decoded_dir = args.output / "decoded" / f"{Path(archive).stem}_{index:04d}_{file_id}"

    payload = b""
    totals: dict[str, int] = {}
    validated = 0
    try:
        if not frames:
            raise ValueError(f"{source_dir}: missing Full HD frames")
        cached_payload = b"" if args.no_reuse_existing else reusable_payload(report_payload, replacement_path)
        cached_rows = (
            []
            if args.no_reuse_existing or not cached_payload
            else reusable_frame_rows(
                args.output,
                archive,
                index,
                file_id,
                frames,
                decoded_dir,
                args.validate_reused_frames,
            )
        )
        if not cached_payload or not cached_rows:
            cached_payload, cached_rows = (
                (b"", [])
                if args.no_reuse_existing
                else reusable_archive_seed(
                    args.archive_seed_output,
                    archive,
                    index,
                    file_id,
                    frames,
                    report_payload,
                    replacement_path,
                    args.validate_reused_frames,
                )
            )
        if cached_payload and cached_rows:
            payload = cached_payload
            frame_rows.extend(cached_rows)
            totals = totals_from_frame_rows(cached_payload, frame_rows)
            validated = len(frame_rows)
        else:
            source_payload = read_mix_entry(resolve_archive_path(archive), index)
            payload, totals = build_payload(source_payload, source_dir, frames, frame_rows, args.progress_every)
            report_payload.parent.mkdir(parents=True, exist_ok=True)
            report_payload.write_bytes(payload)
            replacement_path.parent.mkdir(parents=True, exist_ok=True)
            replacement_path.write_bytes(payload)
            validated = validate_payload(payload, decoded_dir, frame_rows)
        if validated != len(frame_rows):
            issues.append(f"validation_failed:{len(frame_rows) - validated}")
    except Exception as exc:  # noqa: BLE001 - keep a machine-readable gap report
        message = str(exc).replace(";", ",").replace("\n", " ")
        issues.append(f"replacement_failed:{type(exc).__name__}:{message}")

    block_count = (TARGET_SIZE[0] // 4) * (TARGET_SIZE[1] // 4)
    frame_count = len(frame_rows)
    total_blocks = block_count * frame_count
    total_pixels = TARGET_SIZE[0] * TARGET_SIZE[1] * frame_count
    max_vectors = max((int_value(row, "codebook_vectors") for row in frame_rows), default=0)
    status = "pass" if payload and frame_rows and validated == len(frame_rows) and not issues else "gap"
    summary = {
        "status": status,
        "archive": archive,
        "index": entry.get("index", ""),
        "file_id": file_id,
        "source_dir": str(source_dir),
        "replacement_payload": str(report_payload) if report_payload.exists() else "",
        "decoded_dir": str(decoded_dir),
        "frames": str(frame_count),
        "validated_frames": str(validated),
        "width": str(TARGET_SIZE[0]),
        "height": str(TARGET_SIZE[1]),
        "block_count": str(block_count),
        "max_codebook_entries": str(totals.get("max_codebook_entries", 0)),
        "max_vectors_used": str(max_vectors),
        "exact_blocks": str(totals.get("exact_blocks", 0)),
        "fallback_blocks": str(totals.get("fallback_blocks", 0)),
        "exact_block_ratio": ratio(totals.get("exact_blocks", 0), total_blocks),
        "changed_pixels": str(totals.get("changed_pixels", 0)),
        "changed_pixel_ratio": ratio(totals.get("changed_pixels", 0), total_pixels),
        "payload_bytes": str(len(payload)),
        "payload_sha256": sha256_bytes(payload) if payload else "",
        "runtime_replacement_path": str(replacement_path) if replacement_path.exists() else "",
        "issues": ";".join(issues),
        "next_step": "improve the vector quantizer quality, then expand replacement coverage beyond this first payload",
    }
    requirements = [
        {
            "requirement": "fullhd_source_frames",
            "status": "pass" if frames else "gap",
            "evidence": f"frames={len(frames)};source_dir={source_dir}",
            "next_step": "keep all-frame Full HD exports current before encoding replacements",
        },
        {
            "requirement": "dominant_block_quantizer",
            "status": "pass" if frame_rows and max_vectors <= totals.get("max_codebook_entries", 0) else "gap",
            "evidence": (
                f"max_vectors_used={max_vectors};max_codebook_entries={totals.get('max_codebook_entries', 0)};"
                f"exact_block_ratio={summary['exact_block_ratio']};changed_pixel_ratio={summary['changed_pixel_ratio']}"
            ),
            "next_step": "replace dominant-block fallback with nearest-vector or k-means refinement for better quality",
        },
        {
            "requirement": "wvqa_fullhd_payload",
            "status": "pass" if payload else "gap",
            "evidence": f"payload_bytes={len(payload)};sha256={summary['payload_sha256']}",
            "next_step": "decode-validate every produced payload before pack build consumes it",
        },
        {
            "requirement": "decode_validation",
            "status": "pass" if frame_rows and validated == len(frame_rows) else "gap",
            "evidence": f"validated_frames={validated}/{len(frame_rows)};decoded_dir={decoded_dir}",
            "next_step": "compare decoded output against source Full HD frames and track visual error",
        },
        {
            "requirement": "runtime_replacement_file",
            "status": "pass" if replacement_path.exists() else "gap",
            "evidence": str(replacement_path),
            "next_step": "rerun VQA repack readiness and runtime pack build",
        },
    ]
    return summary, requirements, frame_rows


def render_table(rows: list[dict[str, str]], fields: list[str]) -> str:
    head = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def write_html(path: Path, summary: dict[str, str], requirements: list[dict[str, str]], frames: list[dict[str, str]]) -> None:
    payload = {"summary": summary, "requirements": requirements, "frames": frames}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    path.write_text(
        f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LOLG VQA Full HD Replacement Writer</title>
<style>
:root {{ color-scheme: dark; --bg: #101316; --panel: #171d22; --line: #2f3942; --text: #edf3f6; --muted: #9caab3; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; min-height: 100vh; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, sans-serif; }}
.wrap {{ width: min(1500px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12171b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 700; letter-spacing: 0; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; }}
.stat {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label {{ color: var(--muted); }}
.value {{ font-size: 24px; font-weight: 750; line-height: 1.05; margin-top: 4px; }}
.panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 12px; overflow-x: auto; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
table {{ width: 100%; min-width: 920px; border-collapse: collapse; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
td {{ overflow-wrap: anywhere; }}
</style>
</head>
<body>
<header><div class="wrap"><h1>LOLG VQA Full HD Replacement Writer</h1></div></header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Status</div><div class="value">{html.escape(summary['status'])}</div></div>
    <div class="stat"><div class="label">Frames</div><div class="value">{html.escape(summary['frames'])}</div></div>
    <div class="stat"><div class="label">Validated</div><div class="value">{html.escape(summary['validated_frames'])}</div></div>
    <div class="stat"><div class="label">Exact blocks</div><div class="value">{html.escape(summary['exact_block_ratio'])}</div></div>
  </section>
  <section class="panel"><h2>Synthese</h2>{render_table([summary], SUMMARY_FIELDS)}</section>
  <section class="panel"><h2>Requirements</h2>{render_table(requirements, REQUIREMENT_FIELDS)}</section>
  <section class="panel"><h2>Frames</h2>{render_table(frames, FRAME_FIELDS)}</section>
</main>
<script type="application/json" id="vqa-fullhd-replacement-writer">{html.escape(data_json)}</script>
</body>
</html>
""",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Write and validate a first quantized Full HD WVQA replacement.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--fixture-summary", type=Path, default=DEFAULT_FIXTURE_SUMMARY)
    parser.add_argument("--replacements", type=Path, default=DEFAULT_REPLACEMENTS)
    parser.add_argument("--archive-seed-output", type=Path, default=DEFAULT_ARCHIVE_SEED_OUTPUT)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--archive", default="")
    parser.add_argument("--index", default="")
    parser.add_argument("--file-id", default="")
    parser.add_argument("--batch-limit", type=int, default=1)
    parser.add_argument("--max-frames", type=int, default=0)
    parser.add_argument("--no-reuse-existing", action="store_true")
    parser.add_argument(
        "--missing-only",
        action="store_true",
        help="Select only VQA entries whose canonical replacement payload is not present yet.",
    )
    parser.add_argument(
        "--exclude-archive-stem",
        action="append",
        default=[],
        help="Skip selected source archive stems when choosing batch entries, for example L20_BBI.",
    )
    parser.add_argument(
        "--validate-reused-frames",
        action="store_true",
        help="Reopen decoded PNGs for cached payload rows instead of trusting prior validated frames.csv rows.",
    )
    parser.add_argument("--progress-every", type=int, default=0, help="Print encode progress every N frames.")
    parser.add_argument("--fail-on-gaps", action="store_true")
    args = parser.parse_args()

    summary, requirements, frames = build_reports(args)
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDS, [summary])
    write_csv(args.output / "requirements.csv", REQUIREMENT_FIELDS, requirements)
    write_csv(args.output / "frames.csv", FRAME_FIELDS, frames)
    write_html(args.output / "index.html", summary, requirements, frames)

    print(
        "VQA Full HD replacement writer: "
        f"{summary['status']} ({summary['validated_frames']}/{summary['frames']} frames validated, "
        f"{summary['runtime_replacement_path'] or 'no replacement'})"
    )
    print(f"Summary: {args.output / 'summary.csv'}")
    print(f"HTML: {args.output / 'index.html'}")
    if args.fail_on_gaps and summary["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
