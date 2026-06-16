#!/usr/bin/env python3
"""Summarise visual assets stored in Lands of Lore II .MIX archives."""

from __future__ import annotations

import argparse
import struct
import subprocess
from collections import Counter
from pathlib import Path


def read_mix(path: Path) -> tuple[int, bytes, list[tuple[int, int, int]]]:
    data = path.read_bytes()
    count, body_size = struct.unpack_from("<HI", data, 0)
    table_end = 6 + count * 12
    entries = [struct.unpack_from("<III", data, 6 + i * 12) for i in range(count)]
    return table_end, data, entries


def classify(payload: bytes) -> str:
    if payload.startswith(b"FORM"):
        form_type = payload[8:12] if len(payload) >= 12 else b""
        if form_type == b"WVQA":
            return "VQA"
        if form_type == b"XDIR":
            return "XDIR"
        return f"FORM_{form_type.decode('ascii', errors='replace') or 'unknown'}"
    if payload[:4] in {b"\x0a\x05\x01\x08", b"\x0a\x00\x01\x08"}:
        return "PCX"
    if payload.startswith(b"HMI-MIDI"):
        return "HMI"
    if payload.startswith(b"ECHO is OFF"):
        return "BAT"
    if payload.startswith(b"This is a linear executable dll"):
        return "DLL"
    return "BIN"


def file_description(temp_path: Path) -> str:
    result = subprocess.run(
        ["file", "-b", str(temp_path)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archives", nargs="+", type=Path)
    parser.add_argument("--samples", type=Path, default=Path("/tmp/lolg_asset_report_samples"))
    args = parser.parse_args()

    args.samples.mkdir(parents=True, exist_ok=True)
    total = Counter()

    for archive in args.archives:
        table_end, data, entries = read_mix(archive)
        counts = Counter()
        largest: list[tuple[int, int, str]] = []

        for index, (file_id, offset, size) in enumerate(entries):
            payload = data[table_end + offset : table_end + offset + size]
            kind = classify(payload)
            counts[kind] += 1
            total[kind] += 1
            if kind in {"VQA", "PCX", "BIN"}:
                largest.append((size, index, kind))

        print(f"{archive.name}: {len(entries)} entries, " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))

        for size, index, kind in sorted(largest, reverse=True)[:3]:
            file_id, offset, _ = entries[index]
            payload = data[table_end + offset : table_end + offset + size]
            sample = args.samples / f"{archive.stem}_{index:04d}_{file_id:08x}.dat"
            sample.write_bytes(payload[: min(size, 8 * 1024 * 1024)])
            print(f"  sample {index:04d} {kind} {size} bytes: {file_description(sample)}")

    print("TOTAL: " + ", ".join(f"{k}={v}" for k, v in sorted(total.items())))


if __name__ == "__main__":
    main()
