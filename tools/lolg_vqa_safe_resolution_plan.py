#!/usr/bin/env python3
"""Plan VQA replacement resolutions under an observed runtime block budget."""

from __future__ import annotations

import argparse
import csv
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lolg_vqa_decode as vqa  # noqa: E402
from lolg_mix_extract import parse_entries  # noqa: E402


FIELDS = [
    "status",
    "archive",
    "entry_index",
    "file_id",
    "source_bytes",
    "source_width",
    "source_height",
    "frames",
    "block_width",
    "block_height",
    "source_blocks",
    "source_decoded_vpt_bytes",
    "desired_width",
    "desired_height",
    "block_budget",
    "target_width",
    "target_height",
    "target_blocks",
    "target_decoded_vpt_bytes",
    "headroom_blocks",
    "pixel_scale",
    "target_aspect",
    "desired_aspect",
    "issues",
]


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


def choose_target(
    desired_width: int,
    desired_height: int,
    block_width: int,
    block_height: int,
    block_budget: int,
) -> tuple[int, int, int]:
    desired_blocks_x = max(1, desired_width // block_width)
    desired_blocks_y = max(1, desired_height // block_height)
    desired_aspect = desired_width / desired_height
    best: tuple[int, float, int, int] | None = None

    for blocks_y in range(1, desired_blocks_y + 1):
        blocks_x = min(desired_blocks_x, block_budget // blocks_y)
        if blocks_x < 1:
            continue
        blocks = blocks_x * blocks_y
        width = blocks_x * block_width
        height = blocks_y * block_height
        aspect_delta = abs((width / height) - desired_aspect)
        candidate = (blocks, -aspect_delta, width, height)
        if best is None or candidate > best:
            best = candidate

    if best is None:
        raise ValueError("block budget too small for one VQA block")
    blocks, _neg_aspect_delta, width, height = best
    return width, height, blocks


def ratio(value: int | float, total: int | float) -> str:
    if not total:
        return "0.000000"
    return f"{value / total:.6f}"


def plan_archive(
    archive: Path,
    selected_entries: set[int] | None,
    desired_width: int,
    desired_height: int,
    block_budget: int,
) -> list[dict[str, str]]:
    data, entries, table_end = read_mix(archive)
    rows: list[dict[str, str]] = []
    for index, entry in enumerate(entries):
        if selected_entries is not None and index not in selected_entries:
            continue
        file_id, _offset, source_size = entry
        payload = entry_payload(data, table_end, entry)
        if not payload.startswith(b"FORM"):
            continue
        try:
            header, _chunks = vqa.parse_vqa(payload)
        except Exception as exc:
            rows.append(
                {
                    "status": "gap",
                    "archive": str(archive),
                    "entry_index": str(index),
                    "file_id": f"{file_id:08x}",
                    "source_bytes": str(source_size),
                    "issues": f"parse_vqa:{exc}",
                }
            )
            continue
        source_blocks = (header.width // header.block_width) * (header.height // header.block_height)
        target_width, target_height, target_blocks = choose_target(
            desired_width,
            desired_height,
            header.block_width,
            header.block_height,
            block_budget,
        )
        target_pixels = target_width * target_height
        source_pixels = header.width * header.height
        rows.append(
            {
                "status": "pass",
                "archive": str(archive),
                "entry_index": str(index),
                "file_id": f"{file_id:08x}",
                "source_bytes": str(source_size),
                "source_width": str(header.width),
                "source_height": str(header.height),
                "frames": str(header.frame_count),
                "block_width": str(header.block_width),
                "block_height": str(header.block_height),
                "source_blocks": str(source_blocks),
                "source_decoded_vpt_bytes": str(source_blocks * 2),
                "desired_width": str(desired_width),
                "desired_height": str(desired_height),
                "block_budget": str(block_budget),
                "target_width": str(target_width),
                "target_height": str(target_height),
                "target_blocks": str(target_blocks),
                "target_decoded_vpt_bytes": str(target_blocks * 2),
                "headroom_blocks": str(block_budget - target_blocks),
                "pixel_scale": ratio(target_pixels, source_pixels),
                "target_aspect": f"{target_width / target_height:.6f}",
                "desired_aspect": f"{desired_width / desired_height:.6f}",
                "issues": "",
            }
        )
    return rows


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+", type=Path)
    parser.add_argument("--entries", action="append", help="Entry index/range list, e.g. 0,2,19-20")
    parser.add_argument("--desired-width", type=int, default=896)
    parser.add_argument("--desired-height", type=int, default=560)
    parser.add_argument(
        "--block-budget",
        type=int,
        default=31220,
        help="Maximum decoded VPT blocks; 31220 is the highest tested stable MOVIES entry-4 budget.",
    )
    parser.add_argument("--expect-entries", type=int, help="Require exactly this many VQA entries.")
    parser.add_argument(
        "--expect-target",
        action="append",
        default=[],
        help="Require the set of planned targets to match this WxH value; may be repeated.",
    )
    parser.add_argument("-o", "--output", type=Path, default=Path("output/vqa_safe_resolution_plan"))
    args = parser.parse_args()

    if args.desired_width < 1 or args.desired_height < 1:
        raise SystemExit("desired dimensions must be positive")
    if args.block_budget < 1:
        raise SystemExit("block budget must be positive")

    selected_entries = parse_entries(args.entries)
    rows: list[dict[str, str]] = []
    for archive in args.archives:
        rows.extend(plan_archive(archive, selected_entries, args.desired_width, args.desired_height, args.block_budget))

    gaps = sum(1 for row in rows if row.get("status") != "pass")
    issues: list[str] = []
    if gaps:
        issues.append(f"gaps:{gaps}")
    if args.expect_entries is not None and len(rows) != args.expect_entries:
        issues.append(f"entries:{len(rows)}!={args.expect_entries}")
    if args.expect_target:
        expected_targets = set(args.expect_target)
        actual_targets = {
            f"{row.get('target_width')}x{row.get('target_height')}"
            for row in rows
            if row.get("status") == "pass"
        }
        if actual_targets != expected_targets:
            issues.append(
                "targets:"
                + ",".join(sorted(actual_targets))
                + "!="
                + ",".join(sorted(expected_targets))
            )
    summary = {
        "status": "pass" if not issues else "gap",
        "archives": str(len(args.archives)),
        "vqa_entries": str(len(rows)),
        "gaps": str(gaps),
        "desired_width": str(args.desired_width),
        "desired_height": str(args.desired_height),
        "block_budget": str(args.block_budget),
        "issues": ";".join(issues),
        "next_step": "generate per-entry VQA candidates at the planned target dimensions",
    }

    write_csv(args.output / "entries.csv", FIELDS, rows)
    write_csv(args.output / "summary.csv", list(summary.keys()), [summary])
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(
        "VQA safe resolution plan: "
        f"{summary['status']} entries={summary['vqa_entries']} budget={summary['block_budget']} "
        f"desired={summary['desired_width']}x{summary['desired_height']}"
    )
    print(f"Summary: {args.output / 'summary.csv'}")
    print(f"Entries: {args.output / 'entries.csv'}")
    if issues:
        print(f"Issues: {summary['issues']}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
