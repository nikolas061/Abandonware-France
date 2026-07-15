#!/usr/bin/env python3
"""Build a DOSBox-friendly HD LOCALLNG.MIX override.

The generated archive keeps the original LOCALLNG.MIX table order and physical
payload order, but replaces the one VQA payload that exists in the HD archive.
This lets the DOS executable see a layout closer to the retail archive while
still testing the HD movie payload.
"""

from __future__ import annotations

import argparse
import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path


TARGET_FILE_ID = 0xFCA4E133


@dataclass(frozen=True)
class MixEntry:
    file_id: int
    offset: int
    size: int


def read_mix(path: Path) -> tuple[bytes, list[MixEntry], int]:
    data = path.read_bytes()
    if len(data) < 6:
        raise ValueError(f"{path}: too small to be a MIX archive")

    count, body_size = struct.unpack_from("<HI", data, 0)
    table_end = 6 + count * 12
    if table_end > len(data):
        raise ValueError(f"{path}: invalid MIX table")
    if table_end + body_size > len(data):
        raise ValueError(f"{path}: declared MIX body exceeds file size")

    entries: list[MixEntry] = []
    for index in range(count):
        file_id, offset, size = struct.unpack_from("<III", data, 6 + index * 12)
        if offset + size > body_size:
            raise ValueError(f"{path}: entry {index} exceeds declared MIX body")
        entries.append(MixEntry(file_id=file_id, offset=offset, size=size))

    return data, entries, table_end


def entry_payload(data: bytes, table_end: int, entry: MixEntry) -> bytes:
    start = table_end + entry.offset
    return data[start : start + entry.size]


def find_entry(entries: list[MixEntry], file_id: int) -> MixEntry:
    matches = [entry for entry in entries if entry.file_id == file_id]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one entry {file_id:08x}, got {len(matches)}")
    return matches[0]


def sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def build_compat_mix(original_path: Path, hd_path: Path, output_path: Path, report_path: Path) -> None:
    original_data, original_entries, original_table_end = read_mix(original_path)
    hd_data, hd_entries, hd_table_end = read_mix(hd_path)

    original_ids = [entry.file_id for entry in original_entries]
    hd_ids = [entry.file_id for entry in hd_entries]
    if original_ids != hd_ids:
        raise ValueError("original and HD LOCALLNG.MIX do not have the same entry table IDs")

    original_target = find_entry(original_entries, TARGET_FILE_ID)
    hd_target = find_entry(hd_entries, TARGET_FILE_ID)
    hd_target_payload = entry_payload(hd_data, hd_table_end, hd_target)
    if not hd_target_payload.startswith(b"FORM"):
        raise ValueError(f"HD target entry {TARGET_FILE_ID:08x} is not a VQA FORM payload")

    payload_by_id: dict[int, bytes] = {}
    source_by_id: dict[int, str] = {}
    original_sha_by_id: dict[int, str] = {}
    output_sha_by_id: dict[int, str] = {}

    for entry in original_entries:
        original_payload = entry_payload(original_data, original_table_end, entry)
        original_sha_by_id[entry.file_id] = sha1(original_payload)
        if entry.file_id == TARGET_FILE_ID:
            payload = hd_target_payload
            source = "hd"
        else:
            payload = original_payload
            source = "original"
        payload_by_id[entry.file_id] = payload
        output_sha_by_id[entry.file_id] = sha1(payload)
        source_by_id[entry.file_id] = source

    physical_order = sorted(original_entries, key=lambda entry: entry.offset)
    new_offset_by_id: dict[int, int] = {}
    body_parts: list[bytes] = []
    cursor = 0
    for entry in physical_order:
        payload = payload_by_id[entry.file_id]
        new_offset_by_id[entry.file_id] = cursor
        body_parts.append(payload)
        cursor += len(payload)

    body_size = cursor
    table = bytearray()
    table += struct.pack("<HI", len(original_entries), body_size)
    for entry in original_entries:
        payload = payload_by_id[entry.file_id]
        table += struct.pack("<III", entry.file_id, new_offset_by_id[entry.file_id], len(payload))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(bytes(table) + b"".join(body_parts))

    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "index\tfile_id\tsource\toriginal_offset\toutput_offset\toriginal_size\toutput_size\toriginal_sha1\toutput_sha1"
    ]
    for index, entry in enumerate(original_entries):
        payload = payload_by_id[entry.file_id]
        lines.append(
            "\t".join(
                [
                    f"{index:04d}",
                    f"{entry.file_id:08x}",
                    source_by_id[entry.file_id],
                    str(entry.offset),
                    str(new_offset_by_id[entry.file_id]),
                    str(entry.size),
                    str(len(payload)),
                    original_sha_by_id[entry.file_id],
                    output_sha_by_id[entry.file_id],
                ]
            )
        )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {output_path} ({output_path.stat().st_size} bytes)")
    print(f"Report {report_path}")
    print(f"Replaced entry {TARGET_FILE_ID:08x}: {original_target.size} -> {hd_target.size} bytes")
    print("Physical order preserved from original offsets:")
    print(" ".join(f"{entry.file_id:08x}" for entry in physical_order))


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--original",
        type=Path,
        default=repo_root / "C/LOLG/LOCALLNG.MIX",
        help="Original DOS LOCALLNG.MIX",
    )
    parser.add_argument(
        "--hd",
        type=Path,
        default=repo_root / "mod_mix_vqa_fullhd/LOCALLNG.MIX",
        help="HD LOCALLNG.MIX containing the replacement VQA payload",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root / "output/lolg_dosbox_mix_overrides/LOCALLNG.MIX",
        help="Output override MIX path",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=repo_root / "output/lolg_dosbox_mix_overrides/LOCALLNG.tsv",
        help="Output TSV report",
    )
    args = parser.parse_args()

    build_compat_mix(args.original, args.hd, args.output, args.report)


if __name__ == "__main__":
    main()
