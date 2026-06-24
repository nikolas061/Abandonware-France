#!/usr/bin/env python3
"""Build an experimental LOLG95 sidecar suffix patch in an output-only stage."""

from __future__ import annotations

import argparse
import csv
import os
import shutil
from pathlib import Path

from lolg_vqa_runtime_loader_probe import read_binary, section_for_va


DEFAULT_OUTPUT = Path("output/lolg95_sidecar_suffix_patch_probe")
DEFAULT_INPUT = Path("LOLG95.EXE")
DEFAULT_SIDECAR = Path("mod_mix_vqa_fullhd_sidecar/L20_BBI_HD.MIX")
PATCH_IMMEDIATE_VA = 0x004536CE
PATCH_STRING_VA = 0x005AB2D3
PATCH_STRING = b"I_HD.MIX\0"
ORIGINAL_IMMEDIATE = (0x00550BDB).to_bytes(4, "little")
SUMMARY_FIELDS = [
    "status",
    "input_executable",
    "patched_executable",
    "stage_dir",
    "sidecar_source",
    "sidecar_links",
    "patch_immediate_va",
    "patch_string_va",
    "patch_string",
    "top_level_links",
    "issues",
    "next_step",
]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def file_offset_for_va(executable: Path, va: int) -> int:
    info = read_binary(executable)
    section = section_for_va(info.sections, va)
    if section is None or section.raw_offset == 0:
        raise ValueError(f"VA not mapped to file-backed section: {va:#x}")
    return section.raw_offset + (va - section.va)


def link_or_copy(source: Path, target: Path) -> bool:
    if target.exists() or target.is_symlink():
        target.unlink()
    try:
        target.symlink_to(source.resolve())
        return True
    except OSError:
        shutil.copy2(source, target)
        return True


def build_stage(root: Path, stage: Path, patched_executable: Path, sidecar: Path) -> tuple[int, list[str]]:
    issues: list[str] = []
    stage.mkdir(parents=True, exist_ok=True)
    linked = 0
    for source in sorted(root.iterdir()):
        if source.name in {".git", ".agents", ".codex", "output"}:
            continue
        if source.is_file():
            link_or_copy(source, stage / source.name)
            linked += 1
        elif source.name in {"CD", "SAVEGAME", "WOMS", "glshaders", "lib", "mt32-roms"}:
            target = stage / source.name
            if target.exists() or target.is_symlink():
                target.unlink()
            target.symlink_to(source.resolve(), target_is_directory=True)
            linked += 1

    shutil.copy2(patched_executable, stage / patched_executable.name)
    sidecar_links = ["L20_BBI_HD.MIX", "l20_bbI_HD.MIX"]
    for name in sidecar_links:
        link_or_copy(sidecar, stage / name)
    return linked, issues


def build_patch(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    patched = output / "LOLG95_L20_SIDE_SUFFIX.EXE"
    stage = output / "runtime_stage"
    issues: list[str] = []

    if not args.input.is_file():
        issues.append("missing_input_executable")
    if not args.sidecar.is_file():
        issues.append("missing_sidecar")

    sidecar_links = "L20_BBI_HD.MIX;l20_bbI_HD.MIX"
    top_level_links = 0
    if not issues:
        data = bytearray(args.input.read_bytes())
        immediate_offset = file_offset_for_va(args.input, PATCH_IMMEDIATE_VA)
        string_offset = file_offset_for_va(args.input, PATCH_STRING_VA)
        if data[immediate_offset : immediate_offset + 4] != ORIGINAL_IMMEDIATE:
            issues.append("unexpected_suffix_immediate")
        if any(data[string_offset + index] for index in range(len(PATCH_STRING))):
            issues.append("patch_string_cave_not_empty")
        if not issues:
            data[string_offset : string_offset + len(PATCH_STRING)] = PATCH_STRING
            data[immediate_offset : immediate_offset + 4] = PATCH_STRING_VA.to_bytes(4, "little")
            patched.write_bytes(data)
            try:
                os.chmod(patched, args.input.stat().st_mode)
            except OSError:
                pass
            top_level_links, stage_issues = build_stage(args.cwd, stage, patched, args.sidecar)
            issues.extend(stage_issues)

    status = "pass" if not issues else "gap"
    summary = {
        "status": status,
        "input_executable": str(args.input),
        "patched_executable": str(patched),
        "stage_dir": str(stage),
        "sidecar_source": str(args.sidecar),
        "sidecar_links": sidecar_links,
        "patch_immediate_va": f"{PATCH_IMMEDIATE_VA:#010x}",
        "patch_string_va": f"{PATCH_STRING_VA:#010x}",
        "patch_string": PATCH_STRING.rstrip(b"\0").decode("ascii"),
        "top_level_links": str(top_level_links),
        "issues": ";".join(issues),
        "next_step": (
            "run the patched executable in the stage and verify L20_BBI_HD.MIX is opened; "
            "this proves name injection only, not the final sidecar fallback"
        ),
    }
    write_csv(output / "summary.csv", SUMMARY_FIELDS, [summary])
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an output-only LOLG95 I_HD.MIX suffix patch probe.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--sidecar", type=Path, default=DEFAULT_SIDECAR)
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    args = parser.parse_args()

    summary = build_patch(args)
    print(f"LOLG95 sidecar suffix patch probe: {summary['status']}")
    print(f"Patched executable: {summary['patched_executable']}")
    print(f"Stage: {summary['stage_dir']}")
    if summary["issues"]:
        print(f"Issues: {summary['issues']}")


if __name__ == "__main__":
    main()
