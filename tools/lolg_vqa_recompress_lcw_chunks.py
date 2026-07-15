#!/usr/bin/env python3
"""Recompress selected LCW-compressed VQA subchunks inside MIX entries."""

from __future__ import annotations

import argparse
import csv
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lolg_vqa_decode as vqa  # noqa: E402
from westwood_codecs import lcw_compress_vqa_extended  # noqa: E402


SUMMARY_FIELDS = [
    "status",
    "source_mix",
    "output_mix",
    "entries_requested",
    "entries_recompressed",
    "entries_failed",
    "chunk_ids",
    "issues",
]

ENTRY_FIELDS = [
    "status",
    "entry_index",
    "file_id",
    "frames",
    "chunks_seen",
    "chunks_recompressed",
    "synthetic_no_room_cbpz",
    "old_lcw_bytes",
    "new_lcw_bytes",
    "old_payload_bytes",
    "new_payload_bytes",
    "issues",
]


def be32(value: int) -> bytes:
    return struct.pack(">I", value)


def chunk(chunk_id: str, payload: bytes) -> bytes:
    padding = b"\x00" if len(payload) & 1 else b""
    return chunk_id.encode("ascii") + be32(len(payload)) + payload + padding


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


def parse_entries(raw: str) -> list[int]:
    entries: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            entries.extend(range(int(start), int(end) + 1))
        else:
            entries.append(int(part))
    return sorted(dict.fromkeys(entries))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_mix_with_replacements(
    source_mix: Path,
    output_mix: Path,
    replacements: dict[int, bytes],
) -> None:
    source_data, entries, table_end = read_mix(source_mix)
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

    output_mix.parent.mkdir(parents=True, exist_ok=True)
    output_mix.write_bytes(bytes(table) + b"".join(body_parts))


def expected_subchunk_size(chunk_id: str, header: vqa.VqaHeader) -> int | None:
    vector_size = header.block_width * header.block_height
    if chunk_id in {"CBFZ", "CBF0"}:
        return header.max_codebook_entries * vector_size
    if chunk_id in {"VPTZ", "VPT0"}:
        return header.block_count * 2
    return None


def synthetic_long_copy_payload(vector_size: int, output_bytes: int) -> bytes:
    if vector_size <= 0:
        raise ValueError("vector size must be positive")
    literal_size = min(63, vector_size, output_bytes)
    pattern = bytes(((index * 17) + 3) & 0xFF for index in range(literal_size))
    copy_count = max(0, min(0xFFFF, output_bytes - literal_size))
    stream = bytearray()
    stream.append(0x80 | literal_size)
    stream.extend(pattern)
    if copy_count:
        stream.append(0xFE)
        stream.extend((copy_count & 0xFF, (copy_count >> 8) & 0xFF, 0x00, 0x00))
    stream.append(0x80)
    return bytes(stream)


def recompress_payload(
    payload: bytes,
    wanted: set[str],
    synthetic_no_room_cbpz_bytes: int,
) -> tuple[bytes, dict[str, int], list[str]]:
    header, chunks = vqa.parse_vqa(payload)
    output_chunks: list[bytes] = []
    vector_size = header.block_width * header.block_height
    active_codebook: bytes | None = None
    used_synthetic_no_room_cbpz = False
    stats = {
        "frames": 0,
        "chunks_seen": 0,
        "chunks_recompressed": 0,
        "synthetic_no_room_cbpz": 0,
        "old_lcw_bytes": 0,
        "new_lcw_bytes": 0,
    }
    issues: list[str] = []

    for top_chunk in chunks:
        if top_chunk.chunk_id != "VQFR":
            output_chunks.append(chunk(top_chunk.chunk_id, top_chunk.payload))
            continue

        stats["frames"] += 1
        subchunks: list[bytes] = []
        for subchunk in vqa.iter_chunks(top_chunk.payload, 0):
            stats["chunks_seen"] += 1
            decoded: bytes | None = None
            if subchunk.chunk_id in {"CBFZ", "CBF0", "CBPZ", "CBP0"}:
                try:
                    if subchunk.chunk_id.endswith("Z"):
                        decoded = vqa.decode_lcw(
                            subchunk.payload,
                            expected_size=expected_subchunk_size(subchunk.chunk_id, header),
                            allow_signed_source=False,
                        )
                    else:
                        decoded = subchunk.payload
                except Exception as exc:  # noqa: BLE001 - recorded as report context.
                    issues.append(f"{subchunk.chunk_id}:decode_error:{type(exc).__name__}:{exc}")

            if subchunk.chunk_id not in wanted:
                subchunks.append(chunk(subchunk.chunk_id, subchunk.payload))
                if decoded is not None:
                    if subchunk.chunk_id in {"CBFZ", "CBF0"}:
                        active_codebook = decoded
                    elif subchunk.chunk_id in {"CBPZ", "CBP0"}:
                        active_codebook = vqa.apply_cbp_update(active_codebook, decoded, header).codebook
                continue
            if not subchunk.chunk_id.endswith("Z"):
                issues.append(f"{subchunk.chunk_id}:not_lcw")
                subchunks.append(chunk(subchunk.chunk_id, subchunk.payload))
                if decoded is not None and subchunk.chunk_id in {"CBPZ", "CBP0"}:
                    active_codebook = vqa.apply_cbp_update(active_codebook, decoded, header).codebook
                continue
            if decoded is None:
                subchunks.append(chunk(subchunk.chunk_id, subchunk.payload))
                continue
            output_decoded = decoded
            active_vectors = 0 if active_codebook is None else len(active_codebook) // vector_size
            if (
                subchunk.chunk_id == "CBPZ"
                and synthetic_no_room_cbpz_bytes > 0
                and not used_synthetic_no_room_cbpz
                and active_vectors >= header.max_codebook_entries
            ):
                output_decoded = vqa.decode_lcw(
                    synthetic_long_copy_payload(vector_size, synthetic_no_room_cbpz_bytes)
                )
                encoded = synthetic_long_copy_payload(vector_size, synthetic_no_room_cbpz_bytes)
                used_synthetic_no_room_cbpz = True
                stats["synthetic_no_room_cbpz"] += 1
            else:
                encoded = lcw_compress_vqa_extended(output_decoded)
            stats["chunks_recompressed"] += 1
            stats["old_lcw_bytes"] += len(subchunk.payload)
            stats["new_lcw_bytes"] += len(encoded)
            subchunks.append(chunk(subchunk.chunk_id, encoded))
            if subchunk.chunk_id in {"CBPZ", "CBP0"}:
                active_codebook = vqa.apply_cbp_update(active_codebook, output_decoded, header).codebook

        output_chunks.append(chunk("VQFR", b"".join(subchunks)))

    body = b"WVQA" + b"".join(output_chunks)
    return b"FORM" + be32(len(body)) + body, stats, issues


def build(args: argparse.Namespace) -> dict[str, str]:
    source_data, entries, table_end = read_mix(args.source)
    requested = parse_entries(args.entries)
    wanted = {item.strip() for item in args.chunk_ids.split(",") if item.strip()}
    replacements: dict[int, bytes] = {}
    entry_rows: list[dict[str, str]] = []

    for entry_index in requested:
        if entry_index < 0 or entry_index >= len(entries):
            raise ValueError(f"entry {entry_index} outside 0..{len(entries) - 1}")
        file_id, _offset, _size = entries[entry_index]
        payload = entry_payload(source_data, table_end, entries[entry_index])
        if not (payload.startswith(b"FORM") and payload[8:12] == b"WVQA"):
            row = {field: "" for field in ENTRY_FIELDS}
            row.update(
                {
                    "status": "skip",
                    "entry_index": str(entry_index),
                    "file_id": f"{file_id:08x}",
                    "old_payload_bytes": str(len(payload)),
                    "new_payload_bytes": str(len(payload)),
                    "issues": "not_wvqa",
                }
            )
            entry_rows.append(row)
            continue
        try:
            new_payload, stats, issues = recompress_payload(payload, wanted, args.synthetic_no_room_cbpz_bytes)
        except Exception as exc:  # noqa: BLE001 - recorded as report context.
            stats = {
                "frames": 0,
                "chunks_seen": 0,
                "chunks_recompressed": 0,
                "synthetic_no_room_cbpz": 0,
                "old_lcw_bytes": 0,
                "new_lcw_bytes": 0,
            }
            new_payload = payload
            issues = [f"recompress_error:{type(exc).__name__}:{exc}"]
        if not issues and stats["chunks_recompressed"] > 0:
            replacements[entry_index] = new_payload
        row = {
            "status": "pass" if not issues and stats["chunks_recompressed"] > 0 else "gap",
            "entry_index": str(entry_index),
            "file_id": f"{file_id:08x}",
            "frames": str(stats["frames"]),
            "chunks_seen": str(stats["chunks_seen"]),
            "chunks_recompressed": str(stats["chunks_recompressed"]),
            "synthetic_no_room_cbpz": str(stats["synthetic_no_room_cbpz"]),
            "old_lcw_bytes": str(stats["old_lcw_bytes"]),
            "new_lcw_bytes": str(stats["new_lcw_bytes"]),
            "old_payload_bytes": str(len(payload)),
            "new_payload_bytes": str(len(new_payload)),
            "issues": ";".join(issues),
        }
        entry_rows.append(row)

    output_mix = args.output / "mix" / args.source.name
    write_mix_with_replacements(args.source, output_mix, replacements)
    write_csv(args.output / "entries.csv", ENTRY_FIELDS, entry_rows)
    failed = [row for row in entry_rows if row["status"] not in {"pass", "skip"}]
    summary = {
        "status": "pass" if not failed and len(replacements) > 0 else "gap",
        "source_mix": str(args.source),
        "output_mix": str(output_mix),
        "entries_requested": ",".join(str(item) for item in requested),
        "entries_recompressed": str(len(replacements)),
        "entries_failed": str(len(failed)),
        "chunk_ids": ",".join(sorted(wanted)),
        "issues": ";".join(f"{row['entry_index']}:{row['issues']}" for row in failed if row.get("issues")),
    }
    write_csv(args.output / "summary.csv", SUMMARY_FIELDS, [summary])
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--entries", required=True, help="Comma/range list, e.g. 0,19,20")
    parser.add_argument("--chunk-ids", default="CBPZ", help="Comma list of VQA subchunks to recompress")
    parser.add_argument(
        "--synthetic-no-room-cbpz-bytes",
        type=int,
        default=0,
        help="For the first CBPZ seen after the active codebook is full, emit a synthetic long-copy LCW payload of this decoded size.",
    )
    parser.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()

    summary = build(args)
    print(f"VQA LCW recompress: {summary['status']}")
    print(f"Entries recompressed: {summary['entries_recompressed']}")
    print(f"Output: {summary['output_mix']}")
    if summary["issues"]:
        print(f"Issues: {summary['issues']}")


if __name__ == "__main__":
    main()
