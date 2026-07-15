#!/usr/bin/env python3
"""Check whether the current Full HD runtime package is launch-ready."""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import html
import io
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path


DEFAULT_OUTPUT = Path("output/hd_release_check")
DEFAULT_VQA_PACK_SUMMARY = Path("output/vqa_runtime_pack_build/summary.csv")
DEFAULT_AUDIT_SUMMARY = Path("output/fullhd_audit/summary.csv")
DEFAULT_OVERSIZE_SUMMARY = Path("output/vqa_runtime_oversize_budget/summary.csv")
DEFAULT_LCW_PROBE_SUMMARY = Path("output/vqa_lcw_literal_probe/summary.csv")
DEFAULT_WINE_SMOKE_SUMMARY = Path("output/hd_wine_smoke_test/summary.csv")
DEFAULT_WINE_SMOKE_1280_SUMMARY = Path("output/hd_wine_smoke_test_1280x1024/summary.csv")
DEFAULT_WINE_STAGE = Path("output/lolg95_fullhd_wine_runtime/WESTWOOD/LOLG")
DEFAULT_WINEPREFIX = Path("output/lolg95_fullhd_wine_prefix")

CHECK_FIELDS = ["check", "status", "evidence", "next_step"]
SUMMARY_FIELDS = [
    "status",
    "checks",
    "passed",
    "gaps",
    "info",
    "output",
    "issues",
    "next_step",
]

BANNED_WINE_STAGE_FILES = {
    "ddraw.dll",
    "d3dimm.dll",
    "d3d8.dll",
    "dgvoodoo.conf",
    "dgvoodoocpl.exe",
}
EXPECTED_ORIGINAL_STAGE_MIX = {"LOCALLNG.MIX", "MOVIES.MIX"}


def read_csv_first(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return rows[0] if rows else {}


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_csv_fieldnames(path: Path) -> list[str]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or [])


def read_key_value_text(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def as_int(row: dict[str, str], key: str) -> int:
    try:
        return int(row.get(key, ""))
    except ValueError:
        return -1


def pass_if(condition: bool) -> str:
    return "pass" if condition else "gap"


def csv_duplicate_fieldnames(fieldnames: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for field in fieldnames:
        if field in seen and field not in duplicates:
            duplicates.append(field)
        seen.add(field)
    return duplicates


def add_check(
    rows: list[dict[str, str]],
    check: str,
    status: str,
    evidence: str,
    next_step: str,
) -> None:
    rows.append(
        {
            "check": check,
            "status": status,
            "evidence": evidence,
            "next_step": next_step,
        }
    )


def parse_user_reg_section(path: Path, section: str) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    in_section = False
    header = f"[{section}]"
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if line.startswith("["):
            in_section = line.startswith(header)
            continue
        if not in_section or not line.startswith('"') or '"="' not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip('"')] = value.strip().strip('"')
    return values


def shell_check(command: list[str], cwd: Path) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            check=False,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"{type(exc).__name__}:{exc}"
    detail = (result.stdout + result.stderr).strip().replace("\n", " | ")
    return result.returncode == 0, detail


def copy_archive_external_files(
    target_dir: Path,
    archive: Path,
    checksum: Path,
    archive_summary: Path,
    verify_script: Path,
    artifacts: Path,
) -> None:
    for source in (archive, checksum, archive_summary, verify_script, artifacts):
        shutil.copy2(source, target_dir / source.name)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def refresh_archive_companions(
    archive: Path,
    checksum: Path,
    archive_summary: Path,
    verify_script: Path,
    artifacts: Path,
) -> None:
    archive_sha256 = sha256_file(archive)
    checksum.write_text(f"{archive_sha256}  {archive.name}\n", encoding="utf-8")

    summary_lines = archive_summary.read_text(encoding="utf-8", errors="replace").splitlines()
    summary_rewrites = {
        "archive_size": str(archive.stat().st_size),
        "sha256": archive_sha256,
        "sha256_file": checksum.name,
    }
    rewritten_summary = []
    for line in summary_lines:
        key = line.split("=", 1)[0] if "=" in line else ""
        rewritten_summary.append(f"{key}={summary_rewrites[key]}" if key in summary_rewrites else line)
    archive_summary.write_text("\n".join(rewritten_summary) + "\n", encoding="utf-8")

    artifact_paths = {
        archive.name: archive,
        checksum.name: checksum,
        archive_summary.name: archive_summary,
        verify_script.name: verify_script,
    }
    with artifacts.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    for row in rows:
        path = artifact_paths.get(row.get("path", ""))
        if path is None:
            continue
        row["size"] = str(path.stat().st_size)
        row["sha256"] = sha256_file(path)
        row["executable"] = "1" if path.stat().st_mode & 0o111 else "0"
    with artifacts.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_consistent_unsafe_archive(
    archive: Path,
    checksum: Path,
    archive_summary: Path,
    verify_script: Path,
    artifacts: Path,
) -> None:
    rewritten = archive.with_name(archive.name + ".unsafe")
    with tarfile.open(archive, "r:gz") as source, tarfile.open(rewritten, "w:gz") as target:
        for member in source.getmembers():
            fileobj = source.extractfile(member) if member.isfile() else None
            target.addfile(member, fileobj)
        payload = b"unsafe tar path\n"
        unsafe_member = tarfile.TarInfo("../unsafe.txt")
        unsafe_member.size = len(payload)
        target.addfile(unsafe_member, io.BytesIO(payload))
    rewritten.replace(archive)

    refresh_archive_companions(archive, checksum, archive_summary, verify_script, artifacts)


def write_consistent_unsupported_archive(
    archive: Path,
    checksum: Path,
    archive_summary: Path,
    verify_script: Path,
    artifacts: Path,
) -> None:
    rewritten = archive.with_name(archive.name + ".unsupported")
    with tarfile.open(archive, "r:gz") as source, tarfile.open(rewritten, "w:gz") as target:
        members = source.getmembers()
        top_level = members[0].name.split("/", 1)[0] if members else "hd_support_bundle"
        for member in members:
            fileobj = source.extractfile(member) if member.isfile() else None
            target.addfile(member, fileobj)
        unsupported_member = tarfile.TarInfo(f"{top_level}/unsupported_link")
        unsupported_member.type = tarfile.SYMTYPE
        unsupported_member.linkname = "SUPPORT_SUMMARY.txt"
        target.addfile(unsupported_member)
    rewritten.replace(archive)

    refresh_archive_companions(archive, checksum, archive_summary, verify_script, artifacts)


def write_consistent_wrong_top_level_archive(
    archive: Path,
    checksum: Path,
    archive_summary: Path,
    verify_script: Path,
    artifacts: Path,
) -> None:
    rewritten = archive.with_name(archive.name + ".wrongtop")
    wrong_top_level = "wrong_support_bundle"
    with tarfile.open(archive, "r:gz") as source, tarfile.open(rewritten, "w:gz") as target:
        members = source.getmembers()
        top_level = members[0].name.split("/", 1)[0] if members else "hd_support_bundle"
        for member in members:
            new_member = copy.copy(member)
            if member.name == top_level:
                new_member.name = wrong_top_level
            elif member.name.startswith(f"{top_level}/"):
                new_member.name = wrong_top_level + member.name[len(top_level):]
            fileobj = source.extractfile(member) if member.isfile() else None
            target.addfile(new_member, fileobj)
    rewritten.replace(archive)

    refresh_archive_companions(archive, checksum, archive_summary, verify_script, artifacts)


def write_consistent_multi_top_level_archive(
    archive: Path,
    checksum: Path,
    archive_summary: Path,
    verify_script: Path,
    artifacts: Path,
) -> None:
    rewritten = archive.with_name(archive.name + ".multitop")
    with tarfile.open(archive, "r:gz") as source, tarfile.open(rewritten, "w:gz") as target:
        for member in source.getmembers():
            fileobj = source.extractfile(member) if member.isfile() else None
            target.addfile(member, fileobj)
        payload = b"second top level\n"
        extra_member = tarfile.TarInfo("second_support_bundle/extra.txt")
        extra_member.size = len(payload)
        target.addfile(extra_member, io.BytesIO(payload))
    rewritten.replace(archive)

    refresh_archive_companions(archive, checksum, archive_summary, verify_script, artifacts)


def write_consistent_empty_archive(
    archive: Path,
    checksum: Path,
    archive_summary: Path,
    verify_script: Path,
    artifacts: Path,
) -> None:
    rewritten = archive.with_name(archive.name + ".empty")
    with tarfile.open(rewritten, "w:gz"):
        pass
    rewritten.replace(archive)

    refresh_archive_companions(archive, checksum, archive_summary, verify_script, artifacts)


def write_row_width_broken_artifacts(source: Path, target: Path) -> None:
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    with target.open("w", encoding="utf-8", newline="") as handle:
        for index, line in enumerate(lines):
            if index == 0:
                handle.write(f"{line}\n")
            else:
                handle.write(f"{line},bad\n")


def write_extra_field_artifacts(source: Path, target: Path) -> None:
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    if "extra" not in fieldnames:
        fieldnames.append("extra")
    for row in rows:
        row["extra"] = "bad"
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_duplicate_field_artifacts(source: Path, target: Path) -> None:
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    with target.open("w", encoding="utf-8", newline="") as handle:
        for index, line in enumerate(lines):
            if index == 0:
                handle.write(f"{line},path\n")
            else:
                handle.write(f"{line},duplicate\n")


def write_duplicate_path_artifacts(source: Path, target: Path) -> None:
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    if rows:
        rows.append(dict(rows[0]))
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_missing_field_artifacts(source: Path, target: Path) -> None:
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = [field for field in (reader.fieldnames or []) if field != "sha256"]
    for row in rows:
        row.pop("sha256", None)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_missing_row_artifacts(source: Path, target: Path) -> None:
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    rows = rows[:-1]
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_bad_artifact_size(source: Path, target: Path, artifact_name: str) -> None:
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    for row in rows:
        if row.get("path") == artifact_name:
            row["size"] = "0" if row.get("size") != "0" else "1"
            break
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_invalid_artifact_fields(source: Path, target: Path, artifact_name: str) -> None:
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    for row in rows:
        if row.get("path") == artifact_name:
            row["size"] = "bad-size"
            row["sha256"] = "bad-sha256"
            row["executable"] = "bad-exec"
            break
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_bad_artifact_sha256(source: Path, target: Path, artifact_name: str) -> None:
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    for row in rows:
        if row.get("path") == artifact_name:
            row["sha256"] = "0" * 64
            break
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_bad_artifact_executable(source: Path, target: Path, artifact_name: str) -> None:
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    for row in rows:
        if row.get("path") == artifact_name:
            row["executable"] = "0" if row.get("executable") != "0" else "1"
            break
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_bad_artifact_path(source: Path, target: Path, artifact_name: str) -> None:
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    for row in rows:
        if row.get("path") == artifact_name:
            row["path"] = "wrong_artifact.bin"
            break
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_unsafe_artifact_path(source: Path, target: Path, artifact_name: str) -> None:
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    for row in rows:
        if row.get("path") == artifact_name:
            row["path"] = "../bad.tar.gz"
            break
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_nonportable_artifact_path(source: Path, target: Path, artifact_name: str) -> None:
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    for row in rows:
        if row.get("path") == artifact_name:
            row["path"] = "bad artifact.tar.gz"
            break
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_extra_key_summary(source: Path) -> None:
    text = source.read_text(encoding="utf-8", errors="replace")
    source.write_text(text.rstrip("\n") + "\nunexpected_key=bad\n", encoding="utf-8")


def write_duplicate_key_summary(source: Path) -> None:
    text = source.read_text(encoding="utf-8", errors="replace")
    source.write_text(text.rstrip("\n") + "\narchive=duplicate.tar.gz\n", encoding="utf-8")


def write_malformed_line_summary(source: Path) -> None:
    text = source.read_text(encoding="utf-8", errors="replace")
    source.write_text(text.rstrip("\n") + "\nmalformed-summary-line\n", encoding="utf-8")


def write_bad_version_summary(source: Path) -> None:
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    changed = [
        "support_archive_summary_version=2"
        if line.startswith("support_archive_summary_version=")
        else line
        for line in lines
    ]
    source.write_text("\n".join(changed) + "\n", encoding="utf-8")


def write_missing_key_summary(source: Path) -> None:
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    kept = [line for line in lines if not line.startswith("bundle_dir=")]
    source.write_text("\n".join(kept) + "\n", encoding="utf-8")


def write_bad_timestamp_summary(source: Path) -> None:
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    changed = [
        "generated_utc=bad-time" if line.startswith("generated_utc=") else line
        for line in lines
    ]
    source.write_text("\n".join(changed) + "\n", encoding="utf-8")


def write_bad_archive_name_summary(source: Path) -> None:
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    changed = [
        "archive=wrong_archive.tar.gz" if line.startswith("archive=") else line
        for line in lines
    ]
    source.write_text("\n".join(changed) + "\n", encoding="utf-8")


def write_bad_archive_size_summary(source: Path) -> None:
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    changed = [
        "archive_size=0" if line.startswith("archive_size=") else line
        for line in lines
    ]
    source.write_text("\n".join(changed) + "\n", encoding="utf-8")


def write_bad_archive_sha256_summary(source: Path) -> None:
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    changed = [
        f"sha256={'0' * 64}" if line.startswith("sha256=") else line
        for line in lines
    ]
    source.write_text("\n".join(changed) + "\n", encoding="utf-8")


def write_bad_archive_sha256_file_summary(source: Path) -> None:
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    changed = [
        "sha256_file=wrong.sha256" if line.startswith("sha256_file=") else line
        for line in lines
    ]
    source.write_text("\n".join(changed) + "\n", encoding="utf-8")


def write_bad_archive_bundle_dir_summary(source: Path) -> None:
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    changed = [
        "bundle_dir=wrong_bundle" if line.startswith("bundle_dir=") else line
        for line in lines
    ]
    source.write_text("\n".join(changed) + "\n", encoding="utf-8")


def write_bad_checksum(source: Path, archive_name: str) -> None:
    source.write_text(f"{'0' * 64}  {archive_name}\n", encoding="utf-8")


def write_bad_checksum_archive_name(source: Path) -> None:
    parts = source.read_text(encoding="utf-8", errors="replace").strip().split()
    digest = parts[0] if parts else "0" * 64
    source.write_text(f"{digest}  wrong_archive.tar.gz\n", encoding="utf-8")


def write_checksum_archive_path(source: Path, archive_name: str) -> None:
    parts = source.read_text(encoding="utf-8", errors="replace").strip().split()
    digest = parts[0] if parts else "0" * 64
    source.write_text(f"{digest}  subdir/{archive_name}\n", encoding="utf-8")


def write_bad_checksum_format(source: Path, archive_name: str) -> None:
    source.write_text(f"not-a-sha256  {archive_name}\n", encoding="utf-8")


def write_extra_checksum_field(source: Path) -> None:
    text = source.read_text(encoding="utf-8", errors="replace").strip()
    source.write_text(f"{text} unexpected-field\n", encoding="utf-8")


def write_extra_checksum_line(source: Path, archive_name: str) -> None:
    text = source.read_text(encoding="utf-8", errors="replace").rstrip("\n")
    source.write_text(f"{text}\n{'0' * 64}  {archive_name}\n", encoding="utf-8")


def write_row_width_broken_manifest(source: Path) -> None:
    lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
    with source.open("w", encoding="utf-8", newline="") as handle:
        for index, line in enumerate(lines):
            if index == 0:
                handle.write(f"{line}\n")
            else:
                handle.write(f"{line},bad\n")


def write_extra_field_manifest(source: Path) -> None:
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    if "extra" not in fieldnames:
        fieldnames.append("extra")
    for row in rows:
        row["extra"] = "bad"
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_duplicate_field_manifest(source: Path) -> None:
    with source.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    if not rows:
        return
    header = rows[0]
    try:
        path_index = header.index("path")
    except ValueError:
        path_index = 0
    rewritten_rows = [header + ["path"]]
    for row in rows[1:]:
        duplicated_path = row[path_index] if path_index < len(row) else ""
        rewritten_rows.append(row + [duplicated_path])
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerows(rewritten_rows)


def write_missing_field_manifest(source: Path) -> None:
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = [field for field in (reader.fieldnames or []) if field != "sha256"]
    for row in rows:
        row.pop("sha256", None)
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_unsafe_path_manifest(source: Path) -> None:
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    if rows:
        rows[0]["path"] = r"..\bad.txt"
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_noncanonical_path_manifest(source: Path) -> None:
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    if rows:
        rows[0]["path"] = "./" + rows[0].get("path", "")
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_invalid_size_sha_manifest(source: Path) -> None:
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    if rows:
        rows[0]["size"] = "bad-size"
        rows[0]["sha256"] = "bad-sha256"
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_size_mismatch_manifest(source: Path) -> None:
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    if rows:
        try:
            expected_size = int(rows[0].get("size", ""))
        except ValueError:
            expected_size = 0
        rows[0]["size"] = str(expected_size + 1)
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_sha256_mismatch_manifest(source: Path) -> None:
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    if rows:
        rows[0]["sha256"] = "0" * 64
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_invalid_executable_manifest(source: Path) -> None:
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    if rows:
        rows[0]["executable"] = "bad-exec"
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_executable_mismatch_manifest(source: Path) -> None:
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    for row in rows:
        if row.get("path") == "VERIFY_SUPPORT.sh":
            row["executable"] = "0"
            break
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_duplicate_path_manifest(source: Path) -> None:
    with source.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    if len(rows) <= 1:
        return
    rows.append(list(rows[1]))
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)


def write_png_entry_manifest(source: Path, bundle_root: Path) -> None:
    png_relative = "unexpected_probe.png"
    png_path = bundle_root / png_relative
    png_path.write_bytes(b"not a real png, but forbidden by support policy\n")
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    rows.append(
        {
            "path": png_relative,
            "size": str(png_path.stat().st_size),
            "sha256": sha256_file(png_path),
            "executable": "0",
        }
    )
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_not_file_manifest(source: Path, bundle_root: Path) -> None:
    directory_relative = "manifest_directory_probe"
    (bundle_root / directory_relative).mkdir(exist_ok=True)
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    rows.append(
        {
            "path": directory_relative,
            "size": "0",
            "sha256": "0" * 64,
            "executable": "0",
        }
    )
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_html(path: Path, summary: dict[str, str], checks: list[dict[str, str]]) -> None:
    rows_html = []
    for row in checks:
        cls = row["status"]
        rows_html.append(
            "<tr>"
            f"<td>{html.escape(row['check'])}</td>"
            f"<td class='{html.escape(cls)}'>{html.escape(row['status'])}</td>"
            f"<td>{html.escape(row['evidence'])}</td>"
            f"<td>{html.escape(row['next_step'])}</td>"
            "</tr>"
        )
    document = f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>LOLG HD Release Check</title>
<style>
body {{ font-family: sans-serif; margin: 2rem; background: #f7f7f5; color: #171717; }}
table {{ border-collapse: collapse; width: 100%; background: white; }}
th, td {{ border: 1px solid #d7d7d0; padding: 0.45rem 0.6rem; text-align: left; vertical-align: top; }}
th {{ background: #ecece6; }}
.pass {{ color: #106b2f; font-weight: 700; }}
.gap {{ color: #a22522; font-weight: 700; }}
.info {{ color: #555; font-weight: 700; }}
code {{ background: #eee; padding: 0.1rem 0.25rem; }}
</style>
<h1>LOLG HD Release Check</h1>
<p>Status: <strong class="{html.escape(summary['status'])}">{html.escape(summary['status'])}</strong></p>
<p>Checks: {html.escape(summary['passed'])} pass + {html.escape(summary['info'])} info /
{html.escape(summary['checks'])}, gaps={html.escape(summary['gaps'])}</p>
<table>
<thead><tr><th>Check</th><th>Status</th><th>Evidence</th><th>Next step</th></tr></thead>
<tbody>
{''.join(rows_html)}
</tbody>
</table>
</html>
"""
    path.write_text(document, encoding="utf-8")


def run_check(args: argparse.Namespace) -> dict[str, str]:
    root = Path.cwd()
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, str]] = []

    vqa_pack = read_csv_first(args.vqa_pack_summary)
    add_check(
        checks,
        "vqa_runtime_pack",
        (
            "info"
            if not vqa_pack
            else pass_if(
                vqa_pack.get("status") == "pass"
                and as_int(vqa_pack, "replacement_entries") == 1955
                and as_int(vqa_pack, "applied_replacements") == 1955
                and as_int(vqa_pack, "missing_replacements") == 0
                and as_int(vqa_pack, "deferred_replacements") == 0
                and as_int(vqa_pack, "output_archives") == 66
            )
        ),
        (
            f"status={vqa_pack.get('status', '')};"
            f"replacement_entries={vqa_pack.get('replacement_entries', '')};"
            f"applied={vqa_pack.get('applied_replacements', '')};"
            f"missing={vqa_pack.get('missing_replacements', '')};"
            f"deferred={vqa_pack.get('deferred_replacements', '')};"
            f"output_archives={vqa_pack.get('output_archives', '')}"
        ),
        "optional old full-pack report missing; current stage uses safevqa exclusions and sidecar for critical VQA",
    )

    audit = read_csv_first(args.audit_summary)
    add_check(
        checks,
        "fullhd_audit",
        "info" if not audit else pass_if(audit.get("status") == "pass" and as_int(audit, "failed") == 0),
        f"status={audit.get('status', '')};passed={audit.get('passed', '')};failed={audit.get('failed', '')}",
        "optional inventory audit missing; rerun tools/lolg_hd_audit.py when rebuilding assets",
    )

    git_audit_ok, git_audit_detail = shell_check(
        ["python3", "tools/lolg_hd_git_audit.py", "-o", "output/hd_git_audit_release_check"],
        root,
    )
    git_audit = read_csv_first(Path("output/hd_git_audit_release_check/summary.csv"))
    add_check(
        checks,
        "git_tracking_audit",
        pass_if(git_audit_ok and git_audit.get("status") == "pass" and as_int(git_audit, "gaps") == 0),
        (
            f"status={git_audit.get('status', '')};"
            f"required_tracked={git_audit.get('required_tracked', '')}/{git_audit.get('required_checked', '')};"
            f"heavy_ignored={git_audit.get('heavy_ignored', '')}/{git_audit.get('heavy_checked', '')};"
            f"gaps={git_audit.get('gaps', '')};"
            f"detail={git_audit_detail}"
        ),
        "./LOLG_HD.sh git-audit",
    )

    oversize = read_csv_first(args.oversize_summary)
    add_check(
        checks,
        "vqa_oversize_budget",
        (
            "info"
            if not oversize
            else pass_if(
                oversize.get("status") == "pass"
                and as_int(oversize, "oversize_archives") == 0
                and as_int(oversize, "deferred_replacements") == 0
                and as_int(oversize, "required_reduction_bytes") == 0
            )
        ),
        (
            f"status={oversize.get('status', '')};"
            f"oversize={oversize.get('oversize_archives', '')};"
            f"deferred={oversize.get('deferred_replacements', '')};"
            f"required_reduction={oversize.get('required_reduction_bytes', '')}"
        ),
        "optional oversize report missing; critical VQA now excluded or handled by sidecar",
    )

    lcw_probe = read_csv_first(args.lcw_probe_summary)
    add_check(
        checks,
        "vqa_lcw_probe",
        (
            "info"
            if not lcw_probe
            else pass_if(lcw_probe.get("status") == "pass" and as_int(lcw_probe, "roundtrip_failures") == 0)
        ),
        (
            f"status={lcw_probe.get('status', '')};"
            f"cases={lcw_probe.get('roundtrip_cases', '')};"
            f"failures={lcw_probe.get('roundtrip_failures', '')};"
            f"sample={lcw_probe.get('entries_sampled', '')}/{lcw_probe.get('entries_available', '')}"
        ),
        "optional LCW probe missing; use tools/lolg_vqa_lcw_profile.py for current LOCALLNG diagnostics",
    )

    mix_files = sorted(Path("mod_mix_vqa_fullhd").glob("*.MIX"))
    add_check(
        checks,
        "runtime_mix_files",
        pass_if(len(mix_files) == 66),
        f"mod_mix_vqa_fullhd MIX files={len(mix_files)}",
        "rerun the VQA runtime pack build",
    )

    for launcher in (Path("LOLG_HD.sh"), Path("RUN_HD.sh"), Path("RUN_HD_WINE.sh"), Path("RUN_HD_WINE_GAMESCOPE.sh"), Path("PACK_HD_RELEASE.sh"), Path("STOP_HD_WINE.sh"), Path("REPAIR_HD_WINE.sh"), Path("RUN_HD_DESKTOP.sh"), Path("INSTALL_HD_DESKTOP.sh"), Path("UNINSTALL_HD_DESKTOP.sh"), Path("COLLECT_HD_SUPPORT.sh"), Path("VERIFY_HD_MANIFEST.sh")):
        add_check(
            checks,
            f"launcher_{launcher.name}",
            pass_if(launcher.is_file() and launcher.stat().st_mode & 0o111 != 0),
            f"path={launcher};executable={launcher.stat().st_mode & 0o111 != 0 if launcher.exists() else False}",
            f"chmod +x {launcher}",
        )

    shell_syntax_commands = {
        Path("LOLG_HD.sh"): ["sh", "-n", "LOLG_HD.sh"],
        Path("RUN_HD_WINE.sh"): ["bash", "-n", "RUN_HD_WINE.sh"],
        Path("RUN_HD_WINE_GAMESCOPE.sh"): ["bash", "-n", "RUN_HD_WINE_GAMESCOPE.sh"],
        Path("PACK_HD_RELEASE.sh"): ["sh", "-n", "PACK_HD_RELEASE.sh"],
        Path("STOP_HD_WINE.sh"): ["sh", "-n", "STOP_HD_WINE.sh"],
        Path("REPAIR_HD_WINE.sh"): ["sh", "-n", "REPAIR_HD_WINE.sh"],
        Path("RUN_HD_DESKTOP.sh"): ["sh", "-n", "RUN_HD_DESKTOP.sh"],
        Path("INSTALL_HD_DESKTOP.sh"): ["sh", "-n", "INSTALL_HD_DESKTOP.sh"],
        Path("UNINSTALL_HD_DESKTOP.sh"): ["sh", "-n", "UNINSTALL_HD_DESKTOP.sh"],
        Path("COLLECT_HD_SUPPORT.sh"): ["sh", "-n", "COLLECT_HD_SUPPORT.sh"],
        Path("VERIFY_HD_MANIFEST.sh"): ["sh", "-n", "VERIFY_HD_MANIFEST.sh"],
    }
    for script, command in shell_syntax_commands.items():
        syntax_ok, syntax_detail = shell_check(command, root)
        add_check(
            checks,
            f"shell_syntax_{script.name}",
            pass_if(syntax_ok),
            syntax_detail or " ".join(command),
            f"fix {script} shell syntax",
        )

    desktop_files = [
        Path("desktop/lolg-hd.desktop"),
        Path("desktop/lolg-hd-status.desktop"),
        Path("desktop/lolg-hd-repair.desktop"),
    ]
    missing_desktop = [str(path) for path in desktop_files if not path.is_file()]
    add_check(
        checks,
        "desktop_shortcuts_present",
        pass_if(not missing_desktop),
        f"missing={';'.join(missing_desktop)}",
        "restore desktop/lolg-hd*.desktop shortcuts",
    )
    if shutil.which("desktop-file-validate") is not None:
        desktop_ok = True
        desktop_detail_parts: list[str] = []
        for desktop_file in desktop_files:
            ok, detail = shell_check(["desktop-file-validate", str(desktop_file)], root)
            desktop_ok = desktop_ok and ok
            if detail:
                desktop_detail_parts.append(f"{desktop_file}:{detail}")
        add_check(
            checks,
            "desktop_shortcuts_validate",
            pass_if(desktop_ok),
            " | ".join(desktop_detail_parts) or "desktop-file-validate passed",
            "fix desktop entry syntax",
        )
    else:
        add_check(
            checks,
            "desktop_shortcuts_validate",
            "info",
            "desktop-file-validate not installed",
            "install desktop-file-utils to validate shortcuts",
        )

    stage = args.wine_stage
    add_check(
        checks,
        "wine_stage_executable",
        pass_if((stage / "LOLG95.EXE").exists()),
        str(stage / "LOLG95.EXE"),
        "./RUN_HD_WINE.sh --prepare-only",
    )

    bad_stage_files = [
        path.name
        for path in stage.iterdir()
        if path.is_file() and path.name.lower() in BANNED_WINE_STAGE_FILES
    ] if stage.is_dir() else []
    add_check(
        checks,
        "wine_stage_no_dgvoodoo",
        pass_if(stage.is_dir() and not bad_stage_files),
        "banned_files=" + ";".join(bad_stage_files),
        "rerun ./RUN_HD_WINE.sh --prepare-only so the stage removes local wrappers",
    )

    bad_links: list[str] = []
    if stage.is_dir():
        for mix in mix_files:
            target = stage / mix.name
            if not target.is_symlink() or target.resolve() != mix.resolve():
                bad_links.append(mix.name)
    else:
        bad_links = [mix.name for mix in mix_files]
    unexpected_bad_links = [name for name in bad_links if name not in EXPECTED_ORIGINAL_STAGE_MIX]
    add_check(
        checks,
        "wine_stage_vqa_mix_links",
        pass_if(len(mix_files) == 66 and not unexpected_bad_links),
        (
            f"checked={len(mix_files)};"
            f"expected_original={';'.join(sorted(EXPECTED_ORIGINAL_STAGE_MIX))};"
            f"unexpected_bad_links={';'.join(unexpected_bad_links[:20])};"
            f"all_non_hd_links={';'.join(bad_links[:20])}"
        ),
        "./RUN_HD_WINE.sh --prepare-only; LOCALLNG/MOVIES should remain original for safevqa",
    )

    dos_d = args.wineprefix / "dosdevices" / "d:"
    dos_d_raw = args.wineprefix / "dosdevices" / "d::"
    dos_d_target = dos_d.resolve() if dos_d.exists() else None
    add_check(
        checks,
        "wineprefix_drive_d",
        pass_if(
            dos_d.is_symlink()
            and dos_d_target == args.wine_stage.parent.parent.resolve()
            and not dos_d_raw.exists()
        ),
        f"d:={dos_d_target or ''};d::={'present' if dos_d_raw.exists() else 'absent'}",
        "./RUN_HD_WINE.sh --prepare-only",
    )

    user_reg = args.wineprefix / "user.reg"
    direct3d = parse_user_reg_section(user_reg, r"Software\\Wine\\Direct3D")
    desktops = parse_user_reg_section(user_reg, r"Software\\Wine\\Explorer\\Desktops")
    x11 = parse_user_reg_section(user_reg, r"Software\\Wine\\X11 Driver")
    add_check(
        checks,
        "wine_directdraw_registry",
        pass_if(
            direct3d.get("DirectDrawRenderer") == "gdi"
            and direct3d.get("renderer") == "gdi"
            and direct3d.get("UseGLSL") == "enabled"
            and direct3d.get("OffscreenRenderingMode") == "fbo"
            and x11.get("UseXRandR") == "N"
            and x11.get("UseXVidMode") == "N"
        ),
        (
            f"DirectDrawRenderer={direct3d.get('DirectDrawRenderer', '')};"
            f"renderer={direct3d.get('renderer', '')};"
            f"UseGLSL={direct3d.get('UseGLSL', '')};"
            f"OffscreenRenderingMode={direct3d.get('OffscreenRenderingMode', '')};"
            f"UseXRandR={x11.get('UseXRandR', '')};"
            f"UseXVidMode={x11.get('UseXVidMode', '')}"
        ),
        "./RUN_HD_WINE.sh --prepare-only",
    )
    add_check(
        checks,
        "wine_desktop_registry",
        pass_if(desktops.get("LOLG_HD") in {"1920x1080", "1280x1024"}),
        f"LOLG_HD={desktops.get('LOLG_HD', '')}",
        "./RUN_HD_WINE.sh --prepare-only",
    )

    add_check(
        checks,
        "wine_binary",
        pass_if(shutil.which("wine") is not None),
        shutil.which("wine") or "",
        "install Wine",
    )
    add_check(
        checks,
        "xdotool_auto_resize",
        pass_if(shutil.which("xdotool") is not None),
        f"{shutil.which('xdotool') or ''};auto_resize_default=1;resize_game_window_default=1",
        "install xdotool or run RUN_HD_WINE.sh --no-auto-resize --no-resize-game-window for diagnostics",
    )

    for resolution in ("1920x1080", "1280x1024"):
        dry_ok, dry_detail = shell_check(
            ["./RUN_HD_WINE.sh", "--dry-run", "--resolution", resolution],
            root,
        )
        add_check(
            checks,
            f"wine_launcher_resolution_{resolution}",
            pass_if(
                dry_ok
                and f"Resolution Wine: {resolution}" in dry_detail
                and "Resolution supportee: oui" in dry_detail
                and (
                    f"/desktop=LOLG_HD,{resolution}" in dry_detail
                    or f"/desktop=LOLG_HD\\,{resolution}" in dry_detail
                )
            ),
            dry_detail,
            f"./RUN_HD_WINE.sh --dry-run --resolution {resolution}",
        )

    bad_ok, bad_detail = shell_check(
        ["./RUN_HD_WINE.sh", "--dry-run", "--resolution", "640x400"],
        root,
    )
    add_check(
        checks,
        "wine_launcher_rejects_640x400",
        pass_if((not bad_ok) and "Resolution non supportee: 640x400" in bad_detail),
        bad_detail,
        "use 1920x1080 or 1280x1024 unless --allow-unsupported-resolution is intentional",
    )

    sidecar_ok, sidecar_detail = shell_check(["./LOLG_HD.sh", "sidecar-hd", "--no-game", "--dry-run"], root)
    add_check(
        checks,
        "sidecar_handoff_dry_run",
        pass_if(
            sidecar_ok
            and "Player VQA HD:" in sidecar_detail
            and "wine-dgvoodoo-win10-safevqa" in sidecar_detail
        ),
        sidecar_detail,
        "./LOLG_HD.sh sidecar-hd --no-game --dry-run",
    )

    sidecar_smoke_ok, sidecar_smoke_detail = shell_check(["./LOLG_HD.sh", "sidecar-test"], root)
    add_check(
        checks,
        "sidecar_decode_smoke",
        pass_if(
            sidecar_smoke_ok
            and '"status": "decoded"' in sidecar_smoke_detail
            and '"width": 1920' in sidecar_smoke_detail
            and '"height": 1080' in sidecar_smoke_detail
            and '"decoder_returncode": 0' in sidecar_smoke_detail
            and '"decode_dir":' in sidecar_smoke_detail
        ),
        sidecar_smoke_detail,
        "./LOLG_HD.sh sidecar-test",
    )

    sidecar_summary = read_csv_first(Path("output/vqa_external_sidecar_index/summary.csv"))
    sidecar_entries = read_csv_rows(Path("output/vqa_external_sidecar_index/entries.csv"))
    locallng_rows = [
        row
        for row in sidecar_entries
        if row.get("archive") == "LOCALLNG.MIX"
        and row.get("status") == "external_ready"
        and row.get("width") == "1920"
        and row.get("height") == "1080"
    ]
    movies_rows = [
        row
        for row in sidecar_entries
        if row.get("archive") == "MOVIES.MIX"
        and row.get("status") == "external_ready"
        and row.get("width") == "1920"
        and row.get("height") == "1080"
    ]
    movies_ids = {row.get("file_id", "") for row in movies_rows}
    add_check(
        checks,
        "sidecar_critical_manifest_coverage",
        pass_if(
            sidecar_summary.get("status") == "pass"
            and sidecar_summary.get("mix_archives") == "66"
            and sidecar_summary.get("vqa_entries") == "1955"
            and len(locallng_rows) >= 1
            and len(movies_rows) == 28
            and len(movies_ids) == 28
        ),
        (
            f"status={sidecar_summary.get('status', '')};"
            f"archives={sidecar_summary.get('mix_archives', '')};"
            f"vqa={sidecar_summary.get('vqa_entries', '')};"
            f"LOCALLNG_1920={len(locallng_rows)};"
            f"MOVIES_1920={len(movies_rows)};"
            f"MOVIES_unique={len(movies_ids)}"
        ),
        "./LOLG_HD.sh sidecar-test or regenerate output/vqa_external_sidecar_index",
    )

    sidecar_critical_ok, sidecar_critical_detail = shell_check(["./LOLG_HD.sh", "sidecar-critical-test"], root)
    add_check(
        checks,
        "sidecar_critical_decode_smoke",
        pass_if(
            sidecar_critical_ok
            and '"key": "LOCALLNG.MIX:fca4e133"' in sidecar_critical_detail
            and '"key": "MOVIES.MIX:4d6efa8e"' in sidecar_critical_detail
            and sidecar_critical_detail.count('"status": "decoded"') >= 2
            and sidecar_critical_detail.count('"width": 1920') >= 2
            and sidecar_critical_detail.count('"height": 1080') >= 2
            and sidecar_critical_detail.count('"decoder_returncode": 0') >= 2
        ),
        sidecar_critical_detail,
        "./LOLG_HD.sh sidecar-critical-test",
    )

    no_latest_event = output / "sidecar_no_latest_event.json"
    sidecar_locallng_web_ok, sidecar_locallng_web_detail = shell_check(
        [
            "./LOLG_HD.sh",
            "sidecar-web",
            "--check",
            "--summary",
            "--result-file",
            "output/vqa_external_sidecar_cache/LOCALLNG.MIX/fca4e133/result.json",
            "--latest-event-file",
            str(no_latest_event),
        ],
        root,
    )
    sidecar_movies_web_ok, sidecar_movies_web_detail = shell_check(
        [
            "./LOLG_HD.sh",
            "sidecar-web",
            "--check",
            "--summary",
            "--result-file",
            "output/vqa_external_sidecar_cache/MOVIES.MIX/4d6efa8e/result.json",
            "--latest-event-file",
            str(no_latest_event),
        ],
        root,
    )
    sidecar_critical_web_detail = f"LOCALLNG={sidecar_locallng_web_detail};MOVIES={sidecar_movies_web_detail}"
    add_check(
        checks,
        "sidecar_critical_web_inventory",
        pass_if(
            sidecar_locallng_web_ok
            and sidecar_movies_web_ok
            and '"key": "LOCALLNG.MIX:fca4e133"' in sidecar_locallng_web_detail
            and '"key": "MOVIES.MIX:4d6efa8e"' in sidecar_movies_web_detail
            and '"status": "decoded"' in sidecar_locallng_web_detail
            and '"status": "decoded"' in sidecar_movies_web_detail
            and '"width": 1920' in sidecar_locallng_web_detail
            and '"width": 1920' in sidecar_movies_web_detail
            and '"height": 1080' in sidecar_locallng_web_detail
            and '"height": 1080' in sidecar_movies_web_detail
            and '"frame_count": 237' in sidecar_locallng_web_detail
            and ('"frame_count": 1' in sidecar_movies_web_detail or '"frame_count": 75' in sidecar_movies_web_detail)
        ),
        sidecar_critical_web_detail,
        "./LOLG_HD.sh sidecar-web --check --summary for LOCALLNG/MOVIES result files",
    )

    sidecar_critical_status_ok, sidecar_critical_status_detail = shell_check(
        ["./LOLG_HD.sh", "sidecar-critical-status", "--json"],
        root,
    )
    add_check(
        checks,
        "sidecar_critical_status_summary",
        pass_if(
            sidecar_critical_status_ok
            and '"critical_ready": true' in sidecar_critical_status_detail
            and '"key": "LOCALLNG.MIX:fca4e133"' in sidecar_critical_status_detail
            and '"key": "MOVIES.MIX:4d6efa8e"' in sidecar_critical_status_detail
            and sidecar_critical_status_detail.count('"status": "decoded"') >= 2
            and '"ready_frames": 237' in sidecar_critical_status_detail
            and ('"ready_frames": 1' in sidecar_critical_status_detail or '"ready_frames": 75' in sidecar_critical_status_detail)
        ),
        sidecar_critical_status_detail,
        "./LOLG_HD.sh sidecar-critical-status --json",
    )

    support_check_dir = Path("output/hd_support_bundle_check")
    support_check_archive = Path("output/hd_support_bundle_check.tar.gz")
    support_check_archive_sha256 = Path(str(support_check_archive) + ".sha256")
    support_check_archive_summary = Path(str(support_check_archive) + ".summary")
    support_check_archive_verify_script = Path(str(support_check_archive) + ".verify.sh")
    support_check_archive_artifacts = Path(str(support_check_archive) + ".artifacts.csv")
    support_ok, support_detail = shell_check(["./COLLECT_HD_SUPPORT.sh", str(support_check_dir)], root)
    support_sidecar_status = support_check_dir / "reports/sidecar_critical_status.json"
    support_locallng_result = (
        support_check_dir / "reports/vqa_external_sidecar_cache/LOCALLNG.MIX/fca4e133/result.json"
    )
    support_movies_result = (
        support_check_dir / "reports/vqa_external_sidecar_cache/MOVIES.MIX/4d6efa8e/result.json"
    )
    support_locallng_rendered = (
        support_check_dir / "reports/vqa_external_sidecar_cache/LOCALLNG.MIX/fca4e133/decode/rendered_frames.csv"
    )
    support_movies_rendered = (
        support_check_dir / "reports/vqa_external_sidecar_cache/MOVIES.MIX/4d6efa8e/decode/rendered_frames.csv"
    )
    support_locallng_rendered_rows = read_csv_rows(support_locallng_rendered)
    support_movies_rendered_rows = read_csv_rows(support_movies_rendered)
    support_tool_status = support_check_dir / "tools/lolg_hd_status.py"
    support_tool_release_check = support_check_dir / "tools/lolg_hd_release_check.py"
    support_tool_sidecar_status = support_check_dir / "tools/lolg_vqa_external_sidecar_status.py"
    support_tool_sidecar_index = support_check_dir / "tools/lolg_vqa_external_sidecar_index.py"
    support_tool_support_manifest_verify = support_check_dir / "tools/lolg_hd_support_manifest_verify.py"
    support_tool_support_archive_verify = support_check_dir / "tools/lolg_hd_support_archive_verify.py"
    support_tool_vqa_decode = support_check_dir / "tools/lolg_vqa_decode.py"
    support_diagnostic = support_check_dir / "diagnostic.txt"
    support_readme = support_check_dir / "README_SUPPORT.txt"
    support_summary = support_check_dir / "SUPPORT_SUMMARY.txt"
    support_bundle_manifest = support_check_dir / "BUNDLE_MANIFEST.csv"
    support_verify_script = support_check_dir / "VERIFY_SUPPORT.sh"
    support_index_archives = support_check_dir / "reports/vqa_external_sidecar_index/archives.csv"
    support_index_entries = support_check_dir / "reports/vqa_external_sidecar_index/entries.csv"
    support_index_rows = read_csv_rows(support_index_entries)
    support_bundle_manifest_rows = read_csv_rows(support_bundle_manifest)
    support_bundle_manifest_fieldnames = read_csv_fieldnames(support_bundle_manifest)
    support_bundle_manifest_required_fields = {"path", "size", "sha256", "executable"}
    support_bundle_manifest_fields = set(support_bundle_manifest_fieldnames)
    support_bundle_manifest_duplicate_fields = csv_duplicate_fieldnames(support_bundle_manifest_fieldnames)
    support_bundle_manifest_schema_ok = (
        support_bundle_manifest_fields == support_bundle_manifest_required_fields
        and not support_bundle_manifest_duplicate_fields
    )
    support_bundle_manifest_row_width_ok = not any(None in row for row in support_bundle_manifest_rows)
    support_bundle_manifest_paths = {row.get("path", "") for row in support_bundle_manifest_rows}
    support_bundle_manifest_key_paths = [
        "README_SUPPORT.txt",
        "SUPPORT_SUMMARY.txt",
        "VERIFY_SUPPORT.sh",
        "diagnostic.txt",
        "reports/hd_status/summary.csv",
        "reports/vqa_external_sidecar_index/entries.csv",
        "reports/vqa_external_sidecar_cache/LOCALLNG.MIX/fca4e133/decode/rendered_frames.csv",
        "reports/vqa_external_sidecar_cache/MOVIES.MIX/4d6efa8e/decode/rendered_frames.csv",
        "tools/lolg_hd_support_manifest_verify.py",
        "tools/lolg_hd_support_archive_verify.py",
        "tools/lolg_vqa_decode.py",
    ]
    support_bundle_manifest_matched_paths = [
        path for path in support_bundle_manifest_key_paths if path in support_bundle_manifest_paths
    ]
    support_bundle_manifest_pngs = [
        path for path in support_bundle_manifest_paths if path.lower().endswith(".png")
    ]
    support_bundle_manifest_verify_script_executable = any(
        row.get("path") == "VERIFY_SUPPORT.sh" and row.get("executable") == "1"
        for row in support_bundle_manifest_rows
    )
    support_archive_artifacts_rows = read_csv_rows(support_check_archive_artifacts)
    support_archive_artifacts_required_fields = {"path", "size", "sha256", "executable"}
    support_archive_artifacts_fields = (
        set(support_archive_artifacts_rows[0]) if support_archive_artifacts_rows else set()
    )
    support_archive_artifacts_schema_ok = (
        support_archive_artifacts_fields == support_archive_artifacts_required_fields
    )
    support_archive_artifacts_expected_paths = {
        support_check_archive.name,
        support_check_archive_sha256.name,
        support_check_archive_summary.name,
        support_check_archive_verify_script.name,
    }
    support_archive_artifacts_paths = {row.get("path", "") for row in support_archive_artifacts_rows}
    support_archive_artifacts_paths_ok = support_archive_artifacts_paths == support_archive_artifacts_expected_paths
    support_archive_artifacts_row_width_ok = not any(None in row for row in support_archive_artifacts_rows)
    support_locallng_index_rows = [
        row
        for row in support_index_rows
        if row.get("archive") == "LOCALLNG.MIX"
        and row.get("file_id") == "fca4e133"
        and row.get("width") == "1920"
        and row.get("height") == "1080"
    ]
    support_movies_index_rows = [
        row
        for row in support_index_rows
        if row.get("archive") == "MOVIES.MIX"
        and row.get("width") == "1920"
        and row.get("height") == "1080"
    ]
    support_movies_index_ids = {row.get("file_id", "") for row in support_movies_index_rows}
    support_hd_status_summary = read_csv_first(support_check_dir / "reports/hd_status/summary.csv")
    support_status_text = support_sidecar_status.read_text(encoding="utf-8", errors="replace") if support_sidecar_status.exists() else ""
    support_diagnostic_text = support_diagnostic.read_text(encoding="utf-8", errors="replace") if support_diagnostic.exists() else ""
    support_readme_text = support_readme.read_text(encoding="utf-8", errors="replace") if support_readme.exists() else ""
    support_summary_text = support_summary.read_text(encoding="utf-8", errors="replace") if support_summary.exists() else ""
    support_summary_values = read_key_value_text(support_summary_text)
    support_summary_issue_set = {
        issue for issue in support_summary_values.get("support_summary_issues", "").split(";") if issue
    }
    support_summary_release_display_expected = (
        f"{support_summary_values.get('release_pass_count', '')} pass + "
        f"{support_summary_values.get('release_info', '')} info / "
        f"{support_summary_values.get('release_checks', '')}"
    )
    support_summary_release_fields_ok = (
        bool(support_summary_values.get("release_pass_count"))
        and bool(support_summary_values.get("release_checks"))
        and support_summary_values.get("release_info", "") != ""
        and support_summary_values.get("release_passed", "")
        == f"{support_summary_values.get('release_pass_count')}/{support_summary_values.get('release_checks')}"
        and support_summary_values.get("release_display", "") == support_summary_release_display_expected
    )
    support_summary_current_or_stale_release_ok = (
        (
            support_summary_values.get("status") == "pass"
            and support_summary_values.get("ready_to_launch") == "1"
            and support_summary_values.get("release_check") == "pass"
            and support_summary_values.get("manifest") == "pass"
            and not support_summary_issue_set
        )
        or (
            support_summary_issue_set <= {"release_check", "manifest"}
            and support_summary_values.get("manifest_verify") == "pass"
            and support_summary_values.get("resolution") == "pass"
            and "sidecar_critical_full_ready=1" in support_summary_text
            and "movies_ready=75/75" in support_summary_text
            and "locallng_rendered_rows=237" in support_summary_text
            and "movies_rendered_rows=75" in support_summary_text
        )
    )
    support_manifest_verify_ok, support_manifest_verify_detail = shell_check(
        [
            "python3",
            "tools/lolg_hd_support_manifest_verify.py",
            str(support_check_dir),
            "-o",
            "output/hd_support_manifest_verify_check",
        ],
        root,
    )
    support_manifest_verify_summary = read_csv_first(Path("output/hd_support_manifest_verify_check/summary.csv"))
    support_verify_script_ok, support_verify_script_detail = shell_check(
        [
            "env",
            "LOLG_HD_SUPPORT_VERIFY_OUTPUT=output/hd_support_manifest_verify_launcher_check",
            str(support_verify_script),
        ],
        root,
    )
    support_verify_script_summary = read_csv_first(
        Path("output/hd_support_manifest_verify_launcher_check/summary.csv")
    )
    support_manifest_negative_ok = False
    support_manifest_negative_detail = "not_run"
    support_manifest_launcher_negative_ok = False
    support_manifest_launcher_negative_detail = "not_run"
    support_manifest_extra_field_negative_ok = False
    support_manifest_extra_field_negative_detail = "not_run"
    support_manifest_extra_field_launcher_negative_ok = False
    support_manifest_extra_field_launcher_negative_detail = "not_run"
    support_manifest_duplicate_field_negative_ok = False
    support_manifest_duplicate_field_negative_detail = "not_run"
    support_manifest_duplicate_field_launcher_negative_ok = False
    support_manifest_duplicate_field_launcher_negative_detail = "not_run"
    support_manifest_missing_field_negative_ok = False
    support_manifest_missing_field_negative_detail = "not_run"
    support_manifest_missing_field_launcher_negative_ok = False
    support_manifest_missing_field_launcher_negative_detail = "not_run"
    support_manifest_unsafe_negative_ok = False
    support_manifest_unsafe_negative_detail = "not_run"
    support_manifest_unsafe_launcher_negative_ok = False
    support_manifest_unsafe_launcher_negative_detail = "not_run"
    support_manifest_noncanonical_negative_ok = False
    support_manifest_noncanonical_negative_detail = "not_run"
    support_manifest_noncanonical_launcher_negative_ok = False
    support_manifest_noncanonical_launcher_negative_detail = "not_run"
    support_manifest_invalid_fields_negative_ok = False
    support_manifest_invalid_fields_negative_detail = "not_run"
    support_manifest_invalid_fields_launcher_negative_ok = False
    support_manifest_invalid_fields_launcher_negative_detail = "not_run"
    support_manifest_size_mismatch_negative_ok = False
    support_manifest_size_mismatch_negative_detail = "not_run"
    support_manifest_size_mismatch_launcher_negative_ok = False
    support_manifest_size_mismatch_launcher_negative_detail = "not_run"
    support_manifest_sha256_mismatch_negative_ok = False
    support_manifest_sha256_mismatch_negative_detail = "not_run"
    support_manifest_sha256_mismatch_launcher_negative_ok = False
    support_manifest_sha256_mismatch_launcher_negative_detail = "not_run"
    support_manifest_invalid_executable_negative_ok = False
    support_manifest_invalid_executable_negative_detail = "not_run"
    support_manifest_invalid_executable_launcher_negative_ok = False
    support_manifest_invalid_executable_launcher_negative_detail = "not_run"
    support_manifest_executable_mismatch_negative_ok = False
    support_manifest_executable_mismatch_negative_detail = "not_run"
    support_manifest_executable_mismatch_launcher_negative_ok = False
    support_manifest_executable_mismatch_launcher_negative_detail = "not_run"
    support_manifest_missing_file_negative_ok = False
    support_manifest_missing_file_negative_detail = "not_run"
    support_manifest_missing_file_launcher_negative_ok = False
    support_manifest_missing_file_launcher_negative_detail = "not_run"
    support_manifest_not_file_negative_ok = False
    support_manifest_not_file_negative_detail = "not_run"
    support_manifest_not_file_launcher_negative_ok = False
    support_manifest_not_file_launcher_negative_detail = "not_run"
    support_manifest_unexpected_file_negative_ok = False
    support_manifest_unexpected_file_negative_detail = "not_run"
    support_manifest_unexpected_file_launcher_negative_ok = False
    support_manifest_unexpected_file_launcher_negative_detail = "not_run"
    support_manifest_duplicate_path_negative_ok = False
    support_manifest_duplicate_path_negative_detail = "not_run"
    support_manifest_duplicate_path_launcher_negative_ok = False
    support_manifest_duplicate_path_launcher_negative_detail = "not_run"
    support_manifest_png_entry_negative_ok = False
    support_manifest_png_entry_negative_detail = "not_run"
    support_manifest_png_entry_launcher_negative_ok = False
    support_manifest_png_entry_launcher_negative_detail = "not_run"
    if support_check_dir.is_dir() and support_bundle_manifest.is_file():
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_manifest_negative_") as tmp:
            tmp_path = Path(tmp)
            copied_bundle = tmp_path / "bundle"
            shutil.copytree(support_check_dir, copied_bundle)
            copied_manifest = copied_bundle / "BUNDLE_MANIFEST.csv"
            write_row_width_broken_manifest(copied_manifest)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_manifest_verify.py",
                    str(copied_bundle),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_manifest_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("row_width_mismatch") not in {"", "0"}
                and "row_width_mismatch" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_manifest_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"row_width_mismatch={negative_summary.get('row_width_mismatch', '')};"
                f"row_width_gap={int('row_width_mismatch' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_verify_script = copied_bundle / "VERIFY_SUPPORT.sh"
            launcher_output = tmp_path / "verify_launcher"
            launcher_negative_ok, launcher_negative_detail = shell_check(
                [
                    "env",
                    f"LOLG_HD_SUPPORT_VERIFY_OUTPUT={launcher_output}",
                    str(copied_verify_script),
                ],
                root,
            )
            support_manifest_launcher_negative_ok = (
                not launcher_negative_ok
                and "row_width_mismatch" in launcher_negative_detail
                and "Traceback" not in launcher_negative_detail
            )
            support_manifest_launcher_negative_detail = launcher_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_manifest_extra_field_negative_") as tmp:
            tmp_path = Path(tmp)
            copied_bundle = tmp_path / "bundle"
            shutil.copytree(support_check_dir, copied_bundle)
            copied_manifest = copied_bundle / "BUNDLE_MANIFEST.csv"
            write_extra_field_manifest(copied_manifest)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_manifest_verify.py",
                    str(copied_bundle),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_manifest_extra_field_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("manifest_schema") == "gap"
                and negative_summary.get("manifest_extra_fields") == "extra"
                and "manifest_schema_extra_fields:extra" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_manifest_extra_field_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"schema={negative_summary.get('manifest_schema', '')};"
                f"extra={negative_summary.get('manifest_extra_fields', '')};"
                f"extra_gap={int('manifest_schema_extra_fields:extra' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_verify_script = copied_bundle / "VERIFY_SUPPORT.sh"
            launcher_output = tmp_path / "verify_launcher"
            launcher_negative_ok, launcher_negative_detail = shell_check(
                [
                    "env",
                    f"LOLG_HD_SUPPORT_VERIFY_OUTPUT={launcher_output}",
                    str(copied_verify_script),
                ],
                root,
            )
            support_manifest_extra_field_launcher_negative_ok = (
                not launcher_negative_ok
                and "manifest_schema_extra_fields" in launcher_negative_detail
                and "Traceback" not in launcher_negative_detail
            )
            support_manifest_extra_field_launcher_negative_detail = launcher_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_manifest_duplicate_field_negative_") as tmp:
            tmp_path = Path(tmp)
            copied_bundle = tmp_path / "bundle"
            shutil.copytree(support_check_dir, copied_bundle)
            copied_manifest = copied_bundle / "BUNDLE_MANIFEST.csv"
            write_duplicate_field_manifest(copied_manifest)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_manifest_verify.py",
                    str(copied_bundle),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_manifest_duplicate_field_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("manifest_schema") == "gap"
                and negative_summary.get("manifest_duplicate_fields") == "path"
                and "manifest_schema_duplicate_fields:path" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_manifest_duplicate_field_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"schema={negative_summary.get('manifest_schema', '')};"
                f"duplicate={negative_summary.get('manifest_duplicate_fields', '')};"
                f"duplicate_gap={int('manifest_schema_duplicate_fields:path' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_verify_script = copied_bundle / "VERIFY_SUPPORT.sh"
            launcher_output = tmp_path / "verify_launcher"
            launcher_negative_ok, launcher_negative_detail = shell_check(
                [
                    "env",
                    f"LOLG_HD_SUPPORT_VERIFY_OUTPUT={launcher_output}",
                    str(copied_verify_script),
                ],
                root,
            )
            support_manifest_duplicate_field_launcher_negative_ok = (
                not launcher_negative_ok
                and "manifest_schema_duplicate_fields" in launcher_negative_detail
                and "Traceback" not in launcher_negative_detail
            )
            support_manifest_duplicate_field_launcher_negative_detail = launcher_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_manifest_missing_field_negative_") as tmp:
            tmp_path = Path(tmp)
            copied_bundle = tmp_path / "bundle"
            shutil.copytree(support_check_dir, copied_bundle)
            copied_manifest = copied_bundle / "BUNDLE_MANIFEST.csv"
            write_missing_field_manifest(copied_manifest)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_manifest_verify.py",
                    str(copied_bundle),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_manifest_missing_field_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("manifest_schema") == "gap"
                and negative_summary.get("manifest_missing_fields") == "sha256"
                and "manifest_schema_missing_fields:sha256" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_manifest_missing_field_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"schema={negative_summary.get('manifest_schema', '')};"
                f"missing={negative_summary.get('manifest_missing_fields', '')};"
                f"missing_gap={int('manifest_schema_missing_fields:sha256' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_verify_script = copied_bundle / "VERIFY_SUPPORT.sh"
            launcher_output = tmp_path / "verify_launcher"
            launcher_negative_ok, launcher_negative_detail = shell_check(
                [
                    "env",
                    f"LOLG_HD_SUPPORT_VERIFY_OUTPUT={launcher_output}",
                    str(copied_verify_script),
                ],
                root,
            )
            support_manifest_missing_field_launcher_negative_ok = (
                not launcher_negative_ok
                and "manifest_schema_missing_fields" in launcher_negative_detail
                and "Traceback" not in launcher_negative_detail
            )
            support_manifest_missing_field_launcher_negative_detail = launcher_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_manifest_unsafe_negative_") as tmp:
            tmp_path = Path(tmp)
            copied_bundle = tmp_path / "bundle"
            shutil.copytree(support_check_dir, copied_bundle)
            copied_manifest = copied_bundle / "BUNDLE_MANIFEST.csv"
            write_unsafe_path_manifest(copied_manifest)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_manifest_verify.py",
                    str(copied_bundle),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_manifest_unsafe_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("unsafe_paths") not in {"", "0"}
                and "unsafe_path" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_manifest_unsafe_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"unsafe_paths={negative_summary.get('unsafe_paths', '')};"
                f"unsafe_gap={int('unsafe_path' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_verify_script = copied_bundle / "VERIFY_SUPPORT.sh"
            launcher_output = tmp_path / "verify_launcher"
            launcher_negative_ok, launcher_negative_detail = shell_check(
                [
                    "env",
                    f"LOLG_HD_SUPPORT_VERIFY_OUTPUT={launcher_output}",
                    str(copied_verify_script),
                ],
                root,
            )
            support_manifest_unsafe_launcher_negative_ok = (
                not launcher_negative_ok
                and "unsafe_path" in launcher_negative_detail
                and "Traceback" not in launcher_negative_detail
            )
            support_manifest_unsafe_launcher_negative_detail = launcher_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_manifest_noncanonical_negative_") as tmp:
            tmp_path = Path(tmp)
            copied_bundle = tmp_path / "bundle"
            shutil.copytree(support_check_dir, copied_bundle)
            copied_manifest = copied_bundle / "BUNDLE_MANIFEST.csv"
            write_noncanonical_path_manifest(copied_manifest)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_manifest_verify.py",
                    str(copied_bundle),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_manifest_noncanonical_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("noncanonical_paths") not in {"", "0"}
                and "noncanonical_path" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_manifest_noncanonical_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"noncanonical_paths={negative_summary.get('noncanonical_paths', '')};"
                f"noncanonical_gap={int('noncanonical_path' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_verify_script = copied_bundle / "VERIFY_SUPPORT.sh"
            launcher_output = tmp_path / "verify_launcher"
            launcher_negative_ok, launcher_negative_detail = shell_check(
                [
                    "env",
                    f"LOLG_HD_SUPPORT_VERIFY_OUTPUT={launcher_output}",
                    str(copied_verify_script),
                ],
                root,
            )
            support_manifest_noncanonical_launcher_negative_ok = (
                not launcher_negative_ok
                and "noncanonical_path" in launcher_negative_detail
                and "Traceback" not in launcher_negative_detail
            )
            support_manifest_noncanonical_launcher_negative_detail = launcher_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_manifest_invalid_fields_negative_") as tmp:
            tmp_path = Path(tmp)
            copied_bundle = tmp_path / "bundle"
            shutil.copytree(support_check_dir, copied_bundle)
            copied_manifest = copied_bundle / "BUNDLE_MANIFEST.csv"
            write_invalid_size_sha_manifest(copied_manifest)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_manifest_verify.py",
                    str(copied_bundle),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_manifest_invalid_fields_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("size_invalid") not in {"", "0"}
                and negative_summary.get("sha256_invalid") not in {"", "0"}
                and "size_invalid" in negative_checks
                and "sha256_invalid" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_manifest_invalid_fields_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"size_invalid={negative_summary.get('size_invalid', '')};"
                f"sha256_invalid={negative_summary.get('sha256_invalid', '')};"
                f"size_gap={int('size_invalid' in negative_checks)};"
                f"sha_gap={int('sha256_invalid' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_verify_script = copied_bundle / "VERIFY_SUPPORT.sh"
            launcher_output = tmp_path / "verify_launcher"
            launcher_negative_ok, launcher_negative_detail = shell_check(
                [
                    "env",
                    f"LOLG_HD_SUPPORT_VERIFY_OUTPUT={launcher_output}",
                    str(copied_verify_script),
                ],
                root,
            )
            support_manifest_invalid_fields_launcher_negative_ok = (
                not launcher_negative_ok
                and "size_invalid" in launcher_negative_detail
                and "sha256_invalid" in launcher_negative_detail
                and "Traceback" not in launcher_negative_detail
            )
            support_manifest_invalid_fields_launcher_negative_detail = launcher_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_manifest_size_mismatch_negative_") as tmp:
            tmp_path = Path(tmp)
            copied_bundle = tmp_path / "bundle"
            shutil.copytree(support_check_dir, copied_bundle)
            copied_manifest = copied_bundle / "BUNDLE_MANIFEST.csv"
            write_size_mismatch_manifest(copied_manifest)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_manifest_verify.py",
                    str(copied_bundle),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_manifest_size_mismatch_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("size_mismatch") not in {"", "0"}
                and "size_mismatch" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_manifest_size_mismatch_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"size_mismatch={negative_summary.get('size_mismatch', '')};"
                f"size_gap={int('size_mismatch' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_verify_script = copied_bundle / "VERIFY_SUPPORT.sh"
            launcher_output = tmp_path / "verify_launcher"
            launcher_negative_ok, launcher_negative_detail = shell_check(
                [
                    "env",
                    f"LOLG_HD_SUPPORT_VERIFY_OUTPUT={launcher_output}",
                    str(copied_verify_script),
                ],
                root,
            )
            support_manifest_size_mismatch_launcher_negative_ok = (
                not launcher_negative_ok
                and "size_mismatch" in launcher_negative_detail
                and "Traceback" not in launcher_negative_detail
            )
            support_manifest_size_mismatch_launcher_negative_detail = launcher_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_manifest_sha256_mismatch_negative_") as tmp:
            tmp_path = Path(tmp)
            copied_bundle = tmp_path / "bundle"
            shutil.copytree(support_check_dir, copied_bundle)
            copied_manifest = copied_bundle / "BUNDLE_MANIFEST.csv"
            write_sha256_mismatch_manifest(copied_manifest)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_manifest_verify.py",
                    str(copied_bundle),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_manifest_sha256_mismatch_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("sha256_mismatch") not in {"", "0"}
                and "sha256_mismatch" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_manifest_sha256_mismatch_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"sha256_mismatch={negative_summary.get('sha256_mismatch', '')};"
                f"sha_gap={int('sha256_mismatch' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_verify_script = copied_bundle / "VERIFY_SUPPORT.sh"
            launcher_output = tmp_path / "verify_launcher"
            launcher_negative_ok, launcher_negative_detail = shell_check(
                [
                    "env",
                    f"LOLG_HD_SUPPORT_VERIFY_OUTPUT={launcher_output}",
                    str(copied_verify_script),
                ],
                root,
            )
            support_manifest_sha256_mismatch_launcher_negative_ok = (
                not launcher_negative_ok
                and "sha256_mismatch" in launcher_negative_detail
                and "Traceback" not in launcher_negative_detail
            )
            support_manifest_sha256_mismatch_launcher_negative_detail = launcher_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_manifest_invalid_executable_negative_") as tmp:
            tmp_path = Path(tmp)
            copied_bundle = tmp_path / "bundle"
            shutil.copytree(support_check_dir, copied_bundle)
            copied_manifest = copied_bundle / "BUNDLE_MANIFEST.csv"
            write_invalid_executable_manifest(copied_manifest)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_manifest_verify.py",
                    str(copied_bundle),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_manifest_invalid_executable_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("executable_invalid") not in {"", "0"}
                and "executable_invalid" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_manifest_invalid_executable_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"executable_invalid={negative_summary.get('executable_invalid', '')};"
                f"executable_gap={int('executable_invalid' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_verify_script = copied_bundle / "VERIFY_SUPPORT.sh"
            launcher_output = tmp_path / "verify_launcher"
            launcher_negative_ok, launcher_negative_detail = shell_check(
                [
                    "env",
                    f"LOLG_HD_SUPPORT_VERIFY_OUTPUT={launcher_output}",
                    str(copied_verify_script),
                ],
                root,
            )
            support_manifest_invalid_executable_launcher_negative_ok = (
                not launcher_negative_ok
                and "executable_invalid" in launcher_negative_detail
                and "Traceback" not in launcher_negative_detail
            )
            support_manifest_invalid_executable_launcher_negative_detail = launcher_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_manifest_executable_mismatch_negative_") as tmp:
            tmp_path = Path(tmp)
            copied_bundle = tmp_path / "bundle"
            shutil.copytree(support_check_dir, copied_bundle)
            copied_manifest = copied_bundle / "BUNDLE_MANIFEST.csv"
            write_executable_mismatch_manifest(copied_manifest)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_manifest_verify.py",
                    str(copied_bundle),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_manifest_executable_mismatch_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("executable_mismatch") not in {"", "0"}
                and "executable_mismatch" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_manifest_executable_mismatch_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"executable_mismatch={negative_summary.get('executable_mismatch', '')};"
                f"executable_gap={int('executable_mismatch' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_verify_script = copied_bundle / "VERIFY_SUPPORT.sh"
            launcher_output = tmp_path / "verify_launcher"
            launcher_negative_ok, launcher_negative_detail = shell_check(
                [
                    "env",
                    f"LOLG_HD_SUPPORT_VERIFY_OUTPUT={launcher_output}",
                    str(copied_verify_script),
                ],
                root,
            )
            support_manifest_executable_mismatch_launcher_negative_ok = (
                not launcher_negative_ok
                and "executable_mismatch" in launcher_negative_detail
                and "Traceback" not in launcher_negative_detail
            )
            support_manifest_executable_mismatch_launcher_negative_detail = launcher_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_manifest_missing_file_negative_") as tmp:
            tmp_path = Path(tmp)
            copied_bundle = tmp_path / "bundle"
            shutil.copytree(support_check_dir, copied_bundle)
            missing_file = copied_bundle / "diagnostic.txt"
            if missing_file.exists():
                missing_file.unlink()
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_manifest_verify.py",
                    str(copied_bundle),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_manifest_missing_file_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("missing") not in {"", "0"}
                and "missing" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_manifest_missing_file_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"missing={negative_summary.get('missing', '')};"
                f"missing_gap={int('missing' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_verify_script = copied_bundle / "VERIFY_SUPPORT.sh"
            launcher_output = tmp_path / "verify_launcher"
            launcher_negative_ok, launcher_negative_detail = shell_check(
                [
                    "env",
                    f"LOLG_HD_SUPPORT_VERIFY_OUTPUT={launcher_output}",
                    str(copied_verify_script),
                ],
                root,
            )
            support_manifest_missing_file_launcher_negative_ok = (
                not launcher_negative_ok
                and "missing" in launcher_negative_detail
                and "Traceback" not in launcher_negative_detail
            )
            support_manifest_missing_file_launcher_negative_detail = launcher_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_manifest_not_file_negative_") as tmp:
            tmp_path = Path(tmp)
            copied_bundle = tmp_path / "bundle"
            shutil.copytree(support_check_dir, copied_bundle)
            copied_manifest = copied_bundle / "BUNDLE_MANIFEST.csv"
            write_not_file_manifest(copied_manifest, copied_bundle)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_manifest_verify.py",
                    str(copied_bundle),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_manifest_not_file_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("not_file") not in {"", "0"}
                and "not_file" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_manifest_not_file_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"not_file={negative_summary.get('not_file', '')};"
                f"not_file_gap={int('not_file' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_verify_script = copied_bundle / "VERIFY_SUPPORT.sh"
            launcher_output = tmp_path / "verify_launcher"
            launcher_negative_ok, launcher_negative_detail = shell_check(
                [
                    "env",
                    f"LOLG_HD_SUPPORT_VERIFY_OUTPUT={launcher_output}",
                    str(copied_verify_script),
                ],
                root,
            )
            support_manifest_not_file_launcher_negative_ok = (
                not launcher_negative_ok
                and "not_file" in launcher_negative_detail
                and "Traceback" not in launcher_negative_detail
            )
            support_manifest_not_file_launcher_negative_detail = launcher_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_manifest_unexpected_file_negative_") as tmp:
            tmp_path = Path(tmp)
            copied_bundle = tmp_path / "bundle"
            shutil.copytree(support_check_dir, copied_bundle)
            (copied_bundle / "unexpected.txt").write_text("unexpected support file\n", encoding="utf-8")
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_manifest_verify.py",
                    str(copied_bundle),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_manifest_unexpected_file_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("unexpected") not in {"", "0"}
                and "unexpected_file" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_manifest_unexpected_file_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"unexpected={negative_summary.get('unexpected', '')};"
                f"unexpected_gap={int('unexpected_file' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_verify_script = copied_bundle / "VERIFY_SUPPORT.sh"
            launcher_output = tmp_path / "verify_launcher"
            launcher_negative_ok, launcher_negative_detail = shell_check(
                [
                    "env",
                    f"LOLG_HD_SUPPORT_VERIFY_OUTPUT={launcher_output}",
                    str(copied_verify_script),
                ],
                root,
            )
            support_manifest_unexpected_file_launcher_negative_ok = (
                not launcher_negative_ok
                and "unexpected_file" in launcher_negative_detail
                and "Traceback" not in launcher_negative_detail
            )
            support_manifest_unexpected_file_launcher_negative_detail = launcher_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_manifest_duplicate_path_negative_") as tmp:
            tmp_path = Path(tmp)
            copied_bundle = tmp_path / "bundle"
            shutil.copytree(support_check_dir, copied_bundle)
            copied_manifest = copied_bundle / "BUNDLE_MANIFEST.csv"
            write_duplicate_path_manifest(copied_manifest)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_manifest_verify.py",
                    str(copied_bundle),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_manifest_duplicate_path_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("duplicates") not in {"", "0"}
                and "duplicate_path" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_manifest_duplicate_path_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"duplicates={negative_summary.get('duplicates', '')};"
                f"duplicate_gap={int('duplicate_path' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_verify_script = copied_bundle / "VERIFY_SUPPORT.sh"
            launcher_output = tmp_path / "verify_launcher"
            launcher_negative_ok, launcher_negative_detail = shell_check(
                [
                    "env",
                    f"LOLG_HD_SUPPORT_VERIFY_OUTPUT={launcher_output}",
                    str(copied_verify_script),
                ],
                root,
            )
            support_manifest_duplicate_path_launcher_negative_ok = (
                not launcher_negative_ok
                and "duplicate_path" in launcher_negative_detail
                and "Traceback" not in launcher_negative_detail
            )
            support_manifest_duplicate_path_launcher_negative_detail = launcher_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_manifest_png_entry_negative_") as tmp:
            tmp_path = Path(tmp)
            copied_bundle = tmp_path / "bundle"
            shutil.copytree(support_check_dir, copied_bundle)
            copied_manifest = copied_bundle / "BUNDLE_MANIFEST.csv"
            write_png_entry_manifest(copied_manifest, copied_bundle)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_manifest_verify.py",
                    str(copied_bundle),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_manifest_png_entry_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("png_entries") not in {"", "0"}
                and "png_entry" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_manifest_png_entry_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"png_entries={negative_summary.get('png_entries', '')};"
                f"png_gap={int('png_entry' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_verify_script = copied_bundle / "VERIFY_SUPPORT.sh"
            launcher_output = tmp_path / "verify_launcher"
            launcher_negative_ok, launcher_negative_detail = shell_check(
                [
                    "env",
                    f"LOLG_HD_SUPPORT_VERIFY_OUTPUT={launcher_output}",
                    str(copied_verify_script),
                ],
                root,
            )
            support_manifest_png_entry_launcher_negative_ok = (
                not launcher_negative_ok
                and "png_entry" in launcher_negative_detail
                and "Traceback" not in launcher_negative_detail
            )
            support_manifest_png_entry_launcher_negative_detail = launcher_negative_detail
    support_archive_verify_ok, support_archive_verify_detail = shell_check(
        [
            "python3",
            "tools/lolg_hd_support_archive_verify.py",
            str(support_check_archive),
            "-o",
            "output/hd_support_archive_verify_check",
        ],
        root,
    )
    support_archive_verify_summary = read_csv_first(Path("output/hd_support_archive_verify_check/summary.csv"))
    support_archive_companion_ok, support_archive_companion_detail = shell_check(
        [str(support_check_archive_verify_script)],
        root,
    )
    support_archive_companion_copy_ok = False
    support_archive_companion_copy_detail = "not_run"
    support_archive_artifacts_negative_ok = False
    support_archive_artifacts_negative_detail = "not_run"
    support_archive_companion_negative_ok = False
    support_archive_companion_negative_detail = "not_run"
    support_archive_artifacts_extra_field_negative_ok = False
    support_archive_artifacts_extra_field_negative_detail = "not_run"
    support_archive_artifacts_extra_field_companion_negative_ok = False
    support_archive_artifacts_extra_field_companion_negative_detail = "not_run"
    support_archive_artifacts_duplicate_field_negative_ok = False
    support_archive_artifacts_duplicate_field_negative_detail = "not_run"
    support_archive_artifacts_duplicate_field_companion_negative_ok = False
    support_archive_artifacts_duplicate_field_companion_negative_detail = "not_run"
    support_archive_artifacts_duplicate_path_negative_ok = False
    support_archive_artifacts_duplicate_path_negative_detail = "not_run"
    support_archive_artifacts_duplicate_path_companion_negative_ok = False
    support_archive_artifacts_duplicate_path_companion_negative_detail = "not_run"
    support_archive_artifacts_missing_field_negative_ok = False
    support_archive_artifacts_missing_field_negative_detail = "not_run"
    support_archive_artifacts_missing_field_companion_negative_ok = False
    support_archive_artifacts_missing_field_companion_negative_detail = "not_run"
    support_archive_artifacts_missing_row_negative_ok = False
    support_archive_artifacts_missing_row_negative_detail = "not_run"
    support_archive_artifacts_missing_row_companion_negative_ok = False
    support_archive_artifacts_missing_row_companion_negative_detail = "not_run"
    support_archive_artifacts_missing_file_negative_ok = False
    support_archive_artifacts_missing_file_negative_detail = "not_run"
    support_archive_artifacts_missing_file_companion_negative_ok = False
    support_archive_artifacts_missing_file_companion_negative_detail = "not_run"
    support_archive_verify_script_missing_file_negative_ok = False
    support_archive_verify_script_missing_file_negative_detail = "not_run"
    support_archive_verify_script_missing_file_companion_negative_ok = False
    support_archive_verify_script_missing_file_companion_negative_detail = "not_run"
    support_archive_unsafe_tar_negative_ok = False
    support_archive_unsafe_tar_negative_detail = "not_run"
    support_archive_unsafe_tar_companion_negative_ok = False
    support_archive_unsafe_tar_companion_negative_detail = "not_run"
    support_archive_unsupported_tar_negative_ok = False
    support_archive_unsupported_tar_negative_detail = "not_run"
    support_archive_unsupported_tar_companion_negative_ok = False
    support_archive_unsupported_tar_companion_negative_detail = "not_run"
    support_archive_top_level_name_negative_ok = False
    support_archive_top_level_name_negative_detail = "not_run"
    support_archive_top_level_name_companion_negative_ok = False
    support_archive_top_level_name_companion_negative_detail = "not_run"
    support_archive_multi_top_level_negative_ok = False
    support_archive_multi_top_level_negative_detail = "not_run"
    support_archive_multi_top_level_companion_negative_ok = False
    support_archive_multi_top_level_companion_negative_detail = "not_run"
    support_archive_empty_negative_ok = False
    support_archive_empty_negative_detail = "not_run"
    support_archive_empty_companion_negative_ok = False
    support_archive_empty_companion_negative_detail = "not_run"
    support_archive_artifacts_size_negative_ok = False
    support_archive_artifacts_size_negative_detail = "not_run"
    support_archive_artifacts_size_companion_negative_ok = False
    support_archive_artifacts_size_companion_negative_detail = "not_run"
    support_archive_artifacts_sha256_negative_ok = False
    support_archive_artifacts_sha256_negative_detail = "not_run"
    support_archive_artifacts_sha256_companion_negative_ok = False
    support_archive_artifacts_sha256_companion_negative_detail = "not_run"
    support_archive_artifacts_executable_negative_ok = False
    support_archive_artifacts_executable_negative_detail = "not_run"
    support_archive_artifacts_executable_companion_negative_ok = False
    support_archive_artifacts_executable_companion_negative_detail = "not_run"
    support_archive_artifacts_path_negative_ok = False
    support_archive_artifacts_path_negative_detail = "not_run"
    support_archive_artifacts_path_companion_negative_ok = False
    support_archive_artifacts_path_companion_negative_detail = "not_run"
    support_archive_artifacts_unsafe_path_negative_ok = False
    support_archive_artifacts_unsafe_path_negative_detail = "not_run"
    support_archive_artifacts_unsafe_path_companion_negative_ok = False
    support_archive_artifacts_unsafe_path_companion_negative_detail = "not_run"
    support_archive_artifacts_nonportable_path_negative_ok = False
    support_archive_artifacts_nonportable_path_negative_detail = "not_run"
    support_archive_artifacts_nonportable_path_companion_negative_ok = False
    support_archive_artifacts_nonportable_path_companion_negative_detail = "not_run"
    support_archive_artifacts_field_format_negative_ok = False
    support_archive_artifacts_field_format_negative_detail = "not_run"
    support_archive_artifacts_field_format_companion_negative_ok = False
    support_archive_artifacts_field_format_companion_negative_detail = "not_run"
    support_archive_checksum_missing_file_negative_ok = False
    support_archive_checksum_missing_file_negative_detail = "not_run"
    support_archive_checksum_missing_file_companion_negative_ok = False
    support_archive_checksum_missing_file_companion_negative_detail = "not_run"
    support_archive_checksum_negative_ok = False
    support_archive_checksum_negative_detail = "not_run"
    support_archive_checksum_companion_negative_ok = False
    support_archive_checksum_companion_negative_detail = "not_run"
    support_archive_checksum_name_negative_ok = False
    support_archive_checksum_name_negative_detail = "not_run"
    support_archive_checksum_name_companion_negative_ok = False
    support_archive_checksum_name_companion_negative_detail = "not_run"
    support_archive_checksum_archive_path_negative_ok = False
    support_archive_checksum_archive_path_negative_detail = "not_run"
    support_archive_checksum_archive_path_companion_negative_ok = False
    support_archive_checksum_archive_path_companion_negative_detail = "not_run"
    support_archive_checksum_format_negative_ok = False
    support_archive_checksum_format_negative_detail = "not_run"
    support_archive_checksum_format_companion_negative_ok = False
    support_archive_checksum_format_companion_negative_detail = "not_run"
    support_archive_checksum_extra_field_negative_ok = False
    support_archive_checksum_extra_field_negative_detail = "not_run"
    support_archive_checksum_extra_field_companion_negative_ok = False
    support_archive_checksum_extra_field_companion_negative_detail = "not_run"
    support_archive_checksum_line_count_negative_ok = False
    support_archive_checksum_line_count_negative_detail = "not_run"
    support_archive_checksum_line_count_companion_negative_ok = False
    support_archive_checksum_line_count_companion_negative_detail = "not_run"
    support_archive_summary_missing_file_negative_ok = False
    support_archive_summary_missing_file_negative_detail = "not_run"
    support_archive_summary_missing_file_companion_negative_ok = False
    support_archive_summary_missing_file_companion_negative_detail = "not_run"
    support_archive_summary_negative_ok = False
    support_archive_summary_negative_detail = "not_run"
    support_archive_summary_companion_negative_ok = False
    support_archive_summary_companion_negative_detail = "not_run"
    support_archive_summary_duplicate_key_negative_ok = False
    support_archive_summary_duplicate_key_negative_detail = "not_run"
    support_archive_summary_duplicate_key_companion_negative_ok = False
    support_archive_summary_duplicate_key_companion_negative_detail = "not_run"
    support_archive_summary_malformed_line_negative_ok = False
    support_archive_summary_malformed_line_negative_detail = "not_run"
    support_archive_summary_malformed_line_companion_negative_ok = False
    support_archive_summary_malformed_line_companion_negative_detail = "not_run"
    support_archive_summary_missing_key_negative_ok = False
    support_archive_summary_missing_key_negative_detail = "not_run"
    support_archive_summary_missing_key_companion_negative_ok = False
    support_archive_summary_missing_key_companion_negative_detail = "not_run"
    support_archive_summary_version_negative_ok = False
    support_archive_summary_version_negative_detail = "not_run"
    support_archive_summary_version_companion_negative_ok = False
    support_archive_summary_version_companion_negative_detail = "not_run"
    support_archive_summary_timestamp_negative_ok = False
    support_archive_summary_timestamp_negative_detail = "not_run"
    support_archive_summary_timestamp_companion_negative_ok = False
    support_archive_summary_timestamp_companion_negative_detail = "not_run"
    support_archive_summary_archive_name_negative_ok = False
    support_archive_summary_archive_name_negative_detail = "not_run"
    support_archive_summary_archive_name_companion_negative_ok = False
    support_archive_summary_archive_name_companion_negative_detail = "not_run"
    support_archive_summary_size_negative_ok = False
    support_archive_summary_size_negative_detail = "not_run"
    support_archive_summary_size_companion_negative_ok = False
    support_archive_summary_size_companion_negative_detail = "not_run"
    support_archive_summary_sha256_negative_ok = False
    support_archive_summary_sha256_negative_detail = "not_run"
    support_archive_summary_sha256_companion_negative_ok = False
    support_archive_summary_sha256_companion_negative_detail = "not_run"
    support_archive_summary_sha256_file_negative_ok = False
    support_archive_summary_sha256_file_negative_detail = "not_run"
    support_archive_summary_sha256_file_companion_negative_ok = False
    support_archive_summary_sha256_file_companion_negative_detail = "not_run"
    support_archive_summary_bundle_dir_negative_ok = False
    support_archive_summary_bundle_dir_negative_detail = "not_run"
    support_archive_summary_bundle_dir_companion_negative_ok = False
    support_archive_summary_bundle_dir_companion_negative_detail = "not_run"
    if (
        support_check_archive.is_file()
        and support_check_archive_sha256.is_file()
        and support_check_archive_summary.is_file()
        and support_check_archive_verify_script.is_file()
        and support_check_archive_artifacts.is_file()
    ):
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_copy_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            support_archive_companion_copy_ok, support_archive_companion_copy_detail = shell_check(
                [str(copied_script)],
                root,
            )
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_artifacts_missing_file_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_artifacts = tmp_path / support_check_archive_artifacts.name
            copied_artifacts.unlink()
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_artifacts_missing_file_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and "artifacts_missing" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_artifacts_missing_file_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"missing_gap={int('artifacts_missing' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_artifacts_missing_file_companion_negative_ok = (
                not companion_negative_ok
                and "artifacts_missing=" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_artifacts_missing_file_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_verify_script_missing_file_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            copied_script.unlink()
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            artifact_mismatch_issue = f"artifact_mismatch={support_check_archive_verify_script.name}"
            support_archive_verify_script_missing_file_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("artifacts_status") == "gap"
                and artifact_mismatch_issue in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_verify_script_missing_file_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"artifacts={negative_summary.get('artifacts_status', '')};"
                f"artifact_gap={int(artifact_mismatch_issue in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_verify_script_missing_file_companion_negative_ok = (
                not companion_negative_ok
                and "FileNotFoundError" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_verify_script_missing_file_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_unsafe_tar_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_archive = tmp_path / support_check_archive.name
            copied_checksum = tmp_path / support_check_archive_sha256.name
            copied_summary = tmp_path / support_check_archive_summary.name
            copied_script = tmp_path / support_check_archive_verify_script.name
            copied_artifacts = tmp_path / support_check_archive_artifacts.name
            write_consistent_unsafe_archive(
                copied_archive,
                copied_checksum,
                copied_summary,
                copied_script,
                copied_artifacts,
            )
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(copied_archive),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_unsafe_tar_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("safe_paths") == "0"
                and "../unsafe.txt" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_unsafe_tar_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"safe_paths={negative_summary.get('safe_paths', '')};"
                f"unsafe_gap={int('../unsafe.txt' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_unsafe_tar_companion_negative_ok = (
                not companion_negative_ok
                and "unsafe_tar_paths" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_unsafe_tar_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_unsupported_tar_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_archive = tmp_path / support_check_archive.name
            copied_checksum = tmp_path / support_check_archive_sha256.name
            copied_summary = tmp_path / support_check_archive_summary.name
            copied_script = tmp_path / support_check_archive_verify_script.name
            copied_artifacts = tmp_path / support_check_archive_artifacts.name
            write_consistent_unsupported_archive(
                copied_archive,
                copied_checksum,
                copied_summary,
                copied_script,
                copied_artifacts,
            )
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(copied_archive),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_unsupported_tar_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("supported_types") == "0"
                and "unsupported_link" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_unsupported_tar_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"supported_types={negative_summary.get('supported_types', '')};"
                f"unsupported_gap={int('unsupported_link' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_unsupported_tar_companion_negative_ok = (
                not companion_negative_ok
                and "unsupported_tar_members" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_unsupported_tar_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_top_level_name_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_archive = tmp_path / support_check_archive.name
            copied_checksum = tmp_path / support_check_archive_sha256.name
            copied_summary = tmp_path / support_check_archive_summary.name
            copied_script = tmp_path / support_check_archive_verify_script.name
            copied_artifacts = tmp_path / support_check_archive_artifacts.name
            write_consistent_wrong_top_level_archive(
                copied_archive,
                copied_checksum,
                copied_summary,
                copied_script,
                copied_artifacts,
            )
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(copied_archive),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_top_level_name_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("top_level") == "wrong_support_bundle"
                and "top_level_name_mismatch" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_top_level_name_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"top_level={negative_summary.get('top_level', '')};"
                f"top_gap={int('top_level_name_mismatch' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_top_level_name_companion_negative_ok = (
                not companion_negative_ok
                and "top_level_name_mismatch" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_top_level_name_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_multi_top_level_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_archive = tmp_path / support_check_archive.name
            copied_checksum = tmp_path / support_check_archive_sha256.name
            copied_summary = tmp_path / support_check_archive_summary.name
            copied_script = tmp_path / support_check_archive_verify_script.name
            copied_artifacts = tmp_path / support_check_archive_artifacts.name
            write_consistent_multi_top_level_archive(
                copied_archive,
                copied_checksum,
                copied_summary,
                copied_script,
                copied_artifacts,
            )
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(copied_archive),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_multi_top_level_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("single_top_level_status") == "gap"
                and "expected_single_top_level" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_multi_top_level_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"single_top_level={negative_summary.get('single_top_level_status', '')};"
                f"single_gap={int('expected_single_top_level' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_multi_top_level_companion_negative_ok = (
                not companion_negative_ok
                and "top_level_mismatch" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_multi_top_level_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_empty_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_archive = tmp_path / support_check_archive.name
            copied_checksum = tmp_path / support_check_archive_sha256.name
            copied_summary = tmp_path / support_check_archive_summary.name
            copied_script = tmp_path / support_check_archive_verify_script.name
            copied_artifacts = tmp_path / support_check_archive_artifacts.name
            write_consistent_empty_archive(
                copied_archive,
                copied_checksum,
                copied_summary,
                copied_script,
                copied_artifacts,
            )
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(copied_archive),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_empty_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("members") == "0"
                and "archive_empty" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_empty_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"members={negative_summary.get('members', '')};"
                f"empty_gap={int('archive_empty' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_empty_companion_negative_ok = (
                not companion_negative_ok
                and "archive_empty" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_empty_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_artifacts = tmp_path / support_check_archive_artifacts.name
            write_row_width_broken_artifacts(support_check_archive_artifacts, copied_artifacts)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_artifacts_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("artifacts_status") == "gap"
                and "artifacts_row_width_mismatch" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_artifacts_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"artifacts={negative_summary.get('artifacts_status', '')};"
                f"row_width_gap={int('artifacts_row_width_mismatch' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_companion_negative_ok = (
                not companion_negative_ok
                and "artifacts_row_width_mismatch" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_artifacts_schema_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_artifacts = tmp_path / support_check_archive_artifacts.name
            write_extra_field_artifacts(support_check_archive_artifacts, copied_artifacts)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_artifacts_extra_field_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("artifacts_status") == "gap"
                and negative_summary.get("artifacts_schema_status") == "gap"
                and "artifacts_schema_mismatch" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_artifacts_extra_field_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"artifacts={negative_summary.get('artifacts_status', '')};"
                f"schema={negative_summary.get('artifacts_schema_status', '')};"
                f"schema_gap={int('artifacts_schema_mismatch' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_artifacts_extra_field_companion_negative_ok = (
                not companion_negative_ok
                and "artifacts_schema_mismatch" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_artifacts_extra_field_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_artifacts_duplicate_field_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_artifacts = tmp_path / support_check_archive_artifacts.name
            write_duplicate_field_artifacts(support_check_archive_artifacts, copied_artifacts)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_artifacts_duplicate_field_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("artifacts_status") == "gap"
                and negative_summary.get("artifacts_duplicate_fields_status") == "gap"
                and "artifacts_duplicate_fields" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_artifacts_duplicate_field_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"artifacts={negative_summary.get('artifacts_status', '')};"
                f"duplicates={negative_summary.get('artifacts_duplicate_fields_status', '')};"
                f"duplicate_gap={int('artifacts_duplicate_fields' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_artifacts_duplicate_field_companion_negative_ok = (
                not companion_negative_ok
                and "artifacts_duplicate_fields:path" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_artifacts_duplicate_field_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_artifacts_duplicate_path_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_artifacts = tmp_path / support_check_archive_artifacts.name
            write_duplicate_path_artifacts(support_check_archive_artifacts, copied_artifacts)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_artifacts_duplicate_path_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("artifacts_status") == "gap"
                and negative_summary.get("artifacts_duplicate_paths_status") == "gap"
                and "artifacts_duplicate_paths" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_artifacts_duplicate_path_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"artifacts={negative_summary.get('artifacts_status', '')};"
                f"duplicates={negative_summary.get('artifacts_duplicate_paths_status', '')};"
                f"duplicate_gap={int('artifacts_duplicate_paths' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_artifacts_duplicate_path_companion_negative_ok = (
                not companion_negative_ok
                and f"artifacts_duplicate_paths:{support_check_archive.name}" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_artifacts_duplicate_path_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_artifacts_missing_schema_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_artifacts = tmp_path / support_check_archive_artifacts.name
            write_missing_field_artifacts(support_check_archive_artifacts, copied_artifacts)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_artifacts_missing_field_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("artifacts_status") == "gap"
                and negative_summary.get("artifacts_schema_status") == "gap"
                and "artifacts_schema_mismatch" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_artifacts_missing_field_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"artifacts={negative_summary.get('artifacts_status', '')};"
                f"schema={negative_summary.get('artifacts_schema_status', '')};"
                f"schema_gap={int('artifacts_schema_mismatch' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_artifacts_missing_field_companion_negative_ok = (
                not companion_negative_ok
                and "artifacts_schema_mismatch" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_artifacts_missing_field_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_artifacts_missing_row_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_artifacts = tmp_path / support_check_archive_artifacts.name
            write_missing_row_artifacts(support_check_archive_artifacts, copied_artifacts)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_artifacts_missing_row_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("artifacts_status") == "gap"
                and negative_summary.get("artifacts_count_status") == "gap"
                and "artifacts_count_mismatch" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_artifacts_missing_row_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"artifacts={negative_summary.get('artifacts_status', '')};"
                f"count={negative_summary.get('artifacts_count_status', '')};"
                f"count_gap={int('artifacts_count_mismatch' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_artifacts_missing_row_companion_negative_ok = (
                not companion_negative_ok
                and "artifacts_count_mismatch" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_artifacts_missing_row_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_artifacts_field_format_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_artifacts = tmp_path / support_check_archive_artifacts.name
            write_invalid_artifact_fields(
                support_check_archive_artifacts,
                copied_artifacts,
                support_check_archive.name,
            )
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_artifacts_field_format_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("artifacts_status") == "gap"
                and negative_summary.get("artifacts_field_format_status") == "gap"
                and "artifacts_field_format_mismatch" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_artifacts_field_format_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"artifacts={negative_summary.get('artifacts_status', '')};"
                f"field_format={negative_summary.get('artifacts_field_format_status', '')};"
                f"field_format_gap={int('artifacts_field_format_mismatch' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_artifacts_field_format_companion_negative_ok = (
                not companion_negative_ok
                and "artifacts_field_format_mismatch:" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_artifacts_field_format_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_artifacts_size_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_artifacts = tmp_path / support_check_archive_artifacts.name
            write_bad_artifact_size(
                support_check_archive_artifacts,
                copied_artifacts,
                support_check_archive.name,
            )
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            artifact_mismatch_issue = f"artifact_mismatch={support_check_archive.name}"
            support_archive_artifacts_size_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("artifacts_status") == "gap"
                and artifact_mismatch_issue in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_artifacts_size_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"artifacts={negative_summary.get('artifacts_status', '')};"
                f"artifact_gap={int(artifact_mismatch_issue in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            companion_artifact_mismatch_issue = f"artifact_size_mismatch={support_check_archive.name}"
            support_archive_artifacts_size_companion_negative_ok = (
                not companion_negative_ok
                and companion_artifact_mismatch_issue in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_artifacts_size_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_artifacts_sha256_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_artifacts = tmp_path / support_check_archive_artifacts.name
            write_bad_artifact_sha256(
                support_check_archive_artifacts,
                copied_artifacts,
                support_check_archive.name,
            )
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            artifact_mismatch_issue = f"artifact_mismatch={support_check_archive.name}"
            support_archive_artifacts_sha256_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("artifacts_status") == "gap"
                and artifact_mismatch_issue in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_artifacts_sha256_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"artifacts={negative_summary.get('artifacts_status', '')};"
                f"artifact_gap={int(artifact_mismatch_issue in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            companion_artifact_mismatch_issue = f"artifact_sha256_mismatch={support_check_archive.name}"
            support_archive_artifacts_sha256_companion_negative_ok = (
                not companion_negative_ok
                and companion_artifact_mismatch_issue in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_artifacts_sha256_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_artifacts_executable_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_artifacts = tmp_path / support_check_archive_artifacts.name
            write_bad_artifact_executable(
                support_check_archive_artifacts,
                copied_artifacts,
                support_check_archive_verify_script.name,
            )
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            artifact_mismatch_issue = f"artifact_mismatch={support_check_archive_verify_script.name}"
            support_archive_artifacts_executable_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("artifacts_status") == "gap"
                and artifact_mismatch_issue in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_artifacts_executable_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"artifacts={negative_summary.get('artifacts_status', '')};"
                f"artifact_gap={int(artifact_mismatch_issue in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            companion_artifact_mismatch_issue = (
                f"artifact_executable_mismatch={support_check_archive_verify_script.name}"
            )
            support_archive_artifacts_executable_companion_negative_ok = (
                not companion_negative_ok
                and companion_artifact_mismatch_issue in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_artifacts_executable_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_artifacts_path_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_artifacts = tmp_path / support_check_archive_artifacts.name
            write_bad_artifact_path(
                support_check_archive_artifacts,
                copied_artifacts,
                support_check_archive.name,
            )
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_artifacts_path_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("artifacts_status") == "gap"
                and negative_summary.get("artifacts_paths_status") == "gap"
                and "artifacts_paths_mismatch" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_artifacts_path_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"artifacts={negative_summary.get('artifacts_status', '')};"
                f"paths={negative_summary.get('artifacts_paths_status', '')};"
                f"paths_gap={int('artifacts_paths_mismatch' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_artifacts_path_companion_negative_ok = (
                not companion_negative_ok
                and "artifacts_paths_mismatch" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_artifacts_path_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_artifacts_unsafe_path_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_artifacts = tmp_path / support_check_archive_artifacts.name
            write_unsafe_artifact_path(
                support_check_archive_artifacts,
                copied_artifacts,
                support_check_archive.name,
            )
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_artifacts_unsafe_path_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("artifacts_status") == "gap"
                and negative_summary.get("artifacts_safe_paths_status") == "gap"
                and "artifacts_unsafe_paths" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_artifacts_unsafe_path_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"artifacts={negative_summary.get('artifacts_status', '')};"
                f"safe_paths={negative_summary.get('artifacts_safe_paths_status', '')};"
                f"safe_paths_gap={int('artifacts_unsafe_paths' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_artifacts_unsafe_path_companion_negative_ok = (
                not companion_negative_ok
                and "artifacts_unsafe_paths:../bad.tar.gz" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_artifacts_unsafe_path_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_artifacts_nonportable_path_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_artifacts = tmp_path / support_check_archive_artifacts.name
            write_nonportable_artifact_path(
                support_check_archive_artifacts,
                copied_artifacts,
                support_check_archive.name,
            )
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_artifacts_nonportable_path_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("artifacts_status") == "gap"
                and negative_summary.get("artifacts_safe_paths_status") == "gap"
                and "artifacts_unsafe_paths" in negative_checks
                and "bad artifact.tar.gz" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_artifacts_nonportable_path_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"artifacts={negative_summary.get('artifacts_status', '')};"
                f"safe_paths={negative_summary.get('artifacts_safe_paths_status', '')};"
                f"safe_paths_gap={int('artifacts_unsafe_paths' in negative_checks)};"
                f"bad_name_gap={int('bad artifact.tar.gz' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_artifacts_nonportable_path_companion_negative_ok = (
                not companion_negative_ok
                and "artifacts_unsafe_paths:bad artifact.tar.gz" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_artifacts_nonportable_path_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_checksum_missing_file_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_checksum = tmp_path / support_check_archive_sha256.name
            copied_checksum.unlink()
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_checksum_missing_file_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and "checksum_missing" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_checksum_missing_file_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"missing_gap={int('checksum_missing' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_checksum_missing_file_companion_negative_ok = (
                not companion_negative_ok
                and "checksum_missing=" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_checksum_missing_file_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_checksum_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_checksum = tmp_path / support_check_archive_sha256.name
            write_bad_checksum(copied_checksum, support_check_archive.name)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_checksum_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("checksum_status") == "gap"
                and "archive_sha256_mismatch" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_checksum_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"checksum={negative_summary.get('checksum_status', '')};"
                f"sha_gap={int('archive_sha256_mismatch' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_checksum_companion_negative_ok = (
                not companion_negative_ok
                and "archive_sha256_mismatch" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_checksum_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_checksum_name_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_checksum = tmp_path / support_check_archive_sha256.name
            write_bad_checksum_archive_name(copied_checksum)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_checksum_name_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and "checksum_archive_name_mismatch" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_checksum_name_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"name_gap={int('checksum_archive_name_mismatch' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_checksum_name_companion_negative_ok = (
                not companion_negative_ok
                and "checksum_archive_name_mismatch" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_checksum_name_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_checksum_archive_path_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_checksum = tmp_path / support_check_archive_sha256.name
            write_checksum_archive_path(copied_checksum, support_check_archive.name)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_checksum_archive_path_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and "checksum_archive_name_mismatch" in negative_checks
                and "subdir/" + support_check_archive.name in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_checksum_archive_path_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"name_gap={int('checksum_archive_name_mismatch' in negative_checks)};"
                f"path_gap={int(('subdir/' + support_check_archive.name) in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_checksum_archive_path_companion_negative_ok = (
                not companion_negative_ok
                and "checksum_archive_name_mismatch" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_checksum_archive_path_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_checksum_format_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_checksum = tmp_path / support_check_archive_sha256.name
            write_bad_checksum_format(copied_checksum, support_check_archive.name)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_checksum_format_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and "checksum_format_invalid" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_checksum_format_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"format_gap={int('checksum_format_invalid' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_checksum_format_companion_negative_ok = (
                not companion_negative_ok
                and "checksum_format_invalid" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_checksum_format_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_checksum_extra_field_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_checksum = tmp_path / support_check_archive_sha256.name
            write_extra_checksum_field(copied_checksum)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_checksum_extra_field_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and "checksum_format_invalid" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_checksum_extra_field_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"format_gap={int('checksum_format_invalid' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_checksum_extra_field_companion_negative_ok = (
                not companion_negative_ok
                and "checksum_format_invalid" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_checksum_extra_field_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_checksum_line_count_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_checksum = tmp_path / support_check_archive_sha256.name
            write_extra_checksum_line(copied_checksum, support_check_archive.name)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_checksum_line_count_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("checksum_line_count") == "2"
                and "checksum_line_count_mismatch" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_checksum_line_count_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"line_count={negative_summary.get('checksum_line_count', '')};"
                f"line_gap={int('checksum_line_count_mismatch' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_checksum_line_count_companion_negative_ok = (
                not companion_negative_ok
                and "checksum_line_count_mismatch" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_checksum_line_count_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_summary_missing_file_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_summary = tmp_path / support_check_archive_summary.name
            copied_summary.unlink()
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_summary_missing_file_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and "archive_summary_missing" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_summary_missing_file_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"missing_gap={int('archive_summary_missing' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_summary_missing_file_companion_negative_ok = (
                not companion_negative_ok
                and "summary_missing=" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_summary_missing_file_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_summary_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_summary = tmp_path / support_check_archive_summary.name
            write_extra_key_summary(copied_summary)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_summary_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("archive_summary_status") == "gap"
                and negative_summary.get("archive_summary_schema_status") == "gap"
                and negative_summary.get("archive_summary_extra_keys") == "unexpected_key"
                and "archive_summary_schema_mismatch" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_summary_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"summary={negative_summary.get('archive_summary_status', '')};"
                f"schema={negative_summary.get('archive_summary_schema_status', '')};"
                f"extra={negative_summary.get('archive_summary_extra_keys', '')};"
                f"schema_gap={int('archive_summary_schema_mismatch' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_summary_companion_negative_ok = (
                not companion_negative_ok
                and "summary_schema_mismatch" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_summary_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_summary_duplicate_key_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_summary = tmp_path / support_check_archive_summary.name
            write_duplicate_key_summary(copied_summary)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_summary_duplicate_key_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("archive_summary_status") == "gap"
                and negative_summary.get("archive_summary_duplicate_keys") == "archive"
                and "archive_summary_duplicate_keys" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_summary_duplicate_key_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"summary={negative_summary.get('archive_summary_status', '')};"
                f"duplicates={negative_summary.get('archive_summary_duplicate_keys', '')};"
                f"duplicate_gap={int('archive_summary_duplicate_keys' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_summary_duplicate_key_companion_negative_ok = (
                not companion_negative_ok
                and "summary_duplicate_keys:archive" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_summary_duplicate_key_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_summary_malformed_line_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_summary = tmp_path / support_check_archive_summary.name
            write_malformed_line_summary(copied_summary)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_summary_malformed_line_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("archive_summary_status") == "gap"
                and negative_summary.get("archive_summary_malformed_lines") != ""
                and "archive_summary_malformed_lines" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_summary_malformed_line_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"summary={negative_summary.get('archive_summary_status', '')};"
                f"malformed={negative_summary.get('archive_summary_malformed_lines', '')};"
                f"malformed_gap={int('archive_summary_malformed_lines' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_summary_malformed_line_companion_negative_ok = (
                not companion_negative_ok
                and "summary_malformed_lines:" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_summary_malformed_line_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_summary_missing_key_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_summary = tmp_path / support_check_archive_summary.name
            write_missing_key_summary(copied_summary)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_summary_missing_key_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("archive_summary_status") == "gap"
                and negative_summary.get("archive_summary_schema_status") == "gap"
                and negative_summary.get("archive_summary_missing_keys") == "bundle_dir"
                and "archive_summary_schema_mismatch" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_summary_missing_key_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"summary={negative_summary.get('archive_summary_status', '')};"
                f"schema={negative_summary.get('archive_summary_schema_status', '')};"
                f"missing={negative_summary.get('archive_summary_missing_keys', '')};"
                f"schema_gap={int('archive_summary_schema_mismatch' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_summary_missing_key_companion_negative_ok = (
                not companion_negative_ok
                and "summary_schema_mismatch" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_summary_missing_key_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_summary_version_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_summary = tmp_path / support_check_archive_summary.name
            write_bad_version_summary(copied_summary)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_summary_version_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("archive_summary_status") == "gap"
                and "archive_summary_version_mismatch" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_summary_version_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"summary={negative_summary.get('archive_summary_status', '')};"
                f"version_gap={int('archive_summary_version_mismatch' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_summary_version_companion_negative_ok = (
                not companion_negative_ok
                and "summary_support_archive_summary_version_mismatch" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_summary_version_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_summary_timestamp_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_summary = tmp_path / support_check_archive_summary.name
            write_bad_timestamp_summary(copied_summary)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_summary_timestamp_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("archive_summary_status") == "gap"
                and "archive_summary_generated_utc_invalid" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_summary_timestamp_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"summary={negative_summary.get('archive_summary_status', '')};"
                f"timestamp_gap={int('archive_summary_generated_utc_invalid' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_summary_timestamp_companion_negative_ok = (
                not companion_negative_ok
                and "summary_generated_utc_invalid" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_summary_timestamp_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_summary_archive_name_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_summary = tmp_path / support_check_archive_summary.name
            write_bad_archive_name_summary(copied_summary)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_summary_archive_name_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("archive_summary_status") == "gap"
                and "archive_summary_archive_mismatch" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_summary_archive_name_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"summary={negative_summary.get('archive_summary_status', '')};"
                f"archive_gap={int('archive_summary_archive_mismatch' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_summary_archive_name_companion_negative_ok = (
                not companion_negative_ok
                and "summary_archive_mismatch" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_summary_archive_name_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_summary_size_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_summary = tmp_path / support_check_archive_summary.name
            write_bad_archive_size_summary(copied_summary)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_summary_size_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("archive_summary_status") == "gap"
                and "archive_summary_size_mismatch" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_summary_size_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"summary={negative_summary.get('archive_summary_status', '')};"
                f"size_gap={int('archive_summary_size_mismatch' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_summary_size_companion_negative_ok = (
                not companion_negative_ok
                and "summary_archive_size_mismatch" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_summary_size_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_summary_sha256_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_summary = tmp_path / support_check_archive_summary.name
            write_bad_archive_sha256_summary(copied_summary)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_summary_sha256_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("archive_summary_status") == "gap"
                and "archive_summary_sha256_mismatch" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_summary_sha256_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"summary={negative_summary.get('archive_summary_status', '')};"
                f"sha_gap={int('archive_summary_sha256_mismatch' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_summary_sha256_companion_negative_ok = (
                not companion_negative_ok
                and "summary_sha256_mismatch" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_summary_sha256_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_summary_sha256_file_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_summary = tmp_path / support_check_archive_summary.name
            write_bad_archive_sha256_file_summary(copied_summary)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_summary_sha256_file_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("archive_summary_status") == "gap"
                and "archive_summary_sha256_file_mismatch" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_summary_sha256_file_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"summary={negative_summary.get('archive_summary_status', '')};"
                f"sha_file_gap={int('archive_summary_sha256_file_mismatch' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_summary_sha256_file_companion_negative_ok = (
                not companion_negative_ok
                and "summary_sha256_file_mismatch" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_summary_sha256_file_companion_negative_detail = companion_negative_detail
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_summary_bundle_dir_negative_") as tmp:
            tmp_path = Path(tmp)
            copy_archive_external_files(
                tmp_path,
                support_check_archive,
                support_check_archive_sha256,
                support_check_archive_summary,
                support_check_archive_verify_script,
                support_check_archive_artifacts,
            )
            copied_summary = tmp_path / support_check_archive_summary.name
            write_bad_archive_bundle_dir_summary(copied_summary)
            negative_output = tmp_path / "verify"
            negative_ok, negative_detail = shell_check(
                [
                    "python3",
                    "tools/lolg_hd_support_archive_verify.py",
                    str(tmp_path / support_check_archive.name),
                    "-o",
                    str(negative_output),
                ],
                root,
            )
            negative_summary = read_csv_first(negative_output / "summary.csv")
            negative_checks = (negative_output / "checks.csv").read_text(
                encoding="utf-8",
                errors="replace",
            ) if (negative_output / "checks.csv").is_file() else ""
            support_archive_summary_bundle_dir_negative_ok = (
                not negative_ok
                and negative_summary.get("status") == "gap"
                and negative_summary.get("archive_summary_status") == "gap"
                and "archive_summary_bundle_dir_mismatch" in negative_checks
                and "Traceback" not in negative_detail
            )
            support_archive_summary_bundle_dir_negative_detail = (
                f"status={negative_summary.get('status', '')};"
                f"summary={negative_summary.get('archive_summary_status', '')};"
                f"bundle_gap={int('archive_summary_bundle_dir_mismatch' in negative_checks)};"
                f"traceback={int('Traceback' in negative_detail)};"
                f"detail={negative_detail}"
            )
            copied_script = tmp_path / support_check_archive_verify_script.name
            companion_negative_ok, companion_negative_detail = shell_check([str(copied_script)], root)
            support_archive_summary_bundle_dir_companion_negative_ok = (
                not companion_negative_ok
                and "summary_bundle_dir_mismatch" in companion_negative_detail
                and "Traceback" not in companion_negative_detail
            )
            support_archive_summary_bundle_dir_companion_negative_detail = companion_negative_detail
    add_check(
        checks,
        "support_bundle_sidecar_critical",
        pass_if(
            support_ok
            and support_check_archive.is_file()
            and support_check_archive_sha256.is_file()
            and support_check_archive_summary.is_file()
            and support_check_archive_verify_script.is_file()
            and support_check_archive_artifacts.is_file()
            and bool(support_check_archive_verify_script.stat().st_mode & 0o111)
            and len(support_archive_artifacts_rows) == 4
            and support_archive_artifacts_schema_ok
            and support_archive_artifacts_row_width_ok
            and support_archive_artifacts_paths_ok
            and support_sidecar_status.is_file()
            and support_locallng_result.is_file()
            and support_movies_result.is_file()
            and support_locallng_rendered.is_file()
            and support_movies_rendered.is_file()
            and len(support_locallng_rendered_rows) == 237
            and len(support_movies_rendered_rows) == 75
            and support_tool_status.is_file()
            and support_tool_release_check.is_file()
            and support_tool_sidecar_status.is_file()
            and support_tool_sidecar_index.is_file()
            and support_tool_support_manifest_verify.is_file()
            and support_tool_support_archive_verify.is_file()
            and support_tool_vqa_decode.is_file()
            and support_diagnostic.is_file()
            and support_readme.is_file()
            and support_summary.is_file()
            and support_bundle_manifest.is_file()
            and support_verify_script.is_file()
            and bool(support_verify_script.stat().st_mode & 0o111)
            and support_bundle_manifest_schema_ok
            and support_bundle_manifest_row_width_ok
            and len(support_bundle_manifest_rows) >= 30
            and len(support_bundle_manifest_matched_paths) == len(support_bundle_manifest_key_paths)
            and not support_bundle_manifest_pngs
            and support_bundle_manifest_verify_script_executable
            and support_index_archives.is_file()
            and support_index_entries.is_file()
            and len(support_locallng_index_rows) >= 1
            and len(support_movies_index_ids) == 28
            and "tools/lolg_vqa_decode.py" in support_diagnostic_text
            and "tools/lolg_hd_support_manifest_verify.py" in support_diagnostic_text
            and "tools/lolg_hd_support_archive_verify.py" in support_diagnostic_text
            and "pillow=present" in support_diagnostic_text
            and "sidecar_critical_full_ready" in support_readme_text
            and "BUNDLE_MANIFEST.csv" in support_readme_text
            and "VERIFY_SUPPORT.sh" in support_readme_text
            and "hd_support_bundle.tar.gz.artifacts.csv" in support_readme_text
            and "tools/lolg_hd_support_manifest_verify.py" in support_readme_text
            and "tools/lolg_hd_support_archive_verify.py" in support_readme_text
            and "SUPPORT_SUMMARY.txt" in support_readme_text
            and "reports/vqa_external_sidecar_index/entries.csv" in support_readme_text
            and "./LOLG_HD.sh sidecar-critical-warmup" in support_readme_text
            and "./LOLG_HD.sh verify-support" in support_readme_text
            and "./LOLG_HD.sh verify-support-archive" in support_readme_text
            and support_summary_current_or_stale_release_ok
            and support_summary_release_fields_ok
            and support_summary_values.get("manifest_verify") == "pass"
            and support_summary_values.get("resolution") == "pass"
            and "sidecar_critical_full_ready=1" in support_summary_text
            and "movies_ready=75/75" in support_summary_text
            and "locallng_rendered_rows=237" in support_summary_text
            and "movies_rendered_rows=75" in support_summary_text
            and support_manifest_verify_ok
            and support_manifest_verify_summary.get("status") == "pass"
            and support_manifest_verify_summary.get("manifest_schema") == "pass"
            and support_manifest_verify_summary.get("manifest_missing_fields") == ""
            and support_manifest_verify_summary.get("manifest_extra_fields") == ""
            and support_manifest_verify_summary.get("manifest_duplicate_fields") == ""
            and support_manifest_verify_summary.get("duplicates") == "0"
            and support_manifest_verify_summary.get("row_width_mismatch") == "0"
            and support_manifest_verify_summary.get("png_entries") == "0"
            and support_manifest_verify_summary.get("missing") == "0"
            and support_manifest_verify_summary.get("not_file") == "0"
            and support_manifest_verify_summary.get("size_mismatch") == "0"
            and support_manifest_verify_summary.get("size_invalid") == "0"
            and support_manifest_verify_summary.get("sha256_mismatch") == "0"
            and support_manifest_verify_summary.get("sha256_invalid") == "0"
            and support_manifest_verify_summary.get("executable_mismatch") == "0"
            and support_manifest_verify_summary.get("executable_invalid") == "0"
            and support_manifest_verify_summary.get("noncanonical_paths") == "0"
            and support_manifest_verify_summary.get("unexpected") == "0"
            and support_verify_script_ok
            and support_verify_script_summary.get("status") == "pass"
            and support_verify_script_summary.get("manifest_extra_fields") == ""
            and support_verify_script_summary.get("manifest_duplicate_fields") == ""
            and support_verify_script_summary.get("duplicates") == "0"
            and support_verify_script_summary.get("row_width_mismatch") == "0"
            and support_verify_script_summary.get("png_entries") == "0"
            and support_verify_script_summary.get("missing") == "0"
            and support_verify_script_summary.get("not_file") == "0"
            and support_verify_script_summary.get("size_mismatch") == "0"
            and support_verify_script_summary.get("size_invalid") == "0"
            and support_verify_script_summary.get("sha256_mismatch") == "0"
            and support_verify_script_summary.get("sha256_invalid") == "0"
            and support_verify_script_summary.get("noncanonical_paths") == "0"
            and support_verify_script_summary.get("unexpected") == "0"
            and support_archive_verify_ok
            and support_archive_verify_summary.get("status") == "pass"
            and support_archive_verify_summary.get("members") not in {"", "0"}
            and support_archive_verify_summary.get("top_level") == support_check_archive.stem.removesuffix(".tar")
            and support_archive_verify_summary.get("archive_not_empty_status") == "pass"
            and support_archive_verify_summary.get("single_top_level_status") == "pass"
            and support_archive_verify_summary.get("top_level_name_status") == "pass"
            and support_archive_verify_summary.get("safe_paths") == "1"
            and support_archive_verify_summary.get("supported_types") == "1"
            and support_archive_verify_summary.get("checksum_status") == "pass"
            and support_archive_verify_summary.get("checksum_line_count") == "1"
            and support_archive_verify_summary.get("archive_summary_status") == "pass"
            and support_archive_verify_summary.get("archive_summary_schema_status") == "pass"
            and support_archive_verify_summary.get("archive_summary_missing_keys") == ""
            and support_archive_verify_summary.get("archive_summary_extra_keys") == ""
            and support_archive_verify_summary.get("archive_summary_duplicate_keys") == ""
            and support_archive_verify_summary.get("archive_summary_malformed_lines") == ""
            and support_archive_verify_summary.get("artifacts_status") == "pass"
            and support_archive_verify_summary.get("artifacts_files") == "4"
            and support_archive_verify_summary.get("artifacts_schema_status") == "pass"
            and support_archive_verify_summary.get("artifacts_duplicate_fields_status") == "pass"
            and support_archive_verify_summary.get("artifacts_duplicate_paths_status") == "pass"
            and support_archive_verify_summary.get("artifacts_row_width_status") == "pass"
            and support_archive_verify_summary.get("artifacts_field_format_status") == "pass"
            and support_archive_verify_summary.get("artifacts_safe_paths_status") == "pass"
            and support_archive_verify_summary.get("artifacts_count_status") == "pass"
            and support_archive_verify_summary.get("artifacts_paths_status") == "pass"
            and support_archive_verify_summary.get("manifest_status") == "pass"
            and support_archive_verify_summary.get("launcher_status") == "pass"
            and support_archive_companion_ok
            and "support archive companion verify: pass" in support_archive_companion_detail
            and "summary=pass" in support_archive_companion_detail
            and "manifest=pass" in support_archive_companion_detail
            and "artifacts=pass" in support_archive_companion_detail
            and "artifact_duplicate_paths=pass" in support_archive_companion_detail
            and "artifact_field_format=pass" in support_archive_companion_detail
            and "artifact_safe_paths=pass" in support_archive_companion_detail
            and "archive_not_empty=pass" in support_archive_companion_detail
            and "single_top_level=pass" in support_archive_companion_detail
            and "top_level_name=pass" in support_archive_companion_detail
            and support_archive_companion_copy_ok
            and "support archive companion verify: pass" in support_archive_companion_copy_detail
            and "summary=pass" in support_archive_companion_copy_detail
            and "manifest=pass" in support_archive_companion_copy_detail
            and "artifacts=pass" in support_archive_companion_copy_detail
            and "artifact_duplicate_paths=pass" in support_archive_companion_copy_detail
            and "artifact_field_format=pass" in support_archive_companion_copy_detail
            and "artifact_safe_paths=pass" in support_archive_companion_copy_detail
            and "archive_not_empty=pass" in support_archive_companion_copy_detail
            and "single_top_level=pass" in support_archive_companion_copy_detail
            and "top_level_name=pass" in support_archive_companion_copy_detail
            and support_hd_status_summary.get("sidecar_critical_full_ready") in {"0", "1"}
            and '"critical_ready": true' in support_status_text
            and '"key": "LOCALLNG.MIX:fca4e133"' in support_status_text
            and '"key": "MOVIES.MIX:4d6efa8e"' in support_status_text
        ),
        (
            f"{support_detail};"
            f"archive={int(support_check_archive.is_file())};"
            f"archive_sha256={int(support_check_archive_sha256.is_file())};"
            f"archive_summary={int(support_check_archive_summary.is_file())};"
            f"archive_verify_script={int(support_check_archive_verify_script.is_file())};"
            f"archive_verify_script_executable={int(support_check_archive_verify_script.is_file() and bool(support_check_archive_verify_script.stat().st_mode & 0o111))};"
            f"archive_artifacts={int(support_check_archive_artifacts.is_file())};"
            f"archive_artifacts_rows={len(support_archive_artifacts_rows)};"
            f"archive_artifacts_schema={int(support_archive_artifacts_schema_ok)};"
            f"archive_artifacts_row_width={int(support_archive_artifacts_row_width_ok)};"
            f"archive_artifacts_paths={int(support_archive_artifacts_paths_ok)};"
            f"sidecar_status={int(support_sidecar_status.is_file())};"
            f"locallng_result={int(support_locallng_result.is_file())};"
            f"movies_result={int(support_movies_result.is_file())};"
            f"locallng_rendered={len(support_locallng_rendered_rows)};"
            f"movies_rendered={len(support_movies_rendered_rows)};"
            f"tool_status={int(support_tool_status.is_file())};"
            f"tool_release_check={int(support_tool_release_check.is_file())};"
            f"tool_sidecar_status={int(support_tool_sidecar_status.is_file())};"
            f"tool_sidecar_index={int(support_tool_sidecar_index.is_file())};"
            f"tool_support_manifest_verify={int(support_tool_support_manifest_verify.is_file())};"
            f"tool_support_archive_verify={int(support_tool_support_archive_verify.is_file())};"
            f"tool_vqa_decode={int(support_tool_vqa_decode.is_file())};"
            f"diagnostic={int(support_diagnostic.is_file())};"
            f"readme={int(support_readme.is_file())};"
            f"summary={int(support_summary.is_file())};"
            f"bundle_manifest={int(support_bundle_manifest.is_file())};"
            f"bundle_manifest_schema={int(support_bundle_manifest_schema_ok)};"
            f"bundle_manifest_duplicate_fields={','.join(support_bundle_manifest_duplicate_fields)};"
            f"bundle_manifest_row_width={int(support_bundle_manifest_row_width_ok)};"
            f"verify_script={int(support_verify_script.is_file())};"
            f"verify_script_executable={int(support_verify_script.is_file() and bool(support_verify_script.stat().st_mode & 0o111))};"
            f"bundle_manifest_rows={len(support_bundle_manifest_rows)};"
            f"bundle_manifest_pngs={len(support_bundle_manifest_pngs)};"
            f"bundle_manifest_key_paths={len(support_bundle_manifest_matched_paths)}/{len(support_bundle_manifest_key_paths)};"
            f"bundle_manifest_verify_script_executable={int(support_bundle_manifest_verify_script_executable)};"
            f"support_manifest_verify={int(support_manifest_verify_ok)};"
            f"support_manifest_status={support_manifest_verify_summary.get('status', '')};"
            f"support_manifest_schema={support_manifest_verify_summary.get('manifest_schema', '')};"
            f"support_manifest_missing_fields={support_manifest_verify_summary.get('manifest_missing_fields', '')};"
            f"support_manifest_extra_fields={support_manifest_verify_summary.get('manifest_extra_fields', '')};"
            f"support_manifest_duplicate_fields={support_manifest_verify_summary.get('manifest_duplicate_fields', '')};"
            f"support_manifest_duplicate_paths={support_manifest_verify_summary.get('duplicates', '')};"
            f"support_manifest_row_width_mismatch={support_manifest_verify_summary.get('row_width_mismatch', '')};"
            f"support_manifest_pngs={support_manifest_verify_summary.get('png_entries', '')};"
            f"support_manifest_missing={support_manifest_verify_summary.get('missing', '')};"
            f"support_manifest_not_file={support_manifest_verify_summary.get('not_file', '')};"
            f"support_manifest_size_mismatch={support_manifest_verify_summary.get('size_mismatch', '')};"
            f"support_manifest_size_invalid={support_manifest_verify_summary.get('size_invalid', '')};"
            f"support_manifest_sha256_mismatch={support_manifest_verify_summary.get('sha256_mismatch', '')};"
            f"support_manifest_sha256_invalid={support_manifest_verify_summary.get('sha256_invalid', '')};"
            f"support_manifest_executable_mismatch={support_manifest_verify_summary.get('executable_mismatch', '')};"
            f"support_manifest_executable_invalid={support_manifest_verify_summary.get('executable_invalid', '')};"
            f"support_manifest_noncanonical_paths={support_manifest_verify_summary.get('noncanonical_paths', '')};"
            f"support_manifest_unexpected={support_manifest_verify_summary.get('unexpected', '')};"
            f"verify_script_run={int(support_verify_script_ok)};"
            f"verify_script_status={support_verify_script_summary.get('status', '')};"
            f"verify_script_extra_fields={support_verify_script_summary.get('manifest_extra_fields', '')};"
            f"verify_script_duplicate_fields={support_verify_script_summary.get('manifest_duplicate_fields', '')};"
            f"verify_script_duplicate_paths={support_verify_script_summary.get('duplicates', '')};"
            f"verify_script_row_width_mismatch={support_verify_script_summary.get('row_width_mismatch', '')};"
            f"verify_script_pngs={support_verify_script_summary.get('png_entries', '')};"
            f"verify_script_missing={support_verify_script_summary.get('missing', '')};"
            f"verify_script_not_file={support_verify_script_summary.get('not_file', '')};"
            f"verify_script_size_mismatch={support_verify_script_summary.get('size_mismatch', '')};"
            f"verify_script_size_invalid={support_verify_script_summary.get('size_invalid', '')};"
            f"verify_script_sha256_mismatch={support_verify_script_summary.get('sha256_mismatch', '')};"
            f"verify_script_sha256_invalid={support_verify_script_summary.get('sha256_invalid', '')};"
            f"verify_script_noncanonical_paths={support_verify_script_summary.get('noncanonical_paths', '')};"
            f"verify_script_unexpected={support_verify_script_summary.get('unexpected', '')};"
            f"support_archive_verify={int(support_archive_verify_ok)};"
            f"support_archive_status={support_archive_verify_summary.get('status', '')};"
            f"support_archive_members={support_archive_verify_summary.get('members', '')};"
            f"support_archive_top_level={support_archive_verify_summary.get('top_level', '')};"
            f"support_archive_not_empty_status={support_archive_verify_summary.get('archive_not_empty_status', '')};"
            f"support_archive_single_top_level_status={support_archive_verify_summary.get('single_top_level_status', '')};"
            f"support_archive_top_level_name_status={support_archive_verify_summary.get('top_level_name_status', '')};"
            f"support_archive_safe_paths={support_archive_verify_summary.get('safe_paths', '')};"
            f"support_archive_supported_types={support_archive_verify_summary.get('supported_types', '')};"
            f"support_archive_checksum_status={support_archive_verify_summary.get('checksum_status', '')};"
            f"support_archive_checksum_line_count={support_archive_verify_summary.get('checksum_line_count', '')};"
            f"support_archive_summary_status={support_archive_verify_summary.get('archive_summary_status', '')};"
            f"support_archive_summary_schema_status={support_archive_verify_summary.get('archive_summary_schema_status', '')};"
            f"support_archive_summary_missing_keys={support_archive_verify_summary.get('archive_summary_missing_keys', '')};"
            f"support_archive_summary_extra_keys={support_archive_verify_summary.get('archive_summary_extra_keys', '')};"
            f"support_archive_summary_duplicate_keys={support_archive_verify_summary.get('archive_summary_duplicate_keys', '')};"
            f"support_archive_summary_malformed_lines={support_archive_verify_summary.get('archive_summary_malformed_lines', '')};"
            f"support_archive_artifacts_status={support_archive_verify_summary.get('artifacts_status', '')};"
            f"support_archive_artifacts_files={support_archive_verify_summary.get('artifacts_files', '')};"
            f"support_archive_artifacts_schema_status={support_archive_verify_summary.get('artifacts_schema_status', '')};"
            f"support_archive_artifacts_duplicate_fields_status={support_archive_verify_summary.get('artifacts_duplicate_fields_status', '')};"
            f"support_archive_artifacts_duplicate_paths_status={support_archive_verify_summary.get('artifacts_duplicate_paths_status', '')};"
            f"support_archive_artifacts_row_width_status={support_archive_verify_summary.get('artifacts_row_width_status', '')};"
            f"support_archive_artifacts_field_format_status={support_archive_verify_summary.get('artifacts_field_format_status', '')};"
            f"support_archive_artifacts_safe_paths_status={support_archive_verify_summary.get('artifacts_safe_paths_status', '')};"
            f"support_archive_artifacts_count_status={support_archive_verify_summary.get('artifacts_count_status', '')};"
            f"support_archive_artifacts_paths_status={support_archive_verify_summary.get('artifacts_paths_status', '')};"
            f"support_archive_manifest_status={support_archive_verify_summary.get('manifest_status', '')};"
            f"support_archive_launcher_status={support_archive_verify_summary.get('launcher_status', '')};"
            f"support_archive_companion={int(support_archive_companion_ok)};"
            f"support_archive_companion_summary={int('summary=pass' in support_archive_companion_detail)};"
            f"support_archive_companion_manifest={int('manifest=pass' in support_archive_companion_detail)};"
            f"support_archive_companion_artifacts={int('artifacts=pass' in support_archive_companion_detail)};"
            f"support_archive_companion_artifact_duplicate_paths={int('artifact_duplicate_paths=pass' in support_archive_companion_detail)};"
            f"support_archive_companion_artifact_field_format={int('artifact_field_format=pass' in support_archive_companion_detail)};"
            f"support_archive_companion_artifact_safe_paths={int('artifact_safe_paths=pass' in support_archive_companion_detail)};"
            f"support_archive_companion_archive_not_empty={int('archive_not_empty=pass' in support_archive_companion_detail)};"
            f"support_archive_companion_single_top_level={int('single_top_level=pass' in support_archive_companion_detail)};"
            f"support_archive_companion_top_level_name={int('top_level_name=pass' in support_archive_companion_detail)};"
            f"support_archive_companion_copy={int(support_archive_companion_copy_ok)};"
            f"support_archive_companion_copy_summary={int('summary=pass' in support_archive_companion_copy_detail)};"
            f"support_archive_companion_copy_manifest={int('manifest=pass' in support_archive_companion_copy_detail)};"
            f"support_archive_companion_copy_artifacts={int('artifacts=pass' in support_archive_companion_copy_detail)};"
            f"support_archive_companion_copy_artifact_duplicate_paths={int('artifact_duplicate_paths=pass' in support_archive_companion_copy_detail)};"
            f"support_archive_companion_copy_artifact_field_format={int('artifact_field_format=pass' in support_archive_companion_copy_detail)};"
            f"support_archive_companion_copy_artifact_safe_paths={int('artifact_safe_paths=pass' in support_archive_companion_copy_detail)};"
            f"support_archive_companion_copy_archive_not_empty={int('archive_not_empty=pass' in support_archive_companion_copy_detail)};"
            f"support_archive_companion_copy_single_top_level={int('single_top_level=pass' in support_archive_companion_copy_detail)};"
            f"support_archive_companion_copy_top_level_name={int('top_level_name=pass' in support_archive_companion_copy_detail)};"
            f"index_archives={int(support_index_archives.is_file())};"
            f"index_entries={int(support_index_entries.is_file())};"
            f"index_locallng={len(support_locallng_index_rows)};"
            f"index_movies={len(support_movies_index_ids)};"
            f"diagnostic_vqa_decode={int('tools/lolg_vqa_decode.py' in support_diagnostic_text)};"
            f"diagnostic_support_manifest_verify={int('tools/lolg_hd_support_manifest_verify.py' in support_diagnostic_text)};"
            f"diagnostic_support_archive_verify={int('tools/lolg_hd_support_archive_verify.py' in support_diagnostic_text)};"
            f"pillow={int('pillow=present' in support_diagnostic_text)};"
            f"readme_full_ready={int('sidecar_critical_full_ready' in support_readme_text)};"
            f"readme_bundle_manifest={int('BUNDLE_MANIFEST.csv' in support_readme_text)};"
            f"readme_verify_script={int('VERIFY_SUPPORT.sh' in support_readme_text)};"
            f"readme_archive_artifacts={int('hd_support_bundle.tar.gz.artifacts.csv' in support_readme_text)};"
            f"readme_support_manifest_verify={int('tools/lolg_hd_support_manifest_verify.py' in support_readme_text)};"
            f"readme_support_archive_verify={int('tools/lolg_hd_support_archive_verify.py' in support_readme_text)};"
            f"readme_summary={int('SUPPORT_SUMMARY.txt' in support_readme_text)};"
            f"readme_index={int('reports/vqa_external_sidecar_index/entries.csv' in support_readme_text)};"
            f"readme_warmup={int('./LOLG_HD.sh sidecar-critical-warmup' in support_readme_text)};"
            f"readme_verify_support={int('./LOLG_HD.sh verify-support' in support_readme_text)};"
            f"readme_verify_support_archive={int('./LOLG_HD.sh verify-support-archive' in support_readme_text)};"
            f"summary_status={support_summary_values.get('status', '')};"
            f"summary_ready={support_summary_values.get('ready_to_launch', '')};"
            f"summary_release={support_summary_values.get('release_check', '')};"
            f"summary_release_pass_count={support_summary_values.get('release_pass_count', '')};"
            f"summary_release_checks={support_summary_values.get('release_checks', '')};"
            f"summary_release_info={support_summary_values.get('release_info', '')};"
            f"summary_release_display={support_summary_values.get('release_display', '')};"
            f"summary_release_fields_ok={int(support_summary_release_fields_ok)};"
            f"summary_manifest={support_summary_values.get('manifest', '')};"
            f"summary_manifest_verify={support_summary_values.get('manifest_verify', '')};"
            f"summary_resolution={support_summary_values.get('resolution', '')};"
            f"summary_issues={support_summary_values.get('support_summary_issues', '')};"
            f"summary_current_or_stale_release_ok={int(support_summary_current_or_stale_release_ok)};"
            f"summary_full_ready={int('sidecar_critical_full_ready=1' in support_summary_text)};"
            f"summary_movies={int('movies_ready=75/75' in support_summary_text)};"
            f"status_full_ready={support_hd_status_summary.get('sidecar_critical_full_ready', '')};"
            f"status_movies_ready={support_hd_status_summary.get('sidecar_movies_ready_frames', '')}/{support_hd_status_summary.get('sidecar_movies_frames', '')}"
        ),
        "./COLLECT_HD_SUPPORT.sh output/hd_support_bundle_check",
    )
    add_check(
        checks,
        "support_archive_artifacts_missing_file_negative_validation",
        pass_if(
            support_archive_artifacts_missing_file_negative_ok
            and support_archive_artifacts_missing_file_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_artifacts_missing_file_negative_ok)};"
            f"companion={int(support_archive_artifacts_missing_file_companion_negative_ok)};"
            f"verifier_detail={support_archive_artifacts_missing_file_negative_detail};"
            f"companion_detail={support_archive_artifacts_missing_file_companion_negative_detail}"
        ),
        "fix artifacts.csv missing-file rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_verify_script_missing_file_negative_validation",
        pass_if(
            support_archive_verify_script_missing_file_negative_ok
            and support_archive_verify_script_missing_file_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_verify_script_missing_file_negative_ok)};"
            f"companion={int(support_archive_verify_script_missing_file_companion_negative_ok)};"
            f"verifier_detail={support_archive_verify_script_missing_file_negative_detail};"
            f"companion_detail={support_archive_verify_script_missing_file_companion_negative_detail}"
        ),
        "fix archive .verify.sh missing-file rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_unsafe_tar_negative_validation",
        pass_if(support_archive_unsafe_tar_negative_ok and support_archive_unsafe_tar_companion_negative_ok),
        (
            f"verifier={int(support_archive_unsafe_tar_negative_ok)};"
            f"companion={int(support_archive_unsafe_tar_companion_negative_ok)};"
            f"verifier_detail={support_archive_unsafe_tar_negative_detail};"
            f"companion_detail={support_archive_unsafe_tar_companion_negative_detail}"
        ),
        "fix unsafe tar path rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_unsupported_tar_negative_validation",
        pass_if(
            support_archive_unsupported_tar_negative_ok
            and support_archive_unsupported_tar_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_unsupported_tar_negative_ok)};"
            f"companion={int(support_archive_unsupported_tar_companion_negative_ok)};"
            f"verifier_detail={support_archive_unsupported_tar_negative_detail};"
            f"companion_detail={support_archive_unsupported_tar_companion_negative_detail}"
        ),
        "fix unsupported tar member rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_top_level_name_negative_validation",
        pass_if(
            support_archive_top_level_name_negative_ok
            and support_archive_top_level_name_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_top_level_name_negative_ok)};"
            f"companion={int(support_archive_top_level_name_companion_negative_ok)};"
            f"verifier_detail={support_archive_top_level_name_negative_detail};"
            f"companion_detail={support_archive_top_level_name_companion_negative_detail}"
        ),
        "fix wrong top-level tar rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_multi_top_level_negative_validation",
        pass_if(
            support_archive_multi_top_level_negative_ok
            and support_archive_multi_top_level_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_multi_top_level_negative_ok)};"
            f"companion={int(support_archive_multi_top_level_companion_negative_ok)};"
            f"verifier_detail={support_archive_multi_top_level_negative_detail};"
            f"companion_detail={support_archive_multi_top_level_companion_negative_detail}"
        ),
        "fix multi top-level tar rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_empty_negative_validation",
        pass_if(support_archive_empty_negative_ok and support_archive_empty_companion_negative_ok),
        (
            f"verifier={int(support_archive_empty_negative_ok)};"
            f"companion={int(support_archive_empty_companion_negative_ok)};"
            f"verifier_detail={support_archive_empty_negative_detail};"
            f"companion_detail={support_archive_empty_companion_negative_detail}"
        ),
        "fix empty archive rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_artifacts_negative_validation",
        pass_if(support_archive_artifacts_negative_ok and support_archive_companion_negative_ok),
        (
            f"verifier={int(support_archive_artifacts_negative_ok)};"
            f"companion={int(support_archive_companion_negative_ok)};"
            f"verifier_detail={support_archive_artifacts_negative_detail};"
            f"companion_detail={support_archive_companion_negative_detail}"
        ),
        "fix artifacts.csv malformed-row rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_artifacts_extra_field_negative_validation",
        pass_if(
            support_archive_artifacts_extra_field_negative_ok
            and support_archive_artifacts_extra_field_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_artifacts_extra_field_negative_ok)};"
            f"companion={int(support_archive_artifacts_extra_field_companion_negative_ok)};"
            f"verifier_detail={support_archive_artifacts_extra_field_negative_detail};"
            f"companion_detail={support_archive_artifacts_extra_field_companion_negative_detail}"
        ),
        "fix artifacts.csv extra-field rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_artifacts_duplicate_field_negative_validation",
        pass_if(
            support_archive_artifacts_duplicate_field_negative_ok
            and support_archive_artifacts_duplicate_field_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_artifacts_duplicate_field_negative_ok)};"
            f"companion={int(support_archive_artifacts_duplicate_field_companion_negative_ok)};"
            f"verifier_detail={support_archive_artifacts_duplicate_field_negative_detail};"
            f"companion_detail={support_archive_artifacts_duplicate_field_companion_negative_detail}"
        ),
        "fix artifacts.csv duplicate-field rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_artifacts_duplicate_path_negative_validation",
        pass_if(
            support_archive_artifacts_duplicate_path_negative_ok
            and support_archive_artifacts_duplicate_path_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_artifacts_duplicate_path_negative_ok)};"
            f"companion={int(support_archive_artifacts_duplicate_path_companion_negative_ok)};"
            f"verifier_detail={support_archive_artifacts_duplicate_path_negative_detail};"
            f"companion_detail={support_archive_artifacts_duplicate_path_companion_negative_detail}"
        ),
        "fix artifacts.csv duplicate-path rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_artifacts_missing_field_negative_validation",
        pass_if(
            support_archive_artifacts_missing_field_negative_ok
            and support_archive_artifacts_missing_field_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_artifacts_missing_field_negative_ok)};"
            f"companion={int(support_archive_artifacts_missing_field_companion_negative_ok)};"
            f"verifier_detail={support_archive_artifacts_missing_field_negative_detail};"
            f"companion_detail={support_archive_artifacts_missing_field_companion_negative_detail}"
        ),
        "fix artifacts.csv missing-field rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_artifacts_missing_row_negative_validation",
        pass_if(
            support_archive_artifacts_missing_row_negative_ok
            and support_archive_artifacts_missing_row_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_artifacts_missing_row_negative_ok)};"
            f"companion={int(support_archive_artifacts_missing_row_companion_negative_ok)};"
            f"verifier_detail={support_archive_artifacts_missing_row_negative_detail};"
            f"companion_detail={support_archive_artifacts_missing_row_companion_negative_detail}"
        ),
        "fix artifacts.csv missing-row rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_artifacts_field_format_negative_validation",
        pass_if(
            support_archive_artifacts_field_format_negative_ok
            and support_archive_artifacts_field_format_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_artifacts_field_format_negative_ok)};"
            f"companion={int(support_archive_artifacts_field_format_companion_negative_ok)};"
            f"verifier_detail={support_archive_artifacts_field_format_negative_detail};"
            f"companion_detail={support_archive_artifacts_field_format_companion_negative_detail}"
        ),
        "fix artifacts.csv field-format rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_artifacts_size_negative_validation",
        pass_if(
            support_archive_artifacts_size_negative_ok
            and support_archive_artifacts_size_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_artifacts_size_negative_ok)};"
            f"companion={int(support_archive_artifacts_size_companion_negative_ok)};"
            f"verifier_detail={support_archive_artifacts_size_negative_detail};"
            f"companion_detail={support_archive_artifacts_size_companion_negative_detail}"
        ),
        "fix artifacts.csv bad-size rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_artifacts_sha256_negative_validation",
        pass_if(
            support_archive_artifacts_sha256_negative_ok
            and support_archive_artifacts_sha256_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_artifacts_sha256_negative_ok)};"
            f"companion={int(support_archive_artifacts_sha256_companion_negative_ok)};"
            f"verifier_detail={support_archive_artifacts_sha256_negative_detail};"
            f"companion_detail={support_archive_artifacts_sha256_companion_negative_detail}"
        ),
        "fix artifacts.csv bad-sha256 rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_artifacts_executable_negative_validation",
        pass_if(
            support_archive_artifacts_executable_negative_ok
            and support_archive_artifacts_executable_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_artifacts_executable_negative_ok)};"
            f"companion={int(support_archive_artifacts_executable_companion_negative_ok)};"
            f"verifier_detail={support_archive_artifacts_executable_negative_detail};"
            f"companion_detail={support_archive_artifacts_executable_companion_negative_detail}"
        ),
        "fix artifacts.csv executable-flag rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_artifacts_path_negative_validation",
        pass_if(
            support_archive_artifacts_path_negative_ok
            and support_archive_artifacts_path_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_artifacts_path_negative_ok)};"
            f"companion={int(support_archive_artifacts_path_companion_negative_ok)};"
            f"verifier_detail={support_archive_artifacts_path_negative_detail};"
            f"companion_detail={support_archive_artifacts_path_companion_negative_detail}"
        ),
        "fix artifacts.csv bad-path rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_artifacts_unsafe_path_negative_validation",
        pass_if(
            support_archive_artifacts_unsafe_path_negative_ok
            and support_archive_artifacts_unsafe_path_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_artifacts_unsafe_path_negative_ok)};"
            f"companion={int(support_archive_artifacts_unsafe_path_companion_negative_ok)};"
            f"verifier_detail={support_archive_artifacts_unsafe_path_negative_detail};"
            f"companion_detail={support_archive_artifacts_unsafe_path_companion_negative_detail}"
        ),
        "fix artifacts.csv unsafe-path rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_artifacts_nonportable_path_negative_validation",
        pass_if(
            support_archive_artifacts_nonportable_path_negative_ok
            and support_archive_artifacts_nonportable_path_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_artifacts_nonportable_path_negative_ok)};"
            f"companion={int(support_archive_artifacts_nonportable_path_companion_negative_ok)};"
            f"verifier_detail={support_archive_artifacts_nonportable_path_negative_detail};"
            f"companion_detail={support_archive_artifacts_nonportable_path_companion_negative_detail}"
        ),
        "fix artifacts.csv non-portable filename rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_checksum_missing_file_negative_validation",
        pass_if(
            support_archive_checksum_missing_file_negative_ok
            and support_archive_checksum_missing_file_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_checksum_missing_file_negative_ok)};"
            f"companion={int(support_archive_checksum_missing_file_companion_negative_ok)};"
            f"verifier_detail={support_archive_checksum_missing_file_negative_detail};"
            f"companion_detail={support_archive_checksum_missing_file_companion_negative_detail}"
        ),
        "fix archive .sha256 missing-file rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_checksum_negative_validation",
        pass_if(support_archive_checksum_negative_ok and support_archive_checksum_companion_negative_ok),
        (
            f"verifier={int(support_archive_checksum_negative_ok)};"
            f"companion={int(support_archive_checksum_companion_negative_ok)};"
            f"verifier_detail={support_archive_checksum_negative_detail};"
            f"companion_detail={support_archive_checksum_companion_negative_detail}"
        ),
        "fix archive .sha256 mismatch rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_checksum_name_negative_validation",
        pass_if(
            support_archive_checksum_name_negative_ok
            and support_archive_checksum_name_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_checksum_name_negative_ok)};"
            f"companion={int(support_archive_checksum_name_companion_negative_ok)};"
            f"verifier_detail={support_archive_checksum_name_negative_detail};"
            f"companion_detail={support_archive_checksum_name_companion_negative_detail}"
        ),
        "fix archive .sha256 archive-name rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_checksum_archive_path_negative_validation",
        pass_if(
            support_archive_checksum_archive_path_negative_ok
            and support_archive_checksum_archive_path_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_checksum_archive_path_negative_ok)};"
            f"companion={int(support_archive_checksum_archive_path_companion_negative_ok)};"
            f"verifier_detail={support_archive_checksum_archive_path_negative_detail};"
            f"companion_detail={support_archive_checksum_archive_path_companion_negative_detail}"
        ),
        "fix archive .sha256 path-like archive-name rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_checksum_format_negative_validation",
        pass_if(
            support_archive_checksum_format_negative_ok
            and support_archive_checksum_format_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_checksum_format_negative_ok)};"
            f"companion={int(support_archive_checksum_format_companion_negative_ok)};"
            f"verifier_detail={support_archive_checksum_format_negative_detail};"
            f"companion_detail={support_archive_checksum_format_companion_negative_detail}"
        ),
        "fix archive .sha256 format rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_checksum_extra_field_negative_validation",
        pass_if(
            support_archive_checksum_extra_field_negative_ok
            and support_archive_checksum_extra_field_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_checksum_extra_field_negative_ok)};"
            f"companion={int(support_archive_checksum_extra_field_companion_negative_ok)};"
            f"verifier_detail={support_archive_checksum_extra_field_negative_detail};"
            f"companion_detail={support_archive_checksum_extra_field_companion_negative_detail}"
        ),
        "fix archive .sha256 extra-field rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_checksum_line_count_negative_validation",
        pass_if(
            support_archive_checksum_line_count_negative_ok
            and support_archive_checksum_line_count_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_checksum_line_count_negative_ok)};"
            f"companion={int(support_archive_checksum_line_count_companion_negative_ok)};"
            f"verifier_detail={support_archive_checksum_line_count_negative_detail};"
            f"companion_detail={support_archive_checksum_line_count_companion_negative_detail}"
        ),
        "fix archive .sha256 extra-line rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_summary_missing_file_negative_validation",
        pass_if(
            support_archive_summary_missing_file_negative_ok
            and support_archive_summary_missing_file_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_summary_missing_file_negative_ok)};"
            f"companion={int(support_archive_summary_missing_file_companion_negative_ok)};"
            f"verifier_detail={support_archive_summary_missing_file_negative_detail};"
            f"companion_detail={support_archive_summary_missing_file_companion_negative_detail}"
        ),
        "fix archive .summary missing-file rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_summary_negative_validation",
        pass_if(support_archive_summary_negative_ok and support_archive_summary_companion_negative_ok),
        (
            f"verifier={int(support_archive_summary_negative_ok)};"
            f"companion={int(support_archive_summary_companion_negative_ok)};"
            f"verifier_detail={support_archive_summary_negative_detail};"
            f"companion_detail={support_archive_summary_companion_negative_detail}"
        ),
        "fix archive .summary malformed-key rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_summary_duplicate_key_negative_validation",
        pass_if(
            support_archive_summary_duplicate_key_negative_ok
            and support_archive_summary_duplicate_key_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_summary_duplicate_key_negative_ok)};"
            f"companion={int(support_archive_summary_duplicate_key_companion_negative_ok)};"
            f"verifier_detail={support_archive_summary_duplicate_key_negative_detail};"
            f"companion_detail={support_archive_summary_duplicate_key_companion_negative_detail}"
        ),
        "fix archive .summary duplicate-key rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_summary_malformed_line_negative_validation",
        pass_if(
            support_archive_summary_malformed_line_negative_ok
            and support_archive_summary_malformed_line_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_summary_malformed_line_negative_ok)};"
            f"companion={int(support_archive_summary_malformed_line_companion_negative_ok)};"
            f"verifier_detail={support_archive_summary_malformed_line_negative_detail};"
            f"companion_detail={support_archive_summary_malformed_line_companion_negative_detail}"
        ),
        "fix archive .summary malformed-line rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_summary_missing_key_negative_validation",
        pass_if(
            support_archive_summary_missing_key_negative_ok
            and support_archive_summary_missing_key_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_summary_missing_key_negative_ok)};"
            f"companion={int(support_archive_summary_missing_key_companion_negative_ok)};"
            f"verifier_detail={support_archive_summary_missing_key_negative_detail};"
            f"companion_detail={support_archive_summary_missing_key_companion_negative_detail}"
        ),
        "fix archive .summary missing-key rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_summary_version_negative_validation",
        pass_if(
            support_archive_summary_version_negative_ok
            and support_archive_summary_version_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_summary_version_negative_ok)};"
            f"companion={int(support_archive_summary_version_companion_negative_ok)};"
            f"verifier_detail={support_archive_summary_version_negative_detail};"
            f"companion_detail={support_archive_summary_version_companion_negative_detail}"
        ),
        "fix archive .summary version rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_summary_timestamp_negative_validation",
        pass_if(
            support_archive_summary_timestamp_negative_ok
            and support_archive_summary_timestamp_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_summary_timestamp_negative_ok)};"
            f"companion={int(support_archive_summary_timestamp_companion_negative_ok)};"
            f"verifier_detail={support_archive_summary_timestamp_negative_detail};"
            f"companion_detail={support_archive_summary_timestamp_companion_negative_detail}"
        ),
        "fix archive .summary timestamp rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_summary_archive_name_negative_validation",
        pass_if(
            support_archive_summary_archive_name_negative_ok
            and support_archive_summary_archive_name_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_summary_archive_name_negative_ok)};"
            f"companion={int(support_archive_summary_archive_name_companion_negative_ok)};"
            f"verifier_detail={support_archive_summary_archive_name_negative_detail};"
            f"companion_detail={support_archive_summary_archive_name_companion_negative_detail}"
        ),
        "fix archive .summary archive-name rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_summary_size_negative_validation",
        pass_if(
            support_archive_summary_size_negative_ok
            and support_archive_summary_size_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_summary_size_negative_ok)};"
            f"companion={int(support_archive_summary_size_companion_negative_ok)};"
            f"verifier_detail={support_archive_summary_size_negative_detail};"
            f"companion_detail={support_archive_summary_size_companion_negative_detail}"
        ),
        "fix archive .summary size rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_summary_sha256_negative_validation",
        pass_if(
            support_archive_summary_sha256_negative_ok
            and support_archive_summary_sha256_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_summary_sha256_negative_ok)};"
            f"companion={int(support_archive_summary_sha256_companion_negative_ok)};"
            f"verifier_detail={support_archive_summary_sha256_negative_detail};"
            f"companion_detail={support_archive_summary_sha256_companion_negative_detail}"
        ),
        "fix archive .summary sha256 rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_summary_sha256_file_negative_validation",
        pass_if(
            support_archive_summary_sha256_file_negative_ok
            and support_archive_summary_sha256_file_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_summary_sha256_file_negative_ok)};"
            f"companion={int(support_archive_summary_sha256_file_companion_negative_ok)};"
            f"verifier_detail={support_archive_summary_sha256_file_negative_detail};"
            f"companion_detail={support_archive_summary_sha256_file_companion_negative_detail}"
        ),
        "fix archive .summary sha256-file rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_archive_summary_bundle_dir_negative_validation",
        pass_if(
            support_archive_summary_bundle_dir_negative_ok
            and support_archive_summary_bundle_dir_companion_negative_ok
        ),
        (
            f"verifier={int(support_archive_summary_bundle_dir_negative_ok)};"
            f"companion={int(support_archive_summary_bundle_dir_companion_negative_ok)};"
            f"verifier_detail={support_archive_summary_bundle_dir_negative_detail};"
            f"companion_detail={support_archive_summary_bundle_dir_companion_negative_detail}"
        ),
        "fix archive .summary bundle-dir rejection in archive verifier and companion",
    )
    add_check(
        checks,
        "support_bundle_manifest_negative_validation",
        pass_if(support_manifest_negative_ok and support_manifest_launcher_negative_ok),
        (
            f"verifier={int(support_manifest_negative_ok)};"
            f"launcher={int(support_manifest_launcher_negative_ok)};"
            f"verifier_detail={support_manifest_negative_detail};"
            f"launcher_detail={support_manifest_launcher_negative_detail}"
        ),
        "fix BUNDLE_MANIFEST.csv malformed-row rejection in support manifest verifier",
    )
    add_check(
        checks,
        "support_bundle_manifest_extra_field_negative_validation",
        pass_if(
            support_manifest_extra_field_negative_ok
            and support_manifest_extra_field_launcher_negative_ok
        ),
        (
            f"verifier={int(support_manifest_extra_field_negative_ok)};"
            f"launcher={int(support_manifest_extra_field_launcher_negative_ok)};"
            f"verifier_detail={support_manifest_extra_field_negative_detail};"
            f"launcher_detail={support_manifest_extra_field_launcher_negative_detail}"
        ),
        "fix BUNDLE_MANIFEST.csv extra-field rejection in support manifest verifier",
    )
    add_check(
        checks,
        "support_bundle_manifest_duplicate_field_negative_validation",
        pass_if(
            support_manifest_duplicate_field_negative_ok
            and support_manifest_duplicate_field_launcher_negative_ok
        ),
        (
            f"verifier={int(support_manifest_duplicate_field_negative_ok)};"
            f"launcher={int(support_manifest_duplicate_field_launcher_negative_ok)};"
            f"verifier_detail={support_manifest_duplicate_field_negative_detail};"
            f"launcher_detail={support_manifest_duplicate_field_launcher_negative_detail}"
        ),
        "fix BUNDLE_MANIFEST.csv duplicate-field rejection in support manifest verifier",
    )
    add_check(
        checks,
        "support_bundle_manifest_duplicate_path_negative_validation",
        pass_if(
            support_manifest_duplicate_path_negative_ok
            and support_manifest_duplicate_path_launcher_negative_ok
        ),
        (
            f"verifier={int(support_manifest_duplicate_path_negative_ok)};"
            f"launcher={int(support_manifest_duplicate_path_launcher_negative_ok)};"
            f"verifier_detail={support_manifest_duplicate_path_negative_detail};"
            f"launcher_detail={support_manifest_duplicate_path_launcher_negative_detail}"
        ),
        "fix BUNDLE_MANIFEST.csv duplicate-path rejection in support manifest verifier",
    )
    add_check(
        checks,
        "support_bundle_manifest_png_entry_negative_validation",
        pass_if(
            support_manifest_png_entry_negative_ok
            and support_manifest_png_entry_launcher_negative_ok
        ),
        (
            f"verifier={int(support_manifest_png_entry_negative_ok)};"
            f"launcher={int(support_manifest_png_entry_launcher_negative_ok)};"
            f"verifier_detail={support_manifest_png_entry_negative_detail};"
            f"launcher_detail={support_manifest_png_entry_launcher_negative_detail}"
        ),
        "fix BUNDLE_MANIFEST.csv png-entry rejection in support manifest verifier",
    )
    add_check(
        checks,
        "support_bundle_manifest_missing_field_negative_validation",
        pass_if(
            support_manifest_missing_field_negative_ok
            and support_manifest_missing_field_launcher_negative_ok
        ),
        (
            f"verifier={int(support_manifest_missing_field_negative_ok)};"
            f"launcher={int(support_manifest_missing_field_launcher_negative_ok)};"
            f"verifier_detail={support_manifest_missing_field_negative_detail};"
            f"launcher_detail={support_manifest_missing_field_launcher_negative_detail}"
        ),
        "fix BUNDLE_MANIFEST.csv missing-field rejection in support manifest verifier",
    )
    add_check(
        checks,
        "support_bundle_manifest_unsafe_path_negative_validation",
        pass_if(support_manifest_unsafe_negative_ok and support_manifest_unsafe_launcher_negative_ok),
        (
            f"verifier={int(support_manifest_unsafe_negative_ok)};"
            f"launcher={int(support_manifest_unsafe_launcher_negative_ok)};"
            f"verifier_detail={support_manifest_unsafe_negative_detail};"
            f"launcher_detail={support_manifest_unsafe_launcher_negative_detail}"
        ),
        "fix BUNDLE_MANIFEST.csv unsafe-path rejection in support manifest verifier",
    )
    add_check(
        checks,
        "support_bundle_manifest_noncanonical_path_negative_validation",
        pass_if(
            support_manifest_noncanonical_negative_ok
            and support_manifest_noncanonical_launcher_negative_ok
        ),
        (
            f"verifier={int(support_manifest_noncanonical_negative_ok)};"
            f"launcher={int(support_manifest_noncanonical_launcher_negative_ok)};"
            f"verifier_detail={support_manifest_noncanonical_negative_detail};"
            f"launcher_detail={support_manifest_noncanonical_launcher_negative_detail}"
        ),
        "fix BUNDLE_MANIFEST.csv noncanonical-path rejection in support manifest verifier",
    )
    add_check(
        checks,
        "support_bundle_manifest_invalid_fields_negative_validation",
        pass_if(
            support_manifest_invalid_fields_negative_ok
            and support_manifest_invalid_fields_launcher_negative_ok
        ),
        (
            f"verifier={int(support_manifest_invalid_fields_negative_ok)};"
            f"launcher={int(support_manifest_invalid_fields_launcher_negative_ok)};"
            f"verifier_detail={support_manifest_invalid_fields_negative_detail};"
            f"launcher_detail={support_manifest_invalid_fields_launcher_negative_detail}"
        ),
        "fix BUNDLE_MANIFEST.csv invalid size/sha rejection in support manifest verifier",
    )
    add_check(
        checks,
        "support_bundle_manifest_size_mismatch_negative_validation",
        pass_if(
            support_manifest_size_mismatch_negative_ok
            and support_manifest_size_mismatch_launcher_negative_ok
        ),
        (
            f"verifier={int(support_manifest_size_mismatch_negative_ok)};"
            f"launcher={int(support_manifest_size_mismatch_launcher_negative_ok)};"
            f"verifier_detail={support_manifest_size_mismatch_negative_detail};"
            f"launcher_detail={support_manifest_size_mismatch_launcher_negative_detail}"
        ),
        "fix BUNDLE_MANIFEST.csv size-mismatch rejection in support manifest verifier",
    )
    add_check(
        checks,
        "support_bundle_manifest_sha256_mismatch_negative_validation",
        pass_if(
            support_manifest_sha256_mismatch_negative_ok
            and support_manifest_sha256_mismatch_launcher_negative_ok
        ),
        (
            f"verifier={int(support_manifest_sha256_mismatch_negative_ok)};"
            f"launcher={int(support_manifest_sha256_mismatch_launcher_negative_ok)};"
            f"verifier_detail={support_manifest_sha256_mismatch_negative_detail};"
            f"launcher_detail={support_manifest_sha256_mismatch_launcher_negative_detail}"
        ),
        "fix BUNDLE_MANIFEST.csv sha256-mismatch rejection in support manifest verifier",
    )
    add_check(
        checks,
        "support_bundle_manifest_invalid_executable_negative_validation",
        pass_if(
            support_manifest_invalid_executable_negative_ok
            and support_manifest_invalid_executable_launcher_negative_ok
        ),
        (
            f"verifier={int(support_manifest_invalid_executable_negative_ok)};"
            f"launcher={int(support_manifest_invalid_executable_launcher_negative_ok)};"
            f"verifier_detail={support_manifest_invalid_executable_negative_detail};"
            f"launcher_detail={support_manifest_invalid_executable_launcher_negative_detail}"
        ),
        "fix BUNDLE_MANIFEST.csv invalid executable rejection in support manifest verifier",
    )
    add_check(
        checks,
        "support_bundle_manifest_executable_mismatch_negative_validation",
        pass_if(
            support_manifest_executable_mismatch_negative_ok
            and support_manifest_executable_mismatch_launcher_negative_ok
        ),
        (
            f"verifier={int(support_manifest_executable_mismatch_negative_ok)};"
            f"launcher={int(support_manifest_executable_mismatch_launcher_negative_ok)};"
            f"verifier_detail={support_manifest_executable_mismatch_negative_detail};"
            f"launcher_detail={support_manifest_executable_mismatch_launcher_negative_detail}"
        ),
        "fix BUNDLE_MANIFEST.csv executable-mismatch rejection in support manifest verifier",
    )
    add_check(
        checks,
        "support_bundle_manifest_missing_file_negative_validation",
        pass_if(
            support_manifest_missing_file_negative_ok
            and support_manifest_missing_file_launcher_negative_ok
        ),
        (
            f"verifier={int(support_manifest_missing_file_negative_ok)};"
            f"launcher={int(support_manifest_missing_file_launcher_negative_ok)};"
            f"verifier_detail={support_manifest_missing_file_negative_detail};"
            f"launcher_detail={support_manifest_missing_file_launcher_negative_detail}"
        ),
        "fix BUNDLE_MANIFEST.csv missing-file rejection in support manifest verifier",
    )
    add_check(
        checks,
        "support_bundle_manifest_not_file_negative_validation",
        pass_if(
            support_manifest_not_file_negative_ok
            and support_manifest_not_file_launcher_negative_ok
        ),
        (
            f"verifier={int(support_manifest_not_file_negative_ok)};"
            f"launcher={int(support_manifest_not_file_launcher_negative_ok)};"
            f"verifier_detail={support_manifest_not_file_negative_detail};"
            f"launcher_detail={support_manifest_not_file_launcher_negative_detail}"
        ),
        "fix BUNDLE_MANIFEST.csv directory-entry rejection in support manifest verifier",
    )
    add_check(
        checks,
        "support_bundle_manifest_unexpected_file_negative_validation",
        pass_if(
            support_manifest_unexpected_file_negative_ok
            and support_manifest_unexpected_file_launcher_negative_ok
        ),
        (
            f"verifier={int(support_manifest_unexpected_file_negative_ok)};"
            f"launcher={int(support_manifest_unexpected_file_launcher_negative_ok)};"
            f"verifier_detail={support_manifest_unexpected_file_negative_detail};"
            f"launcher_detail={support_manifest_unexpected_file_launcher_negative_detail}"
        ),
        "fix BUNDLE_MANIFEST.csv unexpected-file rejection in support manifest verifier",
    )

    movies_safe_wine_ok, movies_safe_wine_detail = shell_check(
        [
            "env",
            "LOLG_HD_WINE_RUNTIME_ROOT=output/lolg95_movies_safe_dry_run_runtime",
            "WINEPREFIX=output/lolg95_movies_safe_dry_run_wine_prefix",
            "./LOLG_HD.sh",
            "wine-dgvoodoo-win10-safevqa-movies-safe",
            "--dry-run",
        ],
        root,
    )
    add_check(
        checks,
        "wine_safevqa_movies_safe_dry_run",
        pass_if(
            movies_safe_wine_ok
            and "MOVIES.MIX safe 892x560 complet" in movies_safe_wine_detail
            and "Dossier sidecar MIX Wine:" in movies_safe_wine_detail
            and "vqa_contract_batch_writer_movies_0000_0027_892x560_safe/mix" in movies_safe_wine_detail
            and "MIX HD exclus Wine: LOCALLNG.MIX,DANIEL.MIX" in movies_safe_wine_detail
            and "MOVIES.MIX: safe 892x560 complet" in movies_safe_wine_detail
            and "Pack MIX HD global Wine: actif" in movies_safe_wine_detail
        ),
        movies_safe_wine_detail,
        "regenerate MOVIES safe 892x560 or fix wine-dgvoodoo-win10-safevqa-movies-safe",
    )

    movies_safe_stage_root = Path("output/lolg95_movies_safe_stage_check_runtime")
    movies_safe_stage = movies_safe_stage_root / "WESTWOOD" / "LOLG"
    movies_safe_expected_mix = (
        Path("output/vqa_contract_batch_writer_movies_0000_0027_892x560_safe/mix/MOVIES.MIX").resolve()
    )
    movies_safe_prepare_ok, movies_safe_prepare_detail = shell_check(
        [
            "env",
            f"LOLG_HD_WINE_RUNTIME_ROOT={movies_safe_stage_root}",
            "WINEPREFIX=output/lolg95_movies_safe_stage_check_wine_prefix",
            "./LOLG_HD.sh",
            "wine-dgvoodoo-win10-safevqa-movies-safe",
            "--prepare-only",
            "--skip-wine-setup",
        ],
        root,
    )
    movies_safe_stage_movies = movies_safe_stage / "MOVIES.MIX"
    movies_safe_stage_locallng = movies_safe_stage / "LOCALLNG.MIX"
    movies_safe_movies_target = movies_safe_stage_movies.resolve() if movies_safe_stage_movies.exists() else None
    movies_safe_locallng_target = movies_safe_stage_locallng.resolve() if movies_safe_stage_locallng.exists() else None
    add_check(
        checks,
        "wine_safevqa_movies_safe_stage_links",
        pass_if(
            movies_safe_prepare_ok
            and movies_safe_movies_target == movies_safe_expected_mix
            and movies_safe_locallng_target == Path("C/LOLG/LOCALLNG.MIX").resolve()
        ),
        (
            f"{movies_safe_prepare_detail};"
            f"MOVIES={movies_safe_movies_target or ''};"
            f"LOCALLNG={movies_safe_locallng_target or ''}"
        ),
        "fix stage extra-MIX linking for wine-dgvoodoo-win10-safevqa-movies-safe",
    )

    movies_safe_block_ok, movies_safe_block_detail = shell_check(
        [
            "env",
            "LOLG_HD_WINE_RUNTIME_ROOT=output/lolg95_movies_safe_block_check_runtime",
            "WINEPREFIX=output/lolg95_movies_safe_block_check_wine_prefix",
            "./LOLG_HD.sh",
            "wine-dgvoodoo-win10-safevqa-movies-safe",
        ],
        root,
    )
    add_check(
        checks,
        "wine_safevqa_movies_safe_blocks_runtime",
        pass_if(
            (not movies_safe_block_ok)
            and "Lancement bloque: wine-dgvoodoo-win10-safevqa-movies-safe" in movies_safe_block_detail
            and "LOLG_HD_ALLOW_CRASHING_MOVIES_SAFE=1" in movies_safe_block_detail
        ),
        movies_safe_block_detail,
        "keep MOVIES safe direct Wine launch guarded until the page fault is fixed",
    )

    contract_896_ok, contract_896_detail = shell_check(
        [
            "env",
            "LOLG_HD_WINE_RUNTIME_ROOT=output/lolg95_contract_dry_run_runtime",
            "WINEPREFIX=output/lolg95_contract_dry_run_wine_prefix",
            "./LOLG_HD.sh",
            "wine-vqa-contract-locallng-896-padded",
            "--dry-run",
        ],
        root,
    )
    add_check(
        checks,
        "vqa_contract_locallng_896_padded_dry_run",
        pass_if(
            contract_896_ok
            and "LOCALLNG.MIX 896x560" in contract_896_detail
            and "Pack MIX HD global Wine: desactive" in contract_896_detail
            and "MOVIES.MIX: original" in contract_896_detail
        ),
        contract_896_detail,
        "regenerate the LOCALLNG 896 padded candidate or fix LOLG_HD.sh dry-run handoff",
    )

    contract_1280_ok, contract_1280_detail = shell_check(
        [
            "env",
            "LOLG_HD_WINE_RUNTIME_ROOT=output/lolg95_contract_dry_run_runtime",
            "WINEPREFIX=output/lolg95_contract_dry_run_wine_prefix",
            "./LOLG_HD.sh",
            "wine-vqa-contract-locallng",
            "--dry-run",
        ],
        root,
    )
    add_check(
        checks,
        "vqa_contract_locallng_1280_padded_dry_run",
        pass_if(
            contract_1280_ok
            and "LOCALLNG.MIX diagnostic:" in contract_1280_detail
            and "vqa_contract_preserving_writer_locallng_1280x1024_vqaext_padded_cbpz_from_adaptive_decode/mix/LOCALLNG.MIX"
            in contract_1280_detail
            and "Pack MIX HD global Wine: desactive" in contract_1280_detail
            and "MOVIES.MIX: original" in contract_1280_detail
        ),
        contract_1280_detail,
        "regenerate the LOCALLNG 1280 padded candidate or fix LOLG_HD.sh dry-run handoff",
    )

    contract_movies_noroom_ok, contract_movies_noroom_detail = shell_check(
        [
            "env",
            "LOLG_HD_WINE_RUNTIME_ROOT=output/lolg95_contract_dry_run_runtime",
            "WINEPREFIX=output/lolg95_contract_dry_run_wine_prefix",
            "./LOLG_HD.sh",
            "wine-vqa-contract-movies-noroom",
            "--dry-run",
        ],
        root,
    )
    add_check(
        checks,
        "vqa_contract_movies_noroom_dry_run",
        pass_if(
            contract_movies_noroom_ok
            and "MOVIES.MIX 1280 CBPZ no_room" in contract_movies_noroom_detail
            and "Pack MIX HD global Wine: desactive" in contract_movies_noroom_detail
            and "contract-preserving HD 1280 + CBPZ no_room" in contract_movies_noroom_detail
        ),
        contract_movies_noroom_detail,
        "regenerate MOVIES CBPZ no_room or fix LOLG_HD.sh dry-run handoff",
    )

    contract_movies_noroom_only_ok, contract_movies_noroom_only_detail = shell_check(
        [
            "env",
            "LOLG_HD_WINE_RUNTIME_ROOT=output/lolg95_contract_dry_run_runtime",
            "WINEPREFIX=output/lolg95_contract_dry_run_wine_prefix",
            "./LOLG_HD.sh",
            "wine-vqa-contract-movies-noroom-only",
            "--dry-run",
        ],
        root,
    )
    add_check(
        checks,
        "vqa_contract_movies_noroom_only_dry_run",
        pass_if(
            contract_movies_noroom_only_ok
            and "LOCALLNG.MIX original et MOVIES.MIX 1280 CBPZ no_room seul" in contract_movies_noroom_only_detail
            and "Pack MIX HD global Wine: desactive" in contract_movies_noroom_only_detail
            and "contract-preserving HD 1280 + CBPZ no_room seul" in contract_movies_noroom_only_detail
        ),
        contract_movies_noroom_only_detail,
        "regenerate MOVIES CBPZ no_room or fix MOVIES-only dry-run handoff",
    )

    contract_custom_pair_ok, contract_custom_pair_detail = shell_check(
        [
            "env",
            "LOLG_HD_WINE_RUNTIME_ROOT=output/lolg95_contract_dry_run_runtime",
            "WINEPREFIX=output/lolg95_contract_dry_run_wine_prefix",
            "./LOLG_HD.sh",
            "wine-vqa-contract-custom-pair",
            "--dry-run",
            "--no-dxvk",
        ],
        root,
    )
    add_check(
        checks,
        "vqa_contract_custom_pair_dry_run",
        pass_if(
            contract_custom_pair_ok
            and "LOCALLNG.MIX 1024x640 + MOVIES.MIX entree 4 892x560" in contract_custom_pair_detail
            and "MOVIES.MIX custom sous seuil entree 4" in contract_custom_pair_detail
            and "DXVK Wine: desactive" in contract_custom_pair_detail
            and "Pack MIX HD global Wine: desactive" in contract_custom_pair_detail
        ),
        contract_custom_pair_detail,
        "regenerate the custom LOCALLNG/MOVIES threshold pair or fix dry-run handoff",
    )

    safe_plan_dir = output / "vqa_safe_resolution_plan_movies"
    safe_plan_ok, safe_plan_detail = shell_check(
        [
            "env",
            f"LOLG_HD_MOVIES_SAFE_PLAN_OUTPUT={safe_plan_dir}",
            "./LOLG_HD.sh",
            "vqa-plan-movies-safe",
        ],
        root,
    )
    safe_plan_summary = read_csv_first(safe_plan_dir / "summary.csv")
    safe_plan_entries = safe_plan_dir / "entries.csv"
    safe_plan_targets: set[str] = set()
    if safe_plan_entries.exists():
        with safe_plan_entries.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                safe_plan_targets.add(f"{row.get('target_width')}x{row.get('target_height')}")
    add_check(
        checks,
        "vqa_safe_resolution_plan_movies",
        pass_if(
            safe_plan_ok
            and safe_plan_summary.get("status") == "pass"
            and safe_plan_summary.get("vqa_entries") == "28"
            and safe_plan_summary.get("block_budget") == "31220"
            and safe_plan_targets == {"892x560"}
        ),
        safe_plan_detail
        + f";status={safe_plan_summary.get('status', '')};entries={safe_plan_summary.get('vqa_entries', '')};targets={','.join(sorted(safe_plan_targets))}",
        "fix the MOVIES safe resolution planner or regenerate the measured threshold report",
    )

    safe_build_ok, safe_build_detail = shell_check(
        ["./LOLG_HD.sh", "vqa-contract-build-movies-safe", "--dry-run"],
        root,
    )
    add_check(
        checks,
        "vqa_contract_movies_safe_build_dry_run",
        pass_if(
            safe_build_ok
            and "MOVIES safe build: dry-run" in safe_build_detail
            and "tools/lolg_vqa_contract_batch_writer.py" in safe_build_detail
            and "--entries 0-27" in safe_build_detail
            and "--width 892" in safe_build_detail
            and "--height 560" in safe_build_detail
            and "LOLG_HD_MOVIES_SAFE_PLAN_EXPECT_ENTRIES=28" in safe_build_detail
            and "LOLG_HD_MOVIES_SAFE_PLAN_EXPECT_TARGET=892x560" in safe_build_detail
            and "--reuse-root output/vqa_contract_batch_writer_movies_safe_long0_0000_892x560" in safe_build_detail
            and "--reuse-root output/vqa_contract_batch_writer_movies_safe_long1_0001_892x560" in safe_build_detail
            and "--reuse-root output/vqa_contract_batch_writer_movies_safe_long2_0002_892x560" in safe_build_detail
            and "--reuse-root output/vqa_contract_batch_writer_movies_safe_long3_0003_892x560" in safe_build_detail
            and "vqa_contract_batch_writer_movies_0000_0027_892x560_safe" in safe_build_detail
        ),
        safe_build_detail,
        "fix ./LOLG_HD.sh vqa-contract-build-movies-safe --dry-run",
    )

    safe_smoke_ok, safe_smoke_detail = shell_check(
        ["./LOLG_HD.sh", "vqa-contract-build-movies-safe-smoke", "--dry-run"],
        root,
    )
    add_check(
        checks,
        "vqa_contract_movies_safe_smoke_dry_run",
        pass_if(
            safe_smoke_ok
            and "MOVIES safe build: dry-run" in safe_smoke_detail
            and "--entries 4" in safe_smoke_detail
            and "--profiles 4000" in safe_smoke_detail
            and "--width 892" in safe_smoke_detail
            and "--height 560" in safe_smoke_detail
            and "vqa_contract_batch_writer_movies_safe_smoke_0004_892x560" in safe_smoke_detail
        ),
        safe_smoke_detail,
        "fix ./LOLG_HD.sh vqa-contract-build-movies-safe-smoke --dry-run",
    )

    safe_smoke_summary = read_csv_first(
        Path("output/vqa_contract_batch_writer_movies_safe_smoke_0004_892x560/summary.csv")
    )
    safe_smoke_entry = read_csv_first(
        Path("output/vqa_contract_batch_writer_movies_safe_smoke_0004_892x560/entries.csv")
    )
    add_check(
        checks,
        "vqa_contract_movies_safe_smoke_result",
        (
            "info"
            if not safe_smoke_summary
            else pass_if(
                safe_smoke_summary.get("status") == "pass"
                and safe_smoke_summary.get("entries_requested") == "4"
                and safe_smoke_summary.get("entries_replaced") == "1"
                and safe_smoke_summary.get("width") == "892"
                and safe_smoke_summary.get("height") == "560"
                and safe_smoke_entry.get("status") == "pass"
                and safe_smoke_entry.get("entry_index") == "4"
                and safe_smoke_entry.get("profile") == "4000"
                and safe_smoke_entry.get("runtime_compat_status") == "pass"
            )
        ),
        (
            f"status={safe_smoke_summary.get('status', '')};"
            f"entries={safe_smoke_summary.get('entries_requested', '')};"
            f"replaced={safe_smoke_summary.get('entries_replaced', '')};"
            f"target={safe_smoke_summary.get('width', '')}x{safe_smoke_summary.get('height', '')};"
            f"entry_status={safe_smoke_entry.get('status', '')};"
            f"profile={safe_smoke_entry.get('profile', '')};"
            f"runtime={safe_smoke_entry.get('runtime_compat_status', '')};"
            f"max_vptz={safe_smoke_entry.get('max_vptz_size', '')}"
        ),
        "./LOLG_HD.sh vqa-contract-build-movies-safe-smoke",
    )

    safe_long0_summary = read_csv_first(
        Path("output/vqa_contract_batch_writer_movies_safe_long0_0000_892x560/summary.csv")
    )
    safe_long0_entry = read_csv_first(
        Path("output/vqa_contract_batch_writer_movies_safe_long0_0000_892x560/entries.csv")
    )
    add_check(
        checks,
        "vqa_contract_movies_safe_long0_result",
        (
            "info"
            if not safe_long0_summary
            else pass_if(
                safe_long0_summary.get("status") == "pass"
                and safe_long0_summary.get("entries_requested") == "0"
                and safe_long0_summary.get("entries_replaced") == "1"
                and safe_long0_summary.get("width") == "892"
                and safe_long0_summary.get("height") == "560"
                and safe_long0_summary.get("profile_list") == "4000"
                and safe_long0_entry.get("status") == "pass"
                and safe_long0_entry.get("entry_index") == "0"
                and safe_long0_entry.get("runtime_compat_status") == "pass"
                and as_int(safe_long0_entry, "max_vptz_size") > 0
                and as_int(safe_long0_entry, "max_vptz_size") <= 0xFFFF
            )
        ),
        (
            f"status={safe_long0_summary.get('status', '')};"
            f"entries={safe_long0_summary.get('entries_requested', '')};"
            f"replaced={safe_long0_summary.get('entries_replaced', '')};"
            f"target={safe_long0_summary.get('width', '')}x{safe_long0_summary.get('height', '')};"
            f"entry_status={safe_long0_entry.get('status', '')};"
            f"profile={safe_long0_entry.get('profile', '')};"
            f"runtime={safe_long0_entry.get('runtime_compat_status', '')};"
            f"max_vptz={safe_long0_entry.get('max_vptz_size', '')}"
        ),
        "./LOLG_HD.sh vqa-contract-build-movies-safe-long0",
    )

    safe_long1_summary = read_csv_first(
        Path("output/vqa_contract_batch_writer_movies_safe_long1_0001_892x560/summary.csv")
    )
    safe_long1_entry = read_csv_first(
        Path("output/vqa_contract_batch_writer_movies_safe_long1_0001_892x560/entries.csv")
    )
    add_check(
        checks,
        "vqa_contract_movies_safe_long1_result",
        (
            "info"
            if not safe_long1_summary
            else pass_if(
                safe_long1_summary.get("status") == "pass"
                and safe_long1_summary.get("entries_requested") == "1"
                and safe_long1_summary.get("entries_replaced") == "1"
                and safe_long1_summary.get("width") == "892"
                and safe_long1_summary.get("height") == "560"
                and safe_long1_summary.get("profile_list") == "4000"
                and safe_long1_entry.get("status") == "pass"
                and safe_long1_entry.get("entry_index") == "1"
                and safe_long1_entry.get("runtime_compat_status") == "pass"
                and as_int(safe_long1_entry, "max_vptz_size") > 0
                and as_int(safe_long1_entry, "max_vptz_size") <= 0xFFFF
            )
        ),
        (
            f"status={safe_long1_summary.get('status', '')};"
            f"entries={safe_long1_summary.get('entries_requested', '')};"
            f"replaced={safe_long1_summary.get('entries_replaced', '')};"
            f"target={safe_long1_summary.get('width', '')}x{safe_long1_summary.get('height', '')};"
            f"entry_status={safe_long1_entry.get('status', '')};"
            f"profile={safe_long1_entry.get('profile', '')};"
            f"runtime={safe_long1_entry.get('runtime_compat_status', '')};"
            f"max_vptz={safe_long1_entry.get('max_vptz_size', '')}"
        ),
        "./LOLG_HD.sh vqa-contract-build-movies-safe-long1",
    )

    safe_long2_summary = read_csv_first(
        Path("output/vqa_contract_batch_writer_movies_safe_long2_0002_892x560/summary.csv")
    )
    safe_long2_entry = read_csv_first(
        Path("output/vqa_contract_batch_writer_movies_safe_long2_0002_892x560/entries.csv")
    )
    add_check(
        checks,
        "vqa_contract_movies_safe_long2_result",
        (
            "info"
            if not safe_long2_summary
            else pass_if(
                safe_long2_summary.get("status") == "pass"
                and safe_long2_summary.get("entries_requested") == "2"
                and safe_long2_summary.get("entries_replaced") == "1"
                and safe_long2_summary.get("width") == "892"
                and safe_long2_summary.get("height") == "560"
                and safe_long2_summary.get("profile_list") == "4000"
                and safe_long2_entry.get("status") == "pass"
                and safe_long2_entry.get("entry_index") == "2"
                and safe_long2_entry.get("runtime_compat_status") == "pass"
                and as_int(safe_long2_entry, "max_vptz_size") > 0
                and as_int(safe_long2_entry, "max_vptz_size") <= 0xFFFF
            )
        ),
        (
            f"status={safe_long2_summary.get('status', '')};"
            f"entries={safe_long2_summary.get('entries_requested', '')};"
            f"replaced={safe_long2_summary.get('entries_replaced', '')};"
            f"target={safe_long2_summary.get('width', '')}x{safe_long2_summary.get('height', '')};"
            f"entry_status={safe_long2_entry.get('status', '')};"
            f"profile={safe_long2_entry.get('profile', '')};"
            f"runtime={safe_long2_entry.get('runtime_compat_status', '')};"
            f"max_vptz={safe_long2_entry.get('max_vptz_size', '')}"
        ),
        "./LOLG_HD.sh vqa-contract-build-movies-safe-long2",
    )

    safe_long3_summary = read_csv_first(
        Path("output/vqa_contract_batch_writer_movies_safe_long3_0003_892x560/summary.csv")
    )
    safe_long3_entry = read_csv_first(
        Path("output/vqa_contract_batch_writer_movies_safe_long3_0003_892x560/entries.csv")
    )
    add_check(
        checks,
        "vqa_contract_movies_safe_long3_result",
        (
            "info"
            if not safe_long3_summary
            else pass_if(
                safe_long3_summary.get("status") == "pass"
                and safe_long3_summary.get("entries_requested") == "3"
                and safe_long3_summary.get("entries_replaced") == "1"
                and safe_long3_summary.get("width") == "892"
                and safe_long3_summary.get("height") == "560"
                and safe_long3_summary.get("profile_list") == "4000"
                and safe_long3_entry.get("status") == "pass"
                and safe_long3_entry.get("entry_index") == "3"
                and safe_long3_entry.get("runtime_compat_status") == "pass"
                and as_int(safe_long3_entry, "max_vptz_size") > 0
                and as_int(safe_long3_entry, "max_vptz_size") <= 0xFFFF
            )
        ),
        (
            f"status={safe_long3_summary.get('status', '')};"
            f"entries={safe_long3_summary.get('entries_requested', '')};"
            f"replaced={safe_long3_summary.get('entries_replaced', '')};"
            f"target={safe_long3_summary.get('width', '')}x{safe_long3_summary.get('height', '')};"
            f"entry_status={safe_long3_entry.get('status', '')};"
            f"profile={safe_long3_entry.get('profile', '')};"
            f"runtime={safe_long3_entry.get('runtime_compat_status', '')};"
            f"max_vptz={safe_long3_entry.get('max_vptz_size', '')}"
        ),
        "./LOLG_HD.sh vqa-contract-build-movies-safe-long3",
    )

    safe_short_summary = read_csv_first(
        Path("output/vqa_contract_batch_writer_movies_safe_short_0005_0018_892x560/summary.csv")
    )
    safe_short_entries = read_csv_rows(
        Path("output/vqa_contract_batch_writer_movies_safe_short_0005_0018_892x560/entries.csv")
    )
    safe_short_indices = {row.get("entry_index") for row in safe_short_entries}
    safe_short_expected = {str(index) for index in range(5, 19)}
    safe_short_max_vptz = max((as_int(row, "max_vptz_size") for row in safe_short_entries), default=-1)
    add_check(
        checks,
        "vqa_contract_movies_safe_short_result",
        (
            "info"
            if not safe_short_summary
            else pass_if(
                safe_short_summary.get("status") == "pass"
                and safe_short_summary.get("entries_replaced") == "14"
                and safe_short_summary.get("entries_failed") == "0"
                and safe_short_summary.get("width") == "892"
                and safe_short_summary.get("height") == "560"
                and safe_short_summary.get("profile_list") == "4000"
                and len(safe_short_entries) == 14
                and safe_short_indices == safe_short_expected
                and all(row.get("status") == "pass" for row in safe_short_entries)
                and all(row.get("runtime_compat_status") == "pass" for row in safe_short_entries)
                and safe_short_max_vptz > 0
                and safe_short_max_vptz <= 0xFFFF
            )
        ),
        (
            f"status={safe_short_summary.get('status', '')};"
            f"entries={safe_short_summary.get('entries_requested', '')};"
            f"replaced={safe_short_summary.get('entries_replaced', '')};"
            f"failed={safe_short_summary.get('entries_failed', '')};"
            f"target={safe_short_summary.get('width', '')}x{safe_short_summary.get('height', '')};"
            f"profile={safe_short_summary.get('profile_list', '')};"
            f"rows={len(safe_short_entries)};"
            f"max_vptz={safe_short_max_vptz if safe_short_max_vptz >= 0 else ''}"
        ),
        "./LOLG_HD.sh vqa-contract-build-movies-safe-short",
    )

    safe_mid_summary = read_csv_first(
        Path("output/vqa_contract_batch_writer_movies_safe_mid_0019_0020_892x560/summary.csv")
    )
    safe_mid_entries = read_csv_rows(
        Path("output/vqa_contract_batch_writer_movies_safe_mid_0019_0020_892x560/entries.csv")
    )
    safe_mid_indices = {row.get("entry_index") for row in safe_mid_entries}
    safe_mid_max_vptz = max((as_int(row, "max_vptz_size") for row in safe_mid_entries), default=-1)
    add_check(
        checks,
        "vqa_contract_movies_safe_mid_result",
        (
            "info"
            if not safe_mid_summary
            else pass_if(
                safe_mid_summary.get("status") == "pass"
                and safe_mid_summary.get("entries_replaced") == "2"
                and safe_mid_summary.get("entries_failed") == "0"
                and safe_mid_summary.get("width") == "892"
                and safe_mid_summary.get("height") == "560"
                and safe_mid_summary.get("profile_list") == "4000"
                and len(safe_mid_entries) == 2
                and safe_mid_indices == {"19", "20"}
                and all(row.get("status") == "pass" for row in safe_mid_entries)
                and all(row.get("runtime_compat_status") == "pass" for row in safe_mid_entries)
                and safe_mid_max_vptz > 0
                and safe_mid_max_vptz <= 0xFFFF
            )
        ),
        (
            f"status={safe_mid_summary.get('status', '')};"
            f"entries={safe_mid_summary.get('entries_requested', '')};"
            f"replaced={safe_mid_summary.get('entries_replaced', '')};"
            f"failed={safe_mid_summary.get('entries_failed', '')};"
            f"target={safe_mid_summary.get('width', '')}x{safe_mid_summary.get('height', '')};"
            f"profile={safe_mid_summary.get('profile_list', '')};"
            f"rows={len(safe_mid_entries)};"
            f"max_vptz={safe_mid_max_vptz if safe_mid_max_vptz >= 0 else ''}"
        ),
        "./LOLG_HD.sh vqa-contract-build-movies-safe-mid",
    )

    safe_tail_summary = read_csv_first(
        Path("output/vqa_contract_batch_writer_movies_safe_tail_0021_0027_892x560/summary.csv")
    )
    safe_tail_entries = read_csv_rows(
        Path("output/vqa_contract_batch_writer_movies_safe_tail_0021_0027_892x560/entries.csv")
    )
    safe_tail_indices = {row.get("entry_index") for row in safe_tail_entries}
    safe_tail_max_vptz = max((as_int(row, "max_vptz_size") for row in safe_tail_entries), default=-1)
    add_check(
        checks,
        "vqa_contract_movies_safe_tail_result",
        (
            "info"
            if not safe_tail_summary
            else pass_if(
                safe_tail_summary.get("status") == "pass"
                and safe_tail_summary.get("entries_replaced") == "7"
                and safe_tail_summary.get("entries_failed") == "0"
                and safe_tail_summary.get("width") == "892"
                and safe_tail_summary.get("height") == "560"
                and safe_tail_summary.get("profile_list") == "4000"
                and len(safe_tail_entries) == 7
                and safe_tail_indices == {"21", "22", "23", "24", "25", "26", "27"}
                and all(row.get("status") == "pass" for row in safe_tail_entries)
                and all(row.get("runtime_compat_status") == "pass" for row in safe_tail_entries)
                and safe_tail_max_vptz > 0
                and safe_tail_max_vptz <= 0xFFFF
            )
        ),
        (
            f"status={safe_tail_summary.get('status', '')};"
            f"entries={safe_tail_summary.get('entries_requested', '')};"
            f"replaced={safe_tail_summary.get('entries_replaced', '')};"
            f"failed={safe_tail_summary.get('entries_failed', '')};"
            f"target={safe_tail_summary.get('width', '')}x{safe_tail_summary.get('height', '')};"
            f"profile={safe_tail_summary.get('profile_list', '')};"
            f"rows={len(safe_tail_entries)};"
            f"max_vptz={safe_tail_max_vptz if safe_tail_max_vptz >= 0 else ''}"
        ),
        "./LOLG_HD.sh vqa-contract-build-movies-safe-tail",
    )

    safe_full_summary = read_csv_first(
        Path("output/vqa_contract_batch_writer_movies_0000_0027_892x560_safe/summary.csv")
    )
    safe_full_entries = read_csv_rows(
        Path("output/vqa_contract_batch_writer_movies_0000_0027_892x560_safe/entries.csv")
    )
    safe_full_indices = {row.get("entry_index") for row in safe_full_entries}
    safe_full_expected = {str(index) for index in range(28)}
    safe_full_max_vptz = max((as_int(row, "max_vptz_size") for row in safe_full_entries), default=-1)
    add_check(
        checks,
        "vqa_contract_movies_safe_full_result",
        (
            "info"
            if not safe_full_summary
            else pass_if(
                safe_full_summary.get("status") == "pass"
                and safe_full_summary.get("entries_replaced") == "28"
                and safe_full_summary.get("entries_failed") == "0"
                and safe_full_summary.get("native_exact_pass_entries") == "28"
                and safe_full_summary.get("width") == "892"
                and safe_full_summary.get("height") == "560"
                and len(safe_full_entries) == 28
                and safe_full_indices == safe_full_expected
                and all(row.get("status") == "pass" for row in safe_full_entries)
                and all(row.get("runtime_compat_status") == "pass" for row in safe_full_entries)
                and safe_full_max_vptz > 0
                and safe_full_max_vptz <= 0xFFFF
            )
        ),
        (
            f"status={safe_full_summary.get('status', '')};"
            f"replaced={safe_full_summary.get('entries_replaced', '')};"
            f"failed={safe_full_summary.get('entries_failed', '')};"
            f"native_exact={safe_full_summary.get('native_exact_pass_entries', '')};"
            f"target={safe_full_summary.get('width', '')}x{safe_full_summary.get('height', '')};"
            f"rows={len(safe_full_entries)};"
            f"runtime={','.join(sorted({row.get('runtime_compat_status', '') for row in safe_full_entries}))};"
            f"max_vptz={safe_full_max_vptz if safe_full_max_vptz >= 0 else ''}"
        ),
        "./LOLG_HD.sh vqa-contract-build-movies-safe",
    )

    smoke = read_csv_first(args.wine_smoke_summary)
    add_check(
        checks,
        "wine_runtime_smoke_1920x1080",
        (
            "pass"
            if (
                smoke.get("status") == "pass"
                and smoke.get("resolution") == "1920x1080"
                and smoke.get("window_seen") == "1"
                and smoke.get("process_seen") == "1"
                and smoke.get("samples")
                and smoke.get("matching_samples") == smoke.get("samples")
                and not smoke.get("issues")
            )
            else "info"
        ),
        (
            f"status={smoke.get('status', '')};"
            f"resolution={smoke.get('resolution', '')};"
            f"samples={smoke.get('matching_samples', '')}/{smoke.get('samples', '')};"
            f"process_seen={smoke.get('process_seen', '')};"
            f"window_seen={smoke.get('window_seen', '')};"
            f"gl_renderer={smoke.get('gl_renderer', '')};"
            f"gl_renderer_kind={smoke.get('gl_renderer_kind', '')};"
            f"issues={smoke.get('issues', '')}"
        ),
        "diagnostic only; current recommended HD-critical path is ./LOLG_HD.sh sidecar-hd",
    )

    smoke_1280 = read_csv_first(args.wine_smoke_1280_summary)
    add_check(
        checks,
        "wine_runtime_smoke_1280x1024",
        (
            "pass"
            if (
                smoke_1280.get("status") == "pass"
                and smoke_1280.get("resolution") == "1280x1024"
                and smoke_1280.get("window_seen") == "1"
                and smoke_1280.get("process_seen") == "1"
                and smoke_1280.get("samples")
                and smoke_1280.get("matching_samples") == smoke_1280.get("samples")
                and not smoke_1280.get("issues")
            )
            else "info"
        ),
        (
            f"status={smoke_1280.get('status', '')};"
            f"resolution={smoke_1280.get('resolution', '')};"
            f"samples={smoke_1280.get('matching_samples', '')}/{smoke_1280.get('samples', '')};"
            f"process_seen={smoke_1280.get('process_seen', '')};"
            f"window_seen={smoke_1280.get('window_seen', '')};"
            f"gl_renderer={smoke_1280.get('gl_renderer', '')};"
            f"gl_renderer_kind={smoke_1280.get('gl_renderer_kind', '')};"
            f"issues={smoke_1280.get('issues', '')}"
        ),
        "diagnostic only; current recommended HD-critical path is ./LOLG_HD.sh sidecar-hd",
    )

    passed = sum(1 for row in checks if row["status"] == "pass")
    gaps = [row["check"] for row in checks if row["status"] == "gap"]
    info = sum(1 for row in checks if row["status"] == "info")
    status = "pass" if not gaps else "gap"
    summary = {
        "status": status,
        "checks": str(len(checks)),
        "passed": str(passed),
        "gaps": str(len(gaps)),
        "info": str(info),
        "output": str(output),
        "issues": ";".join(gaps),
        "next_step": "release check passed" if not gaps else "fix release check gaps",
    }
    write_csv(output / "checks.csv", CHECK_FIELDS, checks)
    write_csv(output / "summary.csv", SUMMARY_FIELDS, [summary])
    build_html(output / "index.html", summary, checks)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Check the LOLG Full HD launch/release state.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--vqa-pack-summary", type=Path, default=DEFAULT_VQA_PACK_SUMMARY)
    parser.add_argument("--audit-summary", type=Path, default=DEFAULT_AUDIT_SUMMARY)
    parser.add_argument("--oversize-summary", type=Path, default=DEFAULT_OVERSIZE_SUMMARY)
    parser.add_argument("--lcw-probe-summary", type=Path, default=DEFAULT_LCW_PROBE_SUMMARY)
    parser.add_argument("--wine-smoke-summary", type=Path, default=DEFAULT_WINE_SMOKE_SUMMARY)
    parser.add_argument("--wine-smoke-1280-summary", type=Path, default=DEFAULT_WINE_SMOKE_1280_SUMMARY)
    parser.add_argument("--wine-stage", type=Path, default=DEFAULT_WINE_STAGE)
    parser.add_argument("--wineprefix", type=Path, default=DEFAULT_WINEPREFIX)
    args = parser.parse_args()

    summary = run_check(args)
    print(
        "HD release check: "
        f"{summary['status']} ({summary['passed']} pass + {summary['info']} info / "
        f"{summary['checks']} checks, gaps={summary['gaps']})"
    )
    print(f"Summary: {args.output / 'summary.csv'}")
    print(f"HTML: {args.output / 'index.html'}")
    if summary["issues"]:
        print(f"Issues: {summary['issues']}")


if __name__ == "__main__":
    main()
