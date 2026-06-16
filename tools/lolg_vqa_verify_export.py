#!/usr/bin/env python3
"""Verify VQA batch export frame counts against the batch manifest."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path


REPORT_FIELDNAMES = [
    "archive",
    "index",
    "file_id",
    "declared_frames",
    "status",
    "native_frames",
    "fullhd_frames",
    "expected_frames",
    "render_rows",
    "rendered_rows",
    "held_frame_rows",
    "non_output_rows",
    "missing_native_output_rows",
    "missing_fullhd_output_rows",
    "missing_native_output_files",
    "missing_fullhd_output_files",
    "duplicate_frame_rows",
    "missing_frame_rows",
    "render_status_counts",
    "output_dir",
    "issues",
]


def parse_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def count_pngs(path: Path) -> int:
    return sum(1 for _ in path.glob("*.png")) if path.exists() else 0


def format_status_counts(counts: Counter[str]) -> str:
    return ";".join(f"{status}:{count}" for status, count in sorted(counts.items()))


def resolve_output_dir(batch_dir: Path, row: dict[str, str]) -> Path | None:
    raw = row.get("output_dir", "")
    if not raw:
        return None
    path = Path(raw)
    if path.is_absolute():
        return path
    if path.exists():
        return path
    return batch_dir / path.name


def resolve_reported_path(output_dir: Path, raw: str) -> Path | None:
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


def verify_row(
    batch_dir: Path,
    row: dict[str, str],
    *,
    expect_all: bool,
    require_fullhd: bool,
) -> dict[str, str]:
    issues: list[str] = []
    output_dir = resolve_output_dir(batch_dir, row)
    declared_frames = parse_int(row.get("declared_frames"))
    expected_frames = declared_frames if expect_all else None
    native_frames = 0
    fullhd_frames = 0
    render_rows = 0
    rendered_rows = 0
    held_frame_rows = 0
    non_output_rows = 0
    missing_native_output_rows = 0
    missing_fullhd_output_rows = 0
    missing_native_output_files = 0
    missing_fullhd_output_files = 0
    duplicate_frame_rows = 0
    missing_frame_rows = 0
    render_status_counts: Counter[str] = Counter()

    if row.get("status") == "error":
        issues.append("batch_error")

    if output_dir is None:
        issues.append("missing_output_dir")
    elif not output_dir.exists():
        issues.append("output_dir_not_found")
    else:
        native_frames = count_pngs(output_dir / "frames_native")
        fullhd_frames = count_pngs(output_dir / "frames_fullhd")
        render_manifest = output_dir / "rendered_frames.csv"

        if native_frames == 0:
            issues.append("no_native_frames")
        if require_fullhd and fullhd_frames == 0:
            issues.append("no_fullhd_frames")
        if require_fullhd and native_frames != fullhd_frames:
            issues.append("native_fullhd_mismatch")
        if expected_frames is not None and native_frames != expected_frames:
            issues.append("native_count_differs_from_declared")
        if require_fullhd and expected_frames is not None and fullhd_frames != expected_frames:
            issues.append("fullhd_count_differs_from_declared")

        if not render_manifest.exists():
            issues.append("missing_render_manifest")
        else:
            with render_manifest.open(newline="") as handle:
                render_manifest_rows = list(csv.DictReader(handle))
            render_rows = len(render_manifest_rows)
            frame_numbers: list[int] = []

            for render_row in render_manifest_rows:
                status = render_row.get("status", "")
                render_status_counts[status] += 1
                if status == "rendered":
                    rendered_rows += 1
                elif status == "held_frame":
                    held_frame_rows += 1
                else:
                    non_output_rows += 1

                frame_number = parse_int(render_row.get("frame"))
                if frame_number is not None:
                    frame_numbers.append(frame_number)

                produces_output = status in {"rendered", "held_frame"}
                if produces_output:
                    native_output = resolve_reported_path(output_dir, render_row.get("native_output", ""))
                    fullhd_output = resolve_reported_path(output_dir, render_row.get("fullhd_output", ""))
                    if native_output is None:
                        missing_native_output_rows += 1
                    elif not native_output.exists():
                        missing_native_output_files += 1
                    if require_fullhd:
                        if fullhd_output is None:
                            missing_fullhd_output_rows += 1
                        elif not fullhd_output.exists():
                            missing_fullhd_output_files += 1

            duplicate_frame_rows = len(frame_numbers) - len(set(frame_numbers))
            if expected_frames is not None:
                expected_numbers = set(range(expected_frames))
                missing_frame_rows = len(expected_numbers - set(frame_numbers))
                if render_rows != expected_frames:
                    issues.append("render_row_count_differs_from_declared")
                if missing_frame_rows or duplicate_frame_rows:
                    issues.append("render_frame_indices_incomplete")

            if non_output_rows:
                issues.append("render_rows_without_png_output")
            if missing_native_output_rows:
                issues.append("missing_native_output_paths")
            if require_fullhd and missing_fullhd_output_rows:
                issues.append("missing_fullhd_output_paths")
            if missing_native_output_files:
                issues.append("missing_native_output_files")
            if require_fullhd and missing_fullhd_output_files:
                issues.append("missing_fullhd_output_files")

    return {
        "archive": row.get("archive", ""),
        "index": row.get("index", ""),
        "file_id": row.get("file_id", ""),
        "declared_frames": "" if declared_frames is None else str(declared_frames),
        "status": row.get("status", ""),
        "native_frames": str(native_frames),
        "fullhd_frames": str(fullhd_frames),
        "expected_frames": "" if expected_frames is None else str(expected_frames),
        "render_rows": str(render_rows),
        "rendered_rows": str(rendered_rows),
        "held_frame_rows": str(held_frame_rows),
        "non_output_rows": str(non_output_rows),
        "missing_native_output_rows": str(missing_native_output_rows),
        "missing_fullhd_output_rows": str(missing_fullhd_output_rows),
        "missing_native_output_files": str(missing_native_output_files),
        "missing_fullhd_output_files": str(missing_fullhd_output_files),
        "duplicate_frame_rows": str(duplicate_frame_rows),
        "missing_frame_rows": str(missing_frame_rows),
        "render_status_counts": format_status_counts(render_status_counts),
        "output_dir": "" if output_dir is None else str(output_dir),
        "issues": ";".join(issues),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a VQA batch export directory.")
    parser.add_argument("batch_dir", type=Path)
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Manifest CSV to read. Defaults to BATCH_DIR/manifest.csv.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Write per-entry verification CSV. Defaults to BATCH_DIR/verification.csv.",
    )
    parser.add_argument(
        "--expect-all",
        action="store_true",
        help="Require PNG counts to match the declared frame count from the manifest.",
    )
    parser.add_argument(
        "--native-only",
        action="store_true",
        help="Do not require matching Full HD PNGs.",
    )
    parser.add_argument(
        "--fail-on-issues",
        action="store_true",
        help="Exit with code 1 if any issue is found.",
    )
    args = parser.parse_args()

    manifest = args.manifest or args.batch_dir / "manifest.csv"
    report = args.report or args.batch_dir / "verification.csv"

    with manifest.open(newline="") as handle:
        rows = list(csv.DictReader(handle))

    verified = [
        verify_row(
            args.batch_dir,
            row,
            expect_all=args.expect_all,
            require_fullhd=not args.native_only,
        )
        for row in rows
    ]

    report.parent.mkdir(parents=True, exist_ok=True)
    with report.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_FIELDNAMES)
        writer.writeheader()
        writer.writerows(verified)

    issue_rows = [row for row in verified if row["issues"]]
    native_total = sum(parse_int(row["native_frames"]) or 0 for row in verified)
    fullhd_total = sum(parse_int(row["fullhd_frames"]) or 0 for row in verified)
    render_row_total = sum(parse_int(row["render_rows"]) or 0 for row in verified)
    held_frame_total = sum(parse_int(row["held_frame_rows"]) or 0 for row in verified)
    non_output_total = sum(parse_int(row["non_output_rows"]) or 0 for row in verified)

    print(
        f"Verified {len(verified)} entries: "
        f"{native_total} native PNGs, {fullhd_total} Full HD PNGs, "
        f"{render_row_total} render rows, {held_frame_total} held frames, "
        f"{non_output_total} non-output rows, {len(issue_rows)} entries with issues"
    )
    print(f"Report: {report}")

    if issue_rows:
        print("First issues:")
        for row in issue_rows[:10]:
            label = f"{Path(row['archive']).name}#{row['index']}:{row['file_id']}"
            print(f"  {label} {row['issues']}")

    if args.fail_on_issues and issue_rows:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
