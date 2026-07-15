#!/usr/bin/env python3
"""Verify the local LOLG HD release manifest without hashing large MIX files."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
from pathlib import Path


DEFAULT_MANIFEST = Path("output/hd_release_manifest/manifest.csv")
DEFAULT_OUTPUT = Path("output/hd_release_manifest_verify")

CHECK_FIELDS = [
    "path",
    "category",
    "required",
    "status",
    "expected_size",
    "actual_size",
    "expected_executable",
    "actual_executable",
    "sha256_expected",
    "sha256_actual",
    "issues",
]

SUMMARY_FIELDS = [
    "status",
    "checked",
    "passed",
    "gaps",
    "info",
    "required_missing",
    "size_mismatch",
    "executable_mismatch",
    "sha256_mismatch",
    "manifest",
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


def resolve_manifest_path(root: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return root / path


def expected_flag(row: dict[str, str], key: str) -> str:
    value = row.get(key, "").strip()
    return value if value in {"0", "1"} else ""


def build_html(path: Path, summary: dict[str, str], rows: list[dict[str, str]]) -> None:
    table_rows = []
    for row in rows:
        cls = row["status"]
        table_rows.append(
            "<tr>"
            f"<td><code>{html.escape(row['path'])}</code></td>"
            f"<td>{html.escape(row['category'])}</td>"
            f"<td class='{html.escape(cls)}'>{html.escape(row['status'])}</td>"
            f"<td>{html.escape(row['expected_size'])}</td>"
            f"<td>{html.escape(row['actual_size'])}</td>"
            f"<td>{html.escape(row['expected_executable'])}</td>"
            f"<td>{html.escape(row['actual_executable'])}</td>"
            f"<td>{html.escape(row['sha256_expected'][:16])}</td>"
            f"<td>{html.escape(row['sha256_actual'][:16])}</td>"
            f"<td>{html.escape(row['issues'])}</td>"
            "</tr>"
        )
    document = f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>LOLG HD Manifest Verify</title>
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
<h1>LOLG HD Manifest Verify</h1>
<p>Status: <strong class="{html.escape(summary['status'])}">{html.escape(summary['status'])}</strong></p>
<p>Rows: {html.escape(summary['passed'])} pass / {html.escape(summary['checked'])},
gaps={html.escape(summary['gaps'])}, info={html.escape(summary['info'])}</p>
<table>
<thead><tr><th>Path</th><th>Category</th><th>Status</th><th>Expected bytes</th><th>Actual bytes</th><th>Expected exec</th><th>Actual exec</th><th>Expected SHA256</th><th>Actual SHA256</th><th>Issues</th></tr></thead>
<tbody>
{''.join(table_rows)}
</tbody>
</table>
</html>
"""
    path.write_text(document, encoding="utf-8")


def verify_manifest(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    if not args.manifest.exists():
        summary = {
            "status": "gap",
            "checked": "0",
            "passed": "0",
            "gaps": "1",
            "info": "0",
            "required_missing": "0",
            "size_mismatch": "0",
            "executable_mismatch": "0",
            "sha256_mismatch": "0",
            "manifest": str(args.manifest),
            "output": str(output),
            "issues": "manifest_missing",
            "next_step": "./LOLG_HD.sh manifest",
        }
        write_csv(output / "checks.csv", CHECK_FIELDS, [])
        write_csv(output / "summary.csv", SUMMARY_FIELDS, [summary])
        build_html(output / "index.html", summary, [])
        return summary

    with args.manifest.open(newline="", encoding="utf-8") as handle:
        manifest_rows = list(csv.DictReader(handle))

    checks: list[dict[str, str]] = []
    issue_counts = {
        "required_missing": 0,
        "size_mismatch": 0,
        "executable_mismatch": 0,
        "sha256_mismatch": 0,
    }

    for row in manifest_rows:
        raw_path = row.get("path", "").strip()
        category = row.get("category", "")
        required = expected_flag(row, "required")
        expected_size = row.get("size_bytes", "").strip()
        expected_exec = expected_flag(row, "executable")
        expected_sha = row.get("sha256", "").strip()
        path = resolve_manifest_path(args.root, raw_path)
        fail_issues: list[str] = []
        info_issues: list[str] = []
        actual_size = ""
        actual_exec = ""
        actual_sha = ""

        if not raw_path:
            fail_issues.append("path_missing")
        elif not path.exists():
            if required == "1":
                fail_issues.append("missing")
                issue_counts["required_missing"] += 1
            else:
                info_issues.append("optional_missing")
        else:
            stat = path.stat()
            actual_size = str(stat.st_size)
            actual_exec = "1" if stat.st_mode & 0o111 else "0"
            if expected_size and actual_size != expected_size:
                fail_issues.append("size_mismatch")
                issue_counts["size_mismatch"] += 1
            if expected_exec and actual_exec != expected_exec:
                fail_issues.append("executable_mismatch")
                issue_counts["executable_mismatch"] += 1
            if expected_sha:
                if path.is_file():
                    try:
                        actual_sha = sha256_file(path)
                    except OSError as exc:
                        fail_issues.append(f"sha256_error:{type(exc).__name__}")
                else:
                    fail_issues.append("sha256_not_file")
                if actual_sha and actual_sha != expected_sha:
                    fail_issues.append("sha256_mismatch")
                    issue_counts["sha256_mismatch"] += 1
            elif path.is_file():
                info_issues.append("sha256_skipped")

        if fail_issues:
            status = "gap"
        elif info_issues:
            status = "info"
        else:
            status = "pass"

        checks.append(
            {
                "path": raw_path,
                "category": category,
                "required": required,
                "status": status,
                "expected_size": expected_size,
                "actual_size": actual_size,
                "expected_executable": expected_exec,
                "actual_executable": actual_exec,
                "sha256_expected": expected_sha,
                "sha256_actual": actual_sha,
                "issues": ";".join(fail_issues + info_issues),
            }
        )

    gaps = [row for row in checks if row["status"] == "gap"]
    info = [row for row in checks if row["status"] == "info"]
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
        "info": str(len(info)),
        "required_missing": str(issue_counts["required_missing"]),
        "size_mismatch": str(issue_counts["size_mismatch"]),
        "executable_mismatch": str(issue_counts["executable_mismatch"]),
        "sha256_mismatch": str(issue_counts["sha256_mismatch"]),
        "manifest": str(args.manifest),
        "output": str(output),
        "issues": ";".join(issue_names),
        "next_step": "manifest verified" if not gaps else "regenerate manifest or restore listed files",
    }
    write_csv(output / "checks.csv", CHECK_FIELDS, checks)
    write_csv(output / "summary.csv", SUMMARY_FIELDS, [summary])
    build_html(output / "index.html", summary, checks)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify the LOLG HD release manifest without hashing large files."
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()

    summary = verify_manifest(args)
    print(
        "HD release manifest verify: "
        f"{summary['status']} rows={summary['passed']} pass / {summary['checked']} "
        f"gaps={summary['gaps']} info={summary['info']}"
    )
    print(f"Summary: {args.output / 'summary.csv'}")
    print(f"Checks: {args.output / 'checks.csv'}")
    print(f"HTML: {args.output / 'index.html'}")
    if summary["issues"]:
        print(f"Issues: {summary['issues']}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
