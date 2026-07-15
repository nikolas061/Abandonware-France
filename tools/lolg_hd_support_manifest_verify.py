#!/usr/bin/env python3
"""Verify BUNDLE_MANIFEST.csv inside a LOLG HD support bundle."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import re
from pathlib import Path, PurePosixPath


DEFAULT_ROOT = Path("output/hd_support_bundle")
DEFAULT_OUTPUT = Path("output/hd_support_manifest_verify")
MANIFEST_NAME = "BUNDLE_MANIFEST.csv"
MANIFEST_REQUIRED_FIELDS = ["path", "size", "sha256", "executable"]
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")

CHECK_FIELDS = [
    "path",
    "status",
    "expected_size",
    "actual_size",
    "sha256_expected",
    "sha256_actual",
    "expected_executable",
    "actual_executable",
    "issues",
]

SUMMARY_FIELDS = [
    "status",
    "checked",
    "passed",
    "gaps",
    "info",
    "rows",
    "manifest_schema",
    "manifest_missing_fields",
    "manifest_extra_fields",
    "manifest_duplicate_fields",
    "duplicates",
    "missing",
    "not_file",
    "unexpected",
    "size_mismatch",
    "size_invalid",
    "sha256_mismatch",
    "sha256_invalid",
    "executable_mismatch",
    "executable_invalid",
    "unsafe_paths",
    "noncanonical_paths",
    "row_width_mismatch",
    "png_entries",
    "manifest",
    "root",
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_relative_path(raw_path: str) -> bool:
    path = Path(raw_path)
    return bool(raw_path) and "\\" not in raw_path and not path.is_absolute() and ".." not in path.parts


def csv_duplicate_fieldnames(fieldnames: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for field in fieldnames:
        if field in seen and field not in duplicates:
            duplicates.append(field)
        seen.add(field)
    return duplicates


def actual_bundle_files(root: Path) -> set[str]:
    return {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != MANIFEST_NAME
    }


def build_html(path: Path, summary: dict[str, str], rows: list[dict[str, str]]) -> None:
    table_rows = []
    for row in rows:
        cls = row["status"]
        table_rows.append(
            "<tr>"
            f"<td><code>{html.escape(row['path'])}</code></td>"
            f"<td class='{html.escape(cls)}'>{html.escape(row['status'])}</td>"
            f"<td>{html.escape(row['expected_size'])}</td>"
            f"<td>{html.escape(row['actual_size'])}</td>"
            f"<td>{html.escape(row['sha256_expected'][:16])}</td>"
            f"<td>{html.escape(row['sha256_actual'][:16])}</td>"
            f"<td>{html.escape(row['expected_executable'])}</td>"
            f"<td>{html.escape(row['actual_executable'])}</td>"
            f"<td>{html.escape(row['issues'])}</td>"
            "</tr>"
        )
    document = f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>LOLG HD Support Manifest Verify</title>
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
<h1>LOLG HD Support Manifest Verify</h1>
<p>Status: <strong class="{html.escape(summary['status'])}">{html.escape(summary['status'])}</strong></p>
<p>Rows: {html.escape(summary['passed'])} pass / {html.escape(summary['checked'])},
gaps={html.escape(summary['gaps'])}, info={html.escape(summary['info'])}</p>
<p>Strict checks:
schema={html.escape(summary['manifest_schema'])},
extra_fields={html.escape(summary['manifest_extra_fields'])},
duplicate_fields={html.escape(summary['manifest_duplicate_fields'])},
row_width_mismatch={html.escape(summary['row_width_mismatch'])},
unsafe_paths={html.escape(summary['unsafe_paths'])},
noncanonical_paths={html.escape(summary['noncanonical_paths'])},
duplicates={html.escape(summary['duplicates'])},
missing={html.escape(summary['missing'])},
not_file={html.escape(summary['not_file'])},
size_mismatch={html.escape(summary['size_mismatch'])},
size_invalid={html.escape(summary['size_invalid'])},
sha256_mismatch={html.escape(summary['sha256_mismatch'])},
sha256_invalid={html.escape(summary['sha256_invalid'])},
executable_mismatch={html.escape(summary['executable_mismatch'])},
executable_invalid={html.escape(summary['executable_invalid'])},
png_entries={html.escape(summary['png_entries'])},
unexpected={html.escape(summary['unexpected'])}</p>
<table>
<thead><tr><th>Path</th><th>Status</th><th>Expected bytes</th><th>Actual bytes</th><th>Expected SHA256</th><th>Actual SHA256</th><th>Expected exec</th><th>Actual exec</th><th>Issues</th></tr></thead>
<tbody>
{''.join(table_rows)}
</tbody>
</table>
</html>
"""
    path.write_text(document, encoding="utf-8")


def verify_support_manifest(args: argparse.Namespace) -> dict[str, str]:
    root = args.root
    output = args.output
    manifest = args.manifest or root / MANIFEST_NAME
    output.mkdir(parents=True, exist_ok=True)

    if not manifest.exists():
        summary = {
            "status": "gap",
            "checked": "0",
            "passed": "0",
            "gaps": "1",
            "info": "0",
            "rows": "0",
            "manifest_schema": "gap",
            "manifest_missing_fields": ",".join(MANIFEST_REQUIRED_FIELDS),
            "manifest_extra_fields": "",
            "manifest_duplicate_fields": "",
            "duplicates": "0",
            "missing": "0",
            "not_file": "0",
            "unexpected": "0",
            "size_mismatch": "0",
            "size_invalid": "0",
            "sha256_mismatch": "0",
            "sha256_invalid": "0",
            "executable_mismatch": "0",
            "executable_invalid": "0",
            "unsafe_paths": "0",
            "noncanonical_paths": "0",
            "row_width_mismatch": "0",
            "png_entries": "0",
            "manifest": str(manifest),
            "root": str(root),
            "output": str(output),
            "issues": "manifest_missing",
            "next_step": "./LOLG_HD.sh support",
        }
        write_csv(output / "checks.csv", CHECK_FIELDS, [])
        write_csv(output / "summary.csv", SUMMARY_FIELDS, [summary])
        build_html(output / "index.html", summary, [])
        return summary

    with manifest.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        manifest_fields = reader.fieldnames or []
        manifest_rows = list(reader)

    checks: list[dict[str, str]] = []
    missing_manifest_fields = [
        field for field in MANIFEST_REQUIRED_FIELDS if field not in manifest_fields
    ]
    extra_manifest_fields = [
        field for field in manifest_fields if field not in MANIFEST_REQUIRED_FIELDS
    ]
    duplicate_manifest_fields = csv_duplicate_fieldnames(manifest_fields)
    manifest_schema_ok = not missing_manifest_fields and not extra_manifest_fields and not duplicate_manifest_fields
    manifest_schema_issues = []
    if missing_manifest_fields:
        manifest_schema_issues.append("manifest_schema_missing_fields:" + ",".join(missing_manifest_fields))
    if extra_manifest_fields:
        manifest_schema_issues.append("manifest_schema_extra_fields:" + ",".join(extra_manifest_fields))
    if duplicate_manifest_fields:
        manifest_schema_issues.append("manifest_schema_duplicate_fields:" + ",".join(duplicate_manifest_fields))
    checks.append(
        {
            "path": MANIFEST_NAME,
            "status": "pass" if manifest_schema_ok else "gap",
            "expected_size": "",
            "actual_size": "",
            "sha256_expected": "",
            "sha256_actual": "",
            "expected_executable": "",
            "actual_executable": "",
            "issues": ";".join(manifest_schema_issues),
        }
    )
    seen_paths: set[str] = set()
    manifest_paths: set[str] = set()
    issue_counts = {
        "duplicates": 0,
        "missing": 0,
        "not_file": 0,
        "unexpected": 0,
        "size_mismatch": 0,
        "size_invalid": 0,
        "sha256_mismatch": 0,
        "sha256_invalid": 0,
        "executable_mismatch": 0,
        "executable_invalid": 0,
        "unsafe_paths": 0,
        "noncanonical_paths": 0,
        "row_width_mismatch": 0,
        "png_entries": 0,
    }

    for row in manifest_rows:
        raw_path = row.get("path", "").strip()
        expected_size = row.get("size", "").strip()
        expected_sha = row.get("sha256", "").strip()
        expected_executable = row.get("executable", "").strip()
        fail_issues: list[str] = []
        actual_size = ""
        actual_sha = ""
        actual_executable = ""

        if None in row:
            fail_issues.append("row_width_mismatch")
            issue_counts["row_width_mismatch"] += 1

        if raw_path in seen_paths:
            fail_issues.append("duplicate_path")
            issue_counts["duplicates"] += 1
        seen_paths.add(raw_path)

        path_is_safe = safe_relative_path(raw_path)
        if not path_is_safe:
            fail_issues.append("unsafe_path")
            issue_counts["unsafe_paths"] += 1
        else:
            canonical_path = PurePosixPath(raw_path).as_posix()
            if raw_path != canonical_path:
                fail_issues.append("noncanonical_path")
                issue_counts["noncanonical_paths"] += 1
            manifest_paths.add(raw_path)

        try:
            expected_size_int = int(expected_size)
        except ValueError:
            expected_size_int = None
            fail_issues.append("size_invalid")
            issue_counts["size_invalid"] += 1

        if not SHA256_RE.match(expected_sha):
            fail_issues.append("sha256_invalid")
            issue_counts["sha256_invalid"] += 1

        if expected_executable not in {"0", "1"}:
            fail_issues.append("executable_invalid")
            issue_counts["executable_invalid"] += 1

        if raw_path.lower().endswith(".png"):
            fail_issues.append("png_entry")
            issue_counts["png_entries"] += 1

        path = root / raw_path
        if path_is_safe:
            if not path.exists():
                fail_issues.append("missing")
                issue_counts["missing"] += 1
            elif not path.is_file():
                fail_issues.append("not_file")
                issue_counts["not_file"] += 1
            else:
                stat = path.stat()
                actual_size = str(stat.st_size)
                actual_executable = "1" if stat.st_mode & 0o111 else "0"
                if expected_size_int is not None and stat.st_size != expected_size_int:
                    fail_issues.append("size_mismatch")
                    issue_counts["size_mismatch"] += 1
                actual_sha = sha256_file(path)
                if SHA256_RE.match(expected_sha) and actual_sha.lower() != expected_sha.lower():
                    fail_issues.append("sha256_mismatch")
                    issue_counts["sha256_mismatch"] += 1
                if expected_executable in {"0", "1"} and actual_executable != expected_executable:
                    fail_issues.append("executable_mismatch")
                    issue_counts["executable_mismatch"] += 1

        checks.append(
            {
                "path": raw_path,
                "status": "gap" if fail_issues else "pass",
                "expected_size": expected_size,
                "actual_size": actual_size,
                "sha256_expected": expected_sha,
                "sha256_actual": actual_sha,
                "expected_executable": expected_executable,
                "actual_executable": actual_executable,
                "issues": ";".join(fail_issues),
            }
        )

    for extra_path in sorted(actual_bundle_files(root) - manifest_paths):
        issue_counts["unexpected"] += 1
        checks.append(
            {
                "path": extra_path,
                "status": "gap",
                "expected_size": "",
                "actual_size": str((root / extra_path).stat().st_size),
                "sha256_expected": "",
                "sha256_actual": "",
                "expected_executable": "",
                "actual_executable": "1" if (root / extra_path).stat().st_mode & 0o111 else "0",
                "issues": "unexpected_file",
            }
        )

    gaps = [row for row in checks if row["status"] == "gap"]
    passed = [row for row in checks if row["status"] == "pass"]
    issue_names = sorted(
        {
            issue.split(":", 1)[0]
            for row in gaps
            for issue in row["issues"].split(";")
            if issue
        }
    )
    summary = {
        "status": "pass" if not gaps else "gap",
        "checked": str(len(checks)),
        "passed": str(len(passed)),
        "gaps": str(len(gaps)),
        "info": "0",
        "rows": str(len(manifest_rows)),
        "manifest_schema": "pass" if manifest_schema_ok else "gap",
        "manifest_missing_fields": ",".join(missing_manifest_fields),
        "manifest_extra_fields": ",".join(extra_manifest_fields),
        "manifest_duplicate_fields": ",".join(duplicate_manifest_fields),
        "duplicates": str(issue_counts["duplicates"]),
        "missing": str(issue_counts["missing"]),
        "not_file": str(issue_counts["not_file"]),
        "unexpected": str(issue_counts["unexpected"]),
        "size_mismatch": str(issue_counts["size_mismatch"]),
        "size_invalid": str(issue_counts["size_invalid"]),
        "sha256_mismatch": str(issue_counts["sha256_mismatch"]),
        "sha256_invalid": str(issue_counts["sha256_invalid"]),
        "executable_mismatch": str(issue_counts["executable_mismatch"]),
        "executable_invalid": str(issue_counts["executable_invalid"]),
        "unsafe_paths": str(issue_counts["unsafe_paths"]),
        "noncanonical_paths": str(issue_counts["noncanonical_paths"]),
        "row_width_mismatch": str(issue_counts["row_width_mismatch"]),
        "png_entries": str(issue_counts["png_entries"]),
        "manifest": str(manifest),
        "root": str(root),
        "output": str(output),
        "issues": ";".join(issue_names),
        "next_step": "support manifest verified" if not gaps else "regenerate support bundle or restore listed files",
    }
    write_csv(output / "checks.csv", CHECK_FIELDS, checks)
    write_csv(output / "summary.csv", SUMMARY_FIELDS, [summary])
    build_html(output / "index.html", summary, checks)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify a LOLG HD support bundle manifest.")
    parser.add_argument("root", nargs="?", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    summary = verify_support_manifest(args)
    print(
        "HD support manifest verify: "
        f"{summary['status']} rows={summary['passed']} pass / {summary['checked']} "
        f"gaps={summary['gaps']} schema={summary['manifest_schema']} "
        f"duplicate_fields={summary['manifest_duplicate_fields']} "
        f"duplicates={summary['duplicates']} missing={summary['missing']} "
        f"not_file={summary['not_file']} "
        f"noncanonical={summary['noncanonical_paths']} "
        f"size_mismatch={summary['size_mismatch']} sha256_mismatch={summary['sha256_mismatch']} "
        f"png={summary['png_entries']} exec_invalid={summary['executable_invalid']} "
        f"exec_mismatch={summary['executable_mismatch']} "
        f"unexpected={summary['unexpected']}"
    )
    print(f"Summary: {args.output / 'summary.csv'}")
    print(f"Checks: {args.output / 'checks.csv'}")
    print(f"HTML: {args.output / 'index.html'}")
    if summary["issues"]:
        print(f"Issues: {summary['issues']}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
