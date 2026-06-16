#!/usr/bin/env python3
"""Verify the CDCACHE Full HD asset pack manifest and symlink targets."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

from PIL import Image


TARGET_SIZE = (1920, 1080)

REPORT_FIELDNAMES = [
    "row_index",
    "asset_id",
    "asset_kind",
    "linked_to_tex",
    "source_actual_width",
    "source_actual_height",
    "source_mode",
    "source_has_transparency",
    "all_pack_is_symlink",
    "all_pack_target_matches_source",
    "linked_pack_is_symlink",
    "linked_pack_target_matches_source",
    "source_fullhd_path",
    "all_pack_path",
    "linked_pack_path",
    "issues",
]

SUMMARY_FIELDNAMES = [
    "group",
    "rows",
    "linked_to_tex",
    "source_files",
    "all_pack_files",
    "linked_pack_files",
    "transparent_sources",
    "issue_rows",
    "modes",
]


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def resolve_path(raw: str, pack_dir: Path) -> Path | None:
    if not raw:
        return None
    path = Path(raw)
    if path.is_absolute() or path.exists():
        return path
    return pack_dir / path


def read_image_info(path: Path | None, issues: list[str]) -> tuple[int, int, str, bool]:
    if path is None:
        issues.append("missing_source_path")
        return 0, 0, "", False
    if not path.exists():
        issues.append("source_file_not_found")
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
        issues.append(f"source_image_open_failed:{exc}")
        return 0, 0, "", False


def symlink_matches(path: Path | None, source: Path | None, issues: list[str], label: str) -> tuple[bool, bool]:
    if path is None:
        issues.append(f"missing_{label}_path")
        return False, False
    if not path.exists():
        issues.append(f"{label}_file_not_found")
        return path.is_symlink(), False
    is_symlink = path.is_symlink()
    if not is_symlink:
        issues.append(f"{label}_not_symlink")
    target_matches = False
    if source is not None and source.exists():
        try:
            target_matches = path.resolve() == source.resolve()
        except OSError as exc:
            issues.append(f"{label}_resolve_failed:{exc}")
    if not target_matches:
        issues.append(f"{label}_target_mismatch")
    return is_symlink, target_matches


def verify_row(
    pack_dir: Path,
    row_index: int,
    row: dict[str, str],
    seen_asset_ids: set[str],
) -> dict[str, str]:
    issues: list[str] = []
    asset_id = row.get("asset_id", "")
    asset_kind = row.get("asset_kind", "")
    linked_to_tex = row.get("linked_to_tex", "")
    is_linked = parse_bool(linked_to_tex)

    if not asset_id:
        issues.append("missing_asset_id")
    elif asset_id in seen_asset_ids:
        issues.append("duplicate_asset_id")
    seen_asset_ids.add(asset_id)

    if asset_kind not in {"descriptor", "tile"}:
        issues.append("invalid_asset_kind")

    matched_archives = row.get("matched_texture_archives", "")
    linked_path_raw = row.get("linked_pack_path", "")
    if is_linked and not matched_archives:
        issues.append("linked_without_archives")
    if not is_linked and matched_archives:
        issues.append("archives_without_linked_flag")
    if is_linked and not linked_path_raw:
        issues.append("linked_without_link_path")
    if not is_linked and linked_path_raw:
        issues.append("unlinked_with_link_path")

    source_path = resolve_path(row.get("source_fullhd_path", ""), pack_dir)
    all_pack_path = resolve_path(row.get("all_pack_path", ""), pack_dir)
    linked_pack_path = resolve_path(linked_path_raw, pack_dir)

    width, height, mode, has_transparency = read_image_info(source_path, issues)
    if (width, height) != TARGET_SIZE:
        issues.append("source_not_fullhd")
    if row.get("image_mode") and mode and row["image_mode"] != mode:
        issues.append("manifest_image_mode_mismatch")
    if row.get("has_transparency") and parse_bool(row["has_transparency"]) != has_transparency:
        issues.append("manifest_transparency_mismatch")
    if row.get("source_exists") and parse_bool(row["source_exists"]) != (
        source_path is not None and source_path.exists()
    ):
        issues.append("manifest_source_exists_mismatch")

    all_is_symlink, all_target_matches = symlink_matches(
        all_pack_path,
        source_path,
        issues,
        "all_pack",
    )
    if row.get("all_pack_exists") and parse_bool(row["all_pack_exists"]) != (
        all_pack_path is not None and all_pack_path.exists()
    ):
        issues.append("manifest_all_pack_exists_mismatch")

    linked_is_symlink = False
    linked_target_matches = False
    if is_linked or linked_pack_path is not None:
        linked_is_symlink, linked_target_matches = symlink_matches(
            linked_pack_path,
            source_path,
            issues,
            "linked_pack",
        )
        if row.get("linked_pack_exists") and parse_bool(row["linked_pack_exists"]) != (
            linked_pack_path is not None and linked_pack_path.exists()
        ):
            issues.append("manifest_linked_pack_exists_mismatch")

    return {
        "row_index": str(row_index),
        "asset_id": asset_id,
        "asset_kind": asset_kind,
        "linked_to_tex": linked_to_tex,
        "source_actual_width": str(width),
        "source_actual_height": str(height),
        "source_mode": mode,
        "source_has_transparency": str(has_transparency),
        "all_pack_is_symlink": str(all_is_symlink),
        "all_pack_target_matches_source": str(all_target_matches),
        "linked_pack_is_symlink": str(linked_is_symlink),
        "linked_pack_target_matches_source": str(linked_target_matches),
        "source_fullhd_path": "" if source_path is None else str(source_path),
        "all_pack_path": "" if all_pack_path is None else str(all_pack_path),
        "linked_pack_path": "" if linked_pack_path is None else str(linked_pack_path),
        "issues": ";".join(issues),
    }


def write_summary(path: Path, rows: list[dict[str, str]]) -> None:
    groups: dict[str, list[dict[str, str]]] = {
        "descriptor": [row for row in rows if row["asset_kind"] == "descriptor"],
        "tile": [row for row in rows if row["asset_kind"] == "tile"],
        "total": rows,
    }
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDNAMES)
        writer.writeheader()
        for group in ("descriptor", "tile", "total"):
            group_rows = groups[group]
            modes = Counter(row["source_mode"] for row in group_rows if row["source_mode"])
            writer.writerow(
                {
                    "group": group,
                    "rows": str(len(group_rows)),
                    "linked_to_tex": str(
                        sum(1 for row in group_rows if parse_bool(row["linked_to_tex"]))
                    ),
                    "source_files": str(
                        sum(1 for row in group_rows if Path(row["source_fullhd_path"]).exists())
                    ),
                    "all_pack_files": str(
                        sum(1 for row in group_rows if Path(row["all_pack_path"]).exists())
                    ),
                    "linked_pack_files": str(
                        sum(
                            1
                            for row in group_rows
                            if row["linked_pack_path"]
                            and Path(row["linked_pack_path"]).exists()
                        )
                    ),
                    "transparent_sources": str(
                        sum(1 for row in group_rows if row["source_has_transparency"] == "True")
                    ),
                    "issue_rows": str(sum(1 for row in group_rows if row["issues"])),
                    "modes": ";".join(f"{mode}:{count}" for mode, count in sorted(modes.items())),
                }
            )


def verify_contact_sheets(pack_dir: Path, required: bool) -> list[str]:
    issues: list[str] = []
    expected = [
        "contact_sheet_all_descriptors.png",
        "contact_sheet_linked_descriptors.png",
        "contact_sheet_linked_tiles.png",
    ]
    for name in expected:
        path = pack_dir / name
        if not path.exists():
            if required:
                issues.append(f"missing_contact_sheet:{name}")
            continue
        try:
            with Image.open(path) as image:
                if image.width <= 0 or image.height <= 0:
                    issues.append(f"invalid_contact_sheet_dimensions:{name}")
        except Exception as exc:
            issues.append(f"contact_sheet_open_failed:{name}:{exc}")
    return issues


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a CDCACHE HD asset pack.")
    parser.add_argument("pack_dir", type=Path)
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Manifest CSV to read. Defaults to PACK_DIR/manifest.csv.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Write per-entry verification CSV. Defaults to PACK_DIR/verification.csv.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        help="Write verification summary CSV. Defaults to PACK_DIR/verification_summary.csv.",
    )
    parser.add_argument("--require-contact-sheets", action="store_true")
    parser.add_argument("--fail-on-issues", action="store_true")
    args = parser.parse_args()

    manifest = args.manifest or args.pack_dir / "manifest.csv"
    report = args.report or args.pack_dir / "verification.csv"
    summary = args.summary or args.pack_dir / "verification_summary.csv"

    with manifest.open(newline="") as handle:
        source_rows = list(csv.DictReader(handle))

    seen_asset_ids: set[str] = set()
    verified = [
        verify_row(args.pack_dir, index, row, seen_asset_ids)
        for index, row in enumerate(source_rows)
    ]

    contact_sheet_issues = verify_contact_sheets(args.pack_dir, args.require_contact_sheets)
    if contact_sheet_issues:
        verified.append(
            {
                "row_index": "contact_sheets",
                "asset_id": "",
                "asset_kind": "",
                "linked_to_tex": "",
                "source_actual_width": "0",
                "source_actual_height": "0",
                "source_mode": "",
                "source_has_transparency": "False",
                "all_pack_is_symlink": "False",
                "all_pack_target_matches_source": "False",
                "linked_pack_is_symlink": "False",
                "linked_pack_target_matches_source": "False",
                "source_fullhd_path": "",
                "all_pack_path": "",
                "linked_pack_path": "",
                "issues": ";".join(contact_sheet_issues),
            }
        )

    report.parent.mkdir(parents=True, exist_ok=True)
    with report.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_FIELDNAMES)
        writer.writeheader()
        writer.writerows(verified)
    write_summary(summary, verified)

    issue_rows = [row for row in verified if row["issues"]]
    linked_count = sum(1 for row in verified if parse_bool(row["linked_to_tex"]))
    print(
        f"Verified {len(source_rows)} CDCACHE HD pack assets "
        f"({linked_count} linked to .tex archives); "
        f"{len(issue_rows)} entries with issues"
    )
    print(f"Report: {report}")
    print(f"Summary: {summary}")
    if issue_rows:
        print("First issues:")
        for row in issue_rows[:10]:
            print(f"  row {row['row_index']} {row['asset_id']} {row['issues']}")

    if args.fail_on_issues and issue_rows:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
