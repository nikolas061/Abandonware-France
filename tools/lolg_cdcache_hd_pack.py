#!/usr/bin/env python3
"""Create a stable Full HD CDCACHE asset pack from verified texture manifests."""

from __future__ import annotations

import argparse
import csv
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image


TARGET_SIZE = (1920, 1080)

DEFAULT_DESCRIPTOR_MANIFEST = Path("output/cdcache_textures_all_tiled_tiles_rgba/manifest.csv")
DEFAULT_TILE_MANIFEST = Path("output/cdcache_textures_all_tiled_tiles_rgba/tiles_manifest.csv")
DEFAULT_MATERIAL_LINKS = Path("output/texture_report/cdcache_material_texture_links.csv")

PACK_FIELDNAMES = [
    "asset_id",
    "asset_kind",
    "linked_to_tex",
    "matched_texture_archives",
    "archive_tags",
    "pcx_name",
    "base_name",
    "material_names",
    "cache_index",
    "tile_index",
    "tile_x",
    "tile_y",
    "native_width",
    "native_height",
    "content_bbox",
    "visible_pixel_ratio",
    "selected_variant",
    "source_fullhd_path",
    "all_pack_path",
    "linked_pack_path",
    "source_exists",
    "all_pack_exists",
    "linked_pack_exists",
    "image_mode",
    "has_transparency",
    "issues",
]

SUMMARY_FIELDNAMES = [
    "group",
    "assets",
    "linked_to_tex",
    "source_files",
    "all_pack_links",
    "linked_pack_links",
    "transparent_assets",
    "issue_rows",
    "selected_variants",
]


def make_checkerboard(size: tuple[int, int], cell: int = 8) -> Image.Image:
    image = Image.new("RGB", size, (196, 196, 196))
    pixels = image.load()
    width, height = size
    for y in range(height):
        for x in range(width):
            if ((x // cell) + (y // cell)) % 2:
                pixels[x, y] = (232, 232, 232)
    return image


def paste_contained(canvas: Image.Image, source: Image.Image, box: tuple[int, int, int, int]) -> None:
    left, top, right, bottom = box
    box_width = right - left
    box_height = bottom - top
    image = source.convert("RGBA")
    image.thumbnail((box_width, box_height), Image.Resampling.NEAREST)
    x = left + (box_width - image.width) // 2
    y = top + (box_height - image.height) // 2
    canvas.paste(image.convert("RGB"), (x, y), image)


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "unnamed"


def archive_tag(path: str) -> str:
    if not path:
        return "unlinked"
    stem = Path(path).stem
    return safe_name(stem).upper()


def split_archives(raw: str) -> list[str]:
    return [part.strip() for part in re.split(r"[;|]", raw) if part.strip()]


def resolve_existing(raw: str, manifest: Path) -> Path | None:
    if not raw:
        return None
    path = Path(raw)
    if path.is_absolute() or path.exists():
        return path
    candidate = manifest.parent / path
    return candidate


def load_material_names(path: Path) -> dict[tuple[str, str], str]:
    if not path.exists():
        return {}
    grouped: dict[tuple[str, str], set[str]] = defaultdict(set)
    with path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            archive = row.get("archive", "")
            pcx_name = row.get("pcx_name", "").lower()
            name = row.get("material_clean_text", "")
            if archive and pcx_name and name:
                grouped[(archive, pcx_name)].add(name)
    return {key: ";".join(sorted(values)) for key, values in grouped.items()}


def selected_fullhd_path(row: dict[str, str], manifest: Path) -> tuple[str, Path | None]:
    crop = resolve_existing(row.get("crop_fullhd_path", ""), manifest)
    if crop is not None and crop.exists():
        return "crop_fullhd", crop
    fullhd = resolve_existing(row.get("fullhd_path", ""), manifest)
    return "fullhd", fullhd


def image_info(path: Path | None) -> tuple[str, bool, list[str]]:
    issues: list[str] = []
    if path is None:
        return "", False, ["missing_source_fullhd_path"]
    if not path.exists():
        return "", False, ["source_file_not_found"]
    try:
        with Image.open(path) as image:
            mode = image.mode
            if image.size != TARGET_SIZE:
                issues.append("source_not_fullhd")
            has_transparency = False
            if mode == "RGBA":
                alpha_extrema = image.getchannel("A").getextrema()
                has_transparency = bool(alpha_extrema and alpha_extrema[0] < 255)
            elif "transparency" in image.info:
                has_transparency = True
            return mode, has_transparency, issues
    except Exception as exc:
        return "", False, [f"source_image_open_failed:{exc}"]


def make_relative_symlink(target: Path, link: Path, issues: list[str]) -> bool:
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.exists() or link.is_symlink():
        if link.is_symlink():
            current = os.readlink(link)
            expected = os.path.relpath(target, link.parent)
            current_path = (link.parent / current).resolve()
            if current == expected or current_path == target.resolve():
                return True
            link.unlink()
        else:
            issues.append("pack_path_blocked_by_regular_file")
            return False

    try:
        relative_target = os.path.relpath(target, link.parent)
        link.symlink_to(relative_target)
        return True
    except Exception as exc:
        issues.append(f"symlink_failed:{exc}")
        return False


def common_asset_id(row: dict[str, str], asset_kind: str) -> str:
    base = safe_name(row.get("base_name") or row.get("pcx_name", "asset"))
    cache_index = int(row.get("cache_index", "0") or 0)
    if asset_kind == "tile":
        tile_index = int(row.get("tile_index", "0") or 0)
        tile_x = int(row.get("tile_x", "0") or 0)
        tile_y = int(row.get("tile_y", "0") or 0)
        width = row.get("tile_width", "0")
        height = row.get("tile_height", "0")
        return (
            f"{base}_idx{cache_index:04d}_tile{tile_index:04d}"
            f"_x{tile_x:04d}_y{tile_y:04d}_{width}x{height}"
        )
    width = row.get("width", "0")
    height = row.get("height", "0")
    return f"{base}_idx{cache_index:04d}_descriptor_{width}x{height}"


def build_pack_row(
    row: dict[str, str],
    *,
    asset_kind: str,
    manifest: Path,
    output_dir: Path,
    material_names: dict[tuple[str, str], str],
    create_links: bool,
) -> dict[str, str]:
    issues: list[str] = []
    selected_variant, source_path = selected_fullhd_path(row, manifest)
    mode, has_transparency, image_issues = image_info(source_path)
    issues.extend(image_issues)

    archives = split_archives(row.get("matched_texture_archives", ""))
    linked_to_tex = bool(archives)
    tags = [archive_tag(archive) for archive in archives]
    primary_tag = tags[0] if tags else "UNLINKED"
    asset_id = common_asset_id(row, asset_kind)
    filename = f"{asset_id}_{selected_variant}.png"
    kind_dir = "descriptors" if asset_kind == "descriptor" else "tiles"
    all_pack_path = output_dir / "all" / kind_dir / filename
    linked_pack_path = (
        output_dir / "linked_tex" / primary_tag / kind_dir / filename
        if linked_to_tex
        else None
    )

    if create_links and source_path is not None and source_path.exists():
        make_relative_symlink(source_path, all_pack_path, issues)
        if linked_pack_path is not None:
            make_relative_symlink(source_path, linked_pack_path, issues)

    material_values = []
    for archive in archives:
        value = material_names.get((archive, row.get("base_name", "").lower()))
        if value:
            material_values.extend(value.split(";"))
    material_text = ";".join(sorted(set(value for value in material_values if value)))

    native_width = row.get("width") or row.get("tile_width", "")
    native_height = row.get("height") or row.get("tile_height", "")
    if source_path is None or not source_path.exists():
        source_exists = "no"
    else:
        source_exists = "yes"

    return {
        "asset_id": asset_id,
        "asset_kind": asset_kind,
        "linked_to_tex": "yes" if linked_to_tex else "no",
        "matched_texture_archives": ";".join(archives),
        "archive_tags": ";".join(tags),
        "pcx_name": row.get("pcx_name", ""),
        "base_name": row.get("base_name", ""),
        "material_names": material_text,
        "cache_index": row.get("cache_index", ""),
        "tile_index": row.get("tile_index", ""),
        "tile_x": row.get("tile_x", ""),
        "tile_y": row.get("tile_y", ""),
        "native_width": native_width,
        "native_height": native_height,
        "content_bbox": row.get("content_bbox", ""),
        "visible_pixel_ratio": row.get("visible_pixel_ratio", ""),
        "selected_variant": selected_variant,
        "source_fullhd_path": "" if source_path is None else str(source_path),
        "all_pack_path": str(all_pack_path),
        "linked_pack_path": "" if linked_pack_path is None else str(linked_pack_path),
        "source_exists": source_exists,
        "all_pack_exists": "yes" if all_pack_path.exists() else "no",
        "linked_pack_exists": (
            "" if linked_pack_path is None else ("yes" if linked_pack_path.exists() else "no")
        ),
        "image_mode": mode,
        "has_transparency": "yes" if has_transparency else "no",
        "issues": ";".join(issues),
    }


def read_manifest_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_summary(path: Path, rows: list[dict[str, str]]) -> None:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[row["asset_kind"]].append(row)
        groups["total"].append(row)

    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDNAMES)
        writer.writeheader()
        for group in sorted(key for key in groups if key != "total") + ["total"]:
            group_rows = groups[group]
            selected_variants = Counter(row["selected_variant"] for row in group_rows)
            writer.writerow(
                {
                    "group": group,
                    "assets": str(len(group_rows)),
                    "linked_to_tex": str(sum(1 for row in group_rows if row["linked_to_tex"] == "yes")),
                    "source_files": str(sum(1 for row in group_rows if row["source_exists"] == "yes")),
                    "all_pack_links": str(sum(1 for row in group_rows if row["all_pack_exists"] == "yes")),
                    "linked_pack_links": str(
                        sum(1 for row in group_rows if row["linked_pack_exists"] == "yes")
                    ),
                    "transparent_assets": str(
                        sum(1 for row in group_rows if row["has_transparency"] == "yes")
                    ),
                    "issue_rows": str(sum(1 for row in group_rows if row["issues"])),
                    "selected_variants": ";".join(
                        f"{variant}:{count}" for variant, count in sorted(selected_variants.items())
                    ),
                }
            )


def write_contact_sheet(
    path: Path,
    rows: list[dict[str, str]],
    *,
    columns: int,
    thumb_size: tuple[int, int] = (240, 135),
    padding: int = 8,
) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    rows_down = (len(rows) + columns - 1) // columns
    cell_w = thumb_size[0] + padding
    cell_h = thumb_size[1] + padding
    sheet = make_checkerboard((columns * cell_w + padding, rows_down * cell_h + padding))
    for index, row in enumerate(rows):
        source = Path(row["source_fullhd_path"])
        if not source.exists():
            continue
        with Image.open(source) as image:
            col = index % columns
            sheet_row = index // columns
            left = padding + col * cell_w
            top = padding + sheet_row * cell_h
            paste_contained(sheet, image, (left, top, left + thumb_size[0], top + thumb_size[1]))
    sheet.save(path, "PNG")


def write_contact_sheets(output_dir: Path, rows: list[dict[str, str]]) -> list[Path]:
    all_descriptors = [row for row in rows if row["asset_kind"] == "descriptor"]
    linked_descriptors = [
        row for row in all_descriptors if row["linked_to_tex"] == "yes"
    ]
    linked_tiles = [
        row
        for row in rows
        if row["asset_kind"] == "tile" and row["linked_to_tex"] == "yes"
    ]
    sheets = [
        (output_dir / "contact_sheet_all_descriptors.png", all_descriptors, 8),
        (output_dir / "contact_sheet_linked_descriptors.png", linked_descriptors, 7),
        (output_dir / "contact_sheet_linked_tiles.png", linked_tiles, 10),
    ]
    written: list[Path] = []
    for path, sheet_rows, columns in sheets:
        write_contact_sheet(path, sheet_rows, columns=columns)
        if path.exists():
            written.append(path)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a stable symlink pack for verified CDCACHE Full HD PNG assets.",
    )
    parser.add_argument("--descriptor-manifest", type=Path, default=DEFAULT_DESCRIPTOR_MANIFEST)
    parser.add_argument("--tile-manifest", type=Path, default=DEFAULT_TILE_MANIFEST)
    parser.add_argument("--material-links", type=Path, default=DEFAULT_MATERIAL_LINKS)
    parser.add_argument("-o", "--output", type=Path, default=Path("output/cdcache_hd_asset_pack"))
    parser.add_argument(
        "--no-links",
        action="store_true",
        help="Only write manifest and summary; do not create symlinks.",
    )
    parser.add_argument(
        "--contact-sheets",
        action="store_true",
        help="Also write PNG contact sheets for descriptor and .tex-linked assets.",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    material_names = load_material_names(args.material_links)
    rows: list[dict[str, str]] = []
    for row in read_manifest_rows(args.descriptor_manifest):
        rows.append(
            build_pack_row(
                row,
                asset_kind="descriptor",
                manifest=args.descriptor_manifest,
                output_dir=args.output,
                material_names=material_names,
                create_links=not args.no_links,
            )
        )
    for row in read_manifest_rows(args.tile_manifest):
        rows.append(
            build_pack_row(
                row,
                asset_kind="tile",
                manifest=args.tile_manifest,
                output_dir=args.output,
                material_names=material_names,
                create_links=not args.no_links,
            )
        )

    manifest = args.output / "manifest.csv"
    summary = args.output / "summary.csv"
    with manifest.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PACK_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    write_summary(summary, rows)
    contact_sheets = write_contact_sheets(args.output, rows) if args.contact_sheets else []

    issue_rows = [row for row in rows if row["issues"]]
    linked_rows = [row for row in rows if row["linked_to_tex"] == "yes"]
    print(f"CDCACHE HD pack assets: {len(rows)}")
    print(f"Linked to .tex archives: {len(linked_rows)}")
    print(f"Issue rows: {len(issue_rows)}")
    print(f"Manifest: {manifest}")
    print(f"Summary: {summary}")
    for path in contact_sheets:
        print(f"Contact sheet: {path}")
    if issue_rows:
        print("First issues:")
        for row in issue_rows[:10]:
            print(f"  {row['asset_id']} {row['issues']}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
