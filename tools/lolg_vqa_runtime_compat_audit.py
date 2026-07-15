#!/usr/bin/env python3
"""Audit runtime-sensitive differences between original and rewritten WVQA files."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lolg_vqa_decode as vqa  # noqa: E402


DEFAULT_OUTPUT = Path("output/vqa_runtime_compat_audit")
FRAME_FIELDS = [
    "frame",
    "original_vqfr_size",
    "replacement_vqfr_size",
    "original_subchunks",
    "replacement_subchunks",
    "original_codebook_chunks",
    "replacement_codebook_chunks",
    "original_pointer_chunks",
    "replacement_pointer_chunks",
    "original_cbfz_decoded_bytes",
    "replacement_cbfz_decoded_bytes",
    "original_cbpz_chunks",
    "replacement_cbpz_chunks",
    "original_vptz_decoded_bytes",
    "replacement_vptz_decoded_bytes",
    "original_vptz_decode_status",
    "replacement_vptz_decode_status",
    "original_active_codebook_vectors",
    "replacement_active_codebook_vectors",
    "original_pointer_min_index",
    "replacement_pointer_min_index",
    "original_pointer_max_index",
    "replacement_pointer_max_index",
    "original_pointer_drawn_blocks",
    "replacement_pointer_drawn_blocks",
    "original_pointer_missing_blocks",
    "replacement_pointer_missing_blocks",
    "original_pointer_out_of_range_blocks",
    "replacement_pointer_out_of_range_blocks",
    "original_runtime_issues",
    "replacement_runtime_issues",
    "shape_status",
    "issues",
]
SUMMARY_FIELDS = [
    "status",
    "original",
    "replacement",
    "original_bytes",
    "replacement_bytes",
    "original_sha256",
    "replacement_sha256",
    "header_status",
    "allowed_header_changes",
    "top_chunk_status",
    "frame_count_status",
    "frame_shape_status",
    "critical_issues",
    "original_top_chunks",
    "replacement_top_chunks",
    "original_frame_shapes",
    "replacement_frame_shapes",
    "next_step",
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_payload(path: Path, entry: int | None) -> bytes:
    if entry is None:
        return path.read_bytes()
    return vqa.read_mix_entry(path, entry)


def chunk_names(chunks: list[vqa.Chunk]) -> list[str]:
    return [chunk.chunk_id for chunk in chunks]


def chunk_counter_text(names: list[str]) -> str:
    counts = Counter(names)
    return ",".join(f"{name}:{counts[name]}" for name in sorted(counts))


def shape_text(chunks: list[vqa.Chunk]) -> str:
    return "+".join(chunk.chunk_id for chunk in chunks)


def decode_lcw_status(chunk: vqa.Chunk, header: vqa.VqaHeader) -> tuple[str, int]:
    if not chunk.chunk_id.endswith("Z"):
        return "stored", len(chunk.payload)

    expected_size = None
    if chunk.chunk_id in {"VPTZ", "VPT0"}:
        expected_size = header.block_count * 2
    elif chunk.chunk_id in {"CBFZ", "CBF0"}:
        expected_size = header.max_codebook_entries * header.block_width * header.block_height

    if chunk.chunk_id in {"VPTZ", "VPT0"} and expected_size is not None:
        try:
            decoded, status = vqa.decode_lcw_windowed_pointer(chunk.payload, expected_size)
            return status, len(decoded)
        except Exception as exc:
            return f"error:{exc}", 0

    try:
        decoded = vqa.decode_lcw(
            chunk.payload,
            expected_size=expected_size,
            allow_signed_source=chunk.chunk_id in {"VPTZ", "VPT0"},
        )
        return "lcw", len(decoded)
    except Exception:
        return "error", 0


def first_decoded_size(chunks: list[vqa.Chunk], names: set[str], header: vqa.VqaHeader) -> tuple[str, str]:
    statuses: list[str] = []
    sizes: list[str] = []
    for chunk in chunks:
        if chunk.chunk_id not in names:
            continue
        status, size = decode_lcw_status(chunk, header)
        statuses.append(status)
        sizes.append(str(size))
    return "+".join(statuses), "+".join(sizes)


def decode_chunk_payload(chunk: vqa.Chunk, header: vqa.VqaHeader) -> tuple[str, bytes]:
    if not chunk.chunk_id.endswith("Z"):
        return "stored", chunk.payload

    expected_size = None
    if chunk.chunk_id in {"VPTZ", "VPT0"}:
        expected_size = header.block_count * 2
    elif chunk.chunk_id in {"CBFZ", "CBF0"}:
        expected_size = header.max_codebook_entries * header.block_width * header.block_height

    if chunk.chunk_id in {"VPTZ", "VPT0"} and expected_size is not None:
        decoded, status = vqa.decode_lcw_windowed_pointer(chunk.payload, expected_size)
        return status, decoded

    try:
        decoded = vqa.decode_lcw(
            chunk.payload,
            expected_size=expected_size,
            allow_signed_source=chunk.chunk_id in {"VPTZ", "VPT0"},
        )
        return "lcw", decoded
    except Exception:
        raise


def pointer_stats(
    chunk_id: str,
    payload: bytes,
    active_codebook: bytes | None,
    header: vqa.VqaHeader,
) -> vqa.PointerRenderStats:
    vector_size = header.block_width * header.block_height
    if vector_size <= 0 or active_codebook is None:
        return vqa.PointerRenderStats(missing_blocks=header.block_count)
    vector_count = len(active_codebook) // vector_size

    if chunk_id in {"VPTZ", "VPT0"}:
        raw_pointers = [
            payload[offset] | (payload[offset + 1] << 8)
            for offset in range(0, len(payload) - 1, 2)
        ][: header.block_count]
        pointers: list[int | None] = raw_pointers
    elif chunk_id in {"VPRZ", "VPTR"}:
        pointers = vqa.expand_vpr_pointers(payload, header)
    else:
        return vqa.PointerRenderStats(missing_blocks=header.block_count)

    drawn = 0
    skipped = 0
    explicit_skip = 0
    out_of_range = 0
    indices: set[int] = set()
    min_index: int | None = None
    max_index: int | None = None

    for value in pointers:
        if value is None:
            skipped += 1
            explicit_skip += 1
            continue
        if value >= vector_count:
            skipped += 1
            out_of_range += 1
            continue
        drawn += 1
        indices.add(value)
        min_index = value if min_index is None else min(min_index, value)
        max_index = value if max_index is None else max(max_index, value)

    return vqa.PointerRenderStats(
        drawn_blocks=drawn,
        skipped_blocks=skipped,
        missing_blocks=header.block_count - len(pointers),
        explicit_skip_blocks=explicit_skip,
        out_of_range_blocks=out_of_range,
        unique_indices=len(indices),
        min_index=min_index,
        max_index=max_index,
    )


def frame_runtime_stats(
    chunks: list[vqa.Chunk],
    header: vqa.VqaHeader,
    active_codebook: bytes | None,
) -> tuple[dict[str, str], bytes | None]:
    vector_size = header.block_width * header.block_height
    pointer_seen = False
    pointer_decode_statuses: list[str] = []
    pointer_decoded_sizes: list[str] = []
    pointer_min: list[str] = []
    pointer_max: list[str] = []
    pointer_drawn = 0
    pointer_missing = 0
    pointer_out_of_range = 0
    issues: list[str] = []

    for chunk in chunks:
        try:
            status, decoded = decode_chunk_payload(chunk, header)
        except Exception as exc:  # noqa: BLE001 - surfaced as CSV context.
            issues.append(f"{chunk.chunk_id.lower()}_decode_error:{type(exc).__name__}")
            continue

        if chunk.chunk_id in {"CBFZ", "CBF0"}:
            active_codebook = decoded
            if vector_size <= 0 or len(decoded) % vector_size:
                issues.append("cbfz_unaligned")
        elif chunk.chunk_id in {"CBPZ", "CBP0"}:
            if vector_size <= 0 or len(decoded) % vector_size:
                issues.append("cbpz_unaligned")
            result = vqa.apply_cbp_update(active_codebook, decoded, header)
            if result.codebook is not None:
                active_codebook = result.codebook
            if result.status in {"no_base", "invalid_vector_size"}:
                issues.append(f"cbpz_update_{result.status}")
        elif chunk.chunk_id in {"VPTZ", "VPT0", "VPRZ", "VPTR"}:
            pointer_seen = True
            pointer_decode_statuses.append(status)
            pointer_decoded_sizes.append(str(len(decoded)))
            if chunk.chunk_id in {"VPTZ", "VPT0"} and len(decoded) != header.block_count * 2:
                issues.append(f"vptz_decoded_size:{len(decoded)}!={header.block_count * 2}")
            if active_codebook is None:
                issues.append("pointer_without_codebook")
            stats = pointer_stats(chunk.chunk_id, decoded, active_codebook, header)
            pointer_drawn += stats.drawn_blocks
            pointer_missing += stats.missing_blocks
            pointer_out_of_range += stats.out_of_range_blocks
            if stats.min_index is not None:
                pointer_min.append(str(stats.min_index))
            if stats.max_index is not None:
                pointer_max.append(str(stats.max_index))
            if stats.missing_blocks:
                issues.append(f"pointer_missing_blocks:{stats.missing_blocks}")
            if stats.out_of_range_blocks:
                issues.append(f"pointer_out_of_range:{stats.out_of_range_blocks}")

    active_vectors = ""
    if active_codebook is not None and vector_size > 0:
        active_vectors = str(len(active_codebook) // vector_size)
    if not pointer_seen:
        pointer_decoded_sizes.append("")
        pointer_decode_statuses.append("")

    return (
        {
            "active_codebook_vectors": active_vectors,
            "pointer_decode_status": "+".join(pointer_decode_statuses),
            "pointer_decoded_bytes": "+".join(pointer_decoded_sizes),
            "pointer_min_index": "+".join(pointer_min),
            "pointer_max_index": "+".join(pointer_max),
            "pointer_drawn_blocks": str(pointer_drawn),
            "pointer_missing_blocks": str(pointer_missing),
            "pointer_out_of_range_blocks": str(pointer_out_of_range),
            "issues": ";".join(issues),
        },
        active_codebook,
    )


def runtime_issue_delta(original_issues: str, replacement_issues: str) -> list[str]:
    original_counts = Counter(issue for issue in original_issues.split(";") if issue)
    replacement_counts = Counter(issue for issue in replacement_issues.split(";") if issue)
    delta = replacement_counts - original_counts
    expanded: list[str] = []
    for issue, count in sorted(delta.items()):
        expanded.extend([issue] * count)
    return expanded


def header_compare(
    original: vqa.VqaHeader,
    replacement: vqa.VqaHeader,
    allow_resolution_change: bool,
) -> tuple[str, list[str], list[str]]:
    issues: list[str] = []
    allowed: list[str] = []
    original_dict = asdict(original)
    replacement_dict = asdict(replacement)
    stable_fields = [
        "version",
        "flags",
        "frame_count",
        "width",
        "height",
        "block_width",
        "block_height",
        "frame_rate",
        "colors",
        "max_codebook_entries",
        "sample_rate",
        "audio_flags",
        "unknown_26",
    ]
    for field in stable_fields:
        if original_dict[field] != replacement_dict[field]:
            if allow_resolution_change and field in {"width", "height"}:
                allowed.append(f"{field}:{original_dict[field]}->{replacement_dict[field]}")
                continue
            issues.append(f"{field}:{original_dict[field]}->{replacement_dict[field]}")
    return ("pass" if not issues else "gap"), issues, allowed


def audit(original_payload: bytes, replacement_payload: bytes, args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]]]:
    original_header, original_chunks = vqa.parse_vqa(original_payload)
    replacement_header, replacement_chunks = vqa.parse_vqa(replacement_payload)

    original_top = chunk_names(original_chunks)
    replacement_top = chunk_names(replacement_chunks)
    original_vqfrs = [chunk for chunk in original_chunks if chunk.chunk_id == "VQFR"]
    replacement_vqfrs = [chunk for chunk in replacement_chunks if chunk.chunk_id == "VQFR"]

    allow_resolution_change = bool(getattr(args, "allow_resolution_change", False))
    header_status, header_issues, allowed_header_changes = header_compare(
        original_header,
        replacement_header,
        allow_resolution_change,
    )
    top_non_video_original = [name for name in original_top if name != "VQFR"]
    top_non_video_replacement = [name for name in replacement_top if name != "VQFR"]
    top_chunk_status = "pass" if top_non_video_original == top_non_video_replacement else "gap"
    frame_count_status = "pass" if len(original_vqfrs) == len(replacement_vqfrs) == original_header.frame_count else "gap"

    frame_rows: list[dict[str, str]] = []
    frame_issues: list[str] = []
    original_shapes: Counter[str] = Counter()
    replacement_shapes: Counter[str] = Counter()
    original_active_codebook: bytes | None = None
    replacement_active_codebook: bytes | None = None

    for index in range(max(len(original_vqfrs), len(replacement_vqfrs))):
        original_frame = original_vqfrs[index] if index < len(original_vqfrs) else None
        replacement_frame = replacement_vqfrs[index] if index < len(replacement_vqfrs) else None
        original_subchunks = vqa.iter_chunks(original_frame.payload, 0) if original_frame else []
        replacement_subchunks = vqa.iter_chunks(replacement_frame.payload, 0) if replacement_frame else []
        original_shape = shape_text(original_subchunks)
        replacement_shape = shape_text(replacement_subchunks)
        if original_shape:
            original_shapes[original_shape] += 1
        if replacement_shape:
            replacement_shapes[replacement_shape] += 1

        original_codebook = [chunk.chunk_id for chunk in original_subchunks if chunk.chunk_id in {"CBFZ", "CBF0", "CBPZ", "CBP0"}]
        replacement_codebook = [chunk.chunk_id for chunk in replacement_subchunks if chunk.chunk_id in {"CBFZ", "CBF0", "CBPZ", "CBP0"}]
        original_pointer = [chunk.chunk_id for chunk in original_subchunks if chunk.chunk_id in {"VPTZ", "VPT0", "VPRZ", "VPTR"}]
        replacement_pointer = [chunk.chunk_id for chunk in replacement_subchunks if chunk.chunk_id in {"VPTZ", "VPT0", "VPRZ", "VPTR"}]
        original_vpt_status, original_vpt_size = first_decoded_size(original_subchunks, {"VPTZ", "VPT0"}, original_header)
        replacement_vpt_status, replacement_vpt_size = first_decoded_size(replacement_subchunks, {"VPTZ", "VPT0"}, replacement_header)
        _original_cbf_status, original_cbf_size = first_decoded_size(original_subchunks, {"CBFZ", "CBF0"}, original_header)
        _replacement_cbf_status, replacement_cbf_size = first_decoded_size(replacement_subchunks, {"CBFZ", "CBF0"}, replacement_header)
        original_runtime, original_active_codebook = frame_runtime_stats(
            original_subchunks,
            original_header,
            original_active_codebook,
        )
        replacement_runtime, replacement_active_codebook = frame_runtime_stats(
            replacement_subchunks,
            replacement_header,
            replacement_active_codebook,
        )

        issues: list[str] = []
        if original_shape != replacement_shape:
            issues.append("subchunk_shape_changed")
        if "CBPZ" in original_codebook and "CBPZ" not in replacement_codebook:
            issues.append("cbpz_removed")
        if original_pointer != replacement_pointer and original_pointer:
            issues.append("pointer_chunk_type_changed")
        pointer_decode_failed = replacement_vpt_status.startswith("error") or replacement_vpt_size in {"", "0"}
        replacement_runtime_deltas = [
            f"replacement_{runtime_issue}"
            for runtime_issue in runtime_issue_delta(original_runtime["issues"], replacement_runtime["issues"])
        ]
        issues.extend(replacement_runtime_deltas)
        if (
            original_frame
            and replacement_frame
            and replacement_frame.size < original_frame.size
            and replacement_frame.size < max(64, original_frame.size // 4)
            and (pointer_decode_failed or replacement_runtime_deltas)
        ):
            issues.append("vqfr_size_shrunk_over_75pct")
        if issues:
            frame_issues.extend(f"frame_{index}:{issue}" for issue in issues)

        frame_rows.append(
            {
                "frame": str(index),
                "original_vqfr_size": "" if original_frame is None else str(original_frame.size),
                "replacement_vqfr_size": "" if replacement_frame is None else str(replacement_frame.size),
                "original_subchunks": original_shape,
                "replacement_subchunks": replacement_shape,
                "original_codebook_chunks": "+".join(original_codebook),
                "replacement_codebook_chunks": "+".join(replacement_codebook),
                "original_pointer_chunks": "+".join(original_pointer),
                "replacement_pointer_chunks": "+".join(replacement_pointer),
                "original_cbfz_decoded_bytes": original_cbf_size,
                "replacement_cbfz_decoded_bytes": replacement_cbf_size,
                "original_cbpz_chunks": str(sum(1 for chunk in original_subchunks if chunk.chunk_id in {"CBPZ", "CBP0"})),
                "replacement_cbpz_chunks": str(sum(1 for chunk in replacement_subchunks if chunk.chunk_id in {"CBPZ", "CBP0"})),
                "original_vptz_decoded_bytes": original_vpt_size,
                "replacement_vptz_decoded_bytes": replacement_vpt_size,
                "original_vptz_decode_status": original_vpt_status,
                "replacement_vptz_decode_status": replacement_vpt_status,
                "original_active_codebook_vectors": original_runtime["active_codebook_vectors"],
                "replacement_active_codebook_vectors": replacement_runtime["active_codebook_vectors"],
                "original_pointer_min_index": original_runtime["pointer_min_index"],
                "replacement_pointer_min_index": replacement_runtime["pointer_min_index"],
                "original_pointer_max_index": original_runtime["pointer_max_index"],
                "replacement_pointer_max_index": replacement_runtime["pointer_max_index"],
                "original_pointer_drawn_blocks": original_runtime["pointer_drawn_blocks"],
                "replacement_pointer_drawn_blocks": replacement_runtime["pointer_drawn_blocks"],
                "original_pointer_missing_blocks": original_runtime["pointer_missing_blocks"],
                "replacement_pointer_missing_blocks": replacement_runtime["pointer_missing_blocks"],
                "original_pointer_out_of_range_blocks": original_runtime["pointer_out_of_range_blocks"],
                "replacement_pointer_out_of_range_blocks": replacement_runtime["pointer_out_of_range_blocks"],
                "original_runtime_issues": original_runtime["issues"],
                "replacement_runtime_issues": replacement_runtime["issues"],
                "shape_status": "pass" if not issues else "gap",
                "issues": ";".join(issues),
            }
        )

    frame_shape_status = "pass" if not frame_issues else "gap"
    critical_issues = list(header_issues)
    if top_chunk_status != "pass":
        critical_issues.append("top_non_video_chunk_sequence_changed")
    if frame_count_status != "pass":
        critical_issues.append("frame_count_mismatch")
    critical_issues.extend(frame_issues[:40])

    status = "pass" if not critical_issues else "gap"
    summary = {
        "status": status,
        "original": args.original_label,
        "replacement": args.replacement_label,
        "original_bytes": str(len(original_payload)),
        "replacement_bytes": str(len(replacement_payload)),
        "original_sha256": sha256(original_payload),
        "replacement_sha256": sha256(replacement_payload),
        "header_status": header_status,
        "allowed_header_changes": ";".join(allowed_header_changes),
        "top_chunk_status": top_chunk_status,
        "frame_count_status": frame_count_status,
        "frame_shape_status": frame_shape_status,
        "critical_issues": ";".join(critical_issues),
        "original_top_chunks": chunk_counter_text(original_top),
        "replacement_top_chunks": chunk_counter_text(replacement_top),
        "original_frame_shapes": ";".join(f"{shape}:{count}" for shape, count in sorted(original_shapes.items())),
        "replacement_frame_shapes": ";".join(f"{shape}:{count}" for shape, count in sorted(replacement_shapes.items())),
        "next_step": "make the native writer preserve frame subchunk contract before HD scaling",
    }
    return summary, frame_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--original-entry", type=int)
    parser.add_argument("--replacement", type=Path, required=True)
    parser.add_argument("--replacement-entry", type=int)
    parser.add_argument(
        "--allow-resolution-change",
        action="store_true",
        help="Treat width/height changes as expected HD scaling, while auditing the rest of the WVQA contract.",
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    args.original_label = f"{args.original}:{args.original_entry}" if args.original_entry is not None else str(args.original)
    args.replacement_label = (
        f"{args.replacement}:{args.replacement_entry}" if args.replacement_entry is not None else str(args.replacement)
    )

    original_payload = load_payload(args.original, args.original_entry)
    replacement_payload = load_payload(args.replacement, args.replacement_entry)
    summary, frame_rows = audit(original_payload, replacement_payload, args)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDS, [summary])
    write_csv(args.output / "frames.csv", FRAME_FIELDS, frame_rows)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(f"VQA runtime compat audit: {summary['status']}")
    print(f"Summary: {args.output / 'summary.csv'}")
    if summary["critical_issues"]:
        print(f"Issues: {summary['critical_issues'][:500]}")


if __name__ == "__main__":
    main()
