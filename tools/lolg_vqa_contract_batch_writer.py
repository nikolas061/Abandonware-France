#!/usr/bin/env python3
"""Batch-write contract-preserving WVQA replacements into one MIX archive."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import struct
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lolg_vqa_contract_preserving_writer as contract_writer  # noqa: E402
import lolg_vqa_decode as vqa  # noqa: E402
import lolg_vqa_runtime_compat_audit as compat_audit  # noqa: E402


DEFAULT_OUTPUT = Path("output/vqa_contract_batch_writer")
SUMMARY_FIELDS = [
    "status",
    "source_mix",
    "output_mix",
    "entries_requested",
    "entries_replaced",
    "entries_failed",
    "native_exact_pass_entries",
    "width",
    "height",
    "profile_list",
    "issues",
]
ENTRY_FIELDS = [
    "status",
    "entry_index",
    "file_id",
    "native_exact_status",
    "source_dir",
    "output_payload",
    "width",
    "height",
    "source_width",
    "source_height",
    "frames",
    "validated_frames",
    "profile",
    "adaptive_cbpz",
    "payload_bytes",
    "codebook_vectors",
    "final_codebook_vectors",
    "cbpz_update_vectors",
    "exact_block_ratio",
    "changed_pixel_ratio",
    "max_cbfz_size",
    "max_vptz_size",
    "frame_shapes",
    "runtime_compat_status",
    "issues",
]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


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


def parse_profiles(raw: str) -> list[int]:
    profiles = [int(item.strip()) for item in raw.split(",") if item.strip()]
    if not profiles:
        raise ValueError("profile list is empty")
    return profiles


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
    cursor = 0
    body_parts: list[bytes] = []
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


def count_fullhd_frames(source_dir: Path) -> int:
    return len(list((source_dir / "frames_fullhd").glob("frame_*_fullhd.png")))


def source_dir_for(args: argparse.Namespace, entry_index: int, file_id: int) -> Path:
    return args.source_root / f"{args.source.stem}_{entry_index:04d}_{file_id:08x}_{args.width}x{args.height}"


def ensure_source_frames(
    payload: bytes,
    source_dir: Path,
    frame_count: int,
    target: tuple[int, int],
    rebuild: bool,
) -> None:
    if not rebuild and count_fullhd_frames(source_dir) == frame_count:
        return
    if source_dir.exists():
        shutil.rmtree(source_dir)
    vqa.decode_frames(
        payload,
        source_dir,
        max_frames=None,
        dump_payloads=False,
        render_frames=True,
        fullhd=True,
        target=target,
        fit="contain",
        resample=Image.Resampling.NEAREST,
        background=(0, 0, 0),
        experimental_window_lcw=True,
        transparent_index=None,
        png_optimize=False,
    )


def payload_has_cbpz(payload: bytes) -> bool:
    _header, chunks = vqa.parse_vqa(payload)
    for chunk in chunks:
        if chunk.chunk_id != "VQFR":
            continue
        if any(sub.chunk_id in {"CBPZ", "CBP0"} for sub in vqa.iter_chunks(chunk.payload, 0)):
            return True
    return False


def ratio(numerator: int, denominator: int) -> str:
    return "0.000000" if denominator <= 0 else f"{numerator / denominator:.6f}"


def summarize_trial(
    args: argparse.Namespace,
    source_payload: bytes,
    replacement_payload: bytes,
    totals: dict[str, int],
    frame_rows: list[dict[str, str]],
    validated: int,
    compat_summary: dict[str, str],
    profile: int,
    adaptive_cbpz: bool,
    source_dir: Path,
    output_payload: Path,
    source_header: vqa.VqaHeader,
    file_id: int,
    entry_index: int,
    native_exact_status: str,
    native_exact_issue: str,
) -> dict[str, str]:
    exact_blocks = int(totals.get("exact_blocks", 0))
    fallback_blocks = int(totals.get("fallback_blocks", 0))
    changed_pixels = int(totals.get("changed_pixels", 0))
    issues: list[str] = []
    if native_exact_status != "pass":
        issues.append(native_exact_issue)
    if validated != len(frame_rows):
        issues.append(f"validation_frames:{validated}/{len(frame_rows)}")
    if compat_summary.get("status") != "pass":
        issues.append("runtime_compat_gap")
    if int(totals.get("max_cbfz_size", 0)) > 0xFFFF:
        issues.append("max_cbfz_size_over_u16")
    if int(totals.get("max_vptz_size", 0)) > 0xFFFF:
        issues.append("max_vptz_size_over_u16")

    return {
        "status": "pass" if not issues else "gap",
        "entry_index": str(entry_index),
        "file_id": f"{file_id:08x}",
        "native_exact_status": native_exact_status,
        "source_dir": str(source_dir),
        "output_payload": str(output_payload),
        "width": str(args.width),
        "height": str(args.height),
        "source_width": str(source_header.width),
        "source_height": str(source_header.height),
        "frames": str(len(frame_rows)),
        "validated_frames": str(validated),
        "profile": str(profile),
        "adaptive_cbpz": "1" if adaptive_cbpz else "0",
        "payload_bytes": str(len(replacement_payload)),
        "codebook_vectors": str(totals.get("codebook_vectors", 0)),
        "final_codebook_vectors": str(totals.get("final_codebook_vectors", 0)),
        "cbpz_update_vectors": str(totals.get("cbpz_update_vectors", 0)),
        "exact_block_ratio": ratio(exact_blocks, exact_blocks + fallback_blocks),
        "changed_pixel_ratio": ratio(changed_pixels, args.width * args.height * len(frame_rows)),
        "max_cbfz_size": str(totals.get("max_cbfz_size", 0)),
        "max_vptz_size": str(totals.get("max_vptz_size", 0)),
        "frame_shapes": compat_summary.get("replacement_frame_shapes", ""),
        "runtime_compat_status": compat_summary.get("status", ""),
        "issues": ";".join(issues),
    }


def build_entry(
    args: argparse.Namespace,
    source_payload: bytes,
    entry_index: int,
    file_id: int,
    profiles: list[int],
) -> tuple[bytes | None, dict[str, str]]:
    source_header, source_chunks = vqa.parse_vqa(source_payload)
    source_vqfrs = [chunk for chunk in source_chunks if chunk.chunk_id == "VQFR"]
    native_exact_status, native_exact_issue = contract_writer.native_exact_preflight(source_payload)
    if native_exact_status != "pass":
        row = {field: "" for field in ENTRY_FIELDS}
        row.update(
            {
                "status": "gap",
                "entry_index": str(entry_index),
                "file_id": f"{file_id:08x}",
                "native_exact_status": native_exact_status,
                "issues": native_exact_issue,
            }
        )
        return None, row
    last_row: dict[str, str] | None = None
    for profile in profiles:
        trial_name = f"{entry_index:04d}_{file_id:08x}_cb{profile}"
        for reuse_root in args.reuse_roots:
            reuse_summary = reuse_root / "entries" / trial_name / "summary.csv"
            reuse_payload = reuse_root / "entries" / trial_name / "payload.vqa"
            if not reuse_summary.is_file() or not reuse_payload.is_file():
                continue
            reuse_rows = read_csv(reuse_summary)
            if not reuse_rows:
                continue
            reuse_row = dict(reuse_rows[0])
            if (
                reuse_row.get("status") == "pass"
                and reuse_row.get("file_id", "").lower() == f"{file_id:08x}"
                and reuse_row.get("width") == str(args.width)
                and reuse_row.get("height") == str(args.height)
                and reuse_row.get("profile") == str(profile)
            ):
                reuse_payload_bytes = reuse_payload.read_bytes()
                audit_args = argparse.Namespace(
                    original_label=f"{args.source}:{entry_index}",
                    replacement_label=str(reuse_payload),
                    allow_resolution_change=True,
                )
                compat_summary, _compat_frames = compat_audit.audit(source_payload, reuse_payload_bytes, audit_args)
                reuse_row["runtime_compat_status"] = compat_summary.get("status", "")
                if compat_summary.get("status") != "pass":
                    print(
                        f"Entry {entry_index:04d} {file_id:08x} profile {profile}: "
                        "reuse rejected by current runtime audit",
                        flush=True,
                    )
                    last_row = summarize_trial(
                        args,
                        source_payload,
                        reuse_payload_bytes,
                        {
                            "exact_blocks": 0,
                            "fallback_blocks": 0,
                            "changed_pixels": 0,
                            "max_cbfz_size": int(reuse_row.get("max_cbfz_size") or 0),
                            "max_vptz_size": int(reuse_row.get("max_vptz_size") or 0),
                            "codebook_vectors": int(reuse_row.get("codebook_vectors") or 0),
                            "final_codebook_vectors": int(reuse_row.get("final_codebook_vectors") or 0),
                            "cbpz_update_vectors": int(reuse_row.get("cbpz_update_vectors") or 0),
                        },
                        [],
                        0,
                        compat_summary,
                        profile,
                        adaptive_cbpz=False,
                        source_dir=Path(reuse_row.get("source_dir") or ""),
                        output_payload=reuse_payload,
                        source_header=source_header,
                        file_id=file_id,
                        entry_index=entry_index,
                        native_exact_status=native_exact_status,
                        native_exact_issue=native_exact_issue,
                    )
                    continue
                reuse_row["output_payload"] = str(reuse_payload)
                reuse_row["native_exact_status"] = native_exact_status
                print(
                    f"Entry {entry_index:04d} {file_id:08x} profile {profile}: "
                    f"reuse pass exact={reuse_row.get('exact_block_ratio', '')} "
                    f"max_vptz={reuse_row.get('max_vptz_size', '')}",
                    flush=True,
                )
                return reuse_payload_bytes, reuse_row

    source_dir = source_dir_for(args, entry_index, file_id)
    ensure_source_frames(source_payload, source_dir, len(source_vqfrs), (args.width, args.height), args.rebuild_sources)
    adaptive_cbpz = payload_has_cbpz(source_payload) if args.adaptive_cbpz == "auto" else args.adaptive_cbpz == "yes"

    for profile in profiles:
        trial_dir = args.output / "entries" / f"{entry_index:04d}_{file_id:08x}_cb{profile}"
        payload, totals, frame_rows = contract_writer.build_payload(
            source_payload,
            source_dir,
            (args.width, args.height),
            args.progress_every,
            False,
            args.extended_lcw,
            adaptive_cbpz,
            profile,
            args.max_codebook_entries,
            args.pad_initial_cbfz,
            args.pad_cbpz_to_source_budget,
            args.vqa_extended_lcw,
            args.windowed_pointer_lcw,
            False,
        )
        output_payload = trial_dir / "payload.vqa"
        output_payload.parent.mkdir(parents=True, exist_ok=True)
        output_payload.write_bytes(payload)

        max_cbfz = int(totals.get("max_cbfz_size", 0))
        max_vptz = int(totals.get("max_vptz_size", 0))
        should_validate = args.validate_all_profiles or (max_cbfz <= 0xFFFF and max_vptz <= 0xFFFF)
        validated = 0
        if should_validate:
            validated = contract_writer.validate_payload(
                payload,
                trial_dir / "decoded",
                frame_rows,
                args.extended_lcw,
                args.windowed_pointer_lcw,
            )

        audit_args = argparse.Namespace(
            original_label=f"{args.source}:{entry_index}",
            replacement_label=str(output_payload),
            allow_resolution_change=True,
        )
        compat_summary, compat_frames = compat_audit.audit(source_payload, payload, audit_args)
        compat_dir = trial_dir / "runtime_compat"
        write_csv(compat_dir / "summary.csv", compat_audit.SUMMARY_FIELDS, [compat_summary])
        write_csv(compat_dir / "frames.csv", compat_audit.FRAME_FIELDS, compat_frames)
        write_csv(trial_dir / "frames.csv", contract_writer.FRAME_FIELDS, frame_rows)

        row = summarize_trial(
            args,
            source_payload,
            payload,
            totals,
            frame_rows,
            validated,
            compat_summary,
            profile,
            adaptive_cbpz,
            source_dir,
            output_payload,
            source_header,
            file_id,
            entry_index,
            native_exact_status,
            native_exact_issue,
        )
        write_csv(trial_dir / "summary.csv", ENTRY_FIELDS, [row])
        last_row = row
        print(
            f"Entry {entry_index:04d} {file_id:08x} profile {profile}: "
            f"{row['status']} exact={row['exact_block_ratio']} max_vptz={row['max_vptz_size']} "
            f"issues={row['issues']}",
            flush=True,
        )
        if row["status"] == "pass":
            return payload, row

    assert last_row is not None
    return None, last_row


def build(args: argparse.Namespace) -> dict[str, str]:
    source_data, entries, table_end = read_mix(args.source)
    requested = parse_entries(args.entries)
    profiles = parse_profiles(args.profiles)
    replacements: dict[int, bytes] = {}
    entry_rows: list[dict[str, str]] = []

    for entry_index in requested:
        if entry_index < 0 or entry_index >= len(entries):
            raise ValueError(f"entry {entry_index} outside 0..{len(entries) - 1}")
        file_id, _offset, _size = entries[entry_index]
        source_payload = entry_payload(source_data, table_end, entries[entry_index])
        if not (source_payload.startswith(b"FORM") and source_payload[8:12] == b"WVQA"):
            row = {field: "" for field in ENTRY_FIELDS}
            row.update(
                {
                    "status": "skip",
                    "entry_index": str(entry_index),
                    "file_id": f"{file_id:08x}",
                    "native_exact_status": "skip",
                    "issues": "not_wvqa",
                }
            )
            entry_rows.append(row)
            continue
        replacement, row = build_entry(args, source_payload, entry_index, file_id, profiles)
        entry_rows.append(row)
        if replacement is not None:
            replacements[entry_index] = replacement

    output_mix = args.output / "mix" / args.source.name
    write_mix_with_replacements(args.source, output_mix, replacements)
    write_csv(args.output / "entries.csv", ENTRY_FIELDS, entry_rows)

    failed = [row for row in entry_rows if row["status"] not in {"pass", "skip"}]
    native_exact_pass = [row for row in entry_rows if row.get("native_exact_status") == "pass"]
    summary = {
        "status": "pass" if not failed and len(replacements) == len([row for row in entry_rows if row["status"] == "pass"]) else "gap",
        "source_mix": str(args.source),
        "output_mix": str(output_mix),
        "entries_requested": ",".join(str(item) for item in requested),
        "entries_replaced": str(len(replacements)),
        "entries_failed": str(len(failed)),
        "native_exact_pass_entries": str(len(native_exact_pass)),
        "width": str(args.width),
        "height": str(args.height),
        "profile_list": ",".join(str(item) for item in profiles),
        "issues": ";".join(f"{row['entry_index']}:{row['issues']}" for row in failed if row.get("issues")),
    }
    write_csv(args.output / "summary.csv", SUMMARY_FIELDS, [summary])
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("C/LOLG/MOVIES.MIX"))
    parser.add_argument("--entries", required=True, help="Comma/range list, e.g. 4,5,8-10")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--profiles", default="1024,768,640,512,480,448,416,384,256,128")
    parser.add_argument("--source-root", type=Path, default=Path("output/vqa_contract_batch_sources"))
    parser.add_argument(
        "--reuse-root",
        dest="reuse_roots",
        action="append",
        type=Path,
        default=[],
        help="Reuse passing entry payloads from a previous batch output directory.",
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--extended-lcw", action="store_true")
    parser.add_argument(
        "--vqa-extended-lcw",
        action="store_true",
        help="Use VQA common LCW extended command meanings for codebook chunks.",
    )
    parser.add_argument("--windowed-pointer-lcw", action="store_true")
    parser.add_argument("--adaptive-cbpz", choices=("auto", "yes", "no"), default="auto")
    parser.add_argument(
        "--pad-initial-cbfz",
        action="store_true",
        help="Pad each initial CBFZ with source codebook vectors while preserving the selected pointer profile.",
    )
    parser.add_argument(
        "--pad-cbpz-to-source-budget",
        action="store_true",
        help="Pad adaptive CBPZ updates with duplicate unused vectors up to the original CBPZ vector budget.",
    )
    parser.add_argument(
        "--max-codebook-entries",
        type=int,
        default=0,
        help="Maximum active codebook vectors after CBPZ updates; default follows the source VQA maximum.",
    )
    parser.add_argument("--rebuild-sources", action="store_true")
    parser.add_argument("--validate-all-profiles", action="store_true")
    parser.add_argument("--progress-every", type=int, default=25)
    args = parser.parse_args()
    args.reuse_roots = [args.output, *args.reuse_roots]

    summary = build(args)
    print(f"VQA contract batch writer: {summary['status']}")
    print(f"Entries replaced: {summary['entries_replaced']}")
    print(f"Summary: {args.output / 'summary.csv'}")
    if summary["issues"]:
        print(f"Issues: {summary['issues']}")


if __name__ == "__main__":
    main()
