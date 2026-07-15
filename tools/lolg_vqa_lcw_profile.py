#!/usr/bin/env python3
"""Profile LCW command usage inside Westwood VQA chunks."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import DefaultDict


BASE_DIR = Path(__file__).resolve().parents[1]
TOOLS_DIR = BASE_DIR / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import lolg_vqa_decode as vqa  # noqa: E402


CASE_FIELDS = [
    "label",
    "path",
    "entry",
    "payload_bytes",
    "width",
    "height",
    "frames",
    "block_count",
    "max_codebook_entries",
    "header_max_cbfz",
    "header_max_vptz",
    "max_vqfr",
    "frame_shapes",
]

LCW_FIELDS = [
    "label",
    "chunk_id",
    "source_bytes",
    "ops",
    "literal_ops",
    "short_rel_ops",
    "abs_copy_ops",
    "long_copy_fe_ops",
    "fill_ff_ops",
    "end_ops",
    "literal_out",
    "copy_out",
    "fill_out",
    "max_command_count",
    "errors",
]

FIRST_FRAME_FIELDS = [
    "label",
    "chunk_id",
    "source_bytes",
    "ops",
    "literal_ops",
    "short_rel_ops",
    "abs_copy_ops",
    "long_copy_fe_ops",
    "fill_ff_ops",
    "end_ops",
    "literal_out",
    "copy_out",
    "fill_out",
    "max_command_count",
    "errors",
    "consumed_bytes",
]

DIALECT_FIELDS = [
    "status",
    "reference_label",
    "label",
    "chunk_id",
    "reference_long_copy_fe_ops",
    "long_copy_fe_ops",
    "reference_fill_ff_ops",
    "fill_ff_ops",
    "reference_max_command_count",
    "max_command_count",
    "reference_errors",
    "errors",
    "issues",
]


@dataclass
class LcwProfile:
    counts: Counter[str]
    literal_out: int
    copy_out: int
    fill_out: int
    max_command_count: int
    errors: int
    consumed_bytes: int


def read_payload(path: Path, entry: int | None) -> bytes:
    if entry is None:
        return path.read_bytes()
    return vqa.read_mix_entry(path, entry)


def parse_case(value: str) -> tuple[str, Path, int | None]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("case must be LABEL=PATH[,ENTRY]")
    label, spec = value.split("=", 1)
    label = label.strip()
    if not label:
        raise argparse.ArgumentTypeError("case label is empty")
    path_text = spec
    entry: int | None = None
    if "," in spec:
        maybe_path, maybe_entry = spec.rsplit(",", 1)
        if maybe_entry.strip().isdigit():
            path_text = maybe_path
            entry = int(maybe_entry)
    path = Path(path_text)
    if not path.is_absolute():
        path = BASE_DIR / path
    return label, path, entry


def profile_lcw(payload: bytes) -> LcwProfile:
    pos = 0
    counts: Counter[str] = Counter()
    literal_out = 0
    copy_out = 0
    fill_out = 0
    max_command_count = 0
    errors = 0

    while pos < len(payload):
        command = payload[pos]
        pos += 1

        if command == 0x80:
            counts["end"] += 1
            break

        if command == 0xFF:
            if pos + 3 > len(payload):
                errors += 1
                break
            count = payload[pos] | (payload[pos + 1] << 8)
            pos += 3
            counts["fill_ff"] += 1
            fill_out += count
            max_command_count = max(max_command_count, count)
            continue

        if command == 0xFE:
            if pos + 4 > len(payload):
                errors += 1
                break
            count = payload[pos] | (payload[pos + 1] << 8)
            pos += 4
            counts["long_copy_fe"] += 1
            copy_out += count
            max_command_count = max(max_command_count, count)
            continue

        if (command & 0x80) == 0:
            if pos >= len(payload):
                errors += 1
                break
            count = ((command & 0x70) >> 4) + 3
            pos += 1
            counts["short_rel"] += 1
            copy_out += count
            max_command_count = max(max_command_count, count)
            continue

        if (command & 0x40) == 0:
            count = command & 0x3F
            if pos + count > len(payload):
                errors += 1
                count = max(0, len(payload) - pos)
            pos += count
            counts["literal"] += 1
            literal_out += count
            max_command_count = max(max_command_count, count)
            continue

        if pos + 2 > len(payload):
            errors += 1
            break
        count = (command & 0x3F) + 3
        pos += 2
        counts["abs_copy"] += 1
        copy_out += count
        max_command_count = max(max_command_count, count)

    return LcwProfile(
        counts=counts,
        literal_out=literal_out,
        copy_out=copy_out,
        fill_out=fill_out,
        max_command_count=max_command_count,
        errors=errors,
        consumed_bytes=pos,
    )


def row_from_profile(label: str, chunk_id: str, source_bytes: int, profile: LcwProfile) -> dict[str, str]:
    counts = profile.counts
    ops = sum(counts[name] for name in ("literal", "short_rel", "abs_copy", "long_copy_fe", "fill_ff"))
    return {
        "label": label,
        "chunk_id": chunk_id,
        "source_bytes": str(source_bytes),
        "ops": str(ops),
        "literal_ops": str(counts["literal"]),
        "short_rel_ops": str(counts["short_rel"]),
        "abs_copy_ops": str(counts["abs_copy"]),
        "long_copy_fe_ops": str(counts["long_copy_fe"]),
        "fill_ff_ops": str(counts["fill_ff"]),
        "end_ops": str(counts["end"]),
        "literal_out": str(profile.literal_out),
        "copy_out": str(profile.copy_out),
        "fill_out": str(profile.fill_out),
        "max_command_count": str(profile.max_command_count),
        "errors": str(profile.errors),
    }


def profile_case(label: str, path: Path, entry: int | None) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    payload = read_payload(path, entry)
    header, chunks = vqa.parse_vqa(payload)
    shape_counts: Counter[str] = Counter()
    lcw_counts: DefaultDict[str, Counter[str]] = defaultdict(Counter)
    lcw_bytes: DefaultDict[str, Counter[str]] = defaultdict(Counter)
    max_chunk: Counter[str] = Counter()
    max_command_count_by_chunk: Counter[str] = Counter()
    first_rows: list[dict[str, str]] = []
    frames = 0
    max_vqfr = 0

    for chunk in chunks:
        if chunk.chunk_id != "VQFR":
            continue
        frames += 1
        max_vqfr = max(max_vqfr, chunk.size)
        subchunks = vqa.iter_chunks(chunk.payload, 0)
        shape_counts["+".join(subchunk.chunk_id for subchunk in subchunks)] += 1
        for subchunk in subchunks:
            if not subchunk.chunk_id.endswith("Z"):
                continue
            profile = profile_lcw(subchunk.payload)
            max_chunk[subchunk.chunk_id] = max(max_chunk[subchunk.chunk_id], len(subchunk.payload))
            lcw_counts[subchunk.chunk_id].update(profile.counts)
            lcw_bytes[subchunk.chunk_id].update(
                {
                    "source_bytes": len(subchunk.payload),
                    "literal_out": profile.literal_out,
                    "copy_out": profile.copy_out,
                    "fill_out": profile.fill_out,
                    "errors": profile.errors,
                }
            )
            max_command_count_by_chunk[subchunk.chunk_id] = max(
                max_command_count_by_chunk[subchunk.chunk_id],
                profile.max_command_count,
            )
            if frames == 1:
                first_row = row_from_profile(label, subchunk.chunk_id, len(subchunk.payload), profile)
                first_row["consumed_bytes"] = str(profile.consumed_bytes)
                first_rows.append(first_row)

    case_row = {
        "label": label,
        "path": str(path),
        "entry": "" if entry is None else str(entry),
        "payload_bytes": str(len(payload)),
        "width": str(header.width),
        "height": str(header.height),
        "frames": str(frames),
        "block_count": str(header.block_count),
        "max_codebook_entries": str(header.max_codebook_entries),
        "header_max_cbfz": str(header.max_cbfz_size),
        "header_max_vptz": str(header.max_vptz_size),
        "max_vqfr": str(max_vqfr),
        "frame_shapes": ";".join(f"{shape}:{count}" for shape, count in shape_counts.items()),
    }

    lcw_rows: list[dict[str, str]] = []
    for chunk_id in sorted(lcw_counts):
        profile = LcwProfile(
            counts=lcw_counts[chunk_id],
            literal_out=lcw_bytes[chunk_id]["literal_out"],
            copy_out=lcw_bytes[chunk_id]["copy_out"],
            fill_out=lcw_bytes[chunk_id]["fill_out"],
            max_command_count=max_command_count_by_chunk[chunk_id],
            errors=lcw_bytes[chunk_id]["errors"],
            consumed_bytes=0,
        )
        lcw_rows.append(row_from_profile(label, chunk_id, max_chunk[chunk_id], profile))
        lcw_rows[-1]["source_bytes"] = str(lcw_bytes[chunk_id]["source_bytes"])

    return case_row, lcw_rows, first_rows


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def int_field(row: dict[str, str], key: str) -> int:
    try:
        return int(row.get(key, "0") or "0")
    except ValueError:
        return 0


def build_dialect_rows(reference_label: str, lcw_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_label_chunk = {(row["label"], row["chunk_id"]): row for row in lcw_rows}
    reference_rows = {
        row["chunk_id"]: row
        for row in lcw_rows
        if row["label"] == reference_label
    }
    labels = sorted({row["label"] for row in lcw_rows if row["label"] != reference_label})
    dialect_rows: list[dict[str, str]] = []

    for label in labels:
        for chunk_id, reference in sorted(reference_rows.items()):
            row = by_label_chunk.get((label, chunk_id))
            issues: list[str] = []
            if row is None:
                dialect_rows.append(
                    {
                        "status": "gap",
                        "reference_label": reference_label,
                        "label": label,
                        "chunk_id": chunk_id,
                        "reference_long_copy_fe_ops": reference["long_copy_fe_ops"],
                        "long_copy_fe_ops": "",
                        "reference_fill_ff_ops": reference["fill_ff_ops"],
                        "fill_ff_ops": "",
                        "reference_max_command_count": reference["max_command_count"],
                        "max_command_count": "",
                        "reference_errors": reference["errors"],
                        "errors": "",
                        "issues": "missing_chunk_profile",
                    }
                )
                continue

            reference_long = int_field(reference, "long_copy_fe_ops")
            row_long = int_field(row, "long_copy_fe_ops")
            reference_fill = int_field(reference, "fill_ff_ops")
            row_fill = int_field(row, "fill_ff_ops")
            reference_max = int_field(reference, "max_command_count")
            row_max = int_field(row, "max_command_count")
            reference_errors = int_field(reference, "errors")
            row_errors = int_field(row, "errors")

            if reference_long > 0 and row_long == 0:
                issues.append("long_copy_fe_missing")
            if reference_fill > 0 and row_fill == 0:
                issues.append("fill_ff_missing")
            if reference_max >= 1024 and row_max < reference_max // 4:
                issues.append("max_command_count_shrunk")
            if row_errors > reference_errors:
                issues.append("new_lcw_parse_errors")

            dialect_rows.append(
                {
                    "status": "pass" if not issues else "gap",
                    "reference_label": reference_label,
                    "label": label,
                    "chunk_id": chunk_id,
                    "reference_long_copy_fe_ops": reference["long_copy_fe_ops"],
                    "long_copy_fe_ops": row["long_copy_fe_ops"],
                    "reference_fill_ff_ops": reference["fill_ff_ops"],
                    "fill_ff_ops": row["fill_ff_ops"],
                    "reference_max_command_count": reference["max_command_count"],
                    "max_command_count": row["max_command_count"],
                    "reference_errors": reference["errors"],
                    "errors": row["errors"],
                    "issues": ";".join(issues),
                }
            )

    return dialect_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile LCW command usage inside VQA chunks.")
    parser.add_argument(
        "--case",
        action="append",
        required=True,
        help="Case as LABEL=PATH[,ENTRY]. Use ENTRY for MIX archives; omit it for raw VQA payloads.",
    )
    parser.add_argument("-o", "--output", type=Path, help="Output directory for CSV/JSON reports.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of compact text.")
    parser.add_argument(
        "--reference",
        help="Reference case label for dialect comparison. Defaults to the first --case label.",
    )
    parser.add_argument(
        "--fail-on-dialect-gap",
        action="store_true",
        help="Exit non-zero if any LCW dialect comparison row is a gap.",
    )
    args = parser.parse_args()

    case_rows: list[dict[str, str]] = []
    lcw_rows: list[dict[str, str]] = []
    first_rows: list[dict[str, str]] = []

    for raw_case in args.case:
        label, path, entry = parse_case(raw_case)
        case_row, case_lcw_rows, case_first_rows = profile_case(label, path, entry)
        case_rows.append(case_row)
        lcw_rows.extend(case_lcw_rows)
        first_rows.extend(case_first_rows)

    reference_label = args.reference or case_rows[0]["label"]
    dialect_rows = build_dialect_rows(reference_label, lcw_rows)

    if args.output:
        output = args.output
        write_csv(output / "cases.csv", CASE_FIELDS, case_rows)
        write_csv(output / "lcw.csv", LCW_FIELDS, lcw_rows)
        write_csv(output / "first_frame.csv", FIRST_FRAME_FIELDS, first_rows)
        write_csv(output / "dialect.csv", DIALECT_FIELDS, dialect_rows)
        (output / "summary.json").write_text(
            json.dumps(
                {
                    "cases": case_rows,
                    "lcw": lcw_rows,
                    "first_frame": first_rows,
                    "dialect": dialect_rows,
                },
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    if args.json:
        print(
            json.dumps(
                {"cases": case_rows, "lcw": lcw_rows, "first_frame": first_rows, "dialect": dialect_rows},
                ensure_ascii=True,
                indent=2,
            )
        )
        if args.fail_on_dialect_gap and any(row["status"] != "pass" for row in dialect_rows):
            raise SystemExit(1)
        return

    for row in case_rows:
        print(
            f"{row['label']}: {row['width']}x{row['height']} frames={row['frames']} "
            f"max_cbfz={row['header_max_cbfz']} max_vptz={row['header_max_vptz']} "
            f"payload={row['payload_bytes']}"
        )
    dialect_gaps = sum(1 for row in dialect_rows if row["status"] != "pass")
    if dialect_rows:
        print(f"LCW dialect: {len(dialect_rows) - dialect_gaps}/{len(dialect_rows)} pass, gaps={dialect_gaps}")
    if args.output:
        print(f"Report: {args.output}")
    if args.fail_on_dialect_gap and dialect_gaps:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
