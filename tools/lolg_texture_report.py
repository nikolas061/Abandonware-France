#!/usr/bin/env python3
"""Report Lands of Lore II level texture cache payloads."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import math
import re
import struct
from collections import Counter
from pathlib import Path

from PIL import Image


REPORT_FIELDNAMES = [
    "texture_path",
    "cache_block_offset",
    "cache_table_flags",
    "cache_tail_d0",
    "cache_tail_d4",
    "cache_tail_d8",
    "cache_tail_dc",
    "cache_tail_e0",
    "cache_tail_e4",
    "cache_tail_e8",
    "cache_tail_ec",
    "archive",
    "archive_exists",
    "texture_entry_index",
    "texture_file_id",
    "payload_size",
    "declared_size",
    "payload_declared_size",
    "declared_size_matches_payload_header",
    "packed_ratio",
    "referenced_pcx_count",
    "likely_referenced_pcx_count",
    "low_confidence_pcx_count",
    "referenced_pcx_names",
    "embedded_pcx_signature_count",
    "readable_embedded_pcx_count",
    "status",
]

REFERENCE_FIELDNAMES = [
    "texture_path",
    "archive",
    "texture_entry_index",
    "texture_file_id",
    "reference_index",
    "pcx_name",
    "base_name",
    "is_palette",
    "name_offset",
    "name_offset_hex",
    "name_end_offset",
    "previous_nul_offset",
    "next_nul_offset",
    "byte_before_name",
    "byte_after_name",
    "reference_class",
    "confidence",
    "nearest_project_offset",
    "nearest_project_distance",
    "nearest_wallseh_offset",
    "nearest_wallseh_distance",
    "wallseh_to_name_hex",
    "source_root",
    "source_control_hex",
    "reconstructed_source_path",
    "context_before_hex",
    "context_after_hex",
    "le32_before_name",
    "le32_after_name",
]

REFERENCE_SUMMARY_FIELDNAMES = [
    "texture_path",
    "archive",
    "texture_entry_index",
    "texture_file_id",
    "palette_count",
    "path_string_count",
    "filename_string_count",
    "low_confidence_count",
    "likely_texture_count",
    "source_path_names",
    "reconstructed_source_paths",
    "likely_texture_names",
    "low_confidence_names",
]

TEXTURE_STRING_CLUSTER_FIELDNAMES = [
    "texture_path",
    "archive",
    "texture_entry_index",
    "texture_file_id",
    "reference_index",
    "pcx_name",
    "reference_class",
    "confidence",
    "name_offset",
    "name_offset_hex",
    "previous_reference_distance",
    "next_reference_distance",
    "previous_nul_delta",
    "next_nul_delta",
    "tag_byte",
    "name_length",
    "pre_name_hex",
    "post_terminator_hex",
    "post_terminator_le32",
]

TEXTURE_SEGMENT_FIELDNAMES = [
    "texture_path",
    "archive",
    "texture_entry_index",
    "texture_file_id",
    "segment_index",
    "segment_start",
    "segment_start_hex",
    "segment_end",
    "segment_end_hex",
    "segment_size",
    "reference_index",
    "pcx_name",
    "reference_class",
    "confidence",
    "tag_byte",
    "body_offset",
    "body_offset_hex",
    "body_first_byte",
    "body_first_word",
    "body_head_hex",
    "body_head_ascii",
    "post_terminator_size",
    "body_lcw_status",
    "body_lcw_output_size",
    "body_lcw_input_consumed",
    "body_window_status",
    "body_window_output_size",
    "body_window_input_consumed",
    "entropy",
    "zero_ratio",
    "ff_ratio",
    "printable_ratio",
    "head_hex",
    "head_ascii",
]

TEXTURE_BODY_PREFIX_FIELDNAMES = [
    "reference_class",
    "confidence",
    "body_first_byte",
    "body_first_word",
    "count",
    "total_segment_size",
    "min_segment_size",
    "max_segment_size",
    "avg_segment_size",
    "avg_entropy",
    "sample_names",
    "sample_archives",
]

TEXTURE_SEGMENT_HEAD_PROFILE_FIELDNAMES = [
    "reference_class",
    "confidence",
    "body_first_word",
    "field_width",
    "field_offset",
    "field_offset_hex",
    "segment_count",
    "nonzero_count",
    "nonzero_ratio",
    "unique_count",
    "constant_value_hex",
    "top_values_hex",
    "sample_names",
    "sample_archives",
]

TEXTURE_ARCHIVE_SUMMARY_FIELDNAMES = [
    "texture_path",
    "archive",
    "payload_size",
    "declared_size",
    "payload_declared_size",
    "declared_to_payload_ratio",
    "payload_declared_to_payload_ratio",
    "segment_count",
    "segment_total_size",
    "body_total_size",
    "likely_segment_size",
    "low_confidence_segment_size",
    "avg_segment_entropy",
    "top_body_first_word",
    "top_body_first_word_count",
    "top_body_first_word_size",
]

TEXTURE_PAYLOAD_HEADER_PROFILE_FIELDNAMES = [
    "header_group",
    "field_width",
    "field_offset",
    "field_offset_hex",
    "payload_count",
    "nonzero_count",
    "nonzero_ratio",
    "unique_count",
    "constant_value_hex",
    "top_values_hex",
    "sample_archives",
]

PALETTE_CANDIDATE_FIELDNAMES = [
    "archive",
    "entry_index",
    "file_id",
    "body_offset",
    "size",
    "palette_bytes",
    "max_value",
    "unique_values",
    "vga_6bit_candidate",
    "head_hex",
]

CDCACHE_RAW_REFERENCE_FIELDNAMES = [
    "cache_path",
    "name_offset",
    "name_offset_hex",
    "pcx_name",
    "base_name",
    "previous_nul_offset",
    "next_nul_offset",
    "byte_before_name",
    "byte_after_name",
    "matched_texture_archives",
    "context_before_hex",
    "context_after_hex",
]

CDCACHE_DESCRIPTOR_FIELDNAMES = [
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

CDCACHE_PALETTE_CANDIDATE_FIELDNAMES = [
    "cache_path",
    "source_name_offset",
    "source_name_offset_hex",
    "candidate_offset",
    "candidate_offset_hex",
    "delta_from_name",
    "palette_bytes",
    "max_value",
    "unique_values",
    "vga_6bit_candidate",
    "sha1",
    "matches_local_mix_palette",
    "head_hex",
]

LCW_PROBE_FIELDNAMES = [
    "texture_path",
    "archive",
    "texture_entry_index",
    "texture_file_id",
    "probe_offset",
    "probe_offset_hex",
    "expected_size",
    "status",
    "output_size",
    "input_consumed",
    "note",
    "window_status",
    "window_output_size",
    "window_input_consumed",
    "window_note",
]

HEADER_FIELDNAMES = [
    "texture_path",
    "archive",
    "texture_entry_index",
    "texture_file_id",
    "payload_size",
    "declared_size",
    "payload_declared_size",
    "payload_header_minus_cache_declared",
    "declared_size_minus_payload_size",
    "packed_ratio",
    "header_variant",
    "palette_offset",
    "palette_offset_hex",
    "first_pcx_suffix_offset",
    "first_texture_reference_name_offset",
    "first_source_path_offset",
    "source_path_offsets",
    "sphere_path_offsets",
    "project_path_count",
    "prefix_hex",
    "prefix_ascii",
    "le16_prefix",
    "le32_prefix",
    "marker_offsets",
]

LEVEL_ENTRY_FIELDNAMES = [
    "archive",
    "entry_index",
    "file_id",
    "body_offset",
    "size",
    "second_word",
    "entry_class",
    "entropy",
    "zero_ratio",
    "ff_ratio",
    "ascii_string_count",
    "alpha_string_count",
    "sample_strings",
    "head_hex",
]

MATERIAL_STRING_FIELDNAMES = [
    "archive",
    "entry_index",
    "file_id",
    "string_index",
    "offset",
    "offset_hex",
    "text_end_offset",
    "text_end_offset_hex",
    "previous_nul_offset",
    "next_nul_offset",
    "byte_before_text",
    "byte_after_text",
    "text",
    "clean_text",
    "name_class",
    "name_confidence",
    "clean_offset",
    "clean_offset_hex",
    "cleaning_rule",
    "range_start",
    "range_start_hex",
    "range_end",
    "range_end_hex",
    "range_label",
    "context_before_hex",
    "context_after_hex",
    "le32_before_text",
    "le32_after_text",
]

MATERIAL_SECTION_FIELDNAMES = [
    "archive",
    "entry_index",
    "file_id",
    "section_index",
    "record_offset",
    "record_offset_hex",
    "word0",
    "word1",
    "word2",
    "word3",
    "word4",
    "word5",
    "word6",
    "nonzero_words",
    "plausible_offsets",
]

MATERIAL_RANGE_FIELDNAMES = [
    "archive",
    "entry_index",
    "file_id",
    "range_index",
    "range_start",
    "range_start_hex",
    "range_end",
    "range_end_hex",
    "range_size",
    "range_label",
    "string_count",
    "cleaned_string_count",
    "cleaning_rules",
    "sample_clean_text",
]

MATERIAL_TEXTURE_MATCH_FIELDNAMES = [
    "archive",
    "pcx_name",
    "pcx_stem",
    "material_clean_text",
    "material_offset",
    "material_offset_hex",
    "material_range_label",
    "material_name_class",
    "material_name_confidence",
    "match_type",
    "normalized_pcx",
    "normalized_material",
]

MATERIAL_SEQUENCE_FIELDNAMES = [
    "archive",
    "entry_index",
    "file_id",
    "range_label",
    "sequence_index",
    "current_offset",
    "current_offset_hex",
    "current_clean_text",
    "current_name_class",
    "current_name_confidence",
    "next_offset",
    "next_offset_hex",
    "next_clean_text",
    "next_name_class",
    "next_name_confidence",
    "distance",
    "dominant_distance",
    "matches_dominant_distance",
]

MATERIAL_STRIDE_FIELDNAMES = [
    "archive",
    "entry_index",
    "file_id",
    "range_label",
    "string_count",
    "sequence_count",
    "top_distance",
    "top_distance_count",
    "top_distance_ratio",
    "top_distances",
]

MATERIAL_RECORD_FIELDNAMES = [
    "archive",
    "entry_index",
    "file_id",
    "range_label",
    "record_index",
    "record_size",
    "stride_ratio",
    "record_start",
    "record_start_hex",
    "record_end",
    "record_end_hex",
    "next_record_start",
    "next_record_start_hex",
    "next_distance",
    "matches_stride",
    "record_fits_payload",
    "source_string_index",
    "raw_offset",
    "raw_offset_hex",
    "clean_text",
    "name_class",
    "name_confidence",
    "prefix_delta",
    "matched_pcx_names",
    "matched_pcx_match_types",
    "record_hex",
    "record_ascii",
    "record_le16",
    "record_le32",
]

MATERIAL_RECORD_PROFILE_FIELDNAMES = [
    "archive",
    "entry_index",
    "file_id",
    "range_label",
    "record_size",
    "record_count",
    "matching_stride_count",
    "matching_stride_ratio",
    "matched_record_count",
    "name_class_counts",
    "prefix_delta_counts",
    "top_suffix_8_hex",
    "top_suffix_8_count",
    "top_suffix_12_hex",
    "top_suffix_12_count",
    "top_suffix_16_hex",
    "top_suffix_16_count",
    "sample_texts",
    "matched_pcx_names",
]

MATERIAL_RECORD_FIELD_PROFILE_FIELDNAMES = [
    "archive",
    "entry_index",
    "file_id",
    "range_label",
    "record_size",
    "field_width",
    "field_offset",
    "field_offset_hex",
    "record_count",
    "nonzero_count",
    "nonzero_ratio",
    "unique_count",
    "constant_value_hex",
    "top_values_hex",
    "matched_record_count",
    "matched_nonzero_count",
    "matched_unique_count",
    "matched_top_values_hex",
]

MATERIAL_TEXTURE_RECORD_LINK_FIELDNAMES = [
    "archive",
    "pcx_name",
    "match_type",
    "material_clean_text",
    "material_offset",
    "material_offset_hex",
    "material_range_label",
    "material_name_class",
    "material_name_confidence",
    "texture_segment_index",
    "texture_reference_index",
    "texture_name_offset",
    "texture_name_offset_hex",
    "texture_body_offset",
    "texture_body_offset_hex",
    "texture_body_first_word",
    "texture_segment_size",
    "texture_post_terminator_size",
    "texture_entropy",
    "record_range_label",
    "record_index",
    "record_size",
    "record_start",
    "record_start_hex",
    "record_end_hex",
    "next_distance",
    "matches_stride",
    "prefix_delta",
    "record_suffix_8_hex",
    "record_suffix_12_hex",
    "record_suffix_16_hex",
    "record_le16",
    "record_le32",
    "record_hex",
]

CDCACHE_MATERIAL_TEXTURE_LINK_FIELDNAMES = [
    "archive",
    "pcx_name",
    "material_clean_text",
    "material_offset_hex",
    "material_range_label",
    "texture_segment_index",
    "texture_body_offset_hex",
    "texture_body_first_word",
    "texture_segment_size",
    "record_range_label",
    "record_index",
    "record_size",
    "record_start_hex",
    "cache_name_offset_hex",
    "cache_descriptor_offset_hex",
    "cache_marker_word",
    "cache_origin_x",
    "cache_origin_y",
    "cache_width",
    "cache_height",
    "cache_index",
    "cache_data_offset_hex",
    "cache_content_bbox",
    "cache_data_zero_ratio",
    "cache_data_crosses_next_descriptor",
]

PCX_SIGNATURE_FIELDNAMES = [
    "texture_path",
    "archive",
    "texture_entry_index",
    "texture_file_id",
    "signature_index",
    "signature_offset",
    "signature_offset_hex",
    "signature",
    "pcx_version",
    "pcx_encoding",
    "pcx_bits_per_pixel",
    "xmin",
    "ymin",
    "xmax",
    "ymax",
    "width",
    "height",
    "pil_readable",
    "context_before_hex",
    "context_after_hex",
]

DEFAULT_LCW_PROBE_OFFSETS = [4, 8, 12, 16, 32, 64, 96, 112, 128]
HEADER_PREFIX_BYTES = 160
PCX_NAME_PATTERN = rb"[A-Za-z0-9_:\\./-]+\.pcx"
ASCII_STRING_PATTERN = rb"[ -~]{4,}"


def read_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def read_u32_or_none(data: bytes, offset: int) -> int | None:
    if offset < 0 or offset + 4 > len(data):
        return None
    return read_u32(data, offset)


def format_nearby_le32(data: bytes, base_offset: int, relative_offsets: list[int]) -> str:
    words: list[str] = []
    for relative_offset in relative_offsets:
        value = read_u32_or_none(data, base_offset + relative_offset)
        if value is not None:
            words.append(f"{relative_offset:+d}:{value:08x}")
    return ";".join(words)


def format_byte(data: bytes, offset: int) -> str:
    if offset < 0 or offset >= len(data):
        return ""
    return f"{data[offset]:02x}"


def format_offset(offset: int) -> str:
    return "" if offset < 0 else str(offset)


def format_offset_hex(offset: int) -> str:
    return "" if offset < 0 else f"0x{offset:08x}"


def format_ascii(data: bytes) -> str:
    return "".join(chr(byte) if 32 <= byte < 127 else "." for byte in data)


def format_le16_words(data: bytes, count: int) -> str:
    words: list[str] = []
    limit = min(len(data), count * 2)
    for offset in range(0, limit, 2):
        words.append(f"{offset:02x}:{struct.unpack_from('<H', data, offset)[0]:04x}")
    return ";".join(words)


def format_le32_words(data: bytes, count: int) -> str:
    words: list[str] = []
    limit = min(len(data), count * 4)
    for offset in range(0, limit, 4):
        words.append(f"{offset:02x}:{struct.unpack_from('<I', data, offset)[0]:08x}")
    return ";".join(words)


def find_all_offsets(payload: bytes, needle: bytes, limit: int | None = None) -> list[int]:
    offsets: list[int] = []
    start = 0
    while True:
        offset = payload.find(needle, start)
        if offset < 0:
            return offsets
        offsets.append(offset)
        if limit is not None and len(offsets) >= limit:
            return offsets
        start = offset + 1


def format_offsets(offsets: list[int]) -> str:
    return ";".join(str(offset) for offset in offsets)


def find_nearest_before(payload: bytes, needles: tuple[bytes, ...], offset: int, window: int) -> int:
    start = max(0, offset - window)
    best = -1
    for needle in needles:
        candidate = payload.rfind(needle, start, offset)
        if candidate > best:
            best = candidate
    return best


def classify_pcx_reference(
    name: str,
    base_name: str,
    is_palette: bool,
    null_terminated: bool,
) -> tuple[str, str]:
    stem = base_name.rsplit(".", 1)[0]
    has_path = "\\" in name or "/" in name or ":" in name

    if is_palette:
        return "palette", "high"
    if has_path:
        return "path_string", "high" if null_terminated else "medium"
    if len(stem) <= 2:
        return "short_pcx_like", "low"
    if not null_terminated:
        return "unterminated_pcx_like", "low"
    return "filename_string", "medium"


def parse_cache_list(path: Path) -> list[dict[str, object]]:
    data = path.read_bytes()
    if len(data) < 8:
        return []

    first_block_offset = read_u32(data, 0)
    table_end = min(first_block_offset, len(data))
    block_flags: dict[int, set[int]] = {}
    for offset in range(0, table_end, 8):
        if offset + 8 > len(data):
            break
        block_offset = read_u32(data, offset)
        flag = read_u32(data, offset + 4)
        if block_offset or flag:
            block_flags.setdefault(block_offset, set()).add(flag)

    rows: list[dict[str, object]] = []
    for block_offset in sorted(block_flags):
        if block_offset + 0x100 > len(data):
            continue
        block = data[block_offset : block_offset + 0x100]
        texture_path = block[8:136].split(b"\0", 1)[0].decode("ascii", errors="replace")
        tail = struct.unpack_from("<IIIIIIII", block, 0xD0)
        declared_size = tail[3] or tail[4]
        rows.append(
            {
                "texture_path": texture_path,
                "cache_block_offset": block_offset,
                "cache_table_flags": ";".join(str(flag) for flag in sorted(block_flags[block_offset])),
                "cache_tail": tail,
                "declared_size": declared_size,
            }
        )

    return rows


def archive_for_texture(texture_path: str, game_dir: Path) -> Path:
    stem = Path(texture_path.replace("\\", "/")).stem
    if stem.endswith(".te_"):
        stem = stem[:-4]
    return game_dir / f"{stem.upper()}.MIX"


def read_mix_entry(path: Path, index: int) -> tuple[int, bytes] | None:
    data = path.read_bytes()
    if len(data) < 6:
        return None
    count, body_size = struct.unpack_from("<HI", data, 0)
    table_end = 6 + count * 12
    if index < 0 or index >= count or table_end > len(data):
        return None
    file_id, offset, size = struct.unpack_from("<III", data, 6 + index * 12)
    if offset + size > body_size:
        return None
    return file_id, data[table_end + offset : table_end + offset + size]


def read_mix_entries(path: Path) -> list[tuple[int, int, int, int, bytes]]:
    data = path.read_bytes()
    if len(data) < 6:
        return []

    count, body_size = struct.unpack_from("<HI", data, 0)
    table_end = 6 + count * 12
    if table_end > len(data):
        return []

    entries: list[tuple[int, int, int, int, bytes]] = []
    for index in range(count):
        file_id, offset, size = struct.unpack_from("<III", data, 6 + index * 12)
        if offset + size > body_size:
            continue
        payload = data[table_end + offset : table_end + offset + size]
        entries.append((index, file_id, offset, size, payload))
    return entries


def ascii_strings(payload: bytes) -> list[tuple[int, str]]:
    rows: list[tuple[int, str]] = []
    for match in re.finditer(ASCII_STRING_PATTERN, payload):
        text = match.group().decode("ascii", errors="replace").strip()
        if text and any(char.isalpha() for char in text):
            rows.append((match.start(), text))
    return rows


MATERIAL_TEXT_ANCHOR_PATTERN = re.compile(
    "|".join(
        f"(?:{anchor})"
        for anchor in (
            r"Floor\d*",
            r"floor\d*",
            r"sky\d*",
            r"acid\b",
            r"Middle\b",
            r"Bottom\b",
            r"Ice\b",
            r"Frozen\b",
            r"shallow\b",
            r"medium\b",
            r"deep\b",
            r"River\b",
            r"churning\b",
            r"Water\b",
            r"water\b",
            r"Lava\b",
            r"Pyramid\b",
            r"Magic\b",
            r"Health\b",
            r"Scorched\b",
            r"Blue\b",
            r"Brown\b",
            r"Green\b",
            r"Hanging\b",
            r"Small\b",
            r"Silverleaf\b",
            r"Dead\b",
            r"Ded\b",
            r"Skulls\b",
            r"Ribs\b",
            r"Broken\b",
            r"Bone\b",
            r"Statue\b",
            r"Explosion\b",
            r"Chain\b",
            r"Light\b",
            r"Tumbleweed\b",
            r"Stop\b",
            r"Rubble\b",
            r"Priest\b",
        )
    )
)


def should_strip_material_prefix(prefix: str, anchor: str) -> bool:
    if not prefix or len(prefix) > 8:
        return False
    if any(char.isspace() for char in prefix) or "'" in prefix:
        return False
    if len(prefix) == 1:
        return not prefix.isdigit()
    if len(set(prefix)) == 1 and not prefix.isdigit():
        return True
    if re.fullmatch(r"[^A-Za-z0-9]+", prefix):
        return True
    if re.fullmatch(r"[qv~=*#()+<>|\\/_$%!\"@\[\]^`:;.,-]+", prefix):
        return True
    if anchor.startswith("Floor") and re.fullmatch(r"[A-Za-z]?loor\d+", prefix):
        return True
    return False


def clean_material_text(text: str) -> tuple[str, int, str]:
    original = text
    text = text.strip()
    trim_delta = original.find(text) if text else 0
    if trim_delta < 0:
        trim_delta = 0

    leading_match = re.match(r"^[^A-Za-z0-9]+", text)
    leading_delta = len(leading_match.group()) if leading_match else 0
    if leading_delta:
        text = text[leading_delta:]

    prefix_delta = 0
    prefix_rule = ""
    for match in MATERIAL_TEXT_ANCHOR_PATTERN.finditer(text):
        prefix = text[: match.start()]
        anchor = match.group()
        if should_strip_material_prefix(prefix, anchor):
            prefix_delta = match.start()
            prefix_rule = "stripped_noise_prefix"
            text = text[match.start() :]
        break

    text = text.rstrip("\\|{}[]<>")
    total_delta = trim_delta + leading_delta + prefix_delta
    rule_parts = []
    if trim_delta:
        rule_parts.append("trimmed_whitespace")
    if leading_delta:
        rule_parts.append("stripped_leading_punctuation")
    if prefix_rule:
        rule_parts.append(prefix_rule)
    return text, total_delta, ";".join(rule_parts) if rule_parts else "unchanged"


def classify_material_name(clean_text: str, cleaning_rule: str) -> tuple[str, str]:
    if len(clean_text) < 3 or not any(char.isalpha() for char in clean_text):
        return "fragment", "low"

    if re.search(r"[{}[\]<>|\\`~^]", clean_text):
        return "noisy_printable", "low"

    punctuation = sum(
        1
        for char in clean_text
        if not (char.isalnum() or char.isspace() or char in "_'-/")
    )
    if punctuation > 1:
        return "noisy_printable", "low"

    if MATERIAL_TEXT_ANCHOR_PATTERN.search(clean_text):
        return "material_label", "high" if "stripped_noise_prefix" in cleaning_rule else "medium"

    if " " in clean_text:
        return "material_label", "medium"

    if re.fullmatch(r"[A-Z][A-Z0-9_/-]{2,15}", clean_text):
        return "asset_label", "medium"

    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_'-]{2,31}", clean_text):
        return "name_like", "medium"

    return "noisy_printable", "low"


def shannon_entropy(payload: bytes) -> float:
    if not payload:
        return 0.0
    counts = Counter(payload)
    total = len(payload)
    return -sum((count / total) * math.log2(count / total) for count in counts.values())


def classify_level_entry(payload: bytes, body_offset: int) -> str:
    if body_offset == 0:
        return "texture_payload"
    if len(payload) >= 8:
        second_word = read_u32(payload, 4)
        if second_word == 0x204:
            return "materials"
        if second_word == 0x14B4:
            return "scripts"
    return "unknown"


def material_boundaries(payload: bytes) -> list[tuple[int, str]]:
    boundaries: dict[int, list[str]] = {0x204: ["data_start"], len(payload): ["payload_end"]}
    if len(payload) < 0x204:
        return sorted((offset, "+".join(labels)) for offset, labels in boundaries.items())

    header_count = read_u32(payload, 0)
    record_count = min(header_count, (0x204 - 8) // 28)
    for section_index in range(record_count):
        record_offset = 8 + section_index * 28
        words = struct.unpack_from("<IIIIIII", payload, record_offset)
        for word_index, word in enumerate(words):
            if 0x204 <= word < len(payload):
                boundaries.setdefault(word, []).append(f"section{section_index}.word{word_index}")

    return sorted((offset, "+".join(labels)) for offset, labels in boundaries.items())


def locate_material_range(
    boundaries: list[tuple[int, str]],
    offset: int,
) -> tuple[int, int, str]:
    if not boundaries:
        return 0, 0, ""

    for index, (start, label) in enumerate(boundaries[:-1]):
        end = boundaries[index + 1][0]
        if start <= offset < end:
            return start, end, label

    last_start, last_label = boundaries[-1]
    return last_start, last_start, last_label


def build_level_entry_reports(
    archives: list[Path],
) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    entry_rows: list[dict[str, str]] = []
    material_string_rows: list[dict[str, str]] = []
    material_section_rows: list[dict[str, str]] = []
    material_range_rows: list[dict[str, str]] = []

    for archive in sorted(set(archives)):
        if not archive.exists():
            continue

        for entry_index, file_id, body_offset, size, payload in read_mix_entries(archive):
            entry_class = classify_level_entry(payload, body_offset)
            strings = ascii_strings(payload)
            counts = Counter(payload)
            sample_strings = [text for _offset, text in strings[:20]]
            second_word = read_u32(payload, 4) if len(payload) >= 8 else 0
            entry_rows.append(
                {
                    "archive": str(archive),
                    "entry_index": str(entry_index),
                    "file_id": f"{file_id:08x}",
                    "body_offset": str(body_offset),
                    "size": str(size),
                    "second_word": f"{second_word:08x}" if len(payload) >= 8 else "",
                    "entry_class": entry_class,
                    "entropy": f"{shannon_entropy(payload):.4f}",
                    "zero_ratio": f"{counts[0] / len(payload):.6f}" if payload else "",
                    "ff_ratio": f"{counts[0xFF] / len(payload):.6f}" if payload else "",
                    "ascii_string_count": str(len(re.findall(ASCII_STRING_PATTERN, payload))),
                    "alpha_string_count": str(len(strings)),
                    "sample_strings": "|".join(sample_strings),
                    "head_hex": payload[:32].hex(),
                }
            )

            if entry_class == "materials":
                boundaries = material_boundaries(payload)
                range_stats: dict[int, dict[str, object]] = {
                    start: {
                        "count": 0,
                        "cleaned_count": 0,
                        "rules": Counter(),
                        "examples": [],
                    }
                    for start, _label in boundaries[:-1]
                }
                if len(payload) >= 0x204:
                    header_count = read_u32(payload, 0)
                    record_count = min(header_count, (0x204 - 8) // 28)
                    for section_index in range(record_count):
                        record_offset = 8 + section_index * 28
                        words = struct.unpack_from("<IIIIIII", payload, record_offset)
                        plausible_offsets = [
                            f"word{word_index}=0x{word:08x}"
                            for word_index, word in enumerate(words)
                            if 0x204 <= word < len(payload)
                        ]
                        material_section_rows.append(
                            {
                                "archive": str(archive),
                                "entry_index": str(entry_index),
                                "file_id": f"{file_id:08x}",
                                "section_index": str(section_index),
                                "record_offset": str(record_offset),
                                "record_offset_hex": f"0x{record_offset:08x}",
                                "word0": f"{words[0]:08x}",
                                "word1": f"{words[1]:08x}",
                                "word2": f"{words[2]:08x}",
                                "word3": f"{words[3]:08x}",
                                "word4": f"{words[4]:08x}",
                                "word5": f"{words[5]:08x}",
                                "word6": f"{words[6]:08x}",
                                "nonzero_words": str(sum(1 for word in words if word)),
                                "plausible_offsets": ";".join(plausible_offsets),
                            }
                        )

                for string_index, (offset, text) in enumerate(strings):
                    clean_text, clean_delta, cleaning_rule = clean_material_text(text)
                    name_class, name_confidence = classify_material_name(
                        clean_text,
                        cleaning_rule,
                    )
                    clean_offset = offset + clean_delta
                    text_end_offset = offset + len(text)
                    previous_nul = payload.rfind(b"\0", 0, offset)
                    next_nul = payload.find(b"\0", text_end_offset)
                    context_start = max(0, offset - 32)
                    context_end = min(len(payload), text_end_offset + 32)
                    range_start, range_end, range_label = locate_material_range(
                        boundaries,
                        clean_offset,
                    )
                    stats = range_stats.get(range_start)
                    if stats is not None:
                        stats["count"] = int(stats["count"]) + 1
                        if clean_text != text:
                            stats["cleaned_count"] = int(stats["cleaned_count"]) + 1
                        rules = stats["rules"]
                        if isinstance(rules, Counter):
                            rules[cleaning_rule] += 1
                        examples = stats["examples"]
                        if isinstance(examples, list) and len(examples) < 8:
                            examples.append(clean_text)
                    material_string_rows.append(
                        {
                            "archive": str(archive),
                            "entry_index": str(entry_index),
                            "file_id": f"{file_id:08x}",
                            "string_index": str(string_index),
                            "offset": str(offset),
                            "offset_hex": f"0x{offset:08x}",
                            "text_end_offset": str(text_end_offset),
                            "text_end_offset_hex": f"0x{text_end_offset:08x}",
                            "previous_nul_offset": str(previous_nul),
                            "next_nul_offset": str(next_nul),
                            "byte_before_text": format_byte(payload, offset - 1),
                            "byte_after_text": format_byte(payload, text_end_offset),
                            "text": text,
                            "clean_text": clean_text,
                            "name_class": name_class,
                            "name_confidence": name_confidence,
                            "clean_offset": str(clean_offset),
                            "clean_offset_hex": f"0x{clean_offset:08x}",
                            "cleaning_rule": cleaning_rule,
                            "range_start": str(range_start),
                            "range_start_hex": f"0x{range_start:08x}",
                            "range_end": str(range_end),
                            "range_end_hex": f"0x{range_end:08x}",
                            "range_label": range_label,
                            "context_before_hex": payload[context_start:offset].hex(),
                            "context_after_hex": payload[text_end_offset:context_end].hex(),
                            "le32_before_text": format_nearby_le32(
                                payload,
                                offset,
                                [-32, -28, -24, -20, -16, -12, -8, -4],
                            ),
                            "le32_after_text": format_nearby_le32(
                                payload,
                                text_end_offset,
                                [0, 4, 8, 12, 16, 20, 24, 28],
                            ),
                        }
                    )

                for range_index, (range_start, range_label) in enumerate(boundaries[:-1]):
                    range_end = boundaries[range_index + 1][0]
                    stats = range_stats[range_start]
                    rules = stats["rules"]
                    examples = stats["examples"]
                    material_range_rows.append(
                        {
                            "archive": str(archive),
                            "entry_index": str(entry_index),
                            "file_id": f"{file_id:08x}",
                            "range_index": str(range_index),
                            "range_start": str(range_start),
                            "range_start_hex": f"0x{range_start:08x}",
                            "range_end": str(range_end),
                            "range_end_hex": f"0x{range_end:08x}",
                            "range_size": str(range_end - range_start),
                            "range_label": range_label,
                            "string_count": str(stats["count"]),
                            "cleaned_string_count": str(stats["cleaned_count"]),
                            "cleaning_rules": (
                                ";".join(
                                    f"{rule}:{count}"
                                    for rule, count in sorted(rules.items())
                                )
                                if isinstance(rules, Counter)
                                else ""
                            ),
                            "sample_clean_text": (
                                "|".join(str(example) for example in examples)
                                if isinstance(examples, list)
                                else ""
                            ),
                        }
                    )

    return entry_rows, material_string_rows, material_section_rows, material_range_rows


def find_pcx_references(payload: bytes, context_bytes: int = 32) -> list[dict[str, object]]:
    references: list[dict[str, object]] = []
    for match in re.finditer(PCX_NAME_PATTERN, payload, re.IGNORECASE):
        name = match.group().decode("ascii", errors="replace")
        base_name = name.replace("\\", "/").rsplit("/", 1)[-1]
        previous_nul = payload.rfind(b"\0", 0, match.start())
        next_nul = payload.find(b"\0", match.end())
        nearest_project = find_nearest_before(
            payload,
            (b"F:\\PROJECTS", b"f:\\PROJECTS"),
            match.start(),
            128,
        )
        nearest_wallseh = find_nearest_before(payload, (b"WALLSEH",), match.start(), 64)
        wallseh_to_name = b""
        source_root = ""
        source_control_hex = ""
        reconstructed_source_path = ""
        if nearest_wallseh >= 0:
            wallseh_end = nearest_wallseh + len(b"WALLSEH")
            wallseh_to_name = payload[wallseh_end : match.start()]
            if nearest_project >= 0 and nearest_project < nearest_wallseh:
                source_root = payload[nearest_project:wallseh_end].decode(
                    "ascii",
                    errors="replace",
                )
                source_control_hex = wallseh_to_name.hex()
                reconstructed_source_path = f"{source_root}\\{name}"
        reference_class, confidence = classify_pcx_reference(
            name,
            base_name,
            base_name.lower() == "palette.pcx",
            next_nul == match.end(),
        )
        context_start = max(0, match.start() - context_bytes)
        context_end = min(len(payload), match.end() + context_bytes)
        references.append(
            {
                "name": name,
                "base_name": base_name,
                "is_palette": base_name.lower() == "palette.pcx",
                "name_offset": match.start(),
                "name_end_offset": match.end(),
                "previous_nul_offset": previous_nul,
                "next_nul_offset": next_nul,
                "byte_before_name": format_byte(payload, match.start() - 1),
                "byte_after_name": format_byte(payload, match.end()),
                "reference_class": reference_class,
                "confidence": confidence,
                "nearest_project_offset": nearest_project,
                "nearest_project_distance": (
                    match.start() - nearest_project if nearest_project >= 0 else ""
                ),
                "nearest_wallseh_offset": nearest_wallseh,
                "nearest_wallseh_distance": (
                    match.start() - nearest_wallseh if nearest_wallseh >= 0 else ""
                ),
                "wallseh_to_name_hex": wallseh_to_name.hex(),
                "source_root": source_root,
                "source_control_hex": source_control_hex,
                "reconstructed_source_path": reconstructed_source_path,
                "context_before_hex": payload[context_start : match.start()].hex(),
                "context_after_hex": payload[match.end() : context_end].hex(),
                "le32_before_name": format_nearby_le32(
                    payload,
                    match.start(),
                    [-32, -28, -24, -20, -16, -12, -8, -4],
                ),
                "le32_after_name": format_nearby_le32(
                    payload,
                    match.end(),
                    [0, 4, 8, 12, 16, 20, 24, 28],
                ),
            }
        )
    return references


def count_embedded_pcx(payload: bytes) -> tuple[int, int]:
    signature_count = 0
    readable_count = 0
    for signature in (b"\x0a\x05\x01\x08", b"\x0a\x00\x01\x08"):
        for match in re.finditer(re.escape(signature), payload):
            signature_count += 1
            try:
                with Image.open(io.BytesIO(payload[match.start() :])) as image:
                    image.load()
                readable_count += 1
            except Exception:
                pass
    return signature_count, readable_count


def build_pcx_signature_rows(
    texture_path: str,
    archive: Path,
    texture_file_id: str,
    payload: bytes,
    context_bytes: int = 32,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    signature_index = 0
    for signature in (b"\x0a\x05\x01\x08", b"\x0a\x00\x01\x08"):
        for match in re.finditer(re.escape(signature), payload):
            offset = match.start()
            xmin = ymin = xmax = ymax = width = height = ""
            if offset + 12 <= len(payload):
                xmin_value, ymin_value, xmax_value, ymax_value = struct.unpack_from(
                    "<HHHH",
                    payload,
                    offset + 4,
                )
                xmin = str(xmin_value)
                ymin = str(ymin_value)
                xmax = str(xmax_value)
                ymax = str(ymax_value)
                width = str(xmax_value - xmin_value + 1) if xmax_value >= xmin_value else ""
                height = str(ymax_value - ymin_value + 1) if ymax_value >= ymin_value else ""

            pil_readable = "False"
            try:
                with Image.open(io.BytesIO(payload[offset:])) as image:
                    image.load()
                pil_readable = "True"
            except Exception:
                pass

            context_start = max(0, offset - context_bytes)
            context_end = min(len(payload), offset + len(signature) + context_bytes)
            rows.append(
                {
                    "texture_path": texture_path,
                    "archive": str(archive),
                    "texture_entry_index": "2",
                    "texture_file_id": texture_file_id,
                    "signature_index": str(signature_index),
                    "signature_offset": str(offset),
                    "signature_offset_hex": f"0x{offset:08x}",
                    "signature": signature.hex(),
                    "pcx_version": str(payload[offset + 1]) if offset + 1 < len(payload) else "",
                    "pcx_encoding": str(payload[offset + 2]) if offset + 2 < len(payload) else "",
                    "pcx_bits_per_pixel": str(payload[offset + 3]) if offset + 3 < len(payload) else "",
                    "xmin": xmin,
                    "ymin": ymin,
                    "xmax": xmax,
                    "ymax": ymax,
                    "width": width,
                    "height": height,
                    "pil_readable": pil_readable,
                    "context_before_hex": payload[context_start:offset].hex(),
                    "context_after_hex": payload[offset + len(signature) : context_end].hex(),
                }
            )
            signature_index += 1
    return rows


def scan_lcw_structure(payload: bytes, offset: int, expected_size: int) -> dict[str, str]:
    if offset < 0 or offset >= len(payload):
        return {
            "status": "offset_out_of_range",
            "output_size": "0",
            "input_consumed": "0",
            "note": "",
        }

    pos = offset
    output_size = 0

    def result(status: str, note: str = "") -> dict[str, str]:
        return {
            "status": status,
            "output_size": str(output_size),
            "input_consumed": str(pos - offset),
            "note": note,
        }

    def add_output(count: int) -> dict[str, str] | None:
        nonlocal output_size
        output_size += count
        if expected_size and output_size > expected_size:
            return result("overran_expected")
        return None

    while pos < len(payload):
        if expected_size and output_size == expected_size:
            if pos < len(payload) and payload[pos] == 0x80:
                pos += 1
                return result("end_at_expected")
            return result("reached_expected_without_end")

        command = payload[pos]
        pos += 1

        if command == 0x80:
            if expected_size and output_size == expected_size:
                return result("end_at_expected")
            return result("end_before_expected")

        if command == 0xFF:
            if pos + 3 > len(payload):
                return result("truncated_fill")
            count = payload[pos] | (payload[pos + 1] << 8)
            pos += 3
            overrun = add_output(count)
            if overrun:
                return overrun
            continue

        if command == 0xFE:
            if pos + 4 > len(payload):
                return result("truncated_long_copy")
            count = payload[pos] | (payload[pos + 1] << 8)
            source = payload[pos + 2] | (payload[pos + 3] << 8)
            pos += 4
            if source >= output_size:
                return result("invalid_long_copy_source", f"source={source}")
            overrun = add_output(count)
            if overrun:
                return overrun
            continue

        if (command & 0x80) == 0:
            if pos >= len(payload):
                return result("truncated_short_copy")
            count = ((command & 0x70) >> 4) + 3
            relative = ((command & 0x0F) << 8) | payload[pos]
            pos += 1
            if relative > output_size:
                return result("invalid_short_copy_source", f"relative={relative}")
            overrun = add_output(count)
            if overrun:
                return overrun
            continue

        if (command & 0x40) == 0:
            count = command & 0x3F
            if pos + count > len(payload):
                return result("truncated_literal")
            pos += count
            overrun = add_output(count)
            if overrun:
                return overrun
            continue

        if pos + 2 > len(payload):
            return result("truncated_absolute_copy")
        count = (command & 0x3F) + 3
        source = payload[pos] | (payload[pos + 1] << 8)
        pos += 2
        if source >= output_size:
            return result("invalid_absolute_copy_source", f"source={source}")
        overrun = add_output(count)
        if overrun:
            return overrun

    if expected_size and output_size == expected_size:
        return result("reached_expected_at_eof")
    return result("input_exhausted")


def scan_lcw_window_structure(payload: bytes, offset: int, expected_size: int) -> dict[str, str]:
    if offset < 0 or offset >= len(payload):
        return {
            "status": "offset_out_of_range",
            "output_size": "0",
            "input_consumed": "0",
            "note": "",
        }

    pos = offset
    output_size = 0

    def result(status: str, note: str = "") -> dict[str, str]:
        return {
            "status": status,
            "output_size": str(output_size),
            "input_consumed": str(pos - offset),
            "note": note,
        }

    def add_output(count: int) -> dict[str, str] | None:
        nonlocal output_size
        output_size += count
        if expected_size and output_size > expected_size:
            return result("overran_expected")
        return None

    while pos < len(payload):
        if expected_size and output_size == expected_size:
            if pos < len(payload) and payload[pos] == 0x80:
                pos += 1
                return result("end_at_expected")
            return result("reached_expected_without_end")

        command = payload[pos]
        pos += 1

        if command == 0x80:
            if expected_size and output_size == expected_size:
                return result("end_at_expected")
            return result("end_before_expected")

        if command == 0xFF:
            if pos < len(payload) and payload[pos] == 0x80 and pos + 1 == len(payload):
                return result("ff80_tail")
            if pos + 3 > len(payload):
                return result("truncated_fill")
            count = payload[pos] | (payload[pos + 1] << 8)
            pos += 3
            overrun = add_output(count)
            if overrun:
                return overrun
            continue

        if command == 0xFE:
            if pos + 4 > len(payload):
                return result("truncated_long_copy")
            count = payload[pos] | (payload[pos + 1] << 8)
            pos += 4
            overrun = add_output(count)
            if overrun:
                return overrun
            continue

        if (command & 0x80) == 0:
            if pos >= len(payload):
                return result("truncated_short_copy")
            count = ((command & 0x70) >> 4) + 3
            pos += 1
            overrun = add_output(count)
            if overrun:
                return overrun
            continue

        if (command & 0x40) == 0:
            count = command & 0x3F
            if pos + count > len(payload):
                available = len(payload) - pos
                output_size += available
                pos = len(payload)
                return result("literal_tail")
            pos += count
            overrun = add_output(count)
            if overrun:
                return overrun
            continue

        if pos + 2 > len(payload):
            return result("absolute_tail")
        count = (command & 0x3F) + 3
        pos += 2
        overrun = add_output(count)
        if overrun:
            return overrun

    if expected_size and output_size == expected_size:
        return result("reached_expected_at_eof")
    return result("input_exhausted")


def build_lcw_probe_rows(
    texture_path: str,
    archive: Path,
    texture_file_id: str,
    payload: bytes,
    expected_size: int,
    probe_offsets: list[int],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for probe_offset in probe_offsets:
        probe = scan_lcw_structure(payload, probe_offset, expected_size)
        window_probe = scan_lcw_window_structure(payload, probe_offset, expected_size)
        rows.append(
            {
                "texture_path": texture_path,
                "archive": str(archive),
                "texture_entry_index": "2",
                "texture_file_id": texture_file_id,
                "probe_offset": str(probe_offset),
                "probe_offset_hex": f"0x{probe_offset:08x}",
                "expected_size": str(expected_size),
                "status": probe["status"],
                "output_size": probe["output_size"],
                "input_consumed": probe["input_consumed"],
                "note": probe["note"],
                "window_status": window_probe["status"],
                "window_output_size": window_probe["output_size"],
                "window_input_consumed": window_probe["input_consumed"],
                "window_note": window_probe["note"],
            }
        )
    return rows


def build_header_row(
    texture_path: str,
    archive: Path,
    texture_file_id: str,
    payload: bytes,
    declared_size: int,
    payload_declared_size: int,
) -> dict[str, str]:
    prefix = payload[:HEADER_PREFIX_BYTES]
    lower_payload = payload.lower()
    palette_offset = lower_payload.find(b"palette.pcx")
    first_pcx_suffix_offset = lower_payload.find(b".pcx")

    project_offsets = find_all_offsets(payload, b"F:\\PROJECTS", 16)
    project_offsets.extend(find_all_offsets(payload, b"f:\\PROJECTS", 16))
    project_offsets.sort()

    sphere_offsets: list[int] = []
    for needle in (b"SPHERE1", b"SPHERE2", b"SPHERE3"):
        sphere_offsets.extend(find_all_offsets(payload, needle, 16))
    sphere_offsets.sort()

    texture_reference_name_offsets: list[int] = []
    for match in re.finditer(PCX_NAME_PATTERN, payload, re.IGNORECASE):
        base_name = match.group().decode("ascii", errors="replace")
        if base_name.lower() != "palette.pcx":
            texture_reference_name_offsets.append(match.start())
    first_texture_reference_name_offset = (
        min(texture_reference_name_offsets) if texture_reference_name_offsets else -1
    )

    marker_needles = {
        "common_0000f350": bytes.fromhex("0000f350"),
        "common_01007332": bytes.fromhex("01007332"),
        "common_a2095c02034b": bytes.fromhex("a2095c02034b"),
        "common_a2095c02044b": bytes.fromhex("a2095c02044b"),
        "common_8000e105": bytes.fromhex("8000e105"),
        "wallseh": b"WALLSEH",
    }
    marker_offsets = []
    for marker_name, marker in marker_needles.items():
        offsets = find_all_offsets(payload, marker, 8)
        if offsets:
            marker_offsets.append(f"{marker_name}:{format_offsets(offsets)}")

    header_variant = "unknown"
    common_0000f350 = payload.find(bytes.fromhex("0000f350"))
    if common_0000f350 >= 0:
        header_variant = f"common_marker_at_0x{common_0000f350:02x}"

    packed_ratio = f"{len(payload) / declared_size:.4f}" if declared_size else ""
    return {
        "texture_path": texture_path,
        "archive": str(archive),
        "texture_entry_index": "2",
        "texture_file_id": texture_file_id,
        "payload_size": str(len(payload)),
        "declared_size": str(declared_size),
        "payload_declared_size": str(payload_declared_size),
        "payload_header_minus_cache_declared": str(payload_declared_size - declared_size),
        "declared_size_minus_payload_size": str(declared_size - len(payload)),
        "packed_ratio": packed_ratio,
        "header_variant": header_variant,
        "palette_offset": format_offset(palette_offset),
        "palette_offset_hex": format_offset_hex(palette_offset),
        "first_pcx_suffix_offset": format_offset(first_pcx_suffix_offset),
        "first_texture_reference_name_offset": format_offset(first_texture_reference_name_offset),
        "first_source_path_offset": format_offset(project_offsets[0] if project_offsets else -1),
        "source_path_offsets": format_offsets(project_offsets),
        "sphere_path_offsets": format_offsets(sphere_offsets),
        "project_path_count": str(len(project_offsets)),
        "prefix_hex": prefix.hex(),
        "prefix_ascii": format_ascii(prefix),
        "le16_prefix": format_le16_words(prefix, 80),
        "le32_prefix": format_le32_words(prefix, 40),
        "marker_offsets": ";".join(marker_offsets),
    }


def build_reference_row(
    texture_path: str,
    archive: Path,
    texture_file_id: str,
    reference_index: int,
    reference: dict[str, object],
) -> dict[str, str]:
    name_offset = int(reference["name_offset"])
    return {
        "texture_path": texture_path,
        "archive": str(archive),
        "texture_entry_index": "2",
        "texture_file_id": texture_file_id,
        "reference_index": str(reference_index),
        "pcx_name": str(reference["name"]),
        "base_name": str(reference["base_name"]),
        "is_palette": str(reference["is_palette"]),
        "name_offset": str(name_offset),
        "name_offset_hex": f"0x{name_offset:08x}",
        "name_end_offset": str(reference["name_end_offset"]),
        "previous_nul_offset": str(reference["previous_nul_offset"]),
        "next_nul_offset": str(reference["next_nul_offset"]),
        "byte_before_name": str(reference["byte_before_name"]),
        "byte_after_name": str(reference["byte_after_name"]),
        "reference_class": str(reference["reference_class"]),
        "confidence": str(reference["confidence"]),
        "nearest_project_offset": format_offset(int(reference["nearest_project_offset"])),
        "nearest_project_distance": str(reference["nearest_project_distance"]),
        "nearest_wallseh_offset": format_offset(int(reference["nearest_wallseh_offset"])),
        "nearest_wallseh_distance": str(reference["nearest_wallseh_distance"]),
        "wallseh_to_name_hex": str(reference["wallseh_to_name_hex"]),
        "source_root": str(reference["source_root"]),
        "source_control_hex": str(reference["source_control_hex"]),
        "reconstructed_source_path": str(reference["reconstructed_source_path"]),
        "context_before_hex": str(reference["context_before_hex"]),
        "context_after_hex": str(reference["context_after_hex"]),
        "le32_before_name": str(reference["le32_before_name"]),
        "le32_after_name": str(reference["le32_after_name"]),
    }


def build_texture_string_cluster_rows(
    texture_path: str,
    archive: Path,
    texture_file_id: str,
    references: list[dict[str, object]],
    payload: bytes,
    context_bytes: int = 32,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    sorted_references = sorted(references, key=lambda reference: int(reference["name_offset"]))
    for reference_index, reference in enumerate(sorted_references):
        name_offset = int(reference["name_offset"])
        name_end_offset = int(reference["name_end_offset"])
        previous_nul = int(reference["previous_nul_offset"])
        next_nul = int(reference["next_nul_offset"])
        previous_reference_offset = (
            int(sorted_references[reference_index - 1]["name_offset"])
            if reference_index > 0
            else -1
        )
        next_reference_offset = (
            int(sorted_references[reference_index + 1]["name_offset"])
            if reference_index + 1 < len(sorted_references)
            else -1
        )
        post_terminator_offset = next_nul + 1 if next_nul >= 0 else name_end_offset
        rows.append(
            {
                "texture_path": texture_path,
                "archive": str(archive),
                "texture_entry_index": "2",
                "texture_file_id": texture_file_id,
                "reference_index": str(reference_index),
                "pcx_name": str(reference["name"]),
                "reference_class": str(reference["reference_class"]),
                "confidence": str(reference["confidence"]),
                "name_offset": str(name_offset),
                "name_offset_hex": f"0x{name_offset:08x}",
                "previous_reference_distance": (
                    str(name_offset - previous_reference_offset)
                    if previous_reference_offset >= 0
                    else ""
                ),
                "next_reference_distance": (
                    str(next_reference_offset - name_offset)
                    if next_reference_offset >= 0
                    else ""
                ),
                "previous_nul_delta": (
                    str(name_offset - previous_nul) if previous_nul >= 0 else ""
                ),
                "next_nul_delta": (
                    str(next_nul - name_end_offset) if next_nul >= 0 else ""
                ),
                "tag_byte": format_byte(payload, name_offset - 1),
                "name_length": str(name_end_offset - name_offset),
                "pre_name_hex": payload[
                    max(0, name_offset - context_bytes) : name_offset
                ].hex(),
                "post_terminator_hex": payload[
                    post_terminator_offset : min(len(payload), post_terminator_offset + context_bytes)
                ].hex(),
                "post_terminator_le32": format_nearby_le32(
                    payload,
                    post_terminator_offset,
                    [0, 4, 8, 12, 16, 20, 24, 28],
                ),
            }
        )
    return rows


def build_texture_segment_rows(
    texture_path: str,
    archive: Path,
    texture_file_id: str,
    references: list[dict[str, object]],
    payload: bytes,
    sample_bytes: int = 64,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    sorted_references = sorted(references, key=lambda reference: int(reference["name_offset"]))
    if not sorted_references:
        sorted_references = [
            {
                "name_offset": 0,
                "name_end_offset": 0,
                "next_nul_offset": -1,
                "name": "",
                "reference_class": "payload",
                "confidence": "",
            }
        ]

    if int(sorted_references[0]["name_offset"]) > 0:
        segment = payload[: int(sorted_references[0]["name_offset"])]
        counts = Counter(segment)
        rows.append(
            {
                "texture_path": texture_path,
                "archive": str(archive),
                "texture_entry_index": "2",
                "texture_file_id": texture_file_id,
                "segment_index": "0",
                "segment_start": "0",
                "segment_start_hex": "0x00000000",
                "segment_end": str(int(sorted_references[0]["name_offset"])),
                "segment_end_hex": f"0x{int(sorted_references[0]['name_offset']):08x}",
                "segment_size": str(len(segment)),
                "reference_index": "",
                "pcx_name": "",
                "reference_class": "prefix",
                "confidence": "",
                "tag_byte": "",
                "body_offset": "",
                "body_offset_hex": "",
                "body_first_byte": "",
                "body_first_word": "",
                "body_head_hex": "",
                "body_head_ascii": "",
                "post_terminator_size": "",
                "body_lcw_status": "",
                "body_lcw_output_size": "",
                "body_lcw_input_consumed": "",
                "body_window_status": "",
                "body_window_output_size": "",
                "body_window_input_consumed": "",
                "entropy": f"{shannon_entropy(segment):.4f}",
                "zero_ratio": f"{counts[0] / len(segment):.6f}" if segment else "",
                "ff_ratio": f"{counts[0xFF] / len(segment):.6f}" if segment else "",
                "printable_ratio": (
                    f"{sum(32 <= byte < 127 for byte in segment) / len(segment):.6f}"
                    if segment
                    else ""
                ),
                "head_hex": segment[:sample_bytes].hex(),
                "head_ascii": format_ascii(segment[:sample_bytes]),
            }
        )

    output_index = len(rows)
    for reference_index, reference in enumerate(sorted_references):
        segment_start = int(reference["name_offset"])
        segment_end = (
            int(sorted_references[reference_index + 1]["name_offset"])
            if reference_index + 1 < len(sorted_references)
            else len(payload)
        )
        segment = payload[segment_start:segment_end]
        counts = Counter(segment)
        next_nul = int(reference["next_nul_offset"])
        body_offset = next_nul + 1 if next_nul >= 0 else int(reference["name_end_offset"])
        body_head = payload[body_offset : min(len(payload), body_offset + sample_bytes)]
        post_terminator_size = (
            max(0, segment_end - next_nul - 1) if next_nul >= 0 else ""
        )
        body_lcw_probe = scan_lcw_structure(payload, body_offset, 0)
        body_window_probe = scan_lcw_window_structure(payload, body_offset, 0)
        rows.append(
            {
                "texture_path": texture_path,
                "archive": str(archive),
                "texture_entry_index": "2",
                "texture_file_id": texture_file_id,
                "segment_index": str(output_index),
                "segment_start": str(segment_start),
                "segment_start_hex": f"0x{segment_start:08x}",
                "segment_end": str(segment_end),
                "segment_end_hex": f"0x{segment_end:08x}",
                "segment_size": str(len(segment)),
                "reference_index": str(reference_index),
                "pcx_name": str(reference["name"]),
                "reference_class": str(reference["reference_class"]),
                "confidence": str(reference["confidence"]),
                "tag_byte": format_byte(payload, segment_start - 1),
                "body_offset": str(body_offset),
                "body_offset_hex": f"0x{body_offset:08x}",
                "body_first_byte": format_byte(payload, body_offset),
                "body_first_word": (
                    f"{read_u32(payload, body_offset):08x}"
                    if body_offset + 4 <= len(payload)
                    else ""
                ),
                "body_head_hex": body_head.hex(),
                "body_head_ascii": format_ascii(body_head),
                "post_terminator_size": str(post_terminator_size),
                "body_lcw_status": body_lcw_probe["status"],
                "body_lcw_output_size": body_lcw_probe["output_size"],
                "body_lcw_input_consumed": body_lcw_probe["input_consumed"],
                "body_window_status": body_window_probe["status"],
                "body_window_output_size": body_window_probe["output_size"],
                "body_window_input_consumed": body_window_probe["input_consumed"],
                "entropy": f"{shannon_entropy(segment):.4f}",
                "zero_ratio": f"{counts[0] / len(segment):.6f}" if segment else "",
                "ff_ratio": f"{counts[0xFF] / len(segment):.6f}" if segment else "",
                "printable_ratio": (
                    f"{sum(32 <= byte < 127 for byte in segment) / len(segment):.6f}"
                    if segment
                    else ""
                ),
                "head_hex": segment[:sample_bytes].hex(),
                "head_ascii": format_ascii(segment[:sample_bytes]),
            }
        )
        output_index += 1

    return rows


def build_texture_body_prefix_rows(
    segment_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    groups: dict[tuple[str, str, str, str], dict[str, object]] = {}
    for row in segment_rows:
        if row["reference_class"] == "prefix":
            continue
        key = (
            row["reference_class"],
            row["confidence"],
            row["body_first_byte"],
            row["body_first_word"],
        )
        group = groups.setdefault(
            key,
            {
                "count": 0,
                "total_segment_size": 0,
                "min_segment_size": None,
                "max_segment_size": None,
                "total_entropy": 0.0,
                "sample_names": [],
                "sample_archives": [],
            },
        )
        segment_size = int(row["segment_size"])
        entropy = float(row["entropy"]) if row["entropy"] else 0.0
        group["count"] = int(group["count"]) + 1
        group["total_segment_size"] = int(group["total_segment_size"]) + segment_size
        min_segment_size = group["min_segment_size"]
        max_segment_size = group["max_segment_size"]
        group["min_segment_size"] = (
            segment_size
            if min_segment_size is None
            else min(int(min_segment_size), segment_size)
        )
        group["max_segment_size"] = (
            segment_size
            if max_segment_size is None
            else max(int(max_segment_size), segment_size)
        )
        group["total_entropy"] = float(group["total_entropy"]) + entropy
        sample_names = group["sample_names"]
        if isinstance(sample_names, list) and len(sample_names) < 10:
            sample_names.append(row["pcx_name"])
        sample_archives = group["sample_archives"]
        if isinstance(sample_archives, list) and row["archive"] not in sample_archives:
            if len(sample_archives) < 10:
                sample_archives.append(row["archive"])

    rows: list[dict[str, str]] = []
    for key, group in sorted(
        groups.items(),
        key=lambda item: (
            str(item[0][0]),
            str(item[0][1]),
            -int(item[1]["count"]),
            str(item[0][3]),
        ),
    ):
        reference_class, confidence, body_first_byte, body_first_word = key
        count = int(group["count"])
        total_segment_size = int(group["total_segment_size"])
        rows.append(
            {
                "reference_class": reference_class,
                "confidence": confidence,
                "body_first_byte": body_first_byte,
                "body_first_word": body_first_word,
                "count": str(count),
                "total_segment_size": str(total_segment_size),
                "min_segment_size": str(group["min_segment_size"]),
                "max_segment_size": str(group["max_segment_size"]),
                "avg_segment_size": f"{total_segment_size / count:.2f}" if count else "",
                "avg_entropy": f"{float(group['total_entropy']) / count:.4f}" if count else "",
                "sample_names": "|".join(str(name) for name in group["sample_names"]),
                "sample_archives": "|".join(str(archive) for archive in group["sample_archives"]),
            }
        )
    return rows


def build_texture_archive_summary_rows(
    manifest_rows: list[dict[str, str]],
    segment_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    segments_by_archive: dict[str, list[dict[str, str]]] = {}
    for segment_row in segment_rows:
        segments_by_archive.setdefault(segment_row["archive"], []).append(segment_row)

    rows: list[dict[str, str]] = []
    for manifest_row in manifest_rows:
        archive = manifest_row["archive"]
        segments = segments_by_archive.get(archive, [])
        payload_size = int(manifest_row["payload_size"])
        declared_size = int(manifest_row["declared_size"])
        payload_declared_size = int(manifest_row["payload_declared_size"])
        segment_total_size = sum(int(row["segment_size"]) for row in segments)
        body_total_size = sum(
            int(row["post_terminator_size"])
            for row in segments
            if row["post_terminator_size"]
        )
        likely_segment_size = sum(
            int(row["segment_size"])
            for row in segments
            if row["confidence"] in {"high", "medium"}
        )
        low_confidence_segment_size = sum(
            int(row["segment_size"])
            for row in segments
            if row["confidence"] == "low"
        )
        entropy_values = [float(row["entropy"]) for row in segments if row["entropy"]]
        prefix_sizes: dict[str, int] = {}
        prefix_counts: Counter[str] = Counter()
        for row in segments:
            if row["reference_class"] == "prefix":
                continue
            prefix = row["body_first_word"]
            prefix_counts[prefix] += 1
            prefix_sizes[prefix] = prefix_sizes.get(prefix, 0) + int(row["segment_size"])
        top_prefix = ""
        if prefix_sizes:
            top_prefix = max(prefix_sizes, key=lambda prefix: prefix_sizes[prefix])
        rows.append(
            {
                "texture_path": manifest_row["texture_path"],
                "archive": archive,
                "payload_size": str(payload_size),
                "declared_size": str(declared_size),
                "payload_declared_size": str(payload_declared_size),
                "declared_to_payload_ratio": (
                    f"{declared_size / payload_size:.4f}" if payload_size else ""
                ),
                "payload_declared_to_payload_ratio": (
                    f"{payload_declared_size / payload_size:.4f}" if payload_size else ""
                ),
                "segment_count": str(len(segments)),
                "segment_total_size": str(segment_total_size),
                "body_total_size": str(body_total_size),
                "likely_segment_size": str(likely_segment_size),
                "low_confidence_segment_size": str(low_confidence_segment_size),
                "avg_segment_entropy": (
                    f"{sum(entropy_values) / len(entropy_values):.4f}"
                    if entropy_values
                    else ""
                ),
                "top_body_first_word": top_prefix,
                "top_body_first_word_count": str(prefix_counts[top_prefix]) if top_prefix else "",
                "top_body_first_word_size": str(prefix_sizes[top_prefix]) if top_prefix else "",
            }
        )

    return rows


def normalize_asset_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def build_material_texture_match_rows(
    reference_summary_rows: list[dict[str, str]],
    material_string_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    materials_by_archive: dict[str, list[dict[str, str]]] = {}
    for material_row in material_string_rows:
        if material_row["name_confidence"] not in {"high", "medium"}:
            continue
        normalized_material = normalize_asset_name(material_row["clean_text"])
        if len(normalized_material) < 4:
            continue
        row_copy = dict(material_row)
        row_copy["normalized_material"] = normalized_material
        materials_by_archive.setdefault(material_row["archive"], []).append(row_copy)

    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for reference_row in reference_summary_rows:
        archive = reference_row["archive"]
        materials = materials_by_archive.get(archive, [])
        for pcx_name in (name for name in reference_row["likely_texture_names"].split(";") if name):
            pcx_stem = pcx_name.rsplit(".", 1)[0]
            normalized_pcx = normalize_asset_name(pcx_stem)
            if len(normalized_pcx) < 4:
                continue
            for material_row in materials:
                normalized_material = material_row["normalized_material"]
                match_type = ""
                if normalized_pcx == normalized_material:
                    match_type = "exact_normalized"
                elif normalized_pcx in normalized_material:
                    match_type = "pcx_in_material"
                elif normalized_material in normalized_pcx:
                    match_type = "material_in_pcx"
                if not match_type:
                    continue
                key = (
                    archive,
                    pcx_name,
                    material_row["clean_text"],
                    material_row["offset"],
                )
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "archive": archive,
                        "pcx_name": pcx_name,
                        "pcx_stem": pcx_stem,
                        "material_clean_text": material_row["clean_text"],
                        "material_offset": material_row["offset"],
                        "material_offset_hex": material_row["offset_hex"],
                        "material_range_label": material_row["range_label"],
                        "material_name_class": material_row["name_class"],
                        "material_name_confidence": material_row["name_confidence"],
                        "match_type": match_type,
                        "normalized_pcx": normalized_pcx,
                        "normalized_material": normalized_material,
                    }
                )
    return rows


def build_material_sequence_reports(
    material_string_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    groups: dict[tuple[str, str, str, str], list[dict[str, str]]] = {}
    for row in material_string_rows:
        if row["name_confidence"] not in {"high", "medium"}:
            continue
        groups.setdefault(
            (
                row["archive"],
                row["entry_index"],
                row["file_id"],
                row["range_label"],
            ),
            [],
        ).append(row)

    sequence_rows: list[dict[str, str]] = []
    stride_rows: list[dict[str, str]] = []
    for (archive, entry_index, file_id, range_label), rows in sorted(groups.items()):
        rows = sorted(rows, key=lambda row: int(row["clean_offset"]))
        distances = [
            int(next_row["clean_offset"]) - int(current_row["clean_offset"])
            for current_row, next_row in zip(rows, rows[1:])
        ]
        distance_counts = Counter(distances)
        dominant_distance = distance_counts.most_common(1)[0][0] if distance_counts else 0
        for sequence_index, (current_row, next_row) in enumerate(zip(rows, rows[1:])):
            distance = int(next_row["clean_offset"]) - int(current_row["clean_offset"])
            sequence_rows.append(
                {
                    "archive": archive,
                    "entry_index": entry_index,
                    "file_id": file_id,
                    "range_label": range_label,
                    "sequence_index": str(sequence_index),
                    "current_offset": current_row["clean_offset"],
                    "current_offset_hex": current_row["clean_offset_hex"],
                    "current_clean_text": current_row["clean_text"],
                    "current_name_class": current_row["name_class"],
                    "current_name_confidence": current_row["name_confidence"],
                    "next_offset": next_row["clean_offset"],
                    "next_offset_hex": next_row["clean_offset_hex"],
                    "next_clean_text": next_row["clean_text"],
                    "next_name_class": next_row["name_class"],
                    "next_name_confidence": next_row["name_confidence"],
                    "distance": str(distance),
                    "dominant_distance": str(dominant_distance) if dominant_distance else "",
                    "matches_dominant_distance": str(distance == dominant_distance)
                    if dominant_distance
                    else "",
                }
            )
        sequence_count = max(0, len(rows) - 1)
        top_distances = ";".join(
            f"{distance}:{count}" for distance, count in distance_counts.most_common(12)
        )
        stride_rows.append(
            {
                "archive": archive,
                "entry_index": entry_index,
                "file_id": file_id,
                "range_label": range_label,
                "string_count": str(len(rows)),
                "sequence_count": str(sequence_count),
                "top_distance": str(dominant_distance) if dominant_distance else "",
                "top_distance_count": str(distance_counts[dominant_distance])
                if dominant_distance
                else "",
                "top_distance_ratio": (
                    f"{distance_counts[dominant_distance] / sequence_count:.4f}"
                    if dominant_distance and sequence_count
                    else ""
                ),
                "top_distances": top_distances,
            }
        )

    return sequence_rows, stride_rows


def build_material_record_candidate_rows(
    material_string_rows: list[dict[str, str]],
    material_stride_rows: list[dict[str, str]],
    material_texture_match_rows: list[dict[str, str]],
    min_stride_ratio: float = 0.9,
    min_sequence_count: int = 5,
) -> list[dict[str, str]]:
    payload_cache: dict[tuple[str, int], bytes] = {}

    def material_payload(archive: str, entry_index: int) -> bytes:
        key = (archive, entry_index)
        if key not in payload_cache:
            entry = read_mix_entry(Path(archive), entry_index)
            payload_cache[key] = entry[1] if entry is not None else b""
        return payload_cache[key]

    stride_by_group: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for stride_row in material_stride_rows:
        if not stride_row["top_distance"] or not stride_row["top_distance_ratio"]:
            continue
        if int(stride_row["sequence_count"]) < min_sequence_count:
            continue
        if float(stride_row["top_distance_ratio"]) < min_stride_ratio:
            continue
        stride_by_group[
            (
                stride_row["archive"],
                stride_row["entry_index"],
                stride_row["file_id"],
                stride_row["range_label"],
            )
        ] = stride_row

    matches_by_material: dict[tuple[str, str], list[dict[str, str]]] = {}
    for match_row in material_texture_match_rows:
        matches_by_material.setdefault(
            (match_row["archive"], match_row["material_offset"]),
            [],
        ).append(match_row)

    strings_by_group: dict[tuple[str, str, str, str], list[dict[str, str]]] = {}
    for string_row in material_string_rows:
        if string_row["name_confidence"] not in {"high", "medium"}:
            continue
        group_key = (
            string_row["archive"],
            string_row["entry_index"],
            string_row["file_id"],
            string_row["range_label"],
        )
        if group_key not in stride_by_group:
            continue
        strings_by_group.setdefault(group_key, []).append(string_row)

    rows: list[dict[str, str]] = []
    for group_key, string_rows in sorted(strings_by_group.items()):
        archive, entry_index, file_id, range_label = group_key
        stride_row = stride_by_group[group_key]
        record_size = int(stride_row["top_distance"])
        payload = material_payload(archive, int(entry_index))
        sorted_string_rows = sorted(string_rows, key=lambda row: int(row["clean_offset"]))
        for record_index, string_row in enumerate(sorted_string_rows):
            record_start = int(string_row["clean_offset"])
            record_end = record_start + record_size
            next_record_start = (
                int(sorted_string_rows[record_index + 1]["clean_offset"])
                if record_index + 1 < len(sorted_string_rows)
                else -1
            )
            next_distance = (
                next_record_start - record_start if next_record_start >= 0 else -1
            )
            record = payload[record_start:record_end] if record_end <= len(payload) else b""
            raw_offset = int(string_row["offset"])
            prefix_delta = record_start - raw_offset
            matches = matches_by_material.get((archive, string_row["offset"]), [])
            rows.append(
                {
                    "archive": archive,
                    "entry_index": entry_index,
                    "file_id": file_id,
                    "range_label": range_label,
                    "record_index": str(record_index),
                    "record_size": str(record_size),
                    "stride_ratio": stride_row["top_distance_ratio"],
                    "record_start": str(record_start),
                    "record_start_hex": f"0x{record_start:08x}",
                    "record_end": str(record_end),
                    "record_end_hex": f"0x{record_end:08x}",
                    "next_record_start": str(next_record_start) if next_record_start >= 0 else "",
                    "next_record_start_hex": (
                        f"0x{next_record_start:08x}" if next_record_start >= 0 else ""
                    ),
                    "next_distance": str(next_distance) if next_distance >= 0 else "",
                    "matches_stride": (
                        str(next_distance == record_size) if next_distance >= 0 else ""
                    ),
                    "record_fits_payload": str(record_end <= len(payload)),
                    "source_string_index": string_row["string_index"],
                    "raw_offset": string_row["offset"],
                    "raw_offset_hex": string_row["offset_hex"],
                    "clean_text": string_row["clean_text"],
                    "name_class": string_row["name_class"],
                    "name_confidence": string_row["name_confidence"],
                    "prefix_delta": str(prefix_delta),
                    "matched_pcx_names": ";".join(match["pcx_name"] for match in matches),
                    "matched_pcx_match_types": ";".join(
                        match["match_type"] for match in matches
                    ),
                    "record_hex": record.hex(),
                    "record_ascii": format_ascii(record),
                    "record_le16": format_le16_words(record, max(0, record_size // 2)),
                    "record_le32": format_le32_words(record, max(0, record_size // 4)),
                }
            )

    return rows


def build_material_record_profile_rows(
    material_record_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    groups: dict[tuple[str, str, str, str, str], list[dict[str, str]]] = {}
    for row in material_record_rows:
        groups.setdefault(
            (
                row["archive"],
                row["entry_index"],
                row["file_id"],
                row["range_label"],
                row["record_size"],
            ),
            [],
        ).append(row)

    rows: list[dict[str, str]] = []
    for (archive, entry_index, file_id, range_label, record_size), records in sorted(
        groups.items()
    ):
        suffix_8 = Counter()
        suffix_12 = Counter()
        suffix_16 = Counter()
        name_classes = Counter()
        prefix_deltas = Counter()
        sample_texts: list[str] = []
        matched_pcx_names: list[str] = []
        for record in records:
            record_bytes = bytes.fromhex(record["record_hex"])
            suffix_8[record_bytes[-8:].hex() if len(record_bytes) >= 8 else ""] += 1
            suffix_12[record_bytes[-12:].hex() if len(record_bytes) >= 12 else ""] += 1
            suffix_16[record_bytes[-16:].hex() if len(record_bytes) >= 16 else ""] += 1
            name_classes[record["name_class"]] += 1
            prefix_deltas[record["prefix_delta"]] += 1
            if len(sample_texts) < 12:
                sample_texts.append(record["clean_text"])
            for pcx_name in (name for name in record["matched_pcx_names"].split(";") if name):
                if pcx_name not in matched_pcx_names and len(matched_pcx_names) < 20:
                    matched_pcx_names.append(pcx_name)

        top_suffix_8, top_suffix_8_count = suffix_8.most_common(1)[0]
        top_suffix_12, top_suffix_12_count = suffix_12.most_common(1)[0]
        top_suffix_16, top_suffix_16_count = suffix_16.most_common(1)[0]
        matching_stride_count = sum(
            1 for record in records if record["matches_stride"] == "True"
        )
        rows.append(
            {
                "archive": archive,
                "entry_index": entry_index,
                "file_id": file_id,
                "range_label": range_label,
                "record_size": record_size,
                "record_count": str(len(records)),
                "matching_stride_count": str(matching_stride_count),
                "matching_stride_ratio": f"{matching_stride_count / len(records):.4f}"
                if records
                else "",
                "matched_record_count": str(
                    sum(1 for record in records if record["matched_pcx_names"])
                ),
                "name_class_counts": ";".join(
                    f"{name_class}:{count}"
                    for name_class, count in name_classes.most_common()
                ),
                "prefix_delta_counts": ";".join(
                    f"{prefix_delta}:{count}"
                    for prefix_delta, count in prefix_deltas.most_common()
                ),
                "top_suffix_8_hex": top_suffix_8,
                "top_suffix_8_count": str(top_suffix_8_count),
                "top_suffix_12_hex": top_suffix_12,
                "top_suffix_12_count": str(top_suffix_12_count),
                "top_suffix_16_hex": top_suffix_16,
                "top_suffix_16_count": str(top_suffix_16_count),
                "sample_texts": "|".join(sample_texts),
                "matched_pcx_names": ";".join(matched_pcx_names),
            }
        )

    return rows


def format_top_values(values: Counter[int], width: int, limit: int = 8) -> str:
    return ";".join(
        f"0x{value:0{width * 2}x}:{count}"
        for value, count in values.most_common(limit)
    )


def read_int_le(data: bytes, offset: int, width: int) -> int:
    return int.from_bytes(data[offset : offset + width], "little")


def build_texture_segment_head_profile_rows(
    texture_segment_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    groups: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in texture_segment_rows:
        if row["reference_class"] == "prefix" or not row["body_head_hex"]:
            continue
        groups.setdefault(
            (
                row["reference_class"],
                row["confidence"],
                row["body_first_word"],
            ),
            [],
        ).append(row)

    rows: list[dict[str, str]] = []
    for (reference_class, confidence, body_first_word), segments in sorted(
        groups.items()
    ):
        head_bytes = [bytes.fromhex(segment["body_head_hex"]) for segment in segments]
        sample_names: list[str] = []
        sample_archives: list[str] = []
        for segment in segments:
            if len(sample_names) < 12:
                sample_names.append(segment["pcx_name"])
            if segment["archive"] not in sample_archives and len(sample_archives) < 12:
                sample_archives.append(segment["archive"])
        max_len = max((len(head) for head in head_bytes), default=0)
        for width in (1, 2, 4):
            step = 1 if width == 1 else 2
            for offset in range(0, max(0, max_len - width + 1), step):
                values = Counter(
                    read_int_le(head, offset, width)
                    for head in head_bytes
                    if offset + width <= len(head)
                )
                if not values:
                    continue
                total = sum(values.values())
                nonzero_count = total - values.get(0, 0)
                constant_value = next(iter(values)) if len(values) == 1 else None
                rows.append(
                    {
                        "reference_class": reference_class,
                        "confidence": confidence,
                        "body_first_word": body_first_word,
                        "field_width": str(width),
                        "field_offset": str(offset),
                        "field_offset_hex": f"0x{offset:02x}",
                        "segment_count": str(total),
                        "nonzero_count": str(nonzero_count),
                        "nonzero_ratio": f"{nonzero_count / total:.4f}" if total else "",
                        "unique_count": str(len(values)),
                        "constant_value_hex": (
                            f"0x{constant_value:0{width * 2}x}"
                            if constant_value is not None
                            else ""
                        ),
                        "top_values_hex": format_top_values(values, width),
                        "sample_names": "|".join(sample_names),
                        "sample_archives": "|".join(sample_archives),
                    }
                )

    return rows


def build_texture_payload_header_profile_rows(
    header_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    groups: dict[str, list[dict[str, str]]] = {"all": header_rows}
    for row in header_rows:
        groups.setdefault(row["header_variant"], []).append(row)

    rows: list[dict[str, str]] = []
    for header_group, rows_in_group in sorted(groups.items()):
        payload_headers = [
            bytes.fromhex(row["prefix_hex"])
            for row in rows_in_group
            if row["prefix_hex"]
        ]
        sample_archives: list[str] = []
        for row in rows_in_group:
            if row["archive"] not in sample_archives and len(sample_archives) < 15:
                sample_archives.append(row["archive"])
        max_len = max((len(header) for header in payload_headers), default=0)
        for width in (1, 2, 4):
            step = 1 if width == 1 else 2
            for offset in range(0, max(0, max_len - width + 1), step):
                values = Counter(
                    read_int_le(header, offset, width)
                    for header in payload_headers
                    if offset + width <= len(header)
                )
                if not values:
                    continue
                total = sum(values.values())
                nonzero_count = total - values.get(0, 0)
                constant_value = next(iter(values)) if len(values) == 1 else None
                rows.append(
                    {
                        "header_group": header_group,
                        "field_width": str(width),
                        "field_offset": str(offset),
                        "field_offset_hex": f"0x{offset:02x}",
                        "payload_count": str(total),
                        "nonzero_count": str(nonzero_count),
                        "nonzero_ratio": f"{nonzero_count / total:.4f}" if total else "",
                        "unique_count": str(len(values)),
                        "constant_value_hex": (
                            f"0x{constant_value:0{width * 2}x}"
                            if constant_value is not None
                            else ""
                        ),
                        "top_values_hex": format_top_values(values, width),
                        "sample_archives": "|".join(sample_archives),
                    }
                )

    return rows


def build_palette_candidate_rows(game_dir: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    candidate_sizes = {768, 769, 1024, 1536}
    for archive in sorted(game_dir.glob("*.MIX")):
        try:
            entries = read_mix_entries(archive)
        except (OSError, struct.error):
            continue
        for entry_index, file_id, body_offset, size, payload in entries:
            if size not in candidate_sizes or len(payload) < 768:
                continue
            palette = payload[:768]
            rows.append(
                {
                    "archive": str(archive),
                    "entry_index": str(entry_index),
                    "file_id": f"{file_id:08x}",
                    "body_offset": str(body_offset),
                    "size": str(size),
                    "palette_bytes": "768",
                    "max_value": str(max(palette)),
                    "unique_values": str(len(set(palette))),
                    "vga_6bit_candidate": str(max(palette) <= 63),
                    "head_hex": palette[:32].hex(),
                }
            )
    return rows


def build_cdcache_raw_reference_rows(
    cache_mix: Path,
    reference_summary_rows: list[dict[str, str]],
    context_bytes: int = 32,
) -> list[dict[str, str]]:
    if not cache_mix.exists():
        return []

    archives_by_base_name: dict[str, set[str]] = {}
    for row in reference_summary_rows:
        names = [
            *[name for name in row["likely_texture_names"].split(";") if name],
            *[
                name.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
                for name in row["source_path_names"].split(";")
                if name
            ],
        ]
        for name in names:
            archives_by_base_name.setdefault(name.lower(), set()).add(row["archive"])

    allowed = set(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_:\\./-")
    data = cache_mix.read_bytes()
    lower = data.lower()
    rows: list[dict[str, str]] = []
    seen_offsets: set[int] = set()
    suffix = b".pcx"
    search_offset = 0
    while True:
        suffix_offset = lower.find(suffix, search_offset)
        if suffix_offset < 0:
            break
        name_end = suffix_offset + len(suffix)
        name_start = suffix_offset - 1
        while name_start >= 0 and data[name_start] in allowed:
            name_start -= 1
        name_start += 1
        search_offset = suffix_offset + 1
        if name_start in seen_offsets or name_end - name_start < 5:
            continue
        if name_end - name_start > 160:
            continue
        seen_offsets.add(name_start)
        pcx_name = data[name_start:name_end].decode("ascii", errors="replace")
        base_name = pcx_name.rsplit("\\", 1)[-1].rsplit("/", 1)[-1].lower()
        previous_nul = data.rfind(b"\0", 0, name_start)
        next_nul = data.find(b"\0", name_end)
        rows.append(
            {
                "cache_path": str(cache_mix),
                "name_offset": str(name_start),
                "name_offset_hex": f"0x{name_start:08x}",
                "pcx_name": pcx_name,
                "base_name": base_name,
                "previous_nul_offset": str(previous_nul),
                "next_nul_offset": str(next_nul),
                "byte_before_name": format_byte(data, name_start - 1),
                "byte_after_name": format_byte(data, name_end),
                "matched_texture_archives": ";".join(
                    sorted(archives_by_base_name.get(base_name, set()))
                ),
                "context_before_hex": data[
                    max(0, name_start - context_bytes) : name_start
                ].hex(),
                "context_after_hex": data[
                    name_end : min(len(data), name_end + context_bytes)
                ].hex(),
            }
        )

    return rows


def build_cdcache_descriptor_rows(
    cache_mix: Path,
    raw_reference_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    if not cache_mix.exists():
        return []

    marker_words = {0x028E, 0x828E, 0x008F, 0x808F, 0x00A9, 0x80A9}
    data = cache_mix.read_bytes()
    rows: list[dict[str, str]] = []
    for reference in raw_reference_rows:
        try:
            name_offset = int(reference["name_offset"])
        except ValueError:
            continue

        name_bytes = reference["pcx_name"].encode("ascii", errors="replace")
        name_end = name_offset + len(name_bytes)
        if name_offset < 0 or name_end >= len(data):
            continue
        if data[name_offset:name_end].lower().find(b".pcx") < 0:
            continue

        search_start = name_end + 1 if data[name_end : name_end + 1] == b"\0" else name_end
        search_end = min(len(data), search_start + 48)
        descriptor_offset = -1
        for offset in range(search_start, max(search_start, search_end - 1)):
            if struct.unpack_from("<H", data, offset)[0] not in marker_words:
                continue
            if any(data[padding_offset] != 0 for padding_offset in range(search_start, offset)):
                continue
            descriptor_offset = offset
            break

        if descriptor_offset < 0 or descriptor_offset + 22 > len(data):
            continue

        (
            marker_word,
            origin_x,
            origin_y,
            width,
            height,
            scale,
            cache_index,
        ) = struct.unpack_from("<HHHHHHH", data, descriptor_offset)
        unknown_dword = struct.unpack_from("<I", data, descriptor_offset + 14)[0]
        tail_word0, tail_word1 = struct.unpack_from("<HH", data, descriptor_offset + 18)
        data_offset = descriptor_offset + 22
        data_size_guess = width * height
        data_end = data_offset + data_size_guess
        sample = data[data_offset : min(len(data), data_offset + min(data_size_guess, 4096))]
        head_zero_ratio = (
            f"{sample.count(0) / len(sample):.6f}"
            if sample
            else ""
        )
        pixels = data[data_offset:data_end] if data_end <= len(data) else b""
        if pixels:
            data_zero_ratio = f"{pixels.count(0) / len(pixels):.6f}"
            data_unique_values = str(len(set(pixels)))
        else:
            data_zero_ratio = ""
            data_unique_values = ""

        left = width
        top = height
        right = -1
        bottom = -1
        if pixels and width and height and len(pixels) == width * height:
            for y in range(height):
                row_start = y * width
                row = pixels[row_start : row_start + width]
                for x, value in enumerate(row):
                    if value == 0:
                        continue
                    if x < left:
                        left = x
                    if x > right:
                        right = x
                    if y < top:
                        top = y
                    if y > bottom:
                        bottom = y

        if right >= left and bottom >= top:
            content_width = right - left + 1
            content_height = bottom - top + 1
            content_bbox = f"{left},{top},{right + 1},{bottom + 1}"
            content_area_ratio = f"{(content_width * content_height) / (width * height):.6f}"
        else:
            content_width = 0
            content_height = 0
            content_bbox = ""
            content_area_ratio = "0.000000" if width and height else ""

        rows.append(
            {
                "cache_path": str(cache_mix),
                "name_offset": str(name_offset),
                "name_offset_hex": reference["name_offset_hex"],
                "pcx_name": reference["pcx_name"],
                "base_name": reference["base_name"],
                "matched_texture_archives": reference["matched_texture_archives"],
                "descriptor_offset": str(descriptor_offset),
                "descriptor_offset_hex": f"0x{descriptor_offset:08x}",
                "descriptor_padding": str(descriptor_offset - search_start),
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
                "data_head_zero_ratio": head_zero_ratio,
                "data_unique_values": data_unique_values,
                "data_zero_ratio": data_zero_ratio,
                "content_bbox": content_bbox,
                "content_width": str(content_width),
                "content_height": str(content_height),
                "content_area_ratio": content_area_ratio,
                "next_descriptor_offset": "",
                "next_descriptor_offset_hex": "",
                "next_descriptor_distance": "",
                "gap_to_next_descriptor": "",
                "data_crosses_next_descriptor": "",
            }
        )

    rows.sort(key=lambda row: int(row["descriptor_offset"]))
    for index, row in enumerate(rows):
        if index + 1 >= len(rows):
            continue
        next_offset = int(rows[index + 1]["descriptor_offset"])
        descriptor_offset = int(row["descriptor_offset"])
        data_end = int(row["data_end_guess"])
        row["next_descriptor_offset"] = str(next_offset)
        row["next_descriptor_offset_hex"] = f"0x{next_offset:08x}"
        row["next_descriptor_distance"] = str(next_offset - descriptor_offset)
        row["gap_to_next_descriptor"] = str(next_offset - data_end)
        row["data_crosses_next_descriptor"] = str(data_end > next_offset)

    return rows


def build_cdcache_palette_candidate_rows(
    cache_mix: Path,
    raw_reference_rows: list[dict[str, str]],
    local_mix: Path,
) -> list[dict[str, str]]:
    if not cache_mix.exists():
        return []

    local_palette = b""
    if local_mix.exists():
        try:
            _file_id, local_palette = read_mix_entry(local_mix, 94) or (0, b"")
        except (OSError, struct.error, ValueError):
            local_palette = b""
        local_palette = local_palette[:768]

    data = cache_mix.read_bytes()
    rows: list[dict[str, str]] = []
    for reference in raw_reference_rows:
        if reference["base_name"].lower() != "palette.pcx":
            continue
        try:
            name_offset = int(reference["name_offset"])
        except ValueError:
            continue

        for delta in (1024,):
            candidate_offset = name_offset + delta
            candidate = data[candidate_offset : candidate_offset + 768]
            if len(candidate) != 768:
                continue
            rows.append(
                {
                    "cache_path": str(cache_mix),
                    "source_name_offset": str(name_offset),
                    "source_name_offset_hex": reference["name_offset_hex"],
                    "candidate_offset": str(candidate_offset),
                    "candidate_offset_hex": f"0x{candidate_offset:08x}",
                    "delta_from_name": str(delta),
                    "palette_bytes": "768",
                    "max_value": str(max(candidate)),
                    "unique_values": str(len(set(candidate))),
                    "vga_6bit_candidate": str(max(candidate) <= 63),
                    "sha1": hashlib.sha1(candidate).hexdigest(),
                    "matches_local_mix_palette": str(
                        bool(local_palette) and candidate == local_palette
                    ),
                    "head_hex": candidate[:32].hex(),
                }
            )

    return rows


def build_cdcache_material_texture_link_rows(
    cdcache_descriptor_rows: list[dict[str, str]],
    material_texture_record_link_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    descriptors_by_archive_name: dict[tuple[str, str], list[dict[str, str]]] = {}
    for descriptor in cdcache_descriptor_rows:
        base_name = descriptor["base_name"].lower()
        for archive in descriptor["matched_texture_archives"].split(";"):
            if not archive:
                continue
            descriptors_by_archive_name.setdefault((archive, base_name), []).append(
                descriptor
            )

    rows: list[dict[str, str]] = []
    for link in material_texture_record_link_rows:
        key = (link["archive"], link["pcx_name"].lower())
        for descriptor in descriptors_by_archive_name.get(key, []):
            rows.append(
                {
                    "archive": link["archive"],
                    "pcx_name": link["pcx_name"],
                    "material_clean_text": link["material_clean_text"],
                    "material_offset_hex": link["material_offset_hex"],
                    "material_range_label": link["material_range_label"],
                    "texture_segment_index": link["texture_segment_index"],
                    "texture_body_offset_hex": link["texture_body_offset_hex"],
                    "texture_body_first_word": link["texture_body_first_word"],
                    "texture_segment_size": link["texture_segment_size"],
                    "record_range_label": link["record_range_label"],
                    "record_index": link["record_index"],
                    "record_size": link["record_size"],
                    "record_start_hex": link["record_start_hex"],
                    "cache_name_offset_hex": descriptor["name_offset_hex"],
                    "cache_descriptor_offset_hex": descriptor["descriptor_offset_hex"],
                    "cache_marker_word": descriptor["marker_word"],
                    "cache_origin_x": descriptor["origin_x"],
                    "cache_origin_y": descriptor["origin_y"],
                    "cache_width": descriptor["width"],
                    "cache_height": descriptor["height"],
                    "cache_index": descriptor["cache_index"],
                    "cache_data_offset_hex": descriptor["data_offset_hex"],
                    "cache_content_bbox": descriptor["content_bbox"],
                    "cache_data_zero_ratio": descriptor["data_zero_ratio"],
                    "cache_data_crosses_next_descriptor": descriptor[
                        "data_crosses_next_descriptor"
                    ],
                }
            )

    return rows


def build_material_record_field_profile_rows(
    material_record_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    groups: dict[tuple[str, str, str, str, str], list[dict[str, str]]] = {}
    for row in material_record_rows:
        groups.setdefault(
            (
                row["archive"],
                row["entry_index"],
                row["file_id"],
                row["range_label"],
                row["record_size"],
            ),
            [],
        ).append(row)

    rows: list[dict[str, str]] = []
    for (archive, entry_index, file_id, range_label, record_size), records in sorted(
        groups.items()
    ):
        size = int(record_size)
        record_bytes = [bytes.fromhex(record["record_hex"]) for record in records]
        matched_record_bytes = [
            bytes.fromhex(record["record_hex"])
            for record in records
            if record["matched_pcx_names"]
        ]
        for width in (1, 2, 4):
            step = 1 if width == 1 else 2
            for offset in range(0, max(0, size - width + 1), step):
                values = Counter(
                    read_int_le(record, offset, width)
                    for record in record_bytes
                    if offset + width <= len(record)
                )
                if not values:
                    continue
                matched_values = Counter(
                    read_int_le(record, offset, width)
                    for record in matched_record_bytes
                    if offset + width <= len(record)
                )
                total = sum(values.values())
                nonzero_count = total - values.get(0, 0)
                matched_total = sum(matched_values.values())
                matched_nonzero_count = matched_total - matched_values.get(0, 0)
                constant_value = next(iter(values)) if len(values) == 1 else None
                rows.append(
                    {
                        "archive": archive,
                        "entry_index": entry_index,
                        "file_id": file_id,
                        "range_label": range_label,
                        "record_size": record_size,
                        "field_width": str(width),
                        "field_offset": str(offset),
                        "field_offset_hex": f"0x{offset:02x}",
                        "record_count": str(total),
                        "nonzero_count": str(nonzero_count),
                        "nonzero_ratio": f"{nonzero_count / total:.4f}" if total else "",
                        "unique_count": str(len(values)),
                        "constant_value_hex": (
                            f"0x{constant_value:0{width * 2}x}"
                            if constant_value is not None
                            else ""
                        ),
                        "top_values_hex": format_top_values(values, width),
                        "matched_record_count": str(matched_total),
                        "matched_nonzero_count": str(matched_nonzero_count),
                        "matched_unique_count": str(len(matched_values)),
                        "matched_top_values_hex": format_top_values(matched_values, width)
                        if matched_values
                        else "",
                    }
                )

    return rows


def texture_segment_base_name(pcx_name: str) -> str:
    return re.split(r"[\\/]", pcx_name)[-1].lower()


def build_material_texture_record_link_rows(
    material_texture_match_rows: list[dict[str, str]],
    material_record_rows: list[dict[str, str]],
    texture_segment_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    records_by_material: dict[tuple[str, str], list[dict[str, str]]] = {}
    for record in material_record_rows:
        records_by_material.setdefault(
            (record["archive"], record["raw_offset"]),
            [],
        ).append(record)

    segments_by_texture: dict[tuple[str, str], list[dict[str, str]]] = {}
    for segment in texture_segment_rows:
        if segment["reference_class"] == "prefix" or not segment["pcx_name"]:
            continue
        segments_by_texture.setdefault(
            (segment["archive"], texture_segment_base_name(segment["pcx_name"])),
            [],
        ).append(segment)

    rows: list[dict[str, str]] = []
    for match in material_texture_match_rows:
        records = records_by_material.get(
            (match["archive"], match["material_offset"]),
            [],
        )
        segments = segments_by_texture.get(
            (match["archive"], match["pcx_name"].lower()),
            [],
        )
        if not records:
            records = [{}]
        if not segments:
            segments = [{}]
        for record in records:
            record_bytes = (
                bytes.fromhex(record["record_hex"])
                if record.get("record_hex")
                else b""
            )
            for segment in segments:
                rows.append(
                    {
                        "archive": match["archive"],
                        "pcx_name": match["pcx_name"],
                        "match_type": match["match_type"],
                        "material_clean_text": match["material_clean_text"],
                        "material_offset": match["material_offset"],
                        "material_offset_hex": match["material_offset_hex"],
                        "material_range_label": match["material_range_label"],
                        "material_name_class": match["material_name_class"],
                        "material_name_confidence": match["material_name_confidence"],
                        "texture_segment_index": segment.get("segment_index", ""),
                        "texture_reference_index": segment.get("reference_index", ""),
                        "texture_name_offset": segment.get("segment_start", ""),
                        "texture_name_offset_hex": segment.get("segment_start_hex", ""),
                        "texture_body_offset": segment.get("body_offset", ""),
                        "texture_body_offset_hex": segment.get("body_offset_hex", ""),
                        "texture_body_first_word": segment.get("body_first_word", ""),
                        "texture_segment_size": segment.get("segment_size", ""),
                        "texture_post_terminator_size": segment.get(
                            "post_terminator_size", ""
                        ),
                        "texture_entropy": segment.get("entropy", ""),
                        "record_range_label": record.get("range_label", ""),
                        "record_index": record.get("record_index", ""),
                        "record_size": record.get("record_size", ""),
                        "record_start": record.get("record_start", ""),
                        "record_start_hex": record.get("record_start_hex", ""),
                        "record_end_hex": record.get("record_end_hex", ""),
                        "next_distance": record.get("next_distance", ""),
                        "matches_stride": record.get("matches_stride", ""),
                        "prefix_delta": record.get("prefix_delta", ""),
                        "record_suffix_8_hex": (
                            record_bytes[-8:].hex() if len(record_bytes) >= 8 else ""
                        ),
                        "record_suffix_12_hex": (
                            record_bytes[-12:].hex() if len(record_bytes) >= 12 else ""
                        ),
                        "record_suffix_16_hex": (
                            record_bytes[-16:].hex() if len(record_bytes) >= 16 else ""
                        ),
                        "record_le16": record.get("record_le16", ""),
                        "record_le32": record.get("record_le32", ""),
                        "record_hex": record.get("record_hex", ""),
                    }
                )

    return rows


def parse_lcw_probe_offsets(value: str) -> list[int]:
    offsets: list[int] = []
    for item in value.split(","):
        item = item.strip()
        if item:
            offsets.append(int(item, 0))
    return offsets


def build_report(
    cache_list: Path,
    game_dir: Path,
    lcw_probe_offsets: list[int],
) -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    rows: list[dict[str, str]] = []
    reference_rows: list[dict[str, str]] = []
    reference_summary_rows: list[dict[str, str]] = []
    texture_string_cluster_rows: list[dict[str, str]] = []
    texture_segment_rows: list[dict[str, str]] = []
    lcw_probe_rows: list[dict[str, str]] = []
    header_rows: list[dict[str, str]] = []
    pcx_signature_rows: list[dict[str, str]] = []
    level_archives: list[Path] = []
    for cache_row in parse_cache_list(cache_list):
        texture_path = str(cache_row["texture_path"])
        declared_size = int(cache_row["declared_size"])
        archive = archive_for_texture(texture_path, game_dir)
        level_archives.append(archive)
        entry = read_mix_entry(archive, 2) if archive.exists() else None
        archive_exists = archive.exists()
        texture_file_id = ""
        payload_size = 0
        payload_declared_size = 0
        size_matches = ""
        packed_ratio = ""
        references: list[dict[str, object]] = []
        texture_references: list[dict[str, object]] = []
        likely_references: list[dict[str, object]] = []
        low_confidence_references: list[dict[str, object]] = []
        embedded_signatures = 0
        readable_embedded = 0
        status = "missing_archive"

        if entry is not None:
            file_id, payload = entry
            texture_file_id = f"{file_id:08x}"
            payload_size = len(payload)
            payload_declared_size = read_u32(payload, 0) if len(payload) >= 4 else 0
            size_matches = str(payload_declared_size == declared_size)
            packed_ratio = f"{payload_size / declared_size:.4f}" if declared_size else ""
            references = find_pcx_references(payload)
            texture_references = [
                reference for reference in references if not bool(reference["is_palette"])
            ]
            likely_references = [
                reference
                for reference in texture_references
                if reference["confidence"] in {"high", "medium"}
            ]
            low_confidence_references = [
                reference
                for reference in texture_references
                if reference["confidence"] == "low"
            ]
            path_references = [
                reference
                for reference in texture_references
                if reference["reference_class"] == "path_string"
            ]
            filename_references = [
                reference
                for reference in texture_references
                if reference["reference_class"] == "filename_string"
            ]
            reference_rows.extend(
                build_reference_row(
                    texture_path,
                    archive,
                    texture_file_id,
                    reference_index,
                    reference,
                )
                for reference_index, reference in enumerate(references)
            )
            texture_string_cluster_rows.extend(
                build_texture_string_cluster_rows(
                    texture_path,
                    archive,
                    texture_file_id,
                    references,
                    payload,
                )
            )
            texture_segment_rows.extend(
                build_texture_segment_rows(
                    texture_path,
                    archive,
                    texture_file_id,
                    references,
                    payload,
                )
            )
            reference_summary_rows.append(
                {
                    "texture_path": texture_path,
                    "archive": str(archive),
                    "texture_entry_index": "2",
                    "texture_file_id": texture_file_id,
                    "palette_count": str(
                        sum(1 for reference in references if bool(reference["is_palette"]))
                    ),
                    "path_string_count": str(len(path_references)),
                    "filename_string_count": str(len(filename_references)),
                    "low_confidence_count": str(len(low_confidence_references)),
                    "likely_texture_count": str(len(likely_references)),
                    "source_path_names": ";".join(
                        str(reference["name"]) for reference in path_references
                    ),
                    "reconstructed_source_paths": ";".join(
                        str(reference["reconstructed_source_path"])
                        for reference in path_references
                    ),
                    "likely_texture_names": ";".join(
                        str(reference["base_name"]) for reference in likely_references
                    ),
                    "low_confidence_names": ";".join(
                        str(reference["name"]) for reference in low_confidence_references
                    ),
                }
            )
            embedded_signatures, readable_embedded = count_embedded_pcx(payload)
            pcx_signature_rows.extend(
                build_pcx_signature_rows(
                    texture_path,
                    archive,
                    texture_file_id,
                    payload,
                )
            )
            lcw_probe_rows.extend(
                build_lcw_probe_rows(
                    texture_path,
                    archive,
                    texture_file_id,
                    payload,
                    payload_declared_size or declared_size,
                    lcw_probe_offsets,
                )
            )
            header_rows.append(
                build_header_row(
                    texture_path,
                    archive,
                    texture_file_id,
                    payload,
                    declared_size,
                    payload_declared_size,
                )
            )
            status = "catalogued_not_decoded"
            if readable_embedded:
                status = "embedded_pcx_readable"
        elif archive_exists:
            status = "missing_texture_entry"

        rows.append(
            {
                "texture_path": texture_path,
                "cache_block_offset": str(cache_row["cache_block_offset"]),
                "cache_table_flags": str(cache_row["cache_table_flags"]),
                "cache_tail_d0": f"{int(cache_row['cache_tail'][0]):08x}",
                "cache_tail_d4": f"{int(cache_row['cache_tail'][1]):08x}",
                "cache_tail_d8": f"{int(cache_row['cache_tail'][2]):08x}",
                "cache_tail_dc": f"{int(cache_row['cache_tail'][3]):08x}",
                "cache_tail_e0": f"{int(cache_row['cache_tail'][4]):08x}",
                "cache_tail_e4": f"{int(cache_row['cache_tail'][5]):08x}",
                "cache_tail_e8": f"{int(cache_row['cache_tail'][6]):08x}",
                "cache_tail_ec": f"{int(cache_row['cache_tail'][7]):08x}",
                "archive": str(archive),
                "archive_exists": str(archive_exists),
                "texture_entry_index": "2",
                "texture_file_id": texture_file_id,
                "payload_size": str(payload_size),
                "declared_size": str(declared_size),
                "payload_declared_size": str(payload_declared_size),
                "declared_size_matches_payload_header": size_matches,
                "packed_ratio": packed_ratio,
                "referenced_pcx_count": str(len(texture_references)),
                "likely_referenced_pcx_count": str(len(likely_references)),
                "low_confidence_pcx_count": str(len(low_confidence_references)),
                "referenced_pcx_names": ";".join(
                    str(reference["name"]) for reference in texture_references
                ),
                "embedded_pcx_signature_count": str(embedded_signatures),
                "readable_embedded_pcx_count": str(readable_embedded),
                "status": status,
            }
        )

    (
        level_entry_rows,
        material_string_rows,
        material_section_rows,
        material_range_rows,
    ) = build_level_entry_reports(level_archives)
    return (
        rows,
        reference_rows,
        reference_summary_rows,
        texture_string_cluster_rows,
        texture_segment_rows,
        lcw_probe_rows,
        header_rows,
        pcx_signature_rows,
        level_entry_rows,
        material_string_rows,
        material_section_rows,
        material_range_rows,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Report level texture cache payloads.")
    parser.add_argument("--cache-list", type=Path, default=Path("C/LOLG/CDCACHE.LST"))
    parser.add_argument("--game-dir", type=Path, default=Path("C/LOLG"))
    parser.add_argument("-o", "--output", type=Path, default=Path("output/texture_report"))
    parser.add_argument(
        "--lcw-probe-offsets",
        default=",".join(str(offset) for offset in DEFAULT_LCW_PROBE_OFFSETS),
        help="Comma-separated offsets to scan as possible direct LCW streams.",
    )
    args = parser.parse_args()

    (
        rows,
        reference_rows,
        reference_summary_rows,
        texture_string_cluster_rows,
        texture_segment_rows,
        lcw_probe_rows,
        header_rows,
        pcx_signature_rows,
        level_entry_rows,
        material_string_rows,
        material_section_rows,
        material_range_rows,
    ) = build_report(
        args.cache_list,
        args.game_dir,
        parse_lcw_probe_offsets(args.lcw_probe_offsets),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = args.output / "manifest.csv"
    with manifest.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    references = args.output / "references.csv"
    with references.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REFERENCE_FIELDNAMES)
        writer.writeheader()
        writer.writerows(reference_rows)

    reference_summary = args.output / "reference_summary.csv"
    with reference_summary.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REFERENCE_SUMMARY_FIELDNAMES)
        writer.writeheader()
        writer.writerows(reference_summary_rows)

    texture_string_clusters = args.output / "texture_string_clusters.csv"
    with texture_string_clusters.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TEXTURE_STRING_CLUSTER_FIELDNAMES)
        writer.writeheader()
        writer.writerows(texture_string_cluster_rows)

    texture_segments = args.output / "texture_segments.csv"
    with texture_segments.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TEXTURE_SEGMENT_FIELDNAMES)
        writer.writeheader()
        writer.writerows(texture_segment_rows)

    texture_body_prefixes = args.output / "texture_body_prefixes.csv"
    with texture_body_prefixes.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TEXTURE_BODY_PREFIX_FIELDNAMES)
        writer.writeheader()
        writer.writerows(build_texture_body_prefix_rows(texture_segment_rows))

    texture_segment_head_profiles = args.output / "texture_segment_head_profiles.csv"
    with texture_segment_head_profiles.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=TEXTURE_SEGMENT_HEAD_PROFILE_FIELDNAMES,
        )
        writer.writeheader()
        writer.writerows(build_texture_segment_head_profile_rows(texture_segment_rows))

    texture_archive_summary = args.output / "texture_archive_summary.csv"
    with texture_archive_summary.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TEXTURE_ARCHIVE_SUMMARY_FIELDNAMES)
        writer.writeheader()
        writer.writerows(build_texture_archive_summary_rows(rows, texture_segment_rows))

    lcw_probe = args.output / "lcw_probe.csv"
    with lcw_probe.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LCW_PROBE_FIELDNAMES)
        writer.writeheader()
        writer.writerows(lcw_probe_rows)

    headers = args.output / "headers.csv"
    with headers.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER_FIELDNAMES)
        writer.writeheader()
        writer.writerows(header_rows)

    texture_payload_header_profiles = args.output / "texture_payload_header_profiles.csv"
    with texture_payload_header_profiles.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=TEXTURE_PAYLOAD_HEADER_PROFILE_FIELDNAMES,
        )
        writer.writeheader()
        writer.writerows(build_texture_payload_header_profile_rows(header_rows))

    pcx_signatures = args.output / "pcx_signatures.csv"
    with pcx_signatures.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PCX_SIGNATURE_FIELDNAMES)
        writer.writeheader()
        writer.writerows(pcx_signature_rows)

    palette_candidates = args.output / "palette_candidates.csv"
    with palette_candidates.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PALETTE_CANDIDATE_FIELDNAMES)
        writer.writeheader()
        writer.writerows(build_palette_candidate_rows(args.game_dir))

    cdcache_raw_references = args.output / "cdcache_raw_references.csv"
    cdcache_raw_reference_rows = build_cdcache_raw_reference_rows(
        args.game_dir / "CDCACHE.MIX",
        reference_summary_rows,
    )
    with cdcache_raw_references.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CDCACHE_RAW_REFERENCE_FIELDNAMES)
        writer.writeheader()
        writer.writerows(cdcache_raw_reference_rows)

    cdcache_descriptors = args.output / "cdcache_descriptors.csv"
    cdcache_descriptor_rows = build_cdcache_descriptor_rows(
        args.game_dir / "CDCACHE.MIX",
        cdcache_raw_reference_rows,
    )
    with cdcache_descriptors.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CDCACHE_DESCRIPTOR_FIELDNAMES)
        writer.writeheader()
        writer.writerows(cdcache_descriptor_rows)

    cdcache_palette_candidates = args.output / "cdcache_palette_candidates.csv"
    with cdcache_palette_candidates.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CDCACHE_PALETTE_CANDIDATE_FIELDNAMES)
        writer.writeheader()
        writer.writerows(
            build_cdcache_palette_candidate_rows(
                args.game_dir / "CDCACHE.MIX",
                cdcache_raw_reference_rows,
                args.game_dir / "LOCAL.MIX",
            )
        )

    level_entries = args.output / "level_entries.csv"
    with level_entries.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEVEL_ENTRY_FIELDNAMES)
        writer.writeheader()
        writer.writerows(level_entry_rows)

    material_strings = args.output / "material_strings.csv"
    with material_strings.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MATERIAL_STRING_FIELDNAMES)
        writer.writeheader()
        writer.writerows(material_string_rows)

    material_sections = args.output / "material_sections.csv"
    with material_sections.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MATERIAL_SECTION_FIELDNAMES)
        writer.writeheader()
        writer.writerows(material_section_rows)

    material_ranges = args.output / "material_ranges.csv"
    with material_ranges.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MATERIAL_RANGE_FIELDNAMES)
        writer.writeheader()
        writer.writerows(material_range_rows)

    material_texture_matches = args.output / "material_texture_name_matches.csv"
    material_texture_match_rows = build_material_texture_match_rows(
        reference_summary_rows,
        material_string_rows,
    )
    with material_texture_matches.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MATERIAL_TEXTURE_MATCH_FIELDNAMES)
        writer.writeheader()
        writer.writerows(material_texture_match_rows)

    material_sequence_rows, material_stride_rows = build_material_sequence_reports(
        material_string_rows,
    )
    material_sequences = args.output / "material_sequences.csv"
    with material_sequences.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MATERIAL_SEQUENCE_FIELDNAMES)
        writer.writeheader()
        writer.writerows(material_sequence_rows)

    material_strides = args.output / "material_strides.csv"
    with material_strides.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MATERIAL_STRIDE_FIELDNAMES)
        writer.writeheader()
        writer.writerows(material_stride_rows)

    material_record_candidates = args.output / "material_record_candidates.csv"
    material_record_rows = build_material_record_candidate_rows(
        material_string_rows,
        material_stride_rows,
        material_texture_match_rows,
    )
    with material_record_candidates.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MATERIAL_RECORD_FIELDNAMES)
        writer.writeheader()
        writer.writerows(material_record_rows)

    material_record_profiles = args.output / "material_record_profiles.csv"
    with material_record_profiles.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MATERIAL_RECORD_PROFILE_FIELDNAMES)
        writer.writeheader()
        writer.writerows(build_material_record_profile_rows(material_record_rows))

    material_record_field_profiles = args.output / "material_record_field_profiles.csv"
    with material_record_field_profiles.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=MATERIAL_RECORD_FIELD_PROFILE_FIELDNAMES,
        )
        writer.writeheader()
        writer.writerows(build_material_record_field_profile_rows(material_record_rows))

    material_texture_record_links = args.output / "material_texture_record_links.csv"
    material_texture_record_link_rows = build_material_texture_record_link_rows(
        material_texture_match_rows,
        material_record_rows,
        texture_segment_rows,
    )
    with material_texture_record_links.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=MATERIAL_TEXTURE_RECORD_LINK_FIELDNAMES,
        )
        writer.writeheader()
        writer.writerows(material_texture_record_link_rows)

    cdcache_material_texture_links = args.output / "cdcache_material_texture_links.csv"
    with cdcache_material_texture_links.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=CDCACHE_MATERIAL_TEXTURE_LINK_FIELDNAMES,
        )
        writer.writeheader()
        writer.writerows(
            build_cdcache_material_texture_link_rows(
                cdcache_descriptor_rows,
                material_texture_record_link_rows,
            )
        )

    referenced_total = sum(int(row["referenced_pcx_count"]) for row in rows)
    likely_total = sum(int(row["likely_referenced_pcx_count"]) for row in rows)
    low_confidence_total = sum(int(row["low_confidence_pcx_count"]) for row in rows)
    readable_total = sum(int(row["readable_embedded_pcx_count"]) for row in rows)
    direct_lcw_matches = sum(
        1 for row in lcw_probe_rows if row["status"] == "end_at_expected"
    )
    print(
        f"Reported {len(rows)} texture cache payloads: "
        f"{referenced_total} texture PCX-like references "
        f"({likely_total} likely, {low_confidence_total} low-confidence), "
        f"{len(reference_rows) - referenced_total} palette PCX references, "
        f"{readable_total} readable embedded PCX images, "
        f"{direct_lcw_matches} direct LCW matches"
    )
    print(f"Manifest: {manifest}")
    print(f"References: {references}")
    print(f"Reference summary: {reference_summary}")
    print(f"Texture string clusters: {texture_string_clusters}")
    print(f"Texture segments: {texture_segments}")
    print(f"Texture body prefixes: {texture_body_prefixes}")
    print(f"Texture segment head profiles: {texture_segment_head_profiles}")
    print(f"Texture archive summary: {texture_archive_summary}")
    print(f"LCW probe: {lcw_probe}")
    print(f"Headers: {headers}")
    print(f"Texture payload header profiles: {texture_payload_header_profiles}")
    print(f"PCX signatures: {pcx_signatures}")
    print(f"Palette candidates: {palette_candidates}")
    print(f"CDCACHE raw references: {cdcache_raw_references}")
    print(f"CDCACHE descriptors: {cdcache_descriptors}")
    print(f"CDCACHE palette candidates: {cdcache_palette_candidates}")
    print(f"Level entries: {level_entries}")
    print(f"Material strings: {material_strings}")
    print(f"Material sections: {material_sections}")
    print(f"Material ranges: {material_ranges}")
    print(f"Material/texture name matches: {material_texture_matches}")
    print(f"Material sequences: {material_sequences}")
    print(f"Material strides: {material_strides}")
    print(f"Material record candidates: {material_record_candidates}")
    print(f"Material record profiles: {material_record_profiles}")
    print(f"Material record field profiles: {material_record_field_profiles}")
    print(f"Material/texture record links: {material_texture_record_links}")
    print(f"CDCACHE material/texture links: {cdcache_material_texture_links}")


if __name__ == "__main__":
    main()
