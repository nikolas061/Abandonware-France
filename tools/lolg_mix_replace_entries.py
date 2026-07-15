#!/usr/bin/env python3
"""Replace selected entries in a Westwood MIX archive."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


MANIFEST_FIELDS = [
    "entry_index",
    "file_id",
    "old_size",
    "new_size",
    "replacement",
    "replacement_sha256",
    "status",
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


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


def entry_payload(data: bytes, table_end: int, entry: tuple[int, int, int]) -> bytes:
    _file_id, offset, size = entry
    return data[table_end + offset : table_end + offset + size]


def parse_replacement(value: str) -> tuple[int, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("replacement must be ENTRY_INDEX=PAYLOAD")
    raw_index, raw_path = value.split("=", 1)
    try:
        index = int(raw_index)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid entry index: {raw_index}") from exc
    path = Path(raw_path)
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"replacement payload not found: {path}")
    return index, path


def validate_payload(path: Path, payload: bytes, allow_non_form: bool) -> None:
    if allow_non_form:
        return
    if len(payload) < 12 or payload[:4] != b"FORM" or payload[8:12] != b"WVQA":
        raise ValueError(f"{path}: replacement is not a FORM/WVQA payload")


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def build(args: argparse.Namespace) -> dict[str, Any]:
    source_data, entries, table_end = read_mix(args.source)
    replacements: dict[int, bytes] = {}
    manifest_rows: list[dict[str, str]] = []

    for index, path in args.replace:
        if index < 0 or index >= len(entries):
            raise ValueError(f"entry {index} outside 0..{len(entries) - 1}")
        payload = path.read_bytes()
        validate_payload(path, payload, args.allow_non_form)
        file_id, _offset, old_size = entries[index]
        replacements[index] = payload
        manifest_rows.append(
            {
                "entry_index": str(index),
                "file_id": f"{file_id:08x}",
                "old_size": str(old_size),
                "new_size": str(len(payload)),
                "replacement": str(path),
                "replacement_sha256": sha256(payload),
                "status": "replaced",
            }
        )

    payloads: dict[int, bytes] = {}
    for index, entry in enumerate(entries):
        payloads[index] = replacements.get(index, entry_payload(source_data, table_end, entry))

    physical_order = sorted(range(len(entries)), key=lambda index: entries[index][1])
    offsets: dict[int, int] = {}
    body_parts: list[bytes] = []
    cursor = 0
    for index in physical_order:
        offsets[index] = cursor
        body_parts.append(payloads[index])
        cursor += len(payloads[index])

    table = bytearray(struct.pack("<HI", len(entries), cursor))
    for index, entry in enumerate(entries):
        file_id, _offset, _size = entry
        table.extend(struct.pack("<III", file_id, offsets[index], len(payloads[index])))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(bytes(table) + b"".join(body_parts))
    write_csv(args.manifest_csv, manifest_rows)
    summary = {
        "status": "pass",
        "source": str(args.source),
        "output": str(args.output),
        "entries": len(entries),
        "replacements": len(replacements),
        "body_size": cursor,
        "manifest_csv": str(args.manifest_csv),
    }
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(json.dumps(summary, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Replace selected entries in a Westwood MIX archive.")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--replace",
        action="append",
        type=parse_replacement,
        required=True,
        help="Replacement as ENTRY_INDEX=PAYLOAD. Can be repeated.",
    )
    parser.add_argument("--manifest-csv", type=Path, required=True)
    parser.add_argument("--summary-json", type=Path, required=True)
    parser.add_argument("--allow-non-form", action="store_true")
    args = parser.parse_args()

    summary = build(args)
    print(json.dumps(summary, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
