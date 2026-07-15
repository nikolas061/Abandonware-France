#!/usr/bin/env python3
"""Extract Lands of Lore II Westwood .MIX archives.

The archives used here store entries by 32-bit hash only; original filenames
are not present in the .MIX table. Extracted names therefore include the entry
index, hash, size, and a best-effort extension based on the payload signature.
"""

from __future__ import annotations

import argparse
import struct
from pathlib import Path


def detect_extension(data: bytes) -> str:
    if data.startswith(b"FORM"):
        return "vqa"
    if data[:4] in {b"\x0a\x05\x01\x08", b"\x0a\x00\x01\x08"}:
        return "pcx"
    if data.startswith(b"HMI-MIDI"):
        return "hmi"
    if data.startswith(b"ECHO is OFF"):
        return "bat"
    if data.startswith(b"This is a linear executable dll"):
        return "dll"
    return "bin"


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


def parse_entries(raw_entries: list[str] | None) -> set[int] | None:
    if not raw_entries:
        return None
    selected: set[int] = set()
    for raw in raw_entries:
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                raw_start, raw_end = part.split("-", 1)
                start = int(raw_start, 0)
                end = int(raw_end, 0)
                if end < start:
                    raise ValueError(f"invalid entry range: {part}")
                selected.update(range(start, end + 1))
            else:
                selected.add(int(part, 0))
    return selected


def extract(path: Path, output_dir: Path, selected_entries: set[int] | None, flat: bool) -> None:
    data = path.read_bytes()
    table_end, entries = read_entries(path)
    target_dir = output_dir if flat else output_dir / path.stem
    target_dir.mkdir(parents=True, exist_ok=True)

    for index, (file_id, offset, size) in enumerate(entries):
        if selected_entries is not None and index not in selected_entries:
            continue
        payload = data[table_end + offset : table_end + offset + size]
        ext = detect_extension(payload)
        name = f"{index:04d}_{file_id:08x}_{size}.{ext}"
        (target_dir / name).write_bytes(payload)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archives", nargs="+", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=Path("extracted_mix"))
    parser.add_argument("--entries", action="append", help="Entry index/range list, e.g. 0,2,19-20")
    parser.add_argument("--flat", action="store_true", help="Write directly into output instead of output/archive_stem")
    args = parser.parse_args()

    selected_entries = parse_entries(args.entries)
    for archive in args.archives:
        extract(archive, args.output, selected_entries, args.flat)


if __name__ == "__main__":
    main()
