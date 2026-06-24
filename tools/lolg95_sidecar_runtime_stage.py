#!/usr/bin/env python3
"""Promote the proven LOLG95 L20 sidecar patch into a staged runtime manifest."""

from __future__ import annotations

import argparse
import csv
import shlex
from pathlib import Path


DEFAULT_OUTPUT = Path("output/lolg95_sidecar_runtime_stage")
DEFAULT_PATCH_SUMMARY = Path("output/lolg95_sidecar_additive_patch_probe/summary.csv")
DEFAULT_LOAD_PLAN_SUMMARY = Path("output/vqa_runtime_sidecar_load_plan/summary.csv")
DEFAULT_LOAD_PLAN_ENTRIES = Path("output/vqa_runtime_sidecar_load_plan/entries.csv")
DEFAULT_ARCHIVE_LIST_SUMMARY = Path("output/lolg95_runtime_archive_list_l20_sidecar_probe/summary.csv")

SUMMARY_FIELDS = [
    "status",
    "stage_dir",
    "runtime_executable",
    "run_script",
    "readme",
    "patch_summary",
    "load_plan_summary",
    "load_plan_entries",
    "archive_list_summary",
    "sidecar_links",
    "expected_ids",
    "runtime_sidecar_first",
    "issues",
    "next_step",
]

REQUIREMENT_FIELDS = ["requirement", "status", "evidence", "next_step"]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def first_row(path: Path) -> dict[str, str]:
    rows = read_csv(path)
    return rows[0] if rows else {}


def split_semicolon(value: str) -> list[str]:
    return [part.strip() for part in value.split(";") if part.strip()]


def pass_if(condition: bool) -> str:
    return "pass" if condition else "gap"


def quote_shell(value: str | Path) -> str:
    return shlex.quote(str(value))


def build_run_script(path: Path, stage_dir: Path, runtime_executable: Path, wineprefix: str, wine_desktop: str) -> None:
    runtime_name = runtime_executable.name
    wineprefix_line = (
        f'WINEPREFIX="${{WINEPREFIX:-{quote_shell(Path(wineprefix).resolve())}}}"'
        if wineprefix
        else 'WINEPREFIX="${WINEPREFIX:-}"'
    )
    lines = [
        "#!/bin/sh",
        "set -eu",
        f"STAGE_DIR={quote_shell(stage_dir.resolve())}",
        'WINE_BIN="${WINE:-wine}"',
        wineprefix_line,
        'WINEDEBUG="${WINEDEBUG:--all}"',
        'export WINEDEBUG',
        'if [ -n "$WINEPREFIX" ]; then',
        '  export WINEPREFIX',
        "fi",
        'cd "$STAGE_DIR"',
        f'exec "$WINE_BIN" explorer /desktop={quote_shell(wine_desktop)} ./{quote_shell(runtime_name)} -CD '
        + quote_shell(r"D:\WESTWOOD\LOLG"),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    try:
        path.chmod(path.stat().st_mode | 0o111)
    except OSError:
        pass


def build_readme(
    path: Path,
    summary: dict[str, str],
    requirements: list[dict[str, str]],
    lookup_gap_note: str,
) -> None:
    lines = [
        "LOLG95 sidecar runtime stage",
        "",
        f"status={summary['status']}",
        f"stage_dir={summary['stage_dir']}",
        f"runtime_executable={summary['runtime_executable']}",
        f"run_script={summary['run_script']}",
        "",
        "requirements:",
    ]
    for row in requirements:
        lines.append(f"- {row['requirement']}: {row['status']} ({row['evidence']})")
    lines.extend(
        [
            "",
            lookup_gap_note,
            "",
            f"next_step={summary['next_step']}",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def build_stage(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    patch_summary = first_row(args.patch_summary)
    load_plan_summary = first_row(args.load_plan_summary)
    archive_list_summary = first_row(args.archive_list_summary)
    load_plan_entries = read_csv(args.load_plan_entries)

    stage_dir = Path(patch_summary.get("stage_dir") or args.stage_dir)
    patched_executable = Path(patch_summary.get("patched_executable") or args.runtime_executable)
    runtime_executable = stage_dir / patched_executable.name
    sidecar_links = split_semicolon(patch_summary.get("sidecar_links", ""))
    sidecar_paths = [stage_dir / link for link in sidecar_links]
    run_script = output / "run_lolg95_sidecar_fullhd_wine.sh"
    readme = output / "README.txt"

    expected_ids = load_plan_summary.get("sidecar_entries", "")
    runtime_sidecar_first = load_plan_summary.get("runtime_sidecar_first", "")
    requirements = [
        {
            "requirement": "additive_patch_summary",
            "status": pass_if(patch_summary.get("status") == "pass"),
            "evidence": f"status={patch_summary.get('status', '')};path={args.patch_summary}",
            "next_step": "rerun tools/lolg95_sidecar_additive_patch_probe.py",
        },
        {
            "requirement": "runtime_stage_directory",
            "status": pass_if(stage_dir.is_dir()),
            "evidence": str(stage_dir),
            "next_step": "rebuild the additive runtime stage",
        },
        {
            "requirement": "runtime_executable",
            "status": pass_if(runtime_executable.is_file()),
            "evidence": str(runtime_executable),
            "next_step": "copy the patched executable into the stage",
        },
        {
            "requirement": "sidecar_links",
            "status": pass_if(bool(sidecar_paths) and all(path.exists() for path in sidecar_paths)),
            "evidence": ";".join(str(path) for path in sidecar_paths),
            "next_step": "link L20_BBI_HD.MIX and l20_bbI_HD.MIX into the stage",
        },
        {
            "requirement": "sidecar_load_plan",
            "status": pass_if(
                load_plan_summary.get("status") == "pass"
                and expected_ids
                and runtime_sidecar_first == expected_ids
                and load_plan_summary.get("runtime_base_first") == "0"
                and load_plan_summary.get("runtime_missing") == "0"
                and load_plan_summary.get("runtime_unknown_first") == "0"
            ),
            "evidence": (
                f"status={load_plan_summary.get('status', '')};"
                f"base={load_plan_summary.get('base_entries_verified', '')}/{expected_ids};"
                f"sidecar={load_plan_summary.get('sidecar_entries_verified', '')}/{expected_ids};"
                f"runtime_sidecar_first={runtime_sidecar_first}/{expected_ids}"
            ),
            "next_step": "rerun tools/lolg_vqa_runtime_sidecar_load_plan.py",
        },
        {
            "requirement": "runtime_archive_list_probe",
            "status": pass_if(
                archive_list_summary.get("status") == "pass"
                and archive_list_summary.get("expected_ids") == expected_ids
                and len(load_plan_entries) == int(expected_ids or 0)
            ),
            "evidence": (
                f"status={archive_list_summary.get('status', '')};"
                f"archive_nodes={archive_list_summary.get('archive_nodes', '')};"
                f"expected_ids={archive_list_summary.get('expected_ids', '')}"
            ),
            "next_step": "rerun tools/run_lolg95_runtime_archive_list_probe.py",
        },
    ]

    issues = [row["requirement"] for row in requirements if row["status"] != "pass"]
    status = "pass" if not issues else "gap"
    wineprefix = archive_list_summary.get("wineprefix", "")
    wine_desktop = archive_list_summary.get("wine_desktop", "LOLG,1280x1024") or "LOLG,1280x1024"
    if status == "pass":
        build_run_script(run_script, stage_dir, runtime_executable, wineprefix, wine_desktop)
    else:
        run_script.write_text("# stage requirements are not passing; rerun the report first\n", encoding="utf-8")

    lookup_gap_note = (
        "Direct lookup trace note: output/lolg95_winedbg_mix_lookup_l20_additive_attempt/ "
        "still has target_hits=0 because the automated route did not request these VQA IDs."
    )
    summary = {
        "status": status,
        "stage_dir": str(stage_dir),
        "runtime_executable": str(runtime_executable),
        "run_script": str(run_script),
        "readme": str(readme),
        "patch_summary": str(args.patch_summary),
        "load_plan_summary": str(args.load_plan_summary),
        "load_plan_entries": str(args.load_plan_entries),
        "archive_list_summary": str(args.archive_list_summary),
        "sidecar_links": ";".join(str(path) for path in sidecar_paths),
        "expected_ids": expected_ids,
        "runtime_sidecar_first": runtime_sidecar_first,
        "issues": ";".join(issues),
        "next_step": (
            "capture a played VQA read or promote this staged Wine path after manual visual review"
            if status == "pass"
            else "fix failed stage requirements before using the runtime stage"
        ),
    }
    build_readme(readme, summary, requirements, lookup_gap_note)
    write_csv(output / "summary.csv", SUMMARY_FIELDS, [summary])
    write_csv(output / "requirements.csv", REQUIREMENT_FIELDS, requirements)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a non-destructive LOLG95 sidecar runtime stage manifest.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--patch-summary", type=Path, default=DEFAULT_PATCH_SUMMARY)
    parser.add_argument("--load-plan-summary", type=Path, default=DEFAULT_LOAD_PLAN_SUMMARY)
    parser.add_argument("--load-plan-entries", type=Path, default=DEFAULT_LOAD_PLAN_ENTRIES)
    parser.add_argument("--archive-list-summary", type=Path, default=DEFAULT_ARCHIVE_LIST_SUMMARY)
    parser.add_argument("--stage-dir", type=Path, default=Path("output/lolg95_sidecar_additive_patch_probe/runtime_stage"))
    parser.add_argument(
        "--runtime-executable",
        type=Path,
        default=Path("output/lolg95_sidecar_additive_patch_probe/LOLG95_L20_SIDE_ADD.EXE"),
    )
    args = parser.parse_args()

    summary = build_stage(args)
    print(f"LOLG95 sidecar runtime stage: {summary['status']}")
    print(f"Summary: {args.output / 'summary.csv'}")
    print(f"Run script: {summary['run_script']}")
    if summary["issues"]:
        print(f"Issues: {summary['issues']}")


if __name__ == "__main__":
    main()
