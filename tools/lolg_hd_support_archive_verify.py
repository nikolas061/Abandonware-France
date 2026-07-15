#!/usr/bin/env python3
"""Verify a LOLG HD support bundle tar.gz archive after safe extraction."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import os
import re
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath


DEFAULT_ARCHIVE = Path("output/hd_support_bundle.tar.gz")
DEFAULT_OUTPUT = Path("output/hd_support_archive_verify")
DEFAULT_MANIFEST_VERIFIER = Path("tools/lolg_hd_support_manifest_verify.py")
ARCHIVE_SUMMARY_VERSION = "1"
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
UTC_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
ARTIFACT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
ARCHIVE_SUMMARY_REQUIRED_KEYS = [
    "support_archive_summary_version",
    "generated_utc",
    "archive",
    "archive_size",
    "sha256",
    "sha256_file",
    "bundle_dir",
]

CHECK_FIELDS = ["check", "status", "evidence", "issues"]
SUMMARY_FIELDS = [
    "status",
    "checks",
    "passed",
    "gaps",
    "members",
    "files",
    "top_level",
    "archive_size",
    "archive_not_empty_status",
    "single_top_level_status",
    "top_level_name_status",
    "safe_paths",
    "supported_types",
    "checksum_status",
    "checksum_line_count",
    "checksum_expected",
    "checksum_actual",
    "archive_summary_status",
    "archive_summary_schema_status",
    "archive_summary_missing_keys",
    "archive_summary_extra_keys",
    "archive_summary_duplicate_keys",
    "archive_summary_malformed_lines",
    "archive_summary_sha256",
    "artifacts_status",
    "artifacts_files",
    "artifacts_schema_status",
    "artifacts_duplicate_fields_status",
    "artifacts_duplicate_paths_status",
    "artifacts_row_width_status",
    "artifacts_field_format_status",
    "artifacts_safe_paths_status",
    "artifacts_count_status",
    "artifacts_paths_status",
    "manifest_status",
    "launcher_status",
    "archive",
    "output",
    "issues",
    "next_step",
]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv_first(path: Path) -> dict[str, str]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except FileNotFoundError:
        return {}
    return rows[0] if rows else {}


def read_key_value_file(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except FileNotFoundError:
        return {}
    data: dict[str, str] = {}
    for line in lines:
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def key_value_duplicate_keys(path: Path) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except FileNotFoundError:
        return []
    seen: set[str] = set()
    duplicates: list[str] = []
    for line in lines:
        if not line or line.startswith("#") or "=" not in line:
            continue
        key = line.split("=", 1)[0].strip()
        if key in seen and key not in duplicates:
            duplicates.append(key)
        seen.add(key)
    return duplicates


def key_value_malformed_lines(path: Path) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except FileNotFoundError:
        return []
    malformed: list[str] = []
    for index, line in enumerate(lines, start=1):
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            malformed.append(str(index))
    return malformed


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def csv_fieldnames(handle: csv.DictReader[str]) -> list[str]:
    return [field if field is not None else "<extra>" for field in (handle.fieldnames or [])]


def csv_duplicate_fieldnames(fieldnames: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for field in fieldnames:
        if field in seen and field not in duplicates:
            duplicates.append(field)
        seen.add(field)
    return duplicates


def duplicate_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def add_check(rows: list[dict[str, str]], name: str, ok: bool, evidence: str, issues: str = "") -> None:
    rows.append(
        {
            "check": name,
            "status": "pass" if ok else "gap",
            "evidence": evidence,
            "issues": "" if ok else issues,
        }
    )


def safe_tar_name(name: str) -> bool:
    if not name or name.startswith("/") or "\\" in name:
        return False
    parts = PurePosixPath(name).parts
    return bool(parts) and all(part not in {"", ".", ".."} for part in parts)


def safe_artifact_name(name: str) -> bool:
    if not name or name.startswith("/") or "\\" in name or "/" in name:
        return False
    return name not in {".", ".."} and ARTIFACT_NAME_RE.match(name) is not None


def check_status(rows: list[dict[str, str]], name: str) -> str:
    for row in rows:
        if row["check"] == name:
            return row["status"]
    return ""


def build_html(path: Path, summary: dict[str, str], checks: list[dict[str, str]]) -> None:
    rows = []
    for row in checks:
        status = row["status"]
        rows.append(
            "<tr>"
            f"<td>{html.escape(row['check'])}</td>"
            f"<td class='{html.escape(status)}'>{html.escape(status)}</td>"
            f"<td>{html.escape(row['evidence'])}</td>"
            f"<td>{html.escape(row['issues'])}</td>"
            "</tr>"
        )
    document = f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>LOLG HD Support Archive Verify</title>
<style>
body {{ font-family: sans-serif; margin: 2rem; background: #f7f7f5; color: #171717; }}
table {{ border-collapse: collapse; width: 100%; background: white; }}
th, td {{ border: 1px solid #d7d7d0; padding: 0.45rem 0.6rem; text-align: left; vertical-align: top; }}
th {{ background: #ecece6; }}
.pass {{ color: #106b2f; font-weight: 700; }}
.gap {{ color: #a22522; font-weight: 700; }}
code {{ background: #eee; padding: 0.1rem 0.25rem; }}
</style>
<h1>LOLG HD Support Archive Verify</h1>
<p>Status: <strong class="{html.escape(summary['status'])}">{html.escape(summary['status'])}</strong></p>
<p>Checks: {html.escape(summary['passed'])} pass / {html.escape(summary['checks'])},
gaps={html.escape(summary['gaps'])}</p>
<p>Strict checks:
checksum={html.escape(summary['checksum_status'])},
archive_summary={html.escape(summary['archive_summary_status'])},
summary_schema={html.escape(summary['archive_summary_schema_status'])},
artifacts={html.escape(summary['artifacts_status'])},
artifacts_schema={html.escape(summary['artifacts_schema_status'])},
artifacts_duplicate_paths={html.escape(summary['artifacts_duplicate_paths_status'])},
artifacts_row_width={html.escape(summary['artifacts_row_width_status'])},
artifacts_field_format={html.escape(summary['artifacts_field_format_status'])},
artifacts_safe_paths={html.escape(summary['artifacts_safe_paths_status'])},
artifacts_count={html.escape(summary['artifacts_count_status'])},
artifacts_paths={html.escape(summary['artifacts_paths_status'])},
archive_not_empty={html.escape(summary['archive_not_empty_status'])},
single_top_level={html.escape(summary['single_top_level_status'])},
top_level_name={html.escape(summary['top_level_name_status'])},
safe_paths={html.escape(summary['safe_paths'])},
supported_types={html.escape(summary['supported_types'])},
manifest={html.escape(summary['manifest_status'])},
launcher={html.escape(summary['launcher_status'])}</p>
<table>
<thead><tr><th>Check</th><th>Status</th><th>Evidence</th><th>Issues</th></tr></thead>
<tbody>
{''.join(rows)}
</tbody>
</table>
</html>
"""
    path.write_text(document, encoding="utf-8")


def run_command(command: list[str], env: dict[str, str] | None = None) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            env=env,
            check=False,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"{type(exc).__name__}:{exc}"
    detail = (result.stdout + result.stderr).strip().replace("\n", " | ")
    return result.returncode == 0, detail


def verify_archive(args: argparse.Namespace) -> dict[str, str]:
    archive = args.archive
    checksum = args.checksum or Path(str(archive) + ".sha256")
    archive_summary = args.archive_summary or Path(str(archive) + ".summary")
    artifacts = args.artifacts or Path(str(archive) + ".artifacts.csv")
    archive_companion = Path(str(archive) + ".verify.sh")
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    output_abs = output.resolve()
    checks: list[dict[str, str]] = []
    members: list[tarfile.TarInfo] = []
    top_level = ""
    archive_size = ""
    checksum_status = ""
    checksum_line_count = ""
    checksum_expected = ""
    checksum_actual = ""
    archive_summary_status = ""
    archive_summary_schema_status = ""
    archive_summary_missing_keys = ""
    archive_summary_extra_keys = ""
    archive_summary_duplicate_keys = ""
    archive_summary_malformed_lines = ""
    archive_summary_sha256 = ""
    artifacts_status = ""
    artifacts_files = ""
    manifest_status = ""
    launcher_status = ""

    add_check(checks, "archive_exists", archive.is_file(), str(archive), "archive_missing")
    if archive.is_file():
        archive_size = str(archive.stat().st_size)
        checksum_actual = sha256_file(archive)

    add_check(checks, "checksum_exists", checksum.is_file(), str(checksum), "checksum_missing")
    if checksum.is_file():
        checksum_text = checksum.read_text(encoding="utf-8", errors="replace").strip().splitlines()
        checksum_line_count = str(len(checksum_text))
        add_check(
            checks,
            "checksum_line_count",
            len(checksum_text) == 1,
            checksum_line_count,
            "checksum_line_count_mismatch",
        )
        checksum_parts = checksum_text[0].split() if checksum_text else []
        checksum_expected = checksum_parts[0] if checksum_parts else ""
        checksum_name = checksum_parts[1].lstrip("*") if len(checksum_parts) == 2 else ""
        checksum_format_ok = len(checksum_parts) == 2 and SHA256_RE.match(checksum_expected) is not None
        add_check(
            checks,
            "checksum_format",
            checksum_format_ok,
            checksum_text[0] if checksum_text else "",
            "checksum_format_invalid",
        )
        add_check(
            checks,
            "checksum_archive_name",
            checksum_format_ok and checksum_name == archive.name,
            checksum_name,
            "checksum_archive_name_mismatch",
        )
        if archive.is_file() and checksum_format_ok:
            checksum_status = "pass" if checksum_actual.lower() == checksum_expected.lower() else "gap"
            add_check(
                checks,
                "archive_sha256",
                checksum_status == "pass",
                f"expected={checksum_expected};actual={checksum_actual}",
                "archive_sha256_mismatch",
            )

    add_check(
        checks,
        "archive_summary_exists",
        archive_summary.is_file(),
        str(archive_summary),
        "archive_summary_missing",
    )
    if archive_summary.is_file():
        archive_summary_data = read_key_value_file(archive_summary)
        archive_summary_sha256 = archive_summary_data.get("sha256", "")
        archive_summary_duplicates = key_value_duplicate_keys(archive_summary)
        archive_summary_malformed = key_value_malformed_lines(archive_summary)
        archive_summary_missing = [
            key for key in ARCHIVE_SUMMARY_REQUIRED_KEYS if key not in archive_summary_data
        ]
        archive_summary_extra = [
            key for key in archive_summary_data if key not in ARCHIVE_SUMMARY_REQUIRED_KEYS
        ]
        archive_summary_missing_keys = ",".join(archive_summary_missing)
        archive_summary_extra_keys = ",".join(archive_summary_extra)
        archive_summary_duplicate_keys = ",".join(archive_summary_duplicates)
        archive_summary_malformed_lines = ",".join(archive_summary_malformed)
        archive_summary_schema_ok = not archive_summary_missing and not archive_summary_extra
        archive_summary_schema_status = "pass" if archive_summary_schema_ok else "gap"
        add_check(
            checks,
            "archive_summary_schema",
            archive_summary_schema_ok,
            "keys=" + ",".join(archive_summary_data),
            "archive_summary_schema_mismatch",
        )
        add_check(
            checks,
            "archive_summary_duplicate_keys",
            not archive_summary_duplicates,
            archive_summary_duplicate_keys,
            "archive_summary_duplicate_keys",
        )
        add_check(
            checks,
            "archive_summary_malformed_lines",
            not archive_summary_malformed,
            archive_summary_malformed_lines,
            "archive_summary_malformed_lines",
        )
        summary_checks = [
            (
                "archive_summary_version",
                archive_summary_data.get("support_archive_summary_version") == ARCHIVE_SUMMARY_VERSION,
                archive_summary_data.get("support_archive_summary_version", ""),
                "archive_summary_version_mismatch",
            ),
            (
                "archive_summary_generated_utc",
                UTC_TIMESTAMP_RE.match(archive_summary_data.get("generated_utc", "")) is not None,
                archive_summary_data.get("generated_utc", ""),
                "archive_summary_generated_utc_invalid",
            ),
            (
                "archive_summary_archive",
                archive_summary_data.get("archive") == archive.name,
                archive_summary_data.get("archive", ""),
                "archive_summary_archive_mismatch",
            ),
            (
                "archive_summary_size",
                bool(archive_size) and archive_summary_data.get("archive_size") == archive_size,
                archive_summary_data.get("archive_size", ""),
                "archive_summary_size_mismatch",
            ),
            (
                "archive_summary_sha256",
                bool(checksum_actual)
                and SHA256_RE.match(archive_summary_sha256) is not None
                and archive_summary_sha256.lower() == checksum_actual.lower(),
                archive_summary_sha256,
                "archive_summary_sha256_mismatch",
            ),
            (
                "archive_summary_sha256_file",
                archive_summary_data.get("sha256_file") == checksum.name,
                archive_summary_data.get("sha256_file", ""),
                "archive_summary_sha256_file_mismatch",
            ),
            (
                "archive_summary_bundle_dir",
                archive_summary_data.get("bundle_dir") == archive.stem.removesuffix(".tar"),
                archive_summary_data.get("bundle_dir", ""),
                "archive_summary_bundle_dir_mismatch",
            ),
        ]
        archive_summary_status = (
            "pass"
            if (
                archive_summary_schema_ok
                and not archive_summary_duplicates
                and not archive_summary_malformed
                and all(ok for _, ok, _, _ in summary_checks)
            )
            else "gap"
        )
        for name, ok, evidence, issue in summary_checks:
            add_check(checks, name, ok, evidence, issue)

    artifact_check_start = len(checks)
    add_check(checks, "artifacts_exists", artifacts.is_file(), str(artifacts), "artifacts_missing")
    if artifacts.is_file():
        with artifacts.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            artifact_rows = list(reader)
            artifact_fieldnames = csv_fieldnames(reader)
            artifact_duplicate_fields = csv_duplicate_fieldnames(artifact_fieldnames)
        artifacts_files = str(len(artifact_rows))
        artifact_required_fields = {"path", "size", "sha256", "executable"}
        artifact_fields = set(artifact_fieldnames)
        artifact_schema_ok = artifact_fields == artifact_required_fields
        add_check(
            checks,
            "artifacts_schema",
            artifact_schema_ok,
            ",".join(artifact_fieldnames),
            "artifacts_schema_mismatch",
        )
        add_check(
            checks,
            "artifacts_duplicate_fields",
            not artifact_duplicate_fields,
            ",".join(artifact_duplicate_fields),
            "artifacts_duplicate_fields",
        )
        artifact_row_width_ok = not any(None in row for row in artifact_rows)
        add_check(
            checks,
            "artifacts_row_width",
            artifact_row_width_ok,
            f"rows={len(artifact_rows)}",
            "artifacts_row_width_mismatch",
        )
        artifact_field_format_issues = []
        for row in artifact_rows:
            row_path = row.get("path", "")
            if not row.get("size", "").isdigit():
                artifact_field_format_issues.append(f"size:{row_path}")
            if SHA256_RE.match(row.get("sha256", "")) is None:
                artifact_field_format_issues.append(f"sha256:{row_path}")
            if row.get("executable") not in {"0", "1"}:
                artifact_field_format_issues.append(f"executable:{row_path}")
        artifact_field_format_ok = not artifact_field_format_issues
        add_check(
            checks,
            "artifacts_field_formats",
            artifact_field_format_ok,
            ";".join(artifact_field_format_issues[:5]),
            "artifacts_field_format_mismatch",
        )
        unsafe_artifact_paths = [
            row.get("path", "") for row in artifact_rows if not safe_artifact_name(row.get("path", ""))
        ]
        add_check(
            checks,
            "artifacts_safe_paths",
            not unsafe_artifact_paths,
            ",".join(unsafe_artifact_paths[:5]),
            "artifacts_unsafe_paths",
        )
        expected_artifacts = {
            archive.name: archive,
            checksum.name: checksum,
            archive_summary.name: archive_summary,
            archive_companion.name: archive_companion,
        }
        artifact_duplicate_paths = duplicate_values([row.get("path", "") for row in artifact_rows])
        artifact_paths = {row.get("path", "") for row in artifact_rows}
        add_check(
            checks,
            "artifacts_duplicate_paths",
            not artifact_duplicate_paths,
            ",".join(artifact_duplicate_paths),
            "artifacts_duplicate_paths",
        )
        add_check(
            checks,
            "artifacts_count",
            len(artifact_rows) == len(expected_artifacts),
            f"expected={len(expected_artifacts)};actual={len(artifact_rows)}",
            "artifacts_count_mismatch",
        )
        add_check(
            checks,
            "artifacts_paths",
            artifact_schema_ok
            and artifact_row_width_ok
            and not artifact_duplicate_paths
            and not unsafe_artifact_paths
            and len(artifact_rows) == len(expected_artifacts)
            and artifact_paths == set(expected_artifacts),
            "expected="
            + ";".join(sorted(expected_artifacts))
            + ";actual="
            + ";".join(sorted(artifact_paths)),
            "artifacts_paths_mismatch",
        )
        artifact_paths_ok = (
            artifact_schema_ok
            and artifact_row_width_ok
            and artifact_field_format_ok
            and not artifact_duplicate_paths
            and not unsafe_artifact_paths
            and len(artifact_rows) == len(expected_artifacts)
            and artifact_paths == set(expected_artifacts)
        )
        if artifact_paths_ok:
            rows_by_path = {row.get("path", ""): row for row in artifact_rows}
            for name, path in expected_artifacts.items():
                row = rows_by_path.get(name, {})
                path_exists = path.is_file()
                actual_size = str(path.stat().st_size) if path_exists else ""
                actual_sha256 = sha256_file(path) if path_exists else ""
                actual_executable = "1" if path_exists and path.stat().st_mode & 0o111 else "0"
                row_ok = (
                    path_exists
                    and row.get("size") == actual_size
                    and row.get("sha256", "").lower() == actual_sha256.lower()
                    and row.get("executable") == actual_executable
                )
                add_check(
                    checks,
                    f"artifact_{name}",
                    row_ok,
                    (
                        f"size={row.get('size', '')}/{actual_size};"
                        f"sha256={row.get('sha256', '')}/{actual_sha256};"
                        f"executable={row.get('executable', '')}/{actual_executable}"
                    ),
                    f"artifact_mismatch={name}",
                )
    artifact_checks = checks[artifact_check_start:]
    artifacts_status = "pass" if artifact_checks and all(row["status"] == "pass" for row in artifact_checks) else "gap"

    if archive.is_file():
        try:
            with tarfile.open(archive, "r:gz") as tar:
                members = tar.getmembers()
        except tarfile.TarError as exc:
            add_check(checks, "archive_readable", False, type(exc).__name__, str(exc))
        else:
            add_check(checks, "archive_readable", True, f"members={len(members)}")
            add_check(checks, "archive_not_empty", bool(members), f"members={len(members)}", "archive_empty")

    if members:
        unsafe = [member.name for member in members if not safe_tar_name(member.name)]
        unsupported = [
            member.name for member in members if not (member.isfile() or member.isdir())
        ]
        top_levels = sorted({PurePosixPath(member.name).parts[0] for member in members})
        top_level = top_levels[0] if len(top_levels) == 1 else ""
        expected_top_level = archive.stem.removesuffix(".tar")
        file_members = [member for member in members if member.isfile()]
        verify_member = next(
            (
                member
                for member in members
                if PurePosixPath(member.name).parts == (top_level, "VERIFY_SUPPORT.sh")
            ),
            None,
        )
        manifest_member = next(
            (
                member
                for member in members
                if PurePosixPath(member.name).parts == (top_level, "BUNDLE_MANIFEST.csv")
            ),
            None,
        )
        add_check(checks, "safe_paths", not unsafe, f"unsafe={len(unsafe)}", ";".join(unsafe[:5]))
        add_check(
            checks,
            "supported_types",
            not unsupported,
            f"unsupported={len(unsupported)}",
            ";".join(unsupported[:5]),
        )
        add_check(
            checks,
            "single_top_level",
            len(top_levels) == 1,
            ",".join(top_levels[:5]),
            "expected_single_top_level",
        )
        add_check(
            checks,
            "top_level_name",
            len(top_levels) == 1 and top_level == expected_top_level,
            f"expected={expected_top_level};actual={top_level}",
            "top_level_name_mismatch",
        )
        add_check(
            checks,
            "bundle_manifest_member",
            manifest_member is not None,
            "BUNDLE_MANIFEST.csv",
            "bundle_manifest_missing",
        )
        add_check(
            checks,
            "verify_script_member",
            verify_member is not None,
            "VERIFY_SUPPORT.sh",
            "verify_script_missing",
        )
        add_check(
            checks,
            "verify_script_tar_executable",
            verify_member is not None and bool(verify_member.mode & 0o111),
            f"mode={oct(verify_member.mode) if verify_member else ''}",
            "verify_script_not_executable",
        )
    else:
        file_members = []

    if not any(row["status"] == "gap" for row in checks):
        with tempfile.TemporaryDirectory(prefix="lolg_hd_support_archive_") as tmp:
            tmp_path = Path(tmp)
            with tarfile.open(archive, "r:gz") as tar:
                tar.extractall(tmp_path, filter="data")
            extracted_root = tmp_path / top_level
            add_check(
                checks,
                "extracted_root",
                extracted_root.is_dir(),
                str(extracted_root),
                "extracted_root_missing",
            )
            verify_script = extracted_root / "VERIFY_SUPPORT.sh"
            add_check(
                checks,
                "verify_script_extracted_executable",
                verify_script.is_file() and bool(verify_script.stat().st_mode & 0o111),
                str(verify_script),
                "verify_script_not_executable_after_extract",
            )

            manifest_output = output_abs / "manifest"
            manifest_ok, manifest_detail = run_command(
                [
                    "python3",
                    str(args.manifest_verifier),
                    str(extracted_root),
                    "-o",
                    str(manifest_output),
                ]
            )
            manifest_summary = read_csv_first(manifest_output / "summary.csv")
            manifest_status = manifest_summary.get("status", "")
            add_check(
                checks,
                "manifest_verify_extracted",
                manifest_ok and manifest_status == "pass",
                f"status={manifest_status};{manifest_detail}",
                "manifest_verify_failed",
            )

            launcher_output = output_abs / "launcher"
            launcher_env = os.environ.copy()
            launcher_env["LOLG_HD_SUPPORT_VERIFY_OUTPUT"] = str(launcher_output)
            launcher_ok, launcher_detail = run_command([str(verify_script)], env=launcher_env)
            launcher_summary = read_csv_first(launcher_output / "summary.csv")
            launcher_status = launcher_summary.get("status", "")
            add_check(
                checks,
                "verify_script_extracted_run",
                launcher_ok and launcher_status == "pass",
                f"status={launcher_status};{launcher_detail}",
                "verify_script_run_failed",
            )

    gaps = [row for row in checks if row["status"] == "gap"]
    passed = [row for row in checks if row["status"] == "pass"]
    issue_names = sorted({row["issues"] for row in gaps if row["issues"]})
    safe_paths_status = check_status(checks, "safe_paths")
    supported_types_status = check_status(checks, "supported_types")
    archive_not_empty_status = check_status(checks, "archive_not_empty")
    single_top_level_status = check_status(checks, "single_top_level")
    top_level_name_status = check_status(checks, "top_level_name")
    summary = {
        "status": "pass" if not gaps else "gap",
        "checks": str(len(checks)),
        "passed": str(len(passed)),
        "gaps": str(len(gaps)),
        "members": str(len(members)),
        "files": str(len(file_members)),
        "top_level": top_level,
        "archive_size": archive_size,
        "archive_not_empty_status": archive_not_empty_status,
        "single_top_level_status": single_top_level_status,
        "top_level_name_status": top_level_name_status,
        "safe_paths": "1" if safe_paths_status == "pass" else "0",
        "supported_types": "1" if supported_types_status == "pass" else "0",
        "checksum_status": checksum_status,
        "checksum_line_count": checksum_line_count,
        "checksum_expected": checksum_expected,
        "checksum_actual": checksum_actual,
        "archive_summary_status": archive_summary_status,
        "archive_summary_schema_status": archive_summary_schema_status,
        "archive_summary_missing_keys": archive_summary_missing_keys,
        "archive_summary_extra_keys": archive_summary_extra_keys,
        "archive_summary_duplicate_keys": archive_summary_duplicate_keys,
        "archive_summary_malformed_lines": archive_summary_malformed_lines,
        "archive_summary_sha256": archive_summary_sha256,
        "artifacts_status": artifacts_status,
        "artifacts_files": artifacts_files,
        "artifacts_schema_status": check_status(checks, "artifacts_schema"),
        "artifacts_duplicate_fields_status": check_status(checks, "artifacts_duplicate_fields"),
        "artifacts_duplicate_paths_status": check_status(checks, "artifacts_duplicate_paths"),
        "artifacts_row_width_status": check_status(checks, "artifacts_row_width"),
        "artifacts_field_format_status": check_status(checks, "artifacts_field_formats"),
        "artifacts_safe_paths_status": check_status(checks, "artifacts_safe_paths"),
        "artifacts_count_status": check_status(checks, "artifacts_count"),
        "artifacts_paths_status": check_status(checks, "artifacts_paths"),
        "manifest_status": manifest_status,
        "launcher_status": launcher_status,
        "archive": str(archive),
        "output": str(output),
        "issues": ";".join(issue_names),
        "next_step": "support archive verified" if not gaps else "./LOLG_HD.sh support",
    }
    write_csv(output / "checks.csv", CHECK_FIELDS, checks)
    write_csv(output / "summary.csv", SUMMARY_FIELDS, [summary])
    build_html(output / "index.html", summary, checks)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a LOLG HD support tar.gz archive.")
    parser.add_argument("archive", nargs="?", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--checksum", type=Path)
    parser.add_argument("--archive-summary", type=Path)
    parser.add_argument("--artifacts", type=Path)
    parser.add_argument("--manifest-verifier", type=Path, default=DEFAULT_MANIFEST_VERIFIER)
    args = parser.parse_args()

    summary = verify_archive(args)
    print(
        "HD support archive verify: "
        f"{summary['status']} checks={summary['passed']} pass / {summary['checks']} "
        f"gaps={summary['gaps']} checksum={summary['checksum_status']} "
        f"archive_summary={summary['archive_summary_status']} "
        f"artifacts={summary['artifacts_status']} "
        f"artifact_duplicate_paths={summary['artifacts_duplicate_paths_status']} "
        f"artifact_field_format={summary['artifacts_field_format_status']} "
        f"artifact_safe_paths={summary['artifacts_safe_paths_status']} "
        f"archive_not_empty={summary['archive_not_empty_status']} "
        f"single_top_level={summary['single_top_level_status']} "
        f"top_level_name={summary['top_level_name_status']} "
        f"files={summary['files']} top={summary['top_level']}"
    )
    print(f"Summary: {args.output / 'summary.csv'}")
    print(f"Checks: {args.output / 'checks.csv'}")
    print(f"HTML: {args.output / 'index.html'}")
    if summary["issues"]:
        print(f"Issues: {summary['issues']}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
