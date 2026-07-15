#!/usr/bin/env python3
"""Batch-audit WVQA runtime compatibility for existing MIX replacements."""

from __future__ import annotations

import argparse
import csv
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lolg_vqa_runtime_compat_audit as compat_audit  # noqa: E402


DEFAULT_OUTPUT = Path("output/vqa_runtime_compat_batch_audit")
SUMMARY_FIELDS = [
    "status",
    "original_mix",
    "replacement_mix",
    "entries_requested",
    "entries_pass",
    "entries_gap",
    "entries_failed",
    "allow_resolution_change",
    "entries_csv",
    "issues",
    "next_step",
]
ENTRY_FIELDS = [
    "entry_index",
    "status",
    "runtime_compat_status",
    "original_bytes",
    "replacement_bytes",
    "entry_dir",
    "summary_csv",
    "frames_csv",
    "critical_issues",
]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


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


def build(args: argparse.Namespace) -> dict[str, str]:
    original_data, original_entries, original_table_end = read_mix(args.original)
    replacement_data, replacement_entries, replacement_table_end = read_mix(args.replacement)
    requested = parse_entries(args.entries)

    rows: list[dict[str, str]] = []
    issues: list[str] = []
    entries_pass = 0
    entries_gap = 0
    entries_failed = 0

    for entry_index in requested:
        entry_dir = args.output / f"entry_{entry_index:04d}"
        summary_csv = entry_dir / "summary.csv"
        frames_csv = entry_dir / "frames.csv"
        try:
            if entry_index >= len(original_entries) or entry_index >= len(replacement_entries):
                raise ValueError("entry index outside MIX table")
            original_payload = entry_payload(original_data, original_table_end, original_entries[entry_index])
            replacement_payload = entry_payload(
                replacement_data,
                replacement_table_end,
                replacement_entries[entry_index],
            )
            audit_args = argparse.Namespace(
                original_label=f"{args.original}:{entry_index}",
                replacement_label=f"{args.replacement}:{entry_index}",
                allow_resolution_change=args.allow_resolution_change,
            )
            compat_summary, compat_frames = compat_audit.audit(original_payload, replacement_payload, audit_args)
            write_csv(summary_csv, compat_audit.SUMMARY_FIELDS, [compat_summary])
            write_csv(frames_csv, compat_audit.FRAME_FIELDS, compat_frames)
            runtime_status = compat_summary["status"]
            if runtime_status == "pass":
                status = "pass"
                entries_pass += 1
            else:
                status = "gap"
                entries_gap += 1
                issues.append(f"entry_{entry_index}:{compat_summary['critical_issues'][:200]}")
            row = {
                "entry_index": str(entry_index),
                "status": status,
                "runtime_compat_status": runtime_status,
                "original_bytes": str(len(original_payload)),
                "replacement_bytes": str(len(replacement_payload)),
                "entry_dir": str(entry_dir),
                "summary_csv": str(summary_csv),
                "frames_csv": str(frames_csv),
                "critical_issues": compat_summary["critical_issues"],
            }
        except Exception as exc:  # noqa: BLE001 - reported as CSV issue context.
            entries_failed += 1
            issue = f"entry_{entry_index}:audit_error:{type(exc).__name__}:{exc}"
            issues.append(issue)
            row = {
                "entry_index": str(entry_index),
                "status": "failed",
                "runtime_compat_status": "failed",
                "original_bytes": "",
                "replacement_bytes": "",
                "entry_dir": str(entry_dir),
                "summary_csv": str(summary_csv),
                "frames_csv": str(frames_csv),
                "critical_issues": issue,
            }
        rows.append(row)
        print(
            f"Entry {entry_index:04d}: {row['status']} runtime={row['runtime_compat_status']}",
            flush=True,
        )

    entries_csv = args.output / "entries.csv"
    write_csv(entries_csv, ENTRY_FIELDS, rows)
    status = "pass" if entries_gap == 0 and entries_failed == 0 else "gap"
    summary = {
        "status": status,
        "original_mix": str(args.original),
        "replacement_mix": str(args.replacement),
        "entries_requested": str(len(requested)),
        "entries_pass": str(entries_pass),
        "entries_gap": str(entries_gap),
        "entries_failed": str(entries_failed),
        "allow_resolution_change": "1" if args.allow_resolution_change else "0",
        "entries_csv": str(entries_csv),
        "issues": ";".join(issues[:50]),
        "next_step": "runtime-test audited replacement MIX" if status == "pass" else "fix entries with runtime compat gaps",
    }
    write_csv(args.output / "summary.csv", SUMMARY_FIELDS, [summary])
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--replacement", type=Path, required=True)
    parser.add_argument("--entries", required=True)
    parser.add_argument("--allow-resolution-change", action="store_true")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    summary = build(args)
    print(f"VQA runtime compat batch audit: {summary['status']}")
    print(f"Summary: {args.output / 'summary.csv'}")
    if summary["issues"]:
        print(f"Issues: {summary['issues'][:500]}")


if __name__ == "__main__":
    main()
