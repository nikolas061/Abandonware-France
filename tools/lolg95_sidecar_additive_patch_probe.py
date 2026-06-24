#!/usr/bin/env python3
"""Build an output-only LOLG95 probe that mounts a level HD sidecar additively."""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import struct
from pathlib import Path

from lolg_vqa_runtime_loader_probe import read_binary, read_u16, read_u32, section_for_va


DEFAULT_OUTPUT = Path("output/lolg95_sidecar_additive_patch_probe")
DEFAULT_INPUT = Path("LOLG95.EXE")
DEFAULT_SIDECAR = Path("mod_mix_vqa_fullhd_sidecar/L20_BBI_HD.MIX")

INJECTION_VA = 0x00453723
RETURN_VA = 0x00453729
STUB_VA = 0x005AB2D3
SCRATCH_VA = 0x005AB350
ALLOC_VA = 0x00507680
MIX_CONSTRUCTOR_VA = 0x004E41E0

ORIGINAL_INJECTION = bytes.fromhex("89855e060000")
DGROUP_EXECUTE_CHARACTERISTICS = 0xE0000060

SUMMARY_FIELDS = [
    "status",
    "input_executable",
    "patched_executable",
    "stage_dir",
    "sidecar_source",
    "sidecar_links",
    "injection_va",
    "return_va",
    "stub_va",
    "scratch_va",
    "stub_bytes",
    "patched_section",
    "patched_section_characteristics",
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


def patch_dgroup_execute(data: bytearray) -> tuple[str, str]:
    pe_offset = read_u32(data, 0x3C)
    section_count = read_u16(data, pe_offset + 6)
    optional_header_size = read_u16(data, pe_offset + 20)
    section_table = pe_offset + 24 + optional_header_size
    for index in range(section_count):
        header = section_table + index * 40
        name = bytes(data[header : header + 8]).split(b"\0", 1)[0].decode("ascii", errors="replace")
        if name == "DGROUP":
            struct.pack_into("<I", data, header + 36, DGROUP_EXECUTE_CHARACTERISTICS)
            return name, f"{DGROUP_EXECUTE_CHARACTERISTICS:#010x}"
    return "", ""


def rel32(source_va: int, target_va: int) -> bytes:
    return struct.pack("<i", target_va - (source_va + 5))


def build_stub() -> bytes:
    code = bytearray()
    labels: dict[str, int] = {}
    fixups: list[tuple[int, str, int]] = []

    def mark(label: str) -> None:
        labels[label] = len(code)

    def emit(data: bytes) -> None:
        code.extend(data)

    def emit_jump(opcode: int, label: str) -> None:
        code.append(opcode)
        fixups.append((len(code), label, 1))
        code.append(0)

    def emit_call(target_va: int) -> None:
        instruction_va = STUB_VA + len(code)
        emit(b"\xE8" + rel32(instruction_va, target_va))

    def emit_jmp_abs(target_va: int) -> None:
        instruction_va = STUB_VA + len(code)
        emit(b"\xE9" + rel32(instruction_va, target_va))

    emit(ORIGINAL_INJECTION)
    emit(b"\x60")  # pushad
    emit(b"\x8D\x74\x24\x20")  # lea esi,[esp+0x20], the caller's stack path
    emit(b"\xBF" + struct.pack("<I", SCRATCH_VA))  # mov edi,scratch

    mark("copy_until_dot")
    emit(b"\xAC")  # lodsb
    emit(b"\x3C\x2E")  # cmp al,'.'
    emit_jump(0x74, "dot")
    emit(b"\xAA")  # stosb
    emit(b"\x84\xC0")  # test al,al
    emit_jump(0x74, "alloc")
    emit_jump(0xEB, "copy_until_dot")

    mark("dot")
    emit(b"\xC6\x07\x5F")  # mov byte ptr [edi],'_'
    emit(b"\xC6\x47\x01\x48")  # mov byte ptr [edi+1],'H'
    emit(b"\xC6\x47\x02\x44")  # mov byte ptr [edi+2],'D'
    emit(b"\x83\xC7\x03")  # add edi,3
    emit(b"\xAA")  # write the dot from al

    mark("copy_rest")
    emit(b"\xAC")  # lodsb
    emit(b"\xAA")  # stosb
    emit(b"\x84\xC0")  # test al,al
    emit_jump(0x75, "copy_rest")

    mark("alloc")
    emit(b"\x6A\x24")  # push 0x24
    emit_call(ALLOC_VA)
    emit(b"\x83\xC4\x04")  # add esp,4
    emit(b"\x85\xC0")  # test eax,eax
    emit_jump(0x74, "done")
    emit(b"\x6A\x00")  # push 0
    emit(b"\x68" + struct.pack("<I", SCRATCH_VA))  # push scratch path
    emit(b"\x50")  # push eax, archive object
    emit_call(MIX_CONSTRUCTOR_VA)
    emit(b"\x83\xC4\x0C")  # add esp,0xc

    mark("done")
    emit(b"\x61")  # popad
    emit_jmp_abs(RETURN_VA)

    for offset, label, width in fixups:
        delta = labels[label] - (offset + width)
        if width == 1:
            if not -128 <= delta <= 127:
                raise ValueError(f"short jump out of range for {label}: {delta}")
            code[offset] = delta & 0xFF
        else:
            raise AssertionError(f"unsupported fixup width: {width}")

    return bytes(code)


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
    patched = output / "LOLG95_L20_SIDE_ADD.EXE"
    stage = output / "runtime_stage"
    issues: list[str] = []

    if not args.input.is_file():
        issues.append("missing_input_executable")
    if not args.sidecar.is_file():
        issues.append("missing_sidecar")

    stub = build_stub()
    top_level_links = 0
    patched_section = ""
    patched_section_characteristics = ""
    if not issues:
        data = bytearray(args.input.read_bytes())
        injection_offset = file_offset_for_va(args.input, INJECTION_VA)
        stub_offset = file_offset_for_va(args.input, STUB_VA)
        scratch_offset = file_offset_for_va(args.input, SCRATCH_VA)
        if data[injection_offset : injection_offset + len(ORIGINAL_INJECTION)] != ORIGINAL_INJECTION:
            issues.append("unexpected_injection_bytes")
        if any(data[stub_offset + index] for index in range(len(stub))):
            issues.append("stub_cave_not_empty")
        if any(data[scratch_offset + index] for index in range(96)):
            issues.append("scratch_cave_not_empty")
        patched_section, patched_section_characteristics = patch_dgroup_execute(data)
        if not patched_section:
            issues.append("missing_dgroup_section")
        if not issues:
            patch_jump = b"\xE9" + rel32(INJECTION_VA, STUB_VA) + b"\x90"
            data[injection_offset : injection_offset + len(patch_jump)] = patch_jump
            data[stub_offset : stub_offset + len(stub)] = stub
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
        "sidecar_links": "L20_BBI_HD.MIX;l20_bbI_HD.MIX",
        "injection_va": f"{INJECTION_VA:#010x}",
        "return_va": f"{RETURN_VA:#010x}",
        "stub_va": f"{STUB_VA:#010x}",
        "scratch_va": f"{SCRATCH_VA:#010x}",
        "stub_bytes": str(len(stub)),
        "patched_section": patched_section,
        "patched_section_characteristics": patched_section_characteristics,
        "top_level_links": str(top_level_links),
        "issues": ";".join(issues),
        "next_step": (
            "run the patched executable in the stage and verify L20_BBI.MIX and "
            "L20_BBI_HD.MIX are both opened; this proves additive sidecar mounting, "
            "not yet per-entry fallback selection"
        ),
    }
    write_csv(output / "summary.csv", SUMMARY_FIELDS, [summary])
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an output-only additive LOLG95 L20 sidecar patch probe.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--sidecar", type=Path, default=DEFAULT_SIDECAR)
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    args = parser.parse_args()

    summary = build_patch(args)
    print(f"LOLG95 additive sidecar patch probe: {summary['status']}")
    print(f"Patched executable: {summary['patched_executable']}")
    print(f"Stage: {summary['stage_dir']}")
    if summary["issues"]:
        print(f"Issues: {summary['issues']}")


if __name__ == "__main__":
    main()
