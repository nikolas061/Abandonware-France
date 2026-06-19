#!/usr/bin/env python3
"""Build a manifest-level inventory of generated Full HD image exports."""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from PIL import Image


TARGET_SIZE = (1920, 1080)

DEFAULT_STILL_MANIFESTS = [Path("output/fullhd_images/manifest.csv")]
DEFAULT_VQA_MANIFESTS = [Path("output/vqa_batch_window_lcw_transparent0_allframes/manifest.csv")]
DEFAULT_CDCACHE_MANIFESTS = [
    Path("output/cdcache_textures_all_tiled_tiles_rgba/manifest.csv"),
    Path("output/cdcache_textures_all_tiled_tiles_rgba/tiles_manifest.csv"),
]
DEFAULT_TEX_MATERIAL_DECODE_MANIFESTS = [Path("output/tex_material_decode_pack/manifest.csv")]
DEFAULT_TEX_RAW_SAME_ARCHIVE_PROMOTED_MANIFESTS = [
    Path("output/tex_raw_same_archive_promoted_pack/manifest.csv")
]

INVENTORY_FIELDNAMES = [
    "category",
    "source_manifest",
    "source_archive",
    "source_index",
    "source_id",
    "frame",
    "variant",
    "declared_width",
    "declared_height",
    "output_path",
    "exists",
    "actual_width",
    "actual_height",
    "image_mode",
    "has_transparency",
    "issues",
]

SUMMARY_FIELDNAMES = [
    "category",
    "records",
    "existing_files",
    "fullhd_files",
    "transparent_files",
    "issue_rows",
    "modes",
]


class InventoryStats:
    def __init__(self) -> None:
        self.records = 0
        self.existing_files = 0
        self.fullhd_files = 0
        self.transparent_files = 0
        self.issue_rows = 0
        self.modes: Counter[str] = Counter()

    def add(self, row: dict[str, str]) -> None:
        self.records += 1
        if row["exists"] == "yes":
            self.existing_files += 1
        if (row["actual_width"], row["actual_height"]) == (
            str(TARGET_SIZE[0]),
            str(TARGET_SIZE[1]),
        ):
            self.fullhd_files += 1
        if row["has_transparency"] == "yes":
            self.transparent_files += 1
        if row["issues"]:
            self.issue_rows += 1
        if row["image_mode"]:
            self.modes[row["image_mode"]] += 1

    def as_row(self, category: str) -> dict[str, str]:
        modes = ";".join(f"{mode}:{count}" for mode, count in sorted(self.modes.items()))
        return {
            "category": category,
            "records": str(self.records),
            "existing_files": str(self.existing_files),
            "fullhd_files": str(self.fullhd_files),
            "transparent_files": str(self.transparent_files),
            "issue_rows": str(self.issue_rows),
            "modes": modes,
        }


def existing_paths(paths: Iterable[Path]) -> list[Path]:
    return [path for path in paths if path.exists()]


def resolve_path(raw: str, manifest: Path) -> Path | None:
    if not raw:
        return None
    path = Path(raw)
    if path.is_absolute() or path.exists():
        return path
    return manifest.parent / path


def image_info(path: Path | None, *, inspect_images: bool) -> tuple[int, int, str, bool, list[str]]:
    issues: list[str] = []
    if path is None:
        return 0, 0, "", False, ["missing_output_path"]
    if not path.exists():
        return 0, 0, "", False, ["file_not_found"]
    if not inspect_images:
        return 0, 0, "", False, []

    try:
        with Image.open(path) as image:
            mode = image.mode
            has_transparency = False
            if mode == "RGBA":
                alpha_extrema = image.getchannel("A").getextrema()
                has_transparency = bool(alpha_extrema and alpha_extrema[0] < 255)
            elif "transparency" in image.info:
                has_transparency = True
            return image.size[0], image.size[1], mode, has_transparency, []
    except Exception as exc:
        return 0, 0, "", False, [f"image_open_failed:{exc}"]


def make_row(
    *,
    category: str,
    source_manifest: Path,
    source_archive: str = "",
    source_index: str = "",
    source_id: str = "",
    frame: str = "",
    variant: str,
    declared_width: str = str(TARGET_SIZE[0]),
    declared_height: str = str(TARGET_SIZE[1]),
    output_path: str,
    inspect_images: bool,
) -> dict[str, str]:
    path = resolve_path(output_path, source_manifest)
    actual_width, actual_height, mode, has_transparency, issues = image_info(
        path,
        inspect_images=inspect_images,
    )
    if inspect_images and path is not None and path.exists():
        if (actual_width, actual_height) != TARGET_SIZE:
            issues.append("not_fullhd")
    return {
        "category": category,
        "source_manifest": str(source_manifest),
        "source_archive": source_archive,
        "source_index": source_index,
        "source_id": source_id,
        "frame": frame,
        "variant": variant,
        "declared_width": declared_width,
        "declared_height": declared_height,
        "output_path": "" if path is None else str(path),
        "exists": "yes" if path is not None and path.exists() else "no",
        "actual_width": str(actual_width),
        "actual_height": str(actual_height),
        "image_mode": mode,
        "has_transparency": "yes" if has_transparency else "no",
        "issues": ";".join(issues),
    }


def iter_still_rows(manifest: Path, inspect_images: bool) -> Iterable[dict[str, str]]:
    with manifest.open(newline="") as handle:
        for row in csv.DictReader(handle):
            yield make_row(
                category=f"still_{row.get('source_type', '')}",
                source_manifest=manifest,
                source_archive=row.get("archive", ""),
                source_index=row.get("index", ""),
                source_id=row.get("file_id", ""),
                variant="fullhd",
                declared_width=row.get("output_width", str(TARGET_SIZE[0])),
                declared_height=row.get("output_height", str(TARGET_SIZE[1])),
                output_path=row.get("output_path", ""),
                inspect_images=inspect_images,
            )


def iter_vqa_rows(manifest: Path, inspect_images: bool) -> Iterable[dict[str, str]]:
    with manifest.open(newline="") as handle:
        for entry in csv.DictReader(handle):
            output_dir = resolve_path(entry.get("output_dir", ""), manifest)
            rendered_manifest = None if output_dir is None else output_dir / "rendered_frames.csv"
            if rendered_manifest is None or not rendered_manifest.exists():
                yield make_row(
                    category="vqa_frame",
                    source_manifest=manifest,
                    source_archive=entry.get("archive", ""),
                    source_index=entry.get("index", ""),
                    source_id=entry.get("file_id", ""),
                    variant="fullhd",
                    output_path="",
                    inspect_images=inspect_images,
                )
                continue

            with rendered_manifest.open(newline="") as frame_handle:
                for frame in csv.DictReader(frame_handle):
                    output_path = frame.get("fullhd_output", "")
                    if not output_path:
                        continue
                    yield make_row(
                        category="vqa_frame",
                        source_manifest=manifest,
                        source_archive=entry.get("archive", ""),
                        source_index=entry.get("index", ""),
                        source_id=entry.get("file_id", ""),
                        frame=frame.get("frame", ""),
                        variant="fullhd",
                        output_path=output_path,
                        inspect_images=inspect_images,
                    )


def iter_cdcache_rows(manifest: Path, inspect_images: bool) -> Iterable[dict[str, str]]:
    is_tile_manifest = manifest.name == "tiles_manifest.csv"
    category = "cdcache_tile" if is_tile_manifest else "cdcache_descriptor"
    with manifest.open(newline="") as handle:
        for row in csv.DictReader(handle):
            source_index = row.get("cache_index", "")
            source_id = row.get("base_name", "")
            common = {
                "category": category,
                "source_manifest": manifest,
                "source_archive": row.get("matched_texture_archives", ""),
                "source_index": source_index,
                "source_id": source_id,
                "inspect_images": inspect_images,
            }
            yield make_row(
                **common,
                variant="fullhd",
                declared_width=str(TARGET_SIZE[0]),
                declared_height=str(TARGET_SIZE[1]),
                output_path=row.get("fullhd_path", ""),
            )
            if row.get("crop_fullhd_path"):
                yield make_row(
                    **common,
                    variant="crop_fullhd",
                    declared_width=str(TARGET_SIZE[0]),
                    declared_height=str(TARGET_SIZE[1]),
                    output_path=row.get("crop_fullhd_path", ""),
                )


def iter_tex_material_decode_rows(manifest: Path, inspect_images: bool) -> Iterable[dict[str, str]]:
    with manifest.open(newline="") as handle:
        for row in csv.DictReader(handle):
            yield make_row(
                category="tex_material_decode",
                source_manifest=manifest,
                source_archive=row.get("archive", ""),
                source_index=row.get("segment_index", ""),
                source_id=row.get("asset_id", ""),
                variant="decoded_fullhd",
                declared_width=str(TARGET_SIZE[0]),
                declared_height=str(TARGET_SIZE[1]),
                output_path=row.get("decoded_fullhd_path", ""),
                inspect_images=inspect_images,
            )


def iter_tex_raw_same_archive_promoted_rows(manifest: Path, inspect_images: bool) -> Iterable[dict[str, str]]:
    with manifest.open(newline="") as handle:
        for row in csv.DictReader(handle):
            yield make_row(
                category="tex_raw_same_archive_promoted",
                source_manifest=manifest,
                source_archive=row.get("archive", ""),
                source_index=row.get("review_status", ""),
                source_id=row.get("asset_id", ""),
                variant="promoted_fullhd",
                declared_width=str(TARGET_SIZE[0]),
                declared_height=str(TARGET_SIZE[1]),
                output_path=row.get("promoted_fullhd_path", ""),
                inspect_images=inspect_images,
            )


def write_inventory(
    output_dir: Path,
    still_manifests: list[Path],
    vqa_manifests: list[Path],
    cdcache_manifests: list[Path],
    tex_material_decode_manifests: list[Path],
    tex_raw_same_archive_promoted_manifests: list[Path],
    *,
    inspect_images: bool,
    progress_every: int,
) -> tuple[Path, Path, dict[str, InventoryStats]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    inventory_path = output_dir / "manifest.csv"
    summary_path = output_dir / "summary.csv"
    stats: dict[str, InventoryStats] = defaultdict(InventoryStats)
    stats["total"] = InventoryStats()
    row_count = 0

    sources = []
    for manifest in still_manifests:
        sources.append(iter_still_rows(manifest, inspect_images))
    for manifest in vqa_manifests:
        sources.append(iter_vqa_rows(manifest, inspect_images))
    for manifest in cdcache_manifests:
        sources.append(iter_cdcache_rows(manifest, inspect_images))
    for manifest in tex_material_decode_manifests:
        sources.append(iter_tex_material_decode_rows(manifest, inspect_images))
    for manifest in tex_raw_same_archive_promoted_manifests:
        sources.append(iter_tex_raw_same_archive_promoted_rows(manifest, inspect_images))

    with inventory_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=INVENTORY_FIELDNAMES)
        writer.writeheader()
        for source in sources:
            for row in source:
                writer.writerow(row)
                stats[row["category"]].add(row)
                stats["total"].add(row)
                row_count += 1
                if progress_every and row_count % progress_every == 0:
                    print(f"Inventoried {row_count} Full HD outputs", flush=True)

    with summary_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDNAMES)
        writer.writeheader()
        for category in sorted(key for key in stats if key != "total"):
            writer.writerow(stats[category].as_row(category))
        writer.writerow(stats["total"].as_row("total"))

    return inventory_path, summary_path, stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inventory generated Full HD PNG exports from existing manifests.",
    )
    parser.add_argument("-o", "--output", type=Path, default=Path("output/fullhd_inventory"))
    parser.add_argument("--still-manifest", type=Path, action="append")
    parser.add_argument("--vqa-manifest", type=Path, action="append")
    parser.add_argument("--cdcache-manifest", type=Path, action="append")
    parser.add_argument("--tex-material-decode-manifest", type=Path, action="append")
    parser.add_argument("--tex-raw-same-archive-promoted-manifest", type=Path, action="append")
    parser.add_argument(
        "--no-image-inspection",
        action="store_true",
        help="Only check that manifest paths exist; skip opening PNG files.",
    )
    parser.add_argument("--progress-every", type=int, default=25000)
    args = parser.parse_args()

    still_manifests = args.still_manifest or existing_paths(DEFAULT_STILL_MANIFESTS)
    vqa_manifests = args.vqa_manifest or existing_paths(DEFAULT_VQA_MANIFESTS)
    cdcache_manifests = args.cdcache_manifest or existing_paths(DEFAULT_CDCACHE_MANIFESTS)
    tex_material_decode_manifests = args.tex_material_decode_manifest or existing_paths(
        DEFAULT_TEX_MATERIAL_DECODE_MANIFESTS
    )
    tex_raw_same_archive_promoted_manifests = args.tex_raw_same_archive_promoted_manifest or existing_paths(
        DEFAULT_TEX_RAW_SAME_ARCHIVE_PROMOTED_MANIFESTS
    )
    inspect_images = not args.no_image_inspection

    inventory_path, summary_path, stats = write_inventory(
        args.output,
        still_manifests,
        vqa_manifests,
        cdcache_manifests,
        tex_material_decode_manifests,
        tex_raw_same_archive_promoted_manifests,
        inspect_images=inspect_images,
        progress_every=args.progress_every,
    )

    total = stats["total"]
    print(f"Inventory: {inventory_path}")
    print(f"Summary: {summary_path}")
    print(
        "Full HD inventory rows: "
        f"{total.records}; existing={total.existing_files}; "
        f"1920x1080={total.fullhd_files}; issues={total.issue_rows}"
    )


if __name__ == "__main__":
    main()
