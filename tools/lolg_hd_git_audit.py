#!/usr/bin/env python3
"""Audit Git tracking for lightweight LOLG HD sources and ignored payloads."""

from __future__ import annotations

import argparse
import csv
import html
import subprocess
from pathlib import Path


DEFAULT_MANIFEST = Path("output/hd_release_manifest/manifest.csv")
DEFAULT_OUTPUT = Path("output/hd_git_audit")
DEFAULT_STAGED_SIZE_LIMIT = 64 * 1024 * 1024

HEAVY_PREFIXES = (
    "mod_mix_vqa_fullhd/",
    "C/LOLG/",
)

IGNORE_PROBES = (
    ("output/", "generated reports and runtime stages"),
    ("mod_mix_vqa_fullhd/", "regenerated 19 GB VQA MIX payload pack"),
    ("extracted/", "temporary extraction work directories"),
    ("LOLG_HD_PATCH_runtime_20260701/", "temporary unpacked release/runtime directories"),
    ("previews_te_guarded_cmd20_probe/", "generated texture preview directories"),
    ("reports/LOLG_HD_TEST_IGNORE.tsv", "generated analysis reports"),
    ("reports/LOLG_HD_TEST_IGNORE.png", "generated report images and galleries"),
    ("C/LOLG/", "local game install payload"),
    ("LOLG_HD_TEST_IGNORE.zip", "local release/support ZIP archives"),
    ("backtrace-test.txt", "local Wine crash backtraces"),
)

CHECK_FIELDS = [
    "check",
    "status",
    "path",
    "evidence",
    "next_step",
]

SUMMARY_FIELDS = [
    "status",
    "manifest",
    "output",
    "required_checked",
    "required_tracked",
    "required_gaps",
    "heavy_checked",
    "heavy_ignored",
    "heavy_gaps",
    "staged_checked",
    "staged_large",
    "staged_largest_bytes",
    "staged_size_limit",
    "gaps",
    "issues",
    "next_step",
]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def run_git(args: list[str]) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def git_detail(result: subprocess.CompletedProcess[str] | None) -> str:
    if result is None:
        return "git command unavailable or timed out"
    detail = (result.stdout + result.stderr).strip().replace("\n", " | ")
    return detail or f"returncode={result.returncode}"


def is_safe_manifest_path(path_text: str) -> bool:
    if not path_text or "\\" in path_text:
        return False
    path = Path(path_text)
    if path.is_absolute():
        return False
    return all(part not in {"", ".", ".."} for part in path.parts)


def is_heavy_path(path_text: str) -> bool:
    normalized = path_text.replace("\\", "/")
    return any(normalized.startswith(prefix) for prefix in HEAVY_PREFIXES)


def add_check(
    rows: list[dict[str, str]],
    check: str,
    status: str,
    path: str,
    evidence: str,
    next_step: str,
) -> None:
    rows.append(
        {
            "check": check,
            "status": status,
            "path": path,
            "evidence": evidence,
            "next_step": next_step,
        }
    )


def build_html(path: Path, summary: dict[str, str], rows: list[dict[str, str]]) -> None:
    table_rows = []
    for row in rows:
        status = html.escape(row["status"])
        table_rows.append(
            "<tr>"
            f"<td>{html.escape(row['check'])}</td>"
            f"<td class='{status}'>{status}</td>"
            f"<td>{html.escape(row['path'])}</td>"
            f"<td>{html.escape(row['evidence'])}</td>"
            f"<td>{html.escape(row['next_step'])}</td>"
            "</tr>"
        )
    document = f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>LOLG HD Git Audit</title>
<style>
body {{ font-family: sans-serif; margin: 2rem; color: #202020; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #d0d0d0; padding: 0.35rem 0.5rem; text-align: left; }}
th {{ background: #f2f2f2; }}
.pass {{ color: #087d32; font-weight: 700; }}
.gap {{ color: #b00020; font-weight: 700; }}
</style>
<h1>LOLG HD Git Audit</h1>
<p>Status: <strong class="{html.escape(summary['status'])}">{html.escape(summary['status'])}</strong></p>
<p>Required tracked: {html.escape(summary['required_tracked'])}/{html.escape(summary['required_checked'])};
heavy ignored: {html.escape(summary['heavy_ignored'])}/{html.escape(summary['heavy_checked'])};
staged files over limit: {html.escape(summary['staged_large'])}/{html.escape(summary['staged_checked'])};
gaps: {html.escape(summary['gaps'])}</p>
<table>
<thead><tr><th>Check</th><th>Status</th><th>Path</th><th>Evidence</th><th>Next step</th></tr></thead>
<tbody>
{''.join(table_rows)}
</tbody>
</table>
</html>
"""
    path.write_text(document, encoding="utf-8")


def run_audit(args: argparse.Namespace) -> dict[str, str]:
    checks: list[dict[str, str]] = []
    args.output.mkdir(parents=True, exist_ok=True)

    git_repo = run_git(["rev-parse", "--is-inside-work-tree"])
    git_ok = bool(git_repo and git_repo.returncode == 0 and git_repo.stdout.strip() == "true")
    add_check(
        checks,
        "git_repository",
        "pass" if git_ok else "gap",
        ".",
        git_detail(git_repo),
        "run this audit from the Abandonware-France Git worktree",
    )

    manifest_rows: list[dict[str, str]] = []
    if args.manifest.is_file():
        try:
            manifest_rows = read_manifest(args.manifest)
            manifest_status = "pass"
            manifest_evidence = f"rows={len(manifest_rows)}"
        except csv.Error as exc:
            manifest_status = "gap"
            manifest_evidence = f"csv_error={exc}"
    else:
        manifest_status = "gap"
        manifest_evidence = "missing"
    add_check(
        checks,
        "release_manifest",
        manifest_status,
        str(args.manifest),
        manifest_evidence,
        "./LOLG_HD.sh manifest --skip-check",
    )

    required_checked = 0
    required_tracked = 0
    if git_ok and manifest_status == "pass":
        required_paths = [
            row.get("path", "").strip()
            for row in manifest_rows
            if row.get("required", "").strip() == "1" and not is_heavy_path(row.get("path", "").strip())
        ]
        for path_text in required_paths:
            required_checked += 1
            if not is_safe_manifest_path(path_text):
                add_check(
                    checks,
                    "required_path_safe",
                    "gap",
                    path_text,
                    "unsafe or non-canonical manifest path",
                    "fix output/hd_release_manifest/manifest.csv",
                )
                continue
            tracked = run_git(["ls-files", "--error-unmatch", "--", path_text])
            tracked_ok = bool(tracked and tracked.returncode == 0)
            if tracked_ok:
                required_tracked += 1
            add_check(
                checks,
                "required_tracked",
                "pass" if tracked_ok else "gap",
                path_text,
                git_detail(tracked),
                "git add the lightweight source file or remove it from required manifest rows",
            )

    heavy_checked = 0
    heavy_ignored = 0
    if git_ok:
        for path_text, description in IGNORE_PROBES:
            heavy_checked += 1
            ignored = run_git(["check-ignore", "-q", "--", path_text])
            ignored_ok = bool(ignored and ignored.returncode == 0)
            if ignored_ok:
                heavy_ignored += 1
            add_check(
                checks,
                "heavy_ignored",
                "pass" if ignored_ok else "gap",
                path_text,
                description if ignored_ok else git_detail(ignored),
                "keep generated payloads and archives ignored in .gitignore",
            )

    staged_checked = 0
    staged_large = 0
    staged_largest_bytes = 0
    if git_ok:
        staged = run_git(["diff", "--cached", "--name-only", "--diff-filter=ACMRT"])
        staged_paths = []
        if staged and staged.returncode == 0:
            staged_paths = [line.strip() for line in staged.stdout.splitlines() if line.strip()]
        for path_text in staged_paths:
            if not is_safe_manifest_path(path_text):
                add_check(
                    checks,
                    "staged_path_safe",
                    "gap",
                    path_text,
                    "unsafe or non-canonical staged path",
                    "remove unsafe staged path from the Git index",
                )
                continue
            staged_checked += 1
            path = Path(path_text)
            if not path.is_file():
                continue
            size = path.stat().st_size
            staged_largest_bytes = max(staged_largest_bytes, size)
            if size > args.staged_size_limit:
                staged_large += 1
                add_check(
                    checks,
                    "staged_file_size",
                    "gap",
                    path_text,
                    f"size={size};limit={args.staged_size_limit}",
                    "unstage the large payload and keep it ignored or external",
                )
        add_check(
            checks,
            "staged_size_guard",
            "pass" if staged_large == 0 else "gap",
            ".",
            (
                f"checked={staged_checked};"
                f"large={staged_large};"
                f"largest_bytes={staged_largest_bytes};"
                f"limit={args.staged_size_limit}"
            ),
            "keep staged files lightweight for GitHub Desktop",
        )

    gaps = [row for row in checks if row["status"] == "gap"]
    required_gaps = required_checked - required_tracked
    heavy_gaps = heavy_checked - heavy_ignored
    summary = {
        "status": "pass" if not gaps else "gap",
        "manifest": str(args.manifest),
        "output": str(args.output),
        "required_checked": str(required_checked),
        "required_tracked": str(required_tracked),
        "required_gaps": str(required_gaps),
        "heavy_checked": str(heavy_checked),
        "heavy_ignored": str(heavy_ignored),
        "heavy_gaps": str(heavy_gaps),
        "staged_checked": str(staged_checked),
        "staged_large": str(staged_large),
        "staged_largest_bytes": str(staged_largest_bytes),
        "staged_size_limit": str(args.staged_size_limit),
        "gaps": str(len(gaps)),
        "issues": ";".join(row["check"] + ":" + row["path"] for row in gaps),
        "next_step": "git audit passed" if not gaps else "fix git audit gaps",
    }
    write_csv(args.output / "checks.csv", CHECK_FIELDS, checks)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDS, [summary])
    build_html(args.output / "index.html", summary, checks)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Git tracking for the LOLG HD release.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--staged-size-limit", type=int, default=DEFAULT_STAGED_SIZE_LIMIT)
    args = parser.parse_args()

    summary = run_audit(args)
    print(
        "HD git audit: "
        f"{summary['status']} required_tracked={summary['required_tracked']} pass / "
        f"{summary['required_checked']}, heavy_ignored={summary['heavy_ignored']} pass / "
        f"{summary['heavy_checked']}, staged_large={summary['staged_large']} / "
        f"{summary['staged_checked']}, gaps={summary['gaps']}"
    )
    print(f"Summary: {args.output / 'summary.csv'}")
    print(f"HTML: {args.output / 'index.html'}")
    if summary["issues"]:
        print(f"Issues: {summary['issues']}")
    raise SystemExit(0 if summary["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
