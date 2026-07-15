#!/usr/bin/env python3
"""Write a manifest for Westwood MIX archive entries without extracting them."""

from __future__ import annotations

import argparse
import csv
import hashlib
import struct
import sys
from pathlib import Path
from typing import TextIO


FIELDS = ["archive", "entry_index", "file_id", "offset", "size", "extension", "sha256"]


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


def read_mix(path: Path) -> tuple[bytes, list[tuple[int, int, int]], int]:
    data = path.read_bytes()
    if len(data) < 6:
        raise ValueError(f"{path}: too small to be a MIX archive")
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


def rows_for_archive(path: Path, include_hash: bool) -> list[dict[str, str]]:
    data, entries, table_end = read_mix(path)
    rows: list[dict[str, str]] = []
    for index, (file_id, offset, size) in enumerate(entries):
        payload = data[table_end + offset : table_end + offset + size]
        rows.append(
            {
                "archive": str(path),
                "entry_index": str(index),
                "file_id": f"{file_id:08x}",
                "offset": str(offset),
                "size": str(size),
                "extension": detect_extension(payload),
                "sha256": hashlib.sha256(payload).hexdigest() if include_hash else "",
            }
        )
    return rows


def write_manifest(rows: list[dict[str, str]], handle: TextIO) -> None:
    writer = csv.DictWriter(handle, fieldnames=FIELDS)
    writer.writeheader()
    writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+", type=Path)
    parser.add_argument("--sha256", action="store_true", help="Hash each entry payload.")
    parser.add_argument("-o", "--output-csv", type=Path)
    args = parser.parse_args()

    rows: list[dict[str, str]] = []
    for archive in args.archives:
        rows.extend(rows_for_archive(archive, args.sha256))

    if args.output_csv:
        args.output_csv.parent.mkdir(parents=True, exist_ok=True)
        with args.output_csv.open("w", newline="", encoding="utf-8") as handle:
            write_manifest(rows, handle)
    else:
        write_manifest(rows, sys.stdout)


if __name__ == "__main__":
    main()
