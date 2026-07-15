#!/usr/bin/env python3
"""Write a byte-exact native WVQA fixture and audit its runtime contract.

This is the baseline before changing pixels or resolution: rebuild the selected
FORM/WVQA payload from its parsed chunks, write it back into a MIX copy, and
prove that the rebuilt payload still matches the original runtime contract.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lolg_vqa_decode as vqa  # noqa: E402
import lolg_vqa_runtime_compat_audit as compat_audit  # noqa: E402


DEFAULT_SOURCE = Path("C/LOLG/LOCALLNG.MIX")
DEFAULT_OUTPUT = Path("output/vqa_native_exact_fixture_writer")

SUMMARY_FIELDS = [
    "status",
    "source_mix",
    "entry_index",
    "file_id",
    "output_payload",
    "output_mix",
    "original_payload_bytes",
    "rebuilt_payload_bytes",
    "original_payload_sha256",
    "rebuilt_payload_sha256",
    "payload_exact",
    "mix_exact",
    "runtime_compat_status",
    "runtime_compat_report",
    "top_chunks",
    "frame_shapes",
    "issues",
    "next_step",
]


@dataclass(frozen=True)
class MixEntry:
    file_id: int
    offset: int
    size: int


def be32(value: int) -> bytes:
    return struct.pack(">I", value)


def chunk(name: str, payload: bytes) -> bytes:
    data = name.encode("ascii") + be32(len(payload)) + payload
    if len(payload) & 1:
        data += b"\x00"
    return data


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_mix(path: Path) -> tuple[bytes, list[MixEntry], int]:
    data = path.read_bytes()
    if len(data) < 6:
        raise ValueError(f"{path}: too small to be a MIX archive")
    count, body_size = struct.unpack_from("<HI", data, 0)
    table_end = 6 + count * 12
    if table_end > len(data):
        raise ValueError(f"{path}: invalid MIX table")
    if table_end + body_size > len(data):
        raise ValueError(f"{path}: MIX body exceeds file size")
    entries: list[MixEntry] = []
    for index in range(count):
        file_id, offset, size = struct.unpack_from("<III", data, 6 + index * 12)
        if offset + size > body_size:
            raise ValueError(f"{path}: entry {index} exceeds MIX body")
        entries.append(MixEntry(file_id=file_id, offset=offset, size=size))
    return data, entries, table_end


def entry_payload(data: bytes, table_end: int, entry: MixEntry) -> bytes:
    start = table_end + entry.offset
    return data[start : start + entry.size]


def rebuild_form_wvqa(payload: bytes) -> bytes:
    if len(payload) < 12 or payload[:4] != b"FORM" or payload[8:12] != b"WVQA":
        raise ValueError("selected payload is not FORM/WVQA")
    form_end = min(len(payload), 8 + struct.unpack_from(">I", payload, 4)[0])
    chunks = vqa.iter_chunks(payload, 12, form_end)
    body = b"WVQA" + b"".join(chunk(row.chunk_id, row.payload) for row in chunks)
    return b"FORM" + be32(len(body)) + body


def write_mix_with_replacement(
    source_mix: Path,
    output_mix: Path,
    entry_index: int,
    replacement_payload: bytes,
) -> None:
    source_data, entries, table_end = read_mix(source_mix)
    payloads: dict[int, bytes] = {}
    for index, entry in enumerate(entries):
        payloads[index] = replacement_payload if index == entry_index else entry_payload(source_data, table_end, entry)

    physical_order = sorted(range(len(entries)), key=lambda index: entries[index].offset)
    offsets: dict[int, int] = {}
    cursor = 0
    body_parts: list[bytes] = []
    for index in physical_order:
        offsets[index] = cursor
        body_parts.append(payloads[index])
        cursor += len(payloads[index])

    table = bytearray(struct.pack("<HI", len(entries), cursor))
    for index, entry in enumerate(entries):
        table.extend(struct.pack("<III", entry.file_id, offsets[index], len(payloads[index])))

    output_mix.parent.mkdir(parents=True, exist_ok=True)
    output_mix.write_bytes(bytes(table) + b"".join(body_parts))


def frame_shapes(payload: bytes) -> str:
    _header, chunks = vqa.parse_vqa(payload)
    shapes: dict[str, int] = {}
    for row in chunks:
        if row.chunk_id != "VQFR":
            continue
        shape = "+".join(sub.chunk_id for sub in vqa.iter_chunks(row.payload, 0))
        shapes[shape] = shapes.get(shape, 0) + 1
    return ";".join(f"{shape}:{count}" for shape, count in sorted(shapes.items()))


def top_chunks(payload: bytes) -> str:
    _header, chunks = vqa.parse_vqa(payload)
    counts: dict[str, int] = {}
    for row in chunks:
        counts[row.chunk_id] = counts.get(row.chunk_id, 0) + 1
    return ",".join(f"{name}:{counts[name]}" for name in sorted(counts))


def build(args: argparse.Namespace) -> dict[str, str]:
    source_data, entries, table_end = read_mix(args.source)
    if args.entry < 0 or args.entry >= len(entries):
        raise ValueError(f"entry {args.entry} outside 0..{len(entries) - 1}")

    source_entry = entries[args.entry]
    original_payload = entry_payload(source_data, table_end, source_entry)
    rebuilt_payload = rebuild_form_wvqa(original_payload)

    output_payload = args.output / "payloads" / args.source.stem / f"{source_entry.file_id:08x}.vqa"
    output_mix = args.output / "mix" / args.source.name
    output_payload.parent.mkdir(parents=True, exist_ok=True)
    output_payload.write_bytes(rebuilt_payload)
    write_mix_with_replacement(args.source, output_mix, args.entry, rebuilt_payload)

    audit_args = argparse.Namespace(
        original_label=f"{args.source}:{args.entry}",
        replacement_label=str(output_payload),
    )
    compat_summary, compat_frames = compat_audit.audit(original_payload, rebuilt_payload, audit_args)
    compat_dir = args.output / "runtime_compat"
    write_csv(compat_dir / "summary.csv", compat_audit.SUMMARY_FIELDS, [compat_summary])
    write_csv(compat_dir / "frames.csv", compat_audit.FRAME_FIELDS, compat_frames)

    payload_exact = original_payload == rebuilt_payload
    mix_exact = source_data == output_mix.read_bytes()
    issues: list[str] = []
    if not payload_exact:
        issues.append("payload_not_byte_exact")
    if compat_summary.get("status") != "pass":
        issues.append("runtime_compat_gap")

    status = "pass" if not issues else "gap"
    summary = {
        "status": status,
        "source_mix": str(args.source),
        "entry_index": str(args.entry),
        "file_id": f"{source_entry.file_id:08x}",
        "output_payload": str(output_payload),
        "output_mix": str(output_mix),
        "original_payload_bytes": str(len(original_payload)),
        "rebuilt_payload_bytes": str(len(rebuilt_payload)),
        "original_payload_sha256": sha256(original_payload),
        "rebuilt_payload_sha256": sha256(rebuilt_payload),
        "payload_exact": "1" if payload_exact else "0",
        "mix_exact": "1" if mix_exact else "0",
        "runtime_compat_status": compat_summary.get("status", ""),
        "runtime_compat_report": str(compat_dir / "summary.csv"),
        "top_chunks": top_chunks(rebuilt_payload),
        "frame_shapes": frame_shapes(rebuilt_payload),
        "issues": ";".join(issues),
        "next_step": (
            "use this exact fixture as the baseline for a CBPZ/VPTZ-preserving pixel writer"
            if status == "pass"
            else "fix exact fixture roundtrip before changing VQA pixels"
        ),
    }
    write_csv(args.output / "summary.csv", SUMMARY_FIELDS, [summary])
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (args.output / "header.json").write_text(
        json.dumps(asdict(vqa.parse_vqa(rebuilt_payload)[0]), indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--entry", type=int, default=2)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    summary = build(args)
    print(f"VQA native exact fixture writer: {summary['status']}")
    print(f"Payload exact: {summary['payload_exact']}")
    print(f"Runtime compat: {summary['runtime_compat_status']}")
    print(f"Summary: {args.output / 'summary.csv'}")
    if summary["issues"]:
        print(f"Issues: {summary['issues']}")


if __name__ == "__main__":
    main()
