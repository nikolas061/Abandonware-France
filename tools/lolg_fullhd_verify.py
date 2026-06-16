#!/usr/bin/env python3
"""Verify still-image Full HD exports against their manifest."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

from PIL import Image


REPORT_FIELDNAMES = [
    "source_type",
    "source_path",
    "archive",
    "index",
    "file_id",
    "source_width",
    "source_height",
    "expected_width",
    "expected_height",
    "actual_width",
    "actual_height",
    "output_path",
    "issues",
]


def parse_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def resolve_output_path(output_dir: Path, raw: str) -> Path | None:
    if not raw:
        return None
    path = Path(raw)
    if path.is_absolute() or path.exists():
        return path
    return output_dir / path.name


def verify_row(output_dir: Path, row: dict[str, str]) -> dict[str, str]:
    issues: list[str] = []
    output_path = resolve_output_path(output_dir, row.get("output_path", ""))
    expected_width = parse_int(row.get("output_width"))
    expected_height = parse_int(row.get("output_height"))
    actual_width = 0
    actual_height = 0

    if output_path is None:
        issues.append("missing_output_path")
    elif not output_path.exists():
        issues.append("output_file_not_found")
    else:
        try:
            with Image.open(output_path) as image:
                actual_width, actual_height = image.size
        except Exception as exc:
            issues.append(f"output_image_open_failed:{exc}")

    if expected_width is None or expected_height is None:
        issues.append("missing_expected_dimensions")
    elif actual_width and actual_height and (actual_width, actual_height) != (expected_width, expected_height):
        issues.append("output_dimensions_mismatch")

    return {
        "source_type": row.get("source_type", ""),
        "source_path": row.get("source_path", ""),
        "archive": row.get("archive", ""),
        "index": row.get("index", ""),
        "file_id": row.get("file_id", ""),
        "source_width": row.get("source_width", ""),
        "source_height": row.get("source_height", ""),
        "expected_width": "" if expected_width is None else str(expected_width),
        "expected_height": "" if expected_height is None else str(expected_height),
        "actual_width": str(actual_width),
        "actual_height": str(actual_height),
        "output_path": "" if output_path is None else str(output_path),
        "issues": ";".join(issues),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a still-image Full HD export directory.")
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
    parser.add_argument(
        "--fail-on-issues",
        action="store_true",
        help="Exit with code 1 if any issue is found.",
    )
    args = parser.parse_args()

    manifest = args.manifest or args.output_dir / "manifest.csv"
    report = args.report or args.output_dir / "verification.csv"

    with manifest.open(newline="") as handle:
        rows = list(csv.DictReader(handle))

    verified = [verify_row(args.output_dir, row) for row in rows]
    report.parent.mkdir(parents=True, exist_ok=True)
    with report.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_FIELDNAMES)
        writer.writeheader()
        writer.writerows(verified)

    issue_rows = [row for row in verified if row["issues"]]
    source_type_counts = Counter(row["source_type"] for row in verified)
    print(
        f"Verified {len(verified)} Full HD still-image exports: "
        + ", ".join(f"{source_type}={count}" for source_type, count in sorted(source_type_counts.items()))
        + f"; {len(issue_rows)} entries with issues"
    )
    print(f"Report: {report}")

    if issue_rows:
        print("First issues:")
        for row in issue_rows[:10]:
            label = f"{Path(row['source_path']).name}:{row['index'] or row['file_id']}"
            print(f"  {label} {row['issues']}")

    if args.fail_on_issues and issue_rows:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
