#!/usr/bin/env python3
"""Check LOLG HD Wine launcher resolutions without launching Wine."""

from __future__ import annotations

import argparse
import csv
import html
import subprocess
from pathlib import Path


DEFAULT_OUTPUT = Path("output/hd_resolution_check")
CHECK_FIELDS = ["check", "status", "command", "evidence", "next_step"]
SUMMARY_FIELDS = ["status", "checks", "passed", "gaps", "output", "issues", "next_step"]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_command(command: list[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 124, f"{type(exc).__name__}: {exc}"
    detail = (result.stdout + result.stderr).strip().replace("\n", " | ")
    return result.returncode, detail


def add_check(rows: list[dict[str, str]], name: str, passed: bool, command: list[str], evidence: str, next_step: str) -> None:
    rows.append(
        {
            "check": name,
            "status": "pass" if passed else "gap",
            "command": " ".join(command),
            "evidence": evidence,
            "next_step": next_step,
        }
    )


def accepts_resolution(evidence: str, resolution: str) -> bool:
    return (
        f"Resolution Wine: {resolution}" in evidence
        and "Resolution supportee: oui" in evidence
        and (
            f"/desktop=LOLG_HD,{resolution}" in evidence
            or f"/desktop=LOLG_HD\\,{resolution}" in evidence
        )
    )


def build_html(path: Path, summary: dict[str, str], checks: list[dict[str, str]]) -> None:
    rows_html = []
    for row in checks:
        cls = row["status"]
        rows_html.append(
            "<tr>"
            f"<td>{html.escape(row['check'])}</td>"
            f"<td class='{html.escape(cls)}'>{html.escape(row['status'])}</td>"
            f"<td><code>{html.escape(row['command'])}</code></td>"
            f"<td>{html.escape(row['evidence'])}</td>"
            f"<td>{html.escape(row['next_step'])}</td>"
            "</tr>"
        )
    document = f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<title>LOLG HD Resolution Check</title>
<style>
body {{ font-family: sans-serif; margin: 2rem; background: #f7f7f5; color: #171717; }}
table {{ border-collapse: collapse; width: 100%; background: white; }}
th, td {{ border: 1px solid #d7d7d0; padding: 0.45rem 0.6rem; text-align: left; vertical-align: top; }}
th {{ background: #ecece6; }}
.pass {{ color: #106b2f; font-weight: 700; }}
.gap {{ color: #a22522; font-weight: 700; }}
code {{ background: #eee; padding: 0.1rem 0.25rem; }}
</style>
<h1>LOLG HD Resolution Check</h1>
<p>Status: <strong class="{html.escape(summary['status'])}">{html.escape(summary['status'])}</strong></p>
<p>Checks: {html.escape(summary['passed'])} pass / {html.escape(summary['checks'])},
gaps={html.escape(summary['gaps'])}</p>
<table>
<thead><tr><th>Check</th><th>Status</th><th>Command</th><th>Evidence</th><th>Next step</th></tr></thead>
<tbody>
{''.join(rows_html)}
</tbody>
</table>
</html>
"""
    path.write_text(document, encoding="utf-8")


def run_check(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, str]] = []

    for resolution in ("1920x1080", "1440x1080", "1280x1024"):
        command = ["./RUN_HD_WINE.sh", "--dry-run", "--resolution", resolution]
        returncode, evidence = run_command(command)
        add_check(
            checks,
            f"launcher_accepts_{resolution}",
            returncode == 0 and accepts_resolution(evidence, resolution),
            command,
            evidence,
            f"fix RUN_HD_WINE.sh --resolution {resolution}",
        )

    command = ["./RUN_HD_WINE.sh", "--dry-run", "--resolution", "640x400"]
    returncode, evidence = run_command(command)
    add_check(
        checks,
        "launcher_rejects_640x400",
        returncode != 0 and "Resolution non supportee: 640x400" in evidence,
        command,
        evidence,
        "use 1920x1080, 1440x1080 or 1280x1024; pass --allow-unsupported-resolution only for experiments",
    )

    passed = sum(1 for row in checks if row["status"] == "pass")
    gaps = [row["check"] for row in checks if row["status"] == "gap"]
    summary = {
        "status": "pass" if not gaps else "gap",
        "checks": str(len(checks)),
        "passed": str(passed),
        "gaps": str(len(gaps)),
        "output": str(output),
        "issues": ";".join(gaps),
        "next_step": "resolution check passed" if not gaps else "fix launcher resolution handling",
    }
    write_csv(output / "checks.csv", CHECK_FIELDS, checks)
    write_csv(output / "summary.csv", SUMMARY_FIELDS, [summary])
    build_html(output / "index.html", summary, checks)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Check LOLG HD Wine launcher resolutions without launching Wine.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    summary = run_check(args)
    print(
        "HD resolution check: "
        f"{summary['status']} ({summary['passed']} pass / {summary['checks']} checks, "
        f"gaps={summary['gaps']})"
    )
    print(f"Summary: {args.output / 'summary.csv'}")
    print(f"HTML: {args.output / 'index.html'}")
    if summary["issues"]:
        print(f"Issues: {summary['issues']}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
