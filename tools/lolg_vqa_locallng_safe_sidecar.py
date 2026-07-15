#!/usr/bin/env python3
"""Build a safer Wine LOCALLNG_HD.MIX sidecar.

The current 1920x1080 LOCALLNG VQA payload trips the LOLG95 bootstrap reader.
This probe keeps the original LOCALLNG.MIX archive layout and all non-video VQA
chunks, but replaces the video frames with a smaller compact LCW encode.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import struct
from collections import Counter
from pathlib import Path

from PIL import Image

import lolg_vqa_decode as vqa
import lolg_vqa_fullhd_replacement_writer as writer
import lolg_vqa_runtime_compat_audit as compat_audit
from lolg_rebuild_locallng_dos_compat import MixEntry, entry_payload, read_mix
from westwood_codecs import lcw_compress


TARGET_FILE_ID = 0xFCA4E133
DEFAULT_ORIGINAL = Path("C/LOLG/LOCALLNG.MIX")
DEFAULT_OUTPUT = Path("output/lolg95_locallng_safe_sidecar_960x540")

SUMMARY_FIELDS = [
    "status",
    "original_mix",
    "output_mix",
    "payload_path",
    "decoded_source_dir",
    "decoded_validation_dir",
    "width",
    "height",
    "frames",
    "payload_bytes",
    "mix_bytes",
    "max_cbfz_size",
    "max_vptz_size",
    "max_vqfr_size",
    "lcw_mode",
    "frame_palette_mode",
    "preserved_chunks",
    "runtime_compat_status",
    "runtime_compat_issues",
    "runtime_compat_report",
    "payload_sha256",
    "issues",
    "next_step",
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        csv_writer = csv.DictWriter(handle, fieldnames=fieldnames)
        csv_writer.writeheader()
        csv_writer.writerows(rows)


def find_entry(entries: list[MixEntry], file_id: int) -> MixEntry:
    matches = [entry for entry in entries if entry.file_id == file_id]
    if len(matches) != 1:
        raise ValueError(f"expected one entry {file_id:08x}, got {len(matches)}")
    return matches[0]


def decoded_frame_count(source_dir: Path) -> int:
    return len(list((source_dir / "frames_fullhd").glob("frame_*_fullhd.png")))


def decode_source_frames(
    source_payload: bytes,
    source_dir: Path,
    target: tuple[int, int],
    fit: str,
    filter_name: str,
    transparent_index: int | None,
) -> None:
    filters = {
        "nearest": Image.Resampling.NEAREST,
        "bilinear": Image.Resampling.BILINEAR,
        "bicubic": Image.Resampling.BICUBIC,
        "lanczos": Image.Resampling.LANCZOS,
    }
    if source_dir.exists():
        shutil.rmtree(source_dir)
    vqa.decode_frames(
        source_payload,
        source_dir,
        max_frames=None,
        dump_payloads=False,
        render_frames=True,
        fullhd=True,
        target=target,
        fit=fit,
        resample=filters[filter_name],
        background=(0, 0, 0),
        experimental_window_lcw=True,
        transparent_index=transparent_index,
        png_optimize=False,
    )


def selected_frames(source_dir: Path, expected_count: int) -> list[Path]:
    frames = sorted((source_dir / "frames_fullhd").glob("frame_*_fullhd.png"))
    if len(frames) != expected_count:
        raise ValueError(f"decoded frame count {len(frames)} != expected {expected_count}")
    return frames


def build_compact_video_payload(
    source_payload: bytes,
    source_dir: Path,
    frames: list[Path],
    target: tuple[int, int],
    progress_every: int,
    search_depth: int,
    lcw_mode: str,
) -> tuple[bytes, dict[str, int], list[dict[str, str]]]:
    writer.TARGET_SIZE = target

    if lcw_mode == "compact":
        def compact_lcw(data: bytes) -> bytes:
            return lcw_compress(data, search_depth=search_depth)

        writer.lcw_compress_literal = compact_lcw
    frame_rows: list[dict[str, str]] = []
    payload, totals = writer.build_payload(
        source_payload,
        source_dir,
        frames,
        frame_rows,
        progress_every=progress_every,
    )
    return payload, totals, frame_rows


def transform_generated_vqfr(payload: bytes, frame_index: int, frame_palette_mode: str) -> bytes:
    subchunks = vqa.iter_chunks(payload, 0)
    by_id = {subchunk.chunk_id: subchunk.payload for subchunk in subchunks}
    required = [name for name in ("CBFZ", "VPTZ") if name not in by_id]
    if required:
        raise ValueError(f"generated frame {frame_index} is missing {','.join(required)}")

    if frame_palette_mode == "each":
        return payload

    parts = [writer.chunk("CBFZ", by_id["CBFZ"])]
    if frame_palette_mode == "first" and frame_index == 0 and "CPL0" in by_id:
        parts.append(writer.chunk("CPL0", by_id["CPL0"]))
    parts.append(writer.chunk("VPTZ", by_id["VPTZ"]))
    return b"".join(parts)


def rebuild_vqa_preserving_non_video(
    original_payload: bytes,
    generated_payload: bytes,
    frame_palette_mode: str,
) -> tuple[bytes, Counter[str], int]:
    original_header, original_chunks = vqa.parse_vqa(original_payload)
    _generated_header, generated_chunks = vqa.parse_vqa(generated_payload)
    generated_vqhd = next(chunk for chunk in generated_chunks if chunk.chunk_id == "VQHD")
    generated_vqfrs = [chunk for chunk in generated_chunks if chunk.chunk_id == "VQFR"]
    if len(generated_vqfrs) != original_header.frame_count:
        raise ValueError(
            f"generated VQFR count {len(generated_vqfrs)} != original frame count {original_header.frame_count}"
        )

    preserved = Counter()
    output_chunks: list[bytes] = []
    frame_index = 0
    max_vqfr_size = 0
    for original_chunk in original_chunks:
        if original_chunk.chunk_id == "VQHD":
            output_chunks.append(writer.chunk("VQHD", generated_vqhd.payload))
            continue
        if original_chunk.chunk_id == "VQFR":
            replacement = generated_vqfrs[frame_index]
            replacement_payload = transform_generated_vqfr(
                replacement.payload,
                frame_index,
                frame_palette_mode,
            )
            output_chunks.append(writer.chunk("VQFR", replacement_payload))
            max_vqfr_size = max(max_vqfr_size, len(replacement_payload))
            frame_index += 1
            continue
        output_chunks.append(writer.chunk(original_chunk.chunk_id, original_chunk.payload))
        preserved[original_chunk.chunk_id] += 1

    if frame_index != len(generated_vqfrs):
        raise ValueError(f"used {frame_index} generated frames, expected {len(generated_vqfrs)}")

    body = b"WVQA" + b"".join(output_chunks)
    return b"FORM" + writer.be32(len(body)) + body, preserved, max_vqfr_size


def write_mix_with_payload(
    original_mix: Path,
    replacement_payload: bytes,
    output_mix: Path,
    report_path: Path,
) -> None:
    original_data, entries, table_end = read_mix(original_mix)
    target_entry = find_entry(entries, TARGET_FILE_ID)
    payload_by_id: dict[int, bytes] = {}
    source_by_id: dict[int, str] = {}

    for entry in entries:
        if entry.file_id == TARGET_FILE_ID:
            payload_by_id[entry.file_id] = replacement_payload
            source_by_id[entry.file_id] = "safe_video"
        else:
            payload_by_id[entry.file_id] = entry_payload(original_data, table_end, entry)
            source_by_id[entry.file_id] = "original"

    physical_order = sorted(entries, key=lambda entry: entry.offset)
    new_offset_by_id: dict[int, int] = {}
    body_parts: list[bytes] = []
    cursor = 0
    for entry in physical_order:
        payload = payload_by_id[entry.file_id]
        new_offset_by_id[entry.file_id] = cursor
        body_parts.append(payload)
        cursor += len(payload)

    table = bytearray(struct.pack("<HI", len(entries), cursor))
    for entry in entries:
        payload = payload_by_id[entry.file_id]
        table.extend(struct.pack("<III", entry.file_id, new_offset_by_id[entry.file_id], len(payload)))

    output_mix.parent.mkdir(parents=True, exist_ok=True)
    output_mix.write_bytes(bytes(table) + b"".join(body_parts))

    lines = ["index\tfile_id\tsource\toriginal_size\toutput_size\toriginal_offset\toutput_offset"]
    for index, entry in enumerate(entries):
        lines.append(
            "\t".join(
                [
                    f"{index:04d}",
                    f"{entry.file_id:08x}",
                    source_by_id[entry.file_id],
                    str(entry.size),
                    str(len(payload_by_id[entry.file_id])),
                    str(entry.offset),
                    str(new_offset_by_id[entry.file_id]),
                ]
            )
        )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        f"Replaced {TARGET_FILE_ID:08x}: {target_entry.size} -> "
        f"{len(replacement_payload)} bytes in {output_mix}"
    )


def validate_payload(payload: bytes, output_dir: Path) -> int:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    vqa.decode_frames(
        payload,
        output_dir,
        max_frames=None,
        dump_payloads=False,
        render_frames=True,
        fullhd=False,
        target=(1, 1),
        fit="stretch",
        resample=Image.Resampling.NEAREST,
        background=(0, 0, 0),
        experimental_window_lcw=True,
        transparent_index=None,
        png_optimize=False,
    )
    return len(list((output_dir / "frames_native").glob("frame_*.png")))


def write_runtime_compat_report(
    original_payload: bytes,
    replacement_payload: bytes,
    output_dir: Path,
) -> dict[str, str]:
    audit_args = argparse.Namespace(
        original_label="LOCALLNG.MIX:fca4e133",
        replacement_label=str(output_dir.parent / "payloads" / "fca4e133_safe.vqa"),
    )
    summary, frame_rows = compat_audit.audit(original_payload, replacement_payload, audit_args)
    write_csv(output_dir / "summary.csv", compat_audit.SUMMARY_FIELDS, [summary])
    write_csv(output_dir / "frames.csv", compat_audit.FRAME_FIELDS, frame_rows)
    return summary


def build(args: argparse.Namespace) -> dict[str, str]:
    target = (args.width, args.height)
    output = args.output
    payload_path = output / "payloads" / "fca4e133_safe.vqa"
    sidecar_mix = output / "sidecar" / "LOCALLNG_HD.MIX"
    source_dir = output / "decoded_source"
    validation_dir = output / "decoded_validation"
    report_path = output / "LOCALLNG_HD.tsv"
    issues: list[str] = []

    original_data, entries, table_end = read_mix(args.original)
    source_entry = find_entry(entries, TARGET_FILE_ID)
    source_payload = entry_payload(original_data, table_end, source_entry)
    source_header, _source_chunks = vqa.parse_vqa(source_payload)

    if decoded_frame_count(source_dir) != source_header.frame_count:
        print(f"Decoding source frames to {source_dir}")
        decode_source_frames(source_payload, source_dir, target, args.fit, args.filter, args.transparent_index)

    frames = selected_frames(source_dir, source_header.frame_count)
    generated_payload, totals, frame_rows = build_compact_video_payload(
        source_payload,
        source_dir,
        frames,
        target,
        args.progress_every,
        args.search_depth,
        args.lcw_mode,
    )
    safe_payload, preserved_chunks, max_vqfr_size = rebuild_vqa_preserving_non_video(
        source_payload,
        generated_payload,
        args.frame_palette_mode,
    )

    max_cbfz = int(totals.get("max_cbfz_size", 0))
    max_vptz = int(totals.get("max_vptz_size", 0))
    if max_cbfz > 0xFFFF:
        issues.append(f"max_cbfz_over_16bit:{max_cbfz}")
    if max_vptz > 0xFFFF:
        issues.append(f"max_vptz_over_16bit:{max_vptz}")

    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload_path.write_bytes(safe_payload)
    writer.write_csv(output / "frames.csv", writer.FRAME_FIELDS, frame_rows)
    write_mix_with_payload(args.original, safe_payload, sidecar_mix, report_path)
    validated_frames = validate_payload(safe_payload, validation_dir)
    if validated_frames != source_header.frame_count:
        issues.append(f"validation_frames:{validated_frames}/{source_header.frame_count}")
    compat_summary = write_runtime_compat_report(source_payload, safe_payload, output / "runtime_compat")
    if compat_summary.get("status") != "pass":
        issues.append("runtime_compat_gap")

    status = "pass" if not issues else "gap"
    summary = {
        "status": status,
        "original_mix": str(args.original),
        "output_mix": str(sidecar_mix),
        "payload_path": str(payload_path),
        "decoded_source_dir": str(source_dir),
        "decoded_validation_dir": str(validation_dir),
        "width": str(args.width),
        "height": str(args.height),
        "frames": str(source_header.frame_count),
        "payload_bytes": str(len(safe_payload)),
        "mix_bytes": str(sidecar_mix.stat().st_size if sidecar_mix.exists() else 0),
        "max_cbfz_size": str(max_cbfz),
        "max_vptz_size": str(max_vptz),
        "max_vqfr_size": str(max_vqfr_size),
        "lcw_mode": args.lcw_mode,
        "frame_palette_mode": args.frame_palette_mode,
        "preserved_chunks": ",".join(f"{key}:{value}" for key, value in sorted(preserved_chunks.items())),
        "runtime_compat_status": compat_summary.get("status", ""),
        "runtime_compat_issues": compat_summary.get("critical_issues", ""),
        "runtime_compat_report": str(output / "runtime_compat" / "summary.csv"),
        "payload_sha256": sha256_bytes(safe_payload),
        "issues": ";".join(issues),
        "next_step": (
            "fix WVQA frame contract before runtime launch"
            if compat_summary.get("status") != "pass"
            else "launch the Wine LOCALLNG sidecar patch with this sidecar directory"
        ),
    }
    write_csv(output / "summary.csv", SUMMARY_FIELDS, [summary])
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a safer LOCALLNG_HD.MIX sidecar for Wine.")
    parser.add_argument("--original", type=Path, default=DEFAULT_ORIGINAL)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    parser.add_argument("--fit", choices=("stretch", "contain", "cover"), default="stretch")
    parser.add_argument("--filter", choices=("nearest", "bilinear", "bicubic", "lanczos"), default="lanczos")
    parser.add_argument("--transparent-index", type=int, default=0)
    parser.add_argument("--progress-every", type=int, default=25)
    parser.add_argument("--search-depth", type=int, default=64)
    parser.add_argument("--lcw-mode", choices=("literal", "compact"), default="compact")
    parser.add_argument("--frame-palette-mode", choices=("each", "first", "none"), default="each")
    args = parser.parse_args()

    summary = build(args)
    print(f"LOCALLNG safe sidecar: {summary['status']}")
    print(f"Sidecar MIX: {summary['output_mix']}")
    print(
        "Frames={frames} size={width}x{height} max_cbfz={max_cbfz_size} "
        "max_vptz={max_vptz_size} max_vqfr={max_vqfr_size}".format(**summary)
    )
    if summary["issues"]:
        print(f"Issues: {summary['issues']}")


if __name__ == "__main__":
    main()
