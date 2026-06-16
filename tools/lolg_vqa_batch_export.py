#!/usr/bin/env python3
"""Batch export Lands of Lore II VQA frames to native and Full HD PNGs."""

from __future__ import annotations

import argparse
import contextlib
import csv
import io
import struct
from pathlib import Path

from PIL import Image

import lolg_vqa_decode as vqa


def read_mix_entries(path: Path) -> tuple[int, list[tuple[int, int, int]]]:
    data = path.read_bytes()
    if len(data) < 6:
        raise ValueError(f"{path}: too small to be a MIX archive")

    count, body_size = struct.unpack_from("<HI", data, 0)
    table_end = 6 + count * 12
    if table_end > len(data):
        raise ValueError(f"{path}: invalid MIX table")

    entries: list[tuple[int, int, int]] = []
    max_end = 0
    for index in range(count):
        file_id, offset, size = struct.unpack_from("<III", data, 6 + index * 12)
        entries.append((file_id, offset, size))
        max_end = max(max_end, offset + size)

    if max_end > body_size:
        raise ValueError(f"{path}: entry table exceeds declared body size")

    return table_end, entries


def is_vqa(payload: bytes) -> bool:
    return len(payload) >= 12 and payload[:4] == b"FORM" and payload[8:12] == b"WVQA"


def safe_stem(path: Path) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in path.stem)


def count_pngs(path: Path) -> int:
    return sum(1 for _ in path.glob("*.png")) if path.exists() else 0


def resolve_frame_output(output_dir: Path, raw: str) -> Path | None:
    if not raw:
        return None
    path = Path(raw)
    if path.is_absolute() or path.exists():
        return path
    if "frames_native" in path.parts:
        return output_dir / "frames_native" / path.name
    if "frames_fullhd" in path.parts:
        return output_dir / "frames_fullhd" / path.name
    return output_dir / path


def complete_png_set(output_dir: Path, expected_frames: int, require_fullhd: bool) -> bool:
    render_manifest = output_dir / "rendered_frames.csv"
    if not render_manifest.exists():
        return False

    native_count = count_pngs(output_dir / "frames_native")
    fullhd_count = count_pngs(output_dir / "frames_fullhd")
    if native_count != expected_frames:
        return False
    if require_fullhd and fullhd_count != expected_frames:
        return False

    with render_manifest.open(newline="") as handle:
        render_rows = list(csv.DictReader(handle))

    if len(render_rows) != expected_frames:
        return False

    frame_numbers: set[int] = set()
    for row in render_rows:
        try:
            frame_numbers.add(int(row.get("frame", "")))
        except ValueError:
            return False

        if row.get("status") not in {"rendered", "held_frame"}:
            return False

        native_output = resolve_frame_output(output_dir, row.get("native_output", ""))
        if native_output is None or not native_output.exists():
            return False

        if require_fullhd:
            fullhd_output = resolve_frame_output(output_dir, row.get("fullhd_output", ""))
            if fullhd_output is None or not fullhd_output.exists():
                return False

    if frame_numbers != set(range(expected_frames)):
        return False

    return True


BATCH_FIELDNAMES = [
    "archive",
    "index",
    "file_id",
    "source_size",
    "declared_frames",
    "width",
    "height",
    "blocks_x",
    "blocks_y",
    "status",
    "render_status",
    "pointer_decode_chunk",
    "pointer_decode_status",
    "pointer_decode_source_size",
    "pointer_decode_expected_size",
    "pointer_decode_size",
    "pointer_decode_prefix",
    "pointer_decode_error",
    "pointer_chunk",
    "codebook_vectors",
    "drawn_blocks",
    "skipped_blocks",
    "missing_blocks",
    "pointer_unique_indices",
    "pointer_min_index",
    "pointer_max_index",
    "pointer_explicit_skip_blocks",
    "pointer_out_of_range_blocks",
    "cbp_decode_status",
    "cbp_decoded_bytes",
    "cbp_decoded_vectors",
    "cbp_trailing_bytes",
    "cbp_decode_error",
    "partial_codebook_update",
    "codebook_update_vectors",
    "codebook_update_ignored_bytes",
    "render_frame_status_counts",
    "held_frame_count",
    "non_output_frame_count",
    "native_frames",
    "fullhd_frames",
    "output_dir",
    "render_note",
    "error",
]


def write_batch_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=BATCH_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def read_first_render_row(output_dir: Path) -> dict[str, str]:
    manifest = output_dir / "rendered_frames.csv"
    if not manifest.exists():
        return {}

    with manifest.open(newline="") as handle:
        reader = csv.DictReader(handle)
        return next(reader, {})


def read_render_status_counts(output_dir: Path) -> dict[str, int]:
    manifest = output_dir / "rendered_frames.csv"
    if not manifest.exists():
        return {}

    counts: dict[str, int] = {}
    with manifest.open(newline="") as handle:
        for row in csv.DictReader(handle):
            status = row.get("status", "")
            counts[status] = counts.get(status, 0) + 1
    return counts


def format_status_counts(counts: dict[str, int]) -> str:
    return ";".join(f"{status}:{count}" for status, count in sorted(counts.items()))


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch render VQA entries from MIX archives.")
    parser.add_argument("archives", nargs="+", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=Path("output/vqa_batch"))
    parser.add_argument("--max-frames", type=int, default=1)
    parser.add_argument("--all-frames", action="store_true", help="Render every frame in each VQA entry.")
    parser.add_argument("--limit", type=int, help="Stop after rendering this many VQA entries.")
    parser.add_argument("--dump-payloads", action="store_true")
    parser.add_argument("--native-only", action="store_true", help="Do not write Full HD PNGs.")
    parser.add_argument(
        "--progress-every",
        type=int,
        default=0,
        help="Print batch progress after every N VQA entries. Disabled by default.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Reuse entries whose rendered_frames.csv already exists in the output directory.",
    )
    parser.add_argument(
        "--rerender-incomplete",
        action="store_true",
        help="With --skip-existing, rerender existing entries whose PNG counts are incomplete.",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress per-entry decoder output.")
    parser.add_argument(
        "--experimental-window-lcw",
        action="store_true",
        help="Try the experimental 64K-window LCW fallback for compact VPT chunks.",
    )
    parser.add_argument("--width", type=int, default=vqa.TARGET_SIZE[0])
    parser.add_argument("--height", type=int, default=vqa.TARGET_SIZE[1])
    parser.add_argument("--fit", choices=("contain", "cover", "stretch"), default="contain")
    parser.add_argument("--background", type=vqa.parse_background, default=(0, 0, 0))
    parser.add_argument(
        "--transparent-index",
        type=int,
        help="Palette index to treat as transparent while drawing codebook vectors.",
    )
    parser.add_argument(
        "--filter",
        choices=("nearest", "bilinear", "bicubic", "lanczos"),
        default="nearest",
        help="Resize filter used for Full HD frame exports.",
    )
    parser.add_argument(
        "--fast-png",
        action="store_true",
        help="Disable PNG optimization for faster bulk frame exports.",
    )
    args = parser.parse_args()

    if args.max_frames < 1 and not args.all_frames:
        raise SystemExit("--max-frames must be positive")
    if args.width < 1 or args.height < 1:
        raise SystemExit("width and height must be positive")
    if args.progress_every < 0:
        raise SystemExit("--progress-every must be zero or positive")
    if args.transparent_index is not None and not 0 <= args.transparent_index <= 255:
        raise SystemExit("--transparent-index must be between 0 and 255")

    filters = {
        "nearest": Image.Resampling.NEAREST,
        "bilinear": Image.Resampling.BILINEAR,
        "bicubic": Image.Resampling.BICUBIC,
        "lanczos": Image.Resampling.LANCZOS,
    }

    args.output.mkdir(parents=True, exist_ok=True)
    manifest = args.output / "manifest.csv"
    rows: list[dict[str, str]] = []
    rendered_entries = 0
    max_frames = None if args.all_frames else args.max_frames

    for archive in args.archives:
        data = archive.read_bytes()
        table_end, entries = read_mix_entries(archive)

        for index, (file_id, offset, size) in enumerate(entries):
            payload = data[table_end + offset : table_end + offset + size]
            if not is_vqa(payload):
                continue

            header = vqa.parse_vqa(payload)[0]
            output_dir = args.output / f"{safe_stem(archive)}_{index:04d}_{file_id:08x}"
            expected_frames = header.frame_count if max_frames is None else min(header.frame_count, max_frames)
            status = "ok"
            error = ""
            can_skip_existing = False
            if args.skip_existing:
                if args.rerender_incomplete:
                    can_skip_existing = complete_png_set(output_dir, expected_frames, not args.native_only)
                else:
                    can_skip_existing = (output_dir / "rendered_frames.csv").exists()

            if can_skip_existing:
                status = "skipped_existing"
            else:
                try:
                    if args.quiet:
                        with contextlib.redirect_stdout(io.StringIO()):
                            vqa.decode_frames(
                                payload,
                                output_dir,
                                max_frames,
                                args.dump_payloads,
                                True,
                                not args.native_only,
                                (args.width, args.height),
                                args.fit,
                                filters[args.filter],
                                args.background,
                                args.experimental_window_lcw,
                                args.transparent_index,
                                not args.fast_png,
                            )
                    else:
                        vqa.decode_frames(
                            payload,
                            output_dir,
                            max_frames,
                            args.dump_payloads,
                            True,
                            not args.native_only,
                            (args.width, args.height),
                            args.fit,
                            filters[args.filter],
                            args.background,
                            args.experimental_window_lcw,
                            args.transparent_index,
                            not args.fast_png,
                        )
                except Exception as exc:
                    status = "error"
                    error = str(exc)

            render_row = read_first_render_row(output_dir)
            render_status_counts = read_render_status_counts(output_dir)
            held_frame_count = render_status_counts.get("held_frame", 0)
            non_output_frame_count = sum(
                count
                for row_status, count in render_status_counts.items()
                if row_status not in {"rendered", "held_frame"}
            )
            rows.append(
                {
                    "archive": str(archive),
                    "index": f"{index:04d}",
                    "file_id": f"{file_id:08x}",
                    "source_size": str(size),
                    "declared_frames": str(header.frame_count),
                    "width": str(header.width),
                    "height": str(header.height),
                    "blocks_x": str(header.blocks_x),
                    "blocks_y": str(header.blocks_y),
                    "status": status,
                    "render_status": render_row.get("status", ""),
                    "pointer_decode_chunk": render_row.get("pointer_decode_chunk", ""),
                    "pointer_decode_status": render_row.get("pointer_decode_status", ""),
                    "pointer_decode_source_size": render_row.get("pointer_decode_source_size", ""),
                    "pointer_decode_expected_size": render_row.get("pointer_decode_expected_size", ""),
                    "pointer_decode_size": render_row.get("pointer_decode_size", ""),
                    "pointer_decode_prefix": render_row.get("pointer_decode_prefix", ""),
                    "pointer_decode_error": render_row.get("pointer_decode_error", ""),
                    "pointer_chunk": render_row.get("pointer_chunk", ""),
                    "codebook_vectors": render_row.get("codebook_vectors", ""),
                    "drawn_blocks": render_row.get("drawn_blocks", ""),
                    "skipped_blocks": render_row.get("skipped_blocks", ""),
                    "missing_blocks": render_row.get("missing_blocks", ""),
                    "pointer_unique_indices": render_row.get("pointer_unique_indices", ""),
                    "pointer_min_index": render_row.get("pointer_min_index", ""),
                    "pointer_max_index": render_row.get("pointer_max_index", ""),
                    "pointer_explicit_skip_blocks": render_row.get("pointer_explicit_skip_blocks", ""),
                    "pointer_out_of_range_blocks": render_row.get("pointer_out_of_range_blocks", ""),
                    "cbp_decode_status": render_row.get("cbp_decode_status", ""),
                    "cbp_decoded_bytes": render_row.get("cbp_decoded_bytes", ""),
                    "cbp_decoded_vectors": render_row.get("cbp_decoded_vectors", ""),
                    "cbp_trailing_bytes": render_row.get("cbp_trailing_bytes", ""),
                    "cbp_decode_error": render_row.get("cbp_decode_error", ""),
                    "partial_codebook_update": render_row.get("partial_codebook_update", ""),
                    "codebook_update_vectors": render_row.get("codebook_update_vectors", ""),
                    "codebook_update_ignored_bytes": render_row.get("codebook_update_ignored_bytes", ""),
                    "render_frame_status_counts": format_status_counts(render_status_counts),
                    "held_frame_count": str(held_frame_count),
                    "non_output_frame_count": str(non_output_frame_count),
                    "native_frames": str(count_pngs(output_dir / "frames_native")),
                    "fullhd_frames": str(count_pngs(output_dir / "frames_fullhd")),
                    "output_dir": str(output_dir),
                    "render_note": render_row.get("note", ""),
                    "error": error,
                }
            )
            write_batch_manifest(manifest, rows)

            rendered_entries += 1
            if args.progress_every and rendered_entries % args.progress_every == 0:
                ok_count = sum(1 for row in rows if row["status"] == "ok")
                skipped_count = sum(1 for row in rows if row["status"] == "skipped_existing")
                error_count = sum(1 for row in rows if row["status"] == "error")
                print(
                    f"Progress: {rendered_entries} entries "
                    f"({ok_count} rendered, {skipped_count} skipped, {error_count} errors)"
                )
            if args.limit is not None and rendered_entries >= args.limit:
                break

        if args.limit is not None and rendered_entries >= args.limit:
            break

    write_batch_manifest(manifest, rows)

    ok_count = sum(1 for row in rows if row["status"] == "ok")
    skipped_count = sum(1 for row in rows if row["status"] == "skipped_existing")
    error_count = sum(1 for row in rows if row["status"] == "error")
    print(
        f"Processed {len(rows)} VQA entries to {args.output} "
        f"({ok_count} rendered, {skipped_count} skipped, {error_count} errors)"
    )
    print(f"Manifest: {manifest}")


if __name__ == "__main__":
    main()
