#!/usr/bin/env python3
"""Verify CDCACHE texture PNG exports against their manifest."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

from PIL import Image


TARGET_SIZE = (1920, 1080)

REPORT_FIELDNAMES = [
    "row_index",
    "pcx_name",
    "base_name",
    "matched_texture_archives",
    "decode_mode",
    "expected_image_mode",
    "native_expected_width",
    "native_expected_height",
    "native_actual_width",
    "native_actual_height",
    "native_mode",
    "native_has_transparency",
    "fullhd_actual_width",
    "fullhd_actual_height",
    "fullhd_mode",
    "fullhd_has_transparency",
    "crop_expected_width",
    "crop_expected_height",
    "crop_actual_width",
    "crop_actual_height",
    "crop_mode",
    "crop_has_transparency",
    "crop_fullhd_actual_width",
    "crop_fullhd_actual_height",
    "crop_fullhd_mode",
    "crop_fullhd_has_transparency",
    "content_bbox",
    "visible_pixel_ratio",
    "native_path",
    "fullhd_path",
    "crop_native_path",
    "crop_fullhd_path",
    "issues",
]


def parse_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value, 0)
    except ValueError:
        return None


def parse_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_bbox(value: str) -> tuple[int, int, int, int] | None:
    if not value:
        return None
    parts = value.split(",")
    if len(parts) != 4:
        return None
    try:
        left, top, right, bottom = (int(part) for part in parts)
    except ValueError:
        return None
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def resolve_path(output_dir: Path, raw: str) -> Path | None:
    if not raw:
        return None
    path = Path(raw)
    if path.is_absolute() or path.exists():
        return path
    return output_dir / path.name


def read_image_info(
    path: Path | None,
    issues: list[str],
    label: str,
) -> tuple[int, int, str, bool]:
    if path is None:
        issues.append(f"missing_{label}_path")
        return 0, 0, "", False
    if not path.exists():
        issues.append(f"{label}_file_not_found")
        return 0, 0, "", False
    try:
        with Image.open(path) as image:
            mode = image.mode
            has_transparency = False
            if mode == "RGBA":
                alpha_extrema = image.getchannel("A").getextrema()
                has_transparency = bool(alpha_extrema and alpha_extrema[0] < 255)
            elif "transparency" in image.info:
                has_transparency = True
            return image.size[0], image.size[1], mode, has_transparency
    except Exception as exc:
        issues.append(f"{label}_image_open_failed:{exc}")
        return 0, 0, "", False


def verify_row(
    output_dir: Path,
    row_index: int,
    row: dict[str, str],
    *,
    require_fullhd: bool,
    require_crops: bool,
    target_size: tuple[int, int],
) -> dict[str, str]:
    issues: list[str] = []
    expected_width = parse_int(row.get("width") or row.get("tile_width"))
    expected_height = parse_int(row.get("height") or row.get("tile_height"))
    visible_ratio = parse_float(row.get("visible_pixel_ratio"))
    expected_image_mode = row.get("image_mode", "")
    raw_bbox = row.get("content_bbox", "")
    bbox = parse_bbox(raw_bbox)
    if raw_bbox and bbox is None:
        issues.append("invalid_content_bbox")

    if expected_width is None or expected_height is None:
        issues.append("missing_native_dimensions")
        expected_width = 0
        expected_height = 0
    elif expected_width <= 0 or expected_height <= 0:
        issues.append("invalid_native_dimensions")

    if visible_ratio is None:
        issues.append("missing_visible_pixel_ratio")
    elif not 0.0 <= visible_ratio <= 1.0:
        issues.append("visible_pixel_ratio_out_of_range")

    if bbox is not None and expected_width and expected_height:
        left, top, right, bottom = bbox
        if left < 0 or top < 0 or right > expected_width or bottom > expected_height:
            issues.append("content_bbox_out_of_bounds")

    native_path = resolve_path(output_dir, row.get("native_path", ""))
    native_width, native_height, native_mode, native_has_transparency = read_image_info(
        native_path,
        issues,
        "native",
    )
    if expected_width and expected_height and (native_width, native_height) != (
        expected_width,
        expected_height,
    ):
        issues.append("native_dimensions_mismatch")
    if expected_image_mode and native_mode and native_mode != expected_image_mode:
        issues.append("native_mode_mismatch")

    fullhd_path = resolve_path(output_dir, row.get("fullhd_path", ""))
    if require_fullhd or fullhd_path is not None:
        fullhd_width, fullhd_height, fullhd_mode, fullhd_has_transparency = read_image_info(
            fullhd_path,
            issues,
            "fullhd",
        )
        if (fullhd_width, fullhd_height) != target_size:
            issues.append("fullhd_dimensions_mismatch")
        if expected_image_mode and fullhd_mode and fullhd_mode != expected_image_mode:
            issues.append("fullhd_mode_mismatch")
    else:
        fullhd_width = 0
        fullhd_height = 0
        fullhd_mode = ""
        fullhd_has_transparency = False

    crop_expected_width = 0
    crop_expected_height = 0
    if bbox:
        crop_expected_width = bbox[2] - bbox[0]
        crop_expected_height = bbox[3] - bbox[1]

    crop_native_path = resolve_path(output_dir, row.get("crop_native_path", ""))
    require_crop_for_row = require_crops and bbox is not None
    if require_crop_for_row or crop_native_path is not None:
        crop_width, crop_height, crop_mode, crop_has_transparency = read_image_info(
            crop_native_path,
            issues,
            "crop_native",
        )
        if not bbox:
            issues.append("crop_present_without_valid_bbox")
        elif (crop_width, crop_height) != (crop_expected_width, crop_expected_height):
            issues.append("crop_native_dimensions_mismatch")
        if expected_image_mode and crop_mode and crop_mode != expected_image_mode:
            issues.append("crop_native_mode_mismatch")
    else:
        crop_width = 0
        crop_height = 0
        crop_mode = ""
        crop_has_transparency = False

    crop_fullhd_path = resolve_path(output_dir, row.get("crop_fullhd_path", ""))
    if (require_crop_for_row and require_fullhd) or crop_fullhd_path is not None:
        (
            crop_fullhd_width,
            crop_fullhd_height,
            crop_fullhd_mode,
            crop_fullhd_has_transparency,
        ) = read_image_info(
            crop_fullhd_path,
            issues,
            "crop_fullhd",
        )
        if (crop_fullhd_width, crop_fullhd_height) != target_size:
            issues.append("crop_fullhd_dimensions_mismatch")
        if expected_image_mode and crop_fullhd_mode and crop_fullhd_mode != expected_image_mode:
            issues.append("crop_fullhd_mode_mismatch")
    else:
        crop_fullhd_width = 0
        crop_fullhd_height = 0
        crop_fullhd_mode = ""
        crop_fullhd_has_transparency = False

    return {
        "row_index": str(row_index),
        "pcx_name": row.get("pcx_name", ""),
        "base_name": row.get("base_name", ""),
        "matched_texture_archives": row.get("matched_texture_archives", ""),
        "decode_mode": row.get("decode_mode", ""),
        "expected_image_mode": expected_image_mode,
        "native_expected_width": str(expected_width),
        "native_expected_height": str(expected_height),
        "native_actual_width": str(native_width),
        "native_actual_height": str(native_height),
        "native_mode": native_mode,
        "native_has_transparency": str(native_has_transparency),
        "fullhd_actual_width": str(fullhd_width),
        "fullhd_actual_height": str(fullhd_height),
        "fullhd_mode": fullhd_mode,
        "fullhd_has_transparency": str(fullhd_has_transparency),
        "crop_expected_width": str(crop_expected_width),
        "crop_expected_height": str(crop_expected_height),
        "crop_actual_width": str(crop_width),
        "crop_actual_height": str(crop_height),
        "crop_mode": crop_mode,
        "crop_has_transparency": str(crop_has_transparency),
        "crop_fullhd_actual_width": str(crop_fullhd_width),
        "crop_fullhd_actual_height": str(crop_fullhd_height),
        "crop_fullhd_mode": crop_fullhd_mode,
        "crop_fullhd_has_transparency": str(crop_fullhd_has_transparency),
        "content_bbox": row.get("content_bbox", ""),
        "visible_pixel_ratio": row.get("visible_pixel_ratio", ""),
        "native_path": "" if native_path is None else str(native_path),
        "fullhd_path": "" if fullhd_path is None else str(fullhd_path),
        "crop_native_path": "" if crop_native_path is None else str(crop_native_path),
        "crop_fullhd_path": "" if crop_fullhd_path is None else str(crop_fullhd_path),
        "issues": ";".join(issues),
    }


def duplicate_paths(rows: list[dict[str, str]]) -> set[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        for field in ("native_path", "fullhd_path", "crop_native_path", "crop_fullhd_path"):
            raw = row.get(field, "")
            if raw:
                counts[raw] += 1
    return {path for path, count in counts.items() if count > 1}


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a CDCACHE texture export directory.")
    parser.add_argument("output_dir", type=Path)
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Manifest CSV to read. Defaults to OUTPUT_DIR/manifest.csv.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Write per-entry verification CSV. Defaults to OUTPUT_DIR/verification.csv.",
    )
    parser.add_argument("--native-only", action="store_true")
    parser.add_argument("--require-crops", action="store_true")
    parser.add_argument("--target-width", type=int, default=TARGET_SIZE[0])
    parser.add_argument("--target-height", type=int, default=TARGET_SIZE[1])
    parser.add_argument(
        "--fail-on-issues",
        action="store_true",
        help="Exit with code 1 if any issue is found.",
    )
    args = parser.parse_args()

    manifest = args.manifest or args.output_dir / "manifest.csv"
    report = args.report or args.output_dir / "verification.csv"
    target_size = (args.target_width, args.target_height)

    with manifest.open(newline="") as handle:
        rows = list(csv.DictReader(handle))

    verified = [
        verify_row(
            args.output_dir,
            index,
            row,
            require_fullhd=not args.native_only,
            require_crops=args.require_crops,
            target_size=target_size,
        )
        for index, row in enumerate(rows)
    ]

    duplicates = duplicate_paths(rows)
    if duplicates:
        for row in verified:
            row_duplicates = [
                row[field]
                for field in ("native_path", "fullhd_path", "crop_native_path", "crop_fullhd_path")
                if row.get(field) in duplicates
            ]
            if row_duplicates:
                current = row["issues"]
                duplicate_issue = "duplicate_output_path"
                row["issues"] = f"{current};{duplicate_issue}" if current else duplicate_issue

    report.parent.mkdir(parents=True, exist_ok=True)
    with report.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_FIELDNAMES)
        writer.writeheader()
        writer.writerows(verified)

    issue_rows = [row for row in verified if row["issues"]]
    mode_counts = Counter(row["decode_mode"] for row in verified)
    matched_count = sum(1 for row in verified if row["matched_texture_archives"])
    print(
        f"Verified {len(verified)} CDCACHE texture exports "
        f"({matched_count} linked to .tex archives): "
        + ", ".join(f"{mode}={count}" for mode, count in sorted(mode_counts.items()))
        + f"; {len(issue_rows)} entries with issues"
    )
    print(f"Report: {report}")

    if issue_rows:
        print("First issues:")
        for row in issue_rows[:10]:
            print(
                f"  row {row['row_index']} {row['base_name']} "
                f"{row['decode_mode']} {row['issues']}"
            )

    if args.fail_on_issues and issue_rows:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
