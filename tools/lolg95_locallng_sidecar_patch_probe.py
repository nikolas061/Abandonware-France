#!/usr/bin/env python3
"""Build a Wine-only LOLG95 probe that opens LOCALLNG_HD.MIX.

This patch redirects the three compiled LOCALLNG.MIX string references in
LOLG95.EXE to a new string stored in an existing zero-filled DGROUP cave. The
stage can then keep LOCALLNG.MIX original and provide LOCALLNG_HD.MIX as a
sidecar for a focused Wine runtime test.
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
from pathlib import Path

from lolg_rebuild_locallng_dos_compat import TARGET_FILE_ID, entry_payload, find_entry, read_mix
from lolg_vqa_runtime_loader_probe import read_binary, section_for_va


DEFAULT_OUTPUT = Path("output/lolg95_locallng_sidecar_patch_probe")
DEFAULT_INPUT = Path("C/LOLG/LOLG95.EXE")
DEFAULT_HD_LOCALLNG = Path("mod_mix_vqa_fullhd/LOCALLNG.MIX")
DEFAULT_ORIGINAL_LOCALLNG = Path("C/LOLG/LOCALLNG.MIX")

PATCH_STRING_VA = 0x005AB350
PATCH_STRING = b"LOCALLNG_HD.MIX\0"
ORIGINAL_STRING_VAS = [0x00554266, 0x00554273, 0x00554280]
REFERENCE_IMMEDIATE_VAS = [0x00506138, 0x00506149, 0x0050617A]

SUMMARY_FIELDS = [
    "status",
    "input_executable",
    "patched_executable",
    "sidecar_dir",
    "sidecar_source",
    "sidecar_link",
    "title_fallback",
    "patch_string_va",
    "patch_string",
    "patched_references",
    "issues",
    "next_step",
]

REF_FIELDS = ["reference_va", "old_string_va", "new_string_va", "old_bytes", "new_bytes", "status"]


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


def link_or_copy(source: Path, target: Path) -> str:
    if target.exists() or target.is_symlink():
        target.unlink()
    try:
        target.symlink_to(source.resolve())
        return "symlink"
    except OSError:
        shutil.copy2(source, target)
        return "copy"


def write_title_fallback(original_locallng: Path, target: Path) -> str:
    original_data, entries, table_end = read_mix(original_locallng)
    entry = find_entry(entries, TARGET_FILE_ID)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(entry_payload(original_data, table_end, entry))
    return str(target)


def build_patch(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    sidecar_dir = output / "sidecar"
    patched = output / "LOLG95_LOCALLNG_SIDE.EXE"
    issues: list[str] = []
    ref_rows: list[dict[str, str]] = []
    sidecar_link_mode = ""
    title_fallback = ""

    if not args.input.is_file():
        issues.append("missing_input_executable")
    if not args.hd_locallng.is_file():
        issues.append("missing_hd_locallng")
    if args.title_fallback and not args.original_locallng.is_file():
        issues.append("missing_original_locallng")

    if not issues:
        output.mkdir(parents=True, exist_ok=True)
        data = bytearray(args.input.read_bytes())
        string_offset = file_offset_for_va(args.input, PATCH_STRING_VA)
        if any(data[string_offset + index] for index in range(len(PATCH_STRING))):
            issues.append("patch_string_cave_not_empty")

        for reference_va, original_string_va in zip(REFERENCE_IMMEDIATE_VAS, ORIGINAL_STRING_VAS):
            reference_offset = file_offset_for_va(args.input, reference_va)
            old_bytes = bytes(data[reference_offset : reference_offset + 4])
            expected = original_string_va.to_bytes(4, "little")
            status = "ready"
            if old_bytes != expected:
                status = "unexpected_reference_bytes"
                issues.append(f"{status}:{reference_va:#x}")
            ref_rows.append(
                {
                    "reference_va": f"{reference_va:#010x}",
                    "old_string_va": f"{original_string_va:#010x}",
                    "new_string_va": f"{PATCH_STRING_VA:#010x}",
                    "old_bytes": old_bytes.hex(),
                    "new_bytes": PATCH_STRING_VA.to_bytes(4, "little").hex(),
                    "status": status,
                }
            )

        if not issues:
            data[string_offset : string_offset + len(PATCH_STRING)] = PATCH_STRING
            for reference_va in REFERENCE_IMMEDIATE_VAS:
                reference_offset = file_offset_for_va(args.input, reference_va)
                data[reference_offset : reference_offset + 4] = PATCH_STRING_VA.to_bytes(4, "little")
            patched.write_bytes(data)
            try:
                os.chmod(patched, args.input.stat().st_mode)
            except OSError:
                pass

            sidecar_dir.mkdir(parents=True, exist_ok=True)
            sidecar_link_mode = link_or_copy(args.hd_locallng, sidecar_dir / "LOCALLNG_HD.MIX")
            if args.title_fallback:
                title_fallback = write_title_fallback(
                    args.original_locallng,
                    sidecar_dir / "outtakes" / "TITLE_E.VQA",
                )

    status = "pass" if not issues else "gap"
    summary = {
        "status": status,
        "input_executable": str(args.input),
        "patched_executable": str(patched),
        "sidecar_dir": str(sidecar_dir),
        "sidecar_source": str(args.hd_locallng),
        "sidecar_link": sidecar_link_mode,
        "title_fallback": title_fallback,
        "patch_string_va": f"{PATCH_STRING_VA:#010x}",
        "patch_string": PATCH_STRING.rstrip(b"\0").decode("ascii"),
        "patched_references": str(len(REFERENCE_IMMEDIATE_VAS) if not issues else 0),
        "issues": ";".join(issues),
        "next_step": (
            "launch RUN_HD_WINE.sh with LOCALLNG.MIX excluded, this patched executable, "
            "and the generated sidecar directory"
        ),
    }
    write_csv(output / "summary.csv", SUMMARY_FIELDS, [summary])
    write_csv(output / "references.csv", REF_FIELDS, ref_rows)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a LOCALLNG_HD.MIX Wine sidecar patch probe.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--hd-locallng", type=Path, default=DEFAULT_HD_LOCALLNG)
    parser.add_argument("--original-locallng", type=Path, default=DEFAULT_ORIGINAL_LOCALLNG)
    parser.add_argument(
        "--no-title-fallback",
        dest="title_fallback",
        action="store_false",
        help="Do not write sidecar/outtakes/TITLE_E.VQA from the original LOCALLNG.MIX",
    )
    parser.set_defaults(title_fallback=True)
    args = parser.parse_args()

    summary = build_patch(args)
    print(f"LOLG95 LOCALLNG sidecar patch probe: {summary['status']}")
    print(f"Patched executable: {summary['patched_executable']}")
    print(f"Sidecar dir: {summary['sidecar_dir']}")
    if summary["issues"]:
        print(f"Issues: {summary['issues']}")


if __name__ == "__main__":
    main()
