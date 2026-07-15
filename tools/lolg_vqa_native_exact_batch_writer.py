#!/usr/bin/env python3
"""Batch-rebuild native WVQA entries exactly before attempting HD changes."""

from __future__ import annotations

import argparse
import csv
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lolg_vqa_native_exact_fixture_writer as native_exact  # noqa: E402
import lolg_vqa_runtime_compat_audit as compat_audit  # noqa: E402


DEFAULT_OUTPUT = Path("output/vqa_native_exact_batch_writer")

SUMMARY_FIELDS = [
    "status",
    "source_mix",
    "output_mix",
    "entries_requested",
    "entries_rebuilt",
    "entries_failed",
    "payload_exact_entries",
    "mix_exact",
    "runtime_compat_pass_entries",
    "issues",
    "next_step",
]

ENTRY_FIELDS = [
    "status",
    "entry_index",
    "file_id",
    "output_payload",
    "original_payload_bytes",
    "rebuilt_payload_bytes",
    "original_payload_sha256",
    "rebuilt_payload_sha256",
    "payload_exact",
    "runtime_compat_status",
    "runtime_compat_report",
    "top_chunks",
    "frame_shapes",
    "issues",
]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_entries(raw: str) -> list[int]:
    entries: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start = int(start_text, 0)
            end = int(end_text, 0)
            if end < start:
                raise ValueError(f"invalid entry range: {part}")
            entries.extend(range(start, end + 1))
        else:
            entries.append(int(part, 0))
    return sorted(dict.fromkeys(entries))


def entry_payload(data: bytes, table_end: int, entry: native_exact.MixEntry) -> bytes:
    return native_exact.entry_payload(data, table_end, entry)


def write_mix_with_replacements(
    source_data: bytes,
    entries: list[native_exact.MixEntry],
    table_end: int,
    output_mix: Path,
    replacements: dict[int, bytes],
) -> None:
    payloads: dict[int, bytes] = {}
    for index, entry in enumerate(entries):
        payloads[index] = replacements.get(index, entry_payload(source_data, table_end, entry))

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


def build(args: argparse.Namespace) -> dict[str, str]:
    source_data, mix_entries, table_end = native_exact.read_mix(args.source)
    requested = parse_entries(args.entries)
    out_dir = args.output
    payload_dir = out_dir / "payloads" / args.source.stem
    compat_root = out_dir / "runtime_compat" / args.source.stem
    output_mix = out_dir / "mix" / args.source.name
    payload_dir.mkdir(parents=True, exist_ok=True)

    replacements: dict[int, bytes] = {}
    entry_rows: list[dict[str, str]] = []
    issues: list[str] = []

    for entry_index in requested:
        if entry_index < 0 or entry_index >= len(mix_entries):
            entry_rows.append(
                {
                    "status": "gap",
                    "entry_index": str(entry_index),
                    "file_id": "",
                    "output_payload": "",
                    "original_payload_bytes": "",
                    "rebuilt_payload_bytes": "",
                    "original_payload_sha256": "",
                    "rebuilt_payload_sha256": "",
                    "payload_exact": "0",
                    "runtime_compat_status": "",
                    "runtime_compat_report": "",
                    "top_chunks": "",
                    "frame_shapes": "",
                    "issues": "entry_out_of_range",
                }
            )
            continue

        source_entry = mix_entries[entry_index]
        original_payload = entry_payload(source_data, table_end, source_entry)
        entry_issues: list[str] = []
        try:
            rebuilt_payload = native_exact.rebuild_form_wvqa(original_payload)
        except Exception as exc:  # noqa: BLE001 - written into CSV for analysis.
            rebuilt_payload = b""
            entry_issues.append(f"rebuild_error:{type(exc).__name__}:{exc}")

        output_payload = payload_dir / f"{entry_index:04d}_{source_entry.file_id:08x}.vqa"
        if rebuilt_payload:
            output_payload.write_bytes(rebuilt_payload)
            replacements[entry_index] = rebuilt_payload

        compat_status = ""
        compat_report = ""
        if rebuilt_payload:
            compat_dir = compat_root / f"{entry_index:04d}_{source_entry.file_id:08x}"
            audit_args = argparse.Namespace(
                original_label=f"{args.source}:{entry_index}",
                replacement_label=str(output_payload),
            )
            compat_summary, compat_frames = compat_audit.audit(original_payload, rebuilt_payload, audit_args)
            write_csv(compat_dir / "summary.csv", compat_audit.SUMMARY_FIELDS, [compat_summary])
            write_csv(compat_dir / "frames.csv", compat_audit.FRAME_FIELDS, compat_frames)
            compat_status = compat_summary.get("status", "")
            compat_report = str(compat_dir / "summary.csv")
            if compat_status != "pass":
                entry_issues.append("runtime_compat_gap")

        payload_exact = bool(rebuilt_payload) and original_payload == rebuilt_payload
        if not payload_exact:
            entry_issues.append("payload_not_byte_exact")

        row_status = "pass" if not entry_issues else "gap"
        entry_rows.append(
            {
                "status": row_status,
                "entry_index": str(entry_index),
                "file_id": f"{source_entry.file_id:08x}",
                "output_payload": str(output_payload) if rebuilt_payload else "",
                "original_payload_bytes": str(len(original_payload)),
                "rebuilt_payload_bytes": str(len(rebuilt_payload)),
                "original_payload_sha256": native_exact.sha256(original_payload),
                "rebuilt_payload_sha256": native_exact.sha256(rebuilt_payload) if rebuilt_payload else "",
                "payload_exact": "1" if payload_exact else "0",
                "runtime_compat_status": compat_status,
                "runtime_compat_report": compat_report,
                "top_chunks": native_exact.top_chunks(rebuilt_payload) if rebuilt_payload else "",
                "frame_shapes": native_exact.frame_shapes(rebuilt_payload) if rebuilt_payload else "",
                "issues": ";".join(entry_issues),
            }
        )

    write_mix_with_replacements(source_data, mix_entries, table_end, output_mix, replacements)
    mix_exact = source_data == output_mix.read_bytes()
    if not mix_exact:
        issues.append("mix_not_byte_exact")

    failed_rows = [row for row in entry_rows if row["status"] != "pass"]
    if failed_rows:
        issues.append("entry_gaps:" + ",".join(row["entry_index"] for row in failed_rows))

    payload_exact_entries = sum(1 for row in entry_rows if row["payload_exact"] == "1")
    runtime_pass_entries = sum(1 for row in entry_rows if row["runtime_compat_status"] == "pass")
    status = "pass" if not issues else "gap"
    summary = {
        "status": status,
        "source_mix": str(args.source),
        "output_mix": str(output_mix),
        "entries_requested": ",".join(str(entry) for entry in requested),
        "entries_rebuilt": str(len(replacements)),
        "entries_failed": str(len(failed_rows)),
        "payload_exact_entries": str(payload_exact_entries),
        "mix_exact": "1" if mix_exact else "0",
        "runtime_compat_pass_entries": str(runtime_pass_entries),
        "issues": ";".join(issues),
        "next_step": (
            "use this native-exact batch as the baseline for HD VPTZ/CBPZ changes"
            if status == "pass"
            else "fix native-exact batch before changing pixels or resolution"
        ),
    }
    write_csv(out_dir / "summary.csv", SUMMARY_FIELDS, [summary])
    write_csv(out_dir / "entries.csv", ENTRY_FIELDS, entry_rows)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--entries", required=True, help="Entry list/ranges, e.g. 2 or 0-27.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    summary = build(args)
    print(f"VQA native exact batch writer: {summary['status']}")
    print(f"Entries rebuilt: {summary['entries_rebuilt']}")
    print(f"Payload exact entries: {summary['payload_exact_entries']}")
    print(f"Mix exact: {summary['mix_exact']}")
    print(f"Runtime compat pass entries: {summary['runtime_compat_pass_entries']}")
    print(f"Summary: {args.output / 'summary.csv'}")
    if summary["issues"]:
        print(f"Issues: {summary['issues']}")


if __name__ == "__main__":
    main()
