#!/usr/bin/env python3
"""Probe compiled MIX loader anchors for the VQA sidecar runtime hook."""

from __future__ import annotations

import argparse
import csv
import html
import json
import struct
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


DEFAULT_OUTPUT = Path("output/vqa_runtime_loader_probe")
DEFAULT_INPUTS = [Path("LOLG95.EXE"), Path("LOLG.DAT"), Path("LOLG.EXE")]
DEFAULT_ANCHORS = [
    "SPKSTON%d.MIX",
    "GLOBAL.MIX",
    ".MIX",
    "-NOCDCACHE",
    "MOVIES.MIX",
    "CDCACHE.MIX",
    "DMUSIC.MIX",
    "-NOMIX",
    "LOCAL.MIX",
    "LOCALLNG.MIX",
    "L20_BBI.MIX",
    "L20_BBI_HD.MIX",
]
DEFAULT_IMPORTS = [
    "CreateFileA",
    "ReadFile",
    "SetFilePointer",
    "GetFileSize",
    "CloseHandle",
    "GetLastError",
]

SUMMARY_FIELDS = [
    "status",
    "input_files",
    "pe_files",
    "dos4g_files",
    "anchor_hits",
    "anchor_xrefs",
    "sidecar_name_hits",
    "createfile_iats",
    "createfile_xrefs",
    "hook_candidates",
    "issues",
    "next_step",
]

REQUIREMENT_FIELDS = ["requirement", "status", "evidence", "next_step"]

INPUT_FIELDS = [
    "path",
    "exists",
    "size_bytes",
    "format",
    "image_base",
    "code_sections",
    "data_sections",
    "issues",
]

ANCHOR_FIELDS = [
    "path",
    "anchor",
    "file_offset",
    "section",
    "va",
    "xref_count",
    "xrefs",
    "interpretation",
]

XREF_FIELDS = [
    "path",
    "kind",
    "target",
    "target_va",
    "ref_va",
    "ref_file_offset",
    "section",
    "context_hex",
    "interpretation",
]

IMPORT_FIELDS = [
    "path",
    "dll",
    "function",
    "iat_va",
    "xref_count",
    "xrefs",
    "interpretation",
]

CANDIDATE_FIELDS = ["candidate", "status", "path", "evidence", "next_step"]


@dataclass(frozen=True)
class Section:
    name: str
    va: int
    raw_offset: int
    raw_size: int
    virtual_size: int
    characteristics: int

    @property
    def is_code(self) -> bool:
        return bool(self.characteristics & 0x20)

    @property
    def is_data(self) -> bool:
        return bool(self.characteristics & 0x40)


@dataclass(frozen=True)
class ImportSymbol:
    dll: str
    function: str
    iat_va: int


@dataclass
class BinaryInfo:
    path: Path
    data: bytes
    fmt: str
    image_base: int
    sections: list[Section]
    imports: list[ImportSymbol]
    issues: list[str]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def count_occurrences(data: bytes, needle: bytes) -> int:
    if not needle:
        return 0
    count = 0
    start = 0
    while True:
        index = data.find(needle, start)
        if index < 0:
            return count
        count += 1
        start = index + 1


def find_all(data: bytes, needle: bytes) -> list[int]:
    offsets: list[int] = []
    start = 0
    while True:
        index = data.find(needle, start)
        if index < 0:
            return offsets
        offsets.append(index)
        start = index + 1


def parse_c_string(data: bytes, offset: int) -> str:
    end = data.find(b"\0", offset)
    if end < 0:
        end = len(data)
    return data[offset:end].decode("ascii", errors="replace")


def hex_value(value: int | None) -> str:
    return f"0x{value:08x}" if value is not None else ""


def section_for_offset(sections: list[Section], offset: int) -> Section | None:
    for section in sections:
        if section.raw_offset <= offset < section.raw_offset + section.raw_size:
            return section
    return None


def section_for_va(sections: list[Section], va: int) -> Section | None:
    for section in sections:
        if section.va <= va < section.va + max(section.raw_size, section.virtual_size):
            return section
    return None


def va_from_offset(sections: list[Section], offset: int) -> int | None:
    section = section_for_offset(sections, offset)
    if section is None:
        return None
    return section.va + (offset - section.raw_offset)


def offset_from_rva(sections: list[Section], image_base: int, rva: int) -> int | None:
    va = image_base + rva
    section = section_for_va(sections, va)
    if section is None:
        return None
    return section.raw_offset + (va - section.va)


def read_u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def read_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def parse_pe(path: Path, data: bytes) -> tuple[str, int, list[Section], list[ImportSymbol], list[str]]:
    issues: list[str] = []
    if len(data) < 0x40 or data[:2] != b"MZ":
        return "data", 0, [], [], issues
    pe_offset = read_u32(data, 0x3C)
    if pe_offset + 0x18 >= len(data) or data[pe_offset : pe_offset + 4] != b"PE\0\0":
        signature = b"DOS/4G" if b"DOS/4G" in data[:4096] or b"DOS/4G" in data else b""
        return ("dos4g" if signature else "mz"), 0, [], [], issues

    coff = pe_offset + 4
    section_count = read_u16(data, coff + 2)
    optional_size = read_u16(data, coff + 16)
    optional = coff + 20
    magic = read_u16(data, optional)
    if magic != 0x10B:
        issues.append(f"unsupported_pe_magic:{magic:04x}")
        return "pe", 0, [], [], issues
    image_base = read_u32(data, optional + 28)
    import_rva = read_u32(data, optional + 96 + 8)
    import_size = read_u32(data, optional + 96 + 12)

    sections: list[Section] = []
    section_table = optional + optional_size
    for index in range(section_count):
        entry = section_table + index * 40
        raw_name = data[entry : entry + 8].split(b"\0", 1)[0]
        name = raw_name.decode("ascii", errors="replace")
        virtual_size = read_u32(data, entry + 8)
        virtual_address = read_u32(data, entry + 12)
        raw_size = read_u32(data, entry + 16)
        raw_offset = read_u32(data, entry + 20)
        characteristics = read_u32(data, entry + 36)
        sections.append(
            Section(
                name=name,
                va=image_base + virtual_address,
                raw_offset=raw_offset,
                raw_size=raw_size,
                virtual_size=virtual_size,
                characteristics=characteristics,
            )
        )

    imports: list[ImportSymbol] = []
    if import_rva and import_size:
        descriptor_offset = offset_from_rva(sections, image_base, import_rva)
        if descriptor_offset is None:
            issues.append("import_directory_not_mapped")
        else:
            cursor = descriptor_offset
            while cursor + 20 <= len(data):
                original_thunk, _timestamp, _forwarder, name_rva, first_thunk = struct.unpack_from("<IIIII", data, cursor)
                if not any((original_thunk, name_rva, first_thunk)):
                    break
                name_offset = offset_from_rva(sections, image_base, name_rva)
                dll = parse_c_string(data, name_offset) if name_offset is not None else ""
                thunk_rva = original_thunk or first_thunk
                thunk_offset = offset_from_rva(sections, image_base, thunk_rva)
                if thunk_offset is None:
                    issues.append(f"thunk_not_mapped:{dll}")
                    cursor += 20
                    continue
                thunk_index = 0
                while thunk_offset + thunk_index * 4 + 4 <= len(data):
                    thunk_value = read_u32(data, thunk_offset + thunk_index * 4)
                    if thunk_value == 0:
                        break
                    if not (thunk_value & 0x80000000):
                        name_ptr = offset_from_rva(sections, image_base, thunk_value)
                        if name_ptr is not None and name_ptr + 2 < len(data):
                            function = parse_c_string(data, name_ptr + 2)
                            imports.append(
                                ImportSymbol(
                                    dll=dll,
                                    function=function,
                                    iat_va=image_base + first_thunk + thunk_index * 4,
                                )
                            )
                    thunk_index += 1
                cursor += 20
    return "pe", image_base, sections, imports, issues


def read_binary(path: Path) -> BinaryInfo:
    if not path.exists():
        return BinaryInfo(path=path, data=b"", fmt="missing", image_base=0, sections=[], imports=[], issues=["file_missing"])
    data = path.read_bytes()
    fmt, image_base, sections, imports, issues = parse_pe(path, data)
    if fmt == "mz" and (b"DOS/4G" in data[:4096] or b"DOS/4G" in data):
        fmt = "dos4g"
    return BinaryInfo(path=path, data=data, fmt=fmt, image_base=image_base, sections=sections, imports=imports, issues=issues)


def code_ranges(info: BinaryInfo) -> list[tuple[Section | None, int, bytes]]:
    if info.sections:
        ranges = []
        for section in info.sections:
            if section.is_code and section.raw_size:
                start = section.raw_offset
                ranges.append((section, start, info.data[start : start + section.raw_size]))
        return ranges
    return []


def find_code_xrefs(info: BinaryInfo, target_va: int) -> list[tuple[int, int, Section | None]]:
    pattern = struct.pack("<I", target_va)
    refs: list[tuple[int, int, Section | None]] = []
    for section, start, blob in code_ranges(info):
        for relative in find_all(blob, pattern):
            file_offset = start + relative
            ref_va = va_from_offset(info.sections, file_offset) if info.sections else None
            refs.append((ref_va or 0, file_offset, section))
    return refs


def context_hex(data: bytes, offset: int, radius: int = 12) -> str:
    start = max(0, offset - radius)
    end = min(len(data), offset + 4 + radius)
    return data[start:end].hex()


def anchor_interpretation(anchor: str, xref_count: int) -> str:
    if anchor == "L20_BBI_HD.MIX":
        return "sidecar_name_present" if xref_count else "sidecar_name_absent"
    if anchor == ".MIX" and xref_count:
        return "generic_mix_suffix_constructor"
    if anchor == "CDCACHE.MIX" and xref_count:
        return "cdcache_mount_path"
    if anchor in {"GLOBAL.MIX", "LOCAL.MIX", "LOCALLNG.MIX"} and xref_count:
        return "startup_archive_mount_path"
    if anchor.endswith(".MIX") and xref_count:
        return "mix_archive_anchor"
    if anchor.startswith("-") and xref_count:
        return "command_line_gate"
    return "string_only" if xref_count == 0 else "code_referenced"


def import_interpretation(function: str, xref_count: int) -> str:
    if function == "CreateFileA" and xref_count:
        return "file_open_wrapper_or_direct_open"
    if function in {"ReadFile", "SetFilePointer", "GetFileSize"} and xref_count:
        return "file_payload_io"
    if function in {"CloseHandle", "GetLastError"} and xref_count:
        return "file_lifecycle"
    return "import_unreferenced_by_static_scan"


def build_reports(args: argparse.Namespace) -> tuple[
    dict[str, str],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    infos = [read_binary(path) for path in args.input]
    input_rows: list[dict[str, str]] = []
    anchor_rows: list[dict[str, str]] = []
    xref_rows: list[dict[str, str]] = []
    import_rows: list[dict[str, str]] = []
    candidate_rows: list[dict[str, str]] = []
    issue_counter: Counter[str] = Counter()

    for info in infos:
        if info.issues:
            for issue in info.issues:
                issue_counter[issue] += 1
        input_rows.append(
            {
                "path": str(info.path),
                "exists": "1" if info.path.exists() else "0",
                "size_bytes": str(len(info.data)),
                "format": info.fmt,
                "image_base": hex_value(info.image_base) if info.image_base else "",
                "code_sections": str(sum(1 for section in info.sections if section.is_code)),
                "data_sections": str(sum(1 for section in info.sections if section.is_data)),
                "issues": ";".join(info.issues),
            }
        )

        for anchor in args.anchor:
            offsets = find_all(info.data, anchor.encode("ascii"))
            for offset in offsets:
                section = section_for_offset(info.sections, offset) if info.sections else None
                va = va_from_offset(info.sections, offset) if info.sections else None
                refs = find_code_xrefs(info, va) if va is not None else []
                xrefs_text = ",".join(hex_value(ref_va) for ref_va, _file_offset, _section in refs)
                interpretation = anchor_interpretation(anchor, len(refs))
                anchor_rows.append(
                    {
                        "path": str(info.path),
                        "anchor": anchor,
                        "file_offset": hex_value(offset),
                        "section": section.name if section else "",
                        "va": hex_value(va),
                        "xref_count": str(len(refs)),
                        "xrefs": xrefs_text,
                        "interpretation": interpretation,
                    }
                )
                for ref_va, file_offset, ref_section in refs:
                    xref_rows.append(
                        {
                            "path": str(info.path),
                            "kind": "string_anchor",
                            "target": anchor,
                            "target_va": hex_value(va),
                            "ref_va": hex_value(ref_va),
                            "ref_file_offset": hex_value(file_offset),
                            "section": ref_section.name if ref_section else "",
                            "context_hex": context_hex(info.data, file_offset),
                            "interpretation": interpretation,
                        }
                    )

        imports_by_name: dict[str, list[ImportSymbol]] = {}
        for symbol in info.imports:
            imports_by_name.setdefault(symbol.function, []).append(symbol)
        for function in args.import_name:
            for symbol in imports_by_name.get(function, []):
                refs = find_code_xrefs(info, symbol.iat_va)
                import_rows.append(
                    {
                        "path": str(info.path),
                        "dll": symbol.dll,
                        "function": symbol.function,
                        "iat_va": hex_value(symbol.iat_va),
                        "xref_count": str(len(refs)),
                        "xrefs": ",".join(hex_value(ref_va) for ref_va, _file_offset, _section in refs),
                        "interpretation": import_interpretation(symbol.function, len(refs)),
                    }
                )
                for ref_va, file_offset, ref_section in refs:
                    xref_rows.append(
                        {
                            "path": str(info.path),
                            "kind": "import_iat",
                            "target": symbol.function,
                            "target_va": hex_value(symbol.iat_va),
                            "ref_va": hex_value(ref_va),
                            "ref_file_offset": hex_value(file_offset),
                            "section": ref_section.name if ref_section else "",
                            "context_hex": context_hex(info.data, file_offset),
                            "interpretation": import_interpretation(symbol.function, len(refs)),
                        }
                    )

    def matching_anchors(anchor: str, path: str = "LOLG95.EXE") -> list[dict[str, str]]:
        return [row for row in anchor_rows if Path(row["path"]).name == path and row["anchor"] == anchor]

    def matching_import(function: str, path: str = "LOLG95.EXE") -> list[dict[str, str]]:
        return [row for row in import_rows if Path(row["path"]).name == path and row["function"] == function]

    def joined_xrefs(rows: list[dict[str, str]]) -> str:
        refs: list[str] = []
        for row in rows:
            refs.extend(part for part in row.get("xrefs", "").split(",") if part)
        return ",".join(dict.fromkeys(refs))

    def xref_total(rows: list[dict[str, str]]) -> int:
        return sum(int(row.get("xref_count", "0") or 0) for row in rows)

    generic_mix = matching_anchors(".MIX")
    global_mix = matching_anchors("GLOBAL.MIX")
    local_mix = matching_anchors("LOCAL.MIX")
    cdcache_mix = matching_anchors("CDCACHE.MIX")
    createfile = matching_import("CreateFileA")
    dat_mix_hits = [
        row
        for row in anchor_rows
        if Path(row["path"]).name == "LOLG.DAT" and row["anchor"] in {"GLOBAL.MIX", ".MIX", "CDCACHE.MIX", "LOCAL.MIX"}
    ]

    candidate_rows.extend(
        [
            {
                "candidate": "pe_archive_name_constructor",
                "status": "pass" if xref_total(generic_mix) else "gap",
                "path": "LOLG95.EXE",
                "evidence": f".MIX_xrefs={joined_xrefs(generic_mix)}",
                "next_step": "trace calls around this constructor while opening L20_BBI.MIX",
            },
            {
                "candidate": "pe_startup_archive_mounts",
                "status": "pass" if global_mix and local_mix else "gap",
                "path": "LOLG95.EXE",
                "evidence": (
                    f"GLOBAL.MIX={joined_xrefs(global_mix)};"
                    f"LOCAL.MIX={joined_xrefs(local_mix)}"
                ),
                "next_step": "reuse the same archive mount object only if it accepts additional VQA MIX paths",
            },
            {
                "candidate": "pe_cdcache_mount_path",
                "status": "pass" if xref_total(cdcache_mix) else "gap",
                "path": "LOLG95.EXE",
                "evidence": f"CDCACHE.MIX_xrefs={joined_xrefs(cdcache_mix)}",
                "next_step": "avoid CDCACHE as the sidecar declaration path; use it only as loader architecture evidence",
            },
            {
                "candidate": "pe_createfile_wrapper",
                "status": "pass" if createfile and sum(int(row["xref_count"]) for row in createfile) else "gap",
                "path": "LOLG95.EXE",
                "evidence": "CreateFileA_refs="
                + ",".join(
                    f"{row['iat_va']}->{row['xrefs']}" for row in createfile if int(row["xref_count"])
                ),
                "next_step": "hook or trace this wrapper to add an L20_BBI_HD.MIX fallback after L20_BBI.MIX lookup",
            },
            {
                "candidate": "dos4g_loader_strings",
                "status": "research" if dat_mix_hits else "gap",
                "path": "LOLG.DAT",
                "evidence": f"mix_string_hits={len(dat_mix_hits)};direct_pe_xrefs=0",
                "next_step": "treat DOS/4G as a separate target after the Windows runtime hook is proven",
            },
        ]
    )

    sidecar_name_hits = sum(1 for row in anchor_rows if row["anchor"] == "L20_BBI_HD.MIX")
    anchor_xrefs = sum(int(row["xref_count"]) for row in anchor_rows)
    createfile_xrefs = sum(int(row["xref_count"]) for row in import_rows if row["function"] == "CreateFileA")
    hook_candidates = sum(1 for row in candidate_rows if row["status"] == "pass")
    pe_files = sum(1 for info in infos if info.fmt == "pe")
    dos4g_files = sum(1 for info in infos if info.fmt == "dos4g")
    issues = []
    if sidecar_name_hits == 0:
        issues.append("sidecar_name_absent_from_compiled_loaders")
    issues.append("runtime_loader_hook_missing")

    requirements = [
        {
            "requirement": "compiled_loader_inputs",
            "status": "pass" if pe_files and dos4g_files else "gap",
            "evidence": f"pe_files={pe_files};dos4g_files={dos4g_files};inputs={len(infos)}",
            "next_step": "keep probing both Windows and DOS candidates, but patch one runtime target at a time",
        },
        {
            "requirement": "sidecar_static_name",
            "status": "pass" if sidecar_name_hits else "gap",
            "evidence": f"L20_BBI_HD.MIX_hits={sidecar_name_hits}",
            "next_step": "inject, patch, or wrap the sidecar name because the original binaries do not know it",
        },
        {
            "requirement": "mix_loader_anchors",
            "status": "pass" if anchor_xrefs else "gap",
            "evidence": f"anchor_hits={len(anchor_rows)};anchor_xrefs={anchor_xrefs}",
            "next_step": "use the anchor xrefs to choose the smallest hook surface",
        },
        {
            "requirement": "file_open_imports",
            "status": "pass" if createfile_xrefs else "gap",
            "evidence": f"CreateFileA_iats={len(createfile)};CreateFileA_xrefs={createfile_xrefs}",
            "next_step": "trace CreateFileA calls at runtime and identify the call path for L20_BBI.MIX",
        },
        {
            "requirement": "runtime_loader_hook",
            "status": "gap",
            "evidence": "static anchors found, but no patch/wrapper has opened L20_BBI_HD.MIX after L20_BBI.MIX yet",
            "next_step": "implement a runtime hook or binary patch, then prove the 8 deferred VQA IDs are read from the sidecar",
        },
    ]

    summary = {
        "status": "gap",
        "input_files": str(len(infos)),
        "pe_files": str(pe_files),
        "dos4g_files": str(dos4g_files),
        "anchor_hits": str(len(anchor_rows)),
        "anchor_xrefs": str(anchor_xrefs),
        "sidecar_name_hits": str(sidecar_name_hits),
        "createfile_iats": str(len(createfile)),
        "createfile_xrefs": str(createfile_xrefs),
        "hook_candidates": str(hook_candidates),
        "issues": ";".join(issues),
        "next_step": "trace or hook LOLG95.EXE CreateFileA/archive-open path for L20_BBI.MIX and add L20_BBI_HD.MIX fallback",
    }
    return summary, requirements, input_rows, anchor_rows, xref_rows, import_rows, candidate_rows


def render_table(rows: list[dict[str, str]], fields: list[str]) -> str:
    head = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def write_html(
    path: Path,
    summary: dict[str, str],
    requirements: list[dict[str, str]],
    inputs: list[dict[str, str]],
    anchors: list[dict[str, str]],
    xrefs: list[dict[str, str]],
    imports: list[dict[str, str]],
    candidates: list[dict[str, str]],
) -> None:
    payload = {
        "summary": summary,
        "requirements": requirements,
        "inputs": inputs,
        "anchors": anchors,
        "xrefs": xrefs,
        "imports": imports,
        "candidates": candidates,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    page = f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>VQA Runtime Loader Probe</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; background: #f7f7f3; color: #1f2933; }}
    h1, h2 {{ margin-bottom: 0.4rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
    .stat {{ background: white; border: 1px solid #d7d7ce; border-radius: 6px; padding: 12px; }}
    .label {{ color: #5f6b76; font-size: 0.85rem; }}
    .value {{ font-size: 1.35rem; font-weight: 700; }}
    table {{ border-collapse: collapse; width: 100%; background: white; margin: 12px 0 24px; }}
    th, td {{ border: 1px solid #d7d7ce; padding: 6px 8px; text-align: left; font-size: 0.86rem; }}
    th {{ background: #ecece4; }}
  </style>
</head>
<body>
  <h1>VQA Runtime Loader Probe</h1>
  <div class="grid">
    <div class="stat"><div class="label">Statut</div><div class="value">{html.escape(summary['status'])}</div></div>
    <div class="stat"><div class="label">Xrefs ancres</div><div class="value">{html.escape(summary['anchor_xrefs'])}</div></div>
    <div class="stat"><div class="label">CreateFileA refs</div><div class="value">{html.escape(summary['createfile_xrefs'])}</div></div>
    <div class="stat"><div class="label">Candidats hook</div><div class="value">{html.escape(summary['hook_candidates'])}</div></div>
  </div>
  <h2>Requirements</h2>
  {render_table(requirements, REQUIREMENT_FIELDS)}
  <h2>Candidats hook</h2>
  {render_table(candidates, CANDIDATE_FIELDS)}
  <h2>Inputs</h2>
  {render_table(inputs, INPUT_FIELDS)}
  <h2>Ancres</h2>
  {render_table(anchors, ANCHOR_FIELDS)}
  <h2>Imports</h2>
  {render_table(imports, IMPORT_FIELDS)}
  <h2>Xrefs</h2>
  {render_table(xrefs, XREF_FIELDS)}
  <script type="application/json" id="vqa-runtime-loader-probe">{html.escape(data_json)}</script>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe compiled MIX loader anchors for the VQA sidecar hook.")
    parser.add_argument("--input", type=Path, action="append", default=list(DEFAULT_INPUTS))
    parser.add_argument("--anchor", action="append", default=list(DEFAULT_ANCHORS))
    parser.add_argument("--import-name", action="append", default=list(DEFAULT_IMPORTS))
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    summary, requirements, inputs, anchors, xrefs, imports, candidates = build_reports(args)
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDS, [summary])
    write_csv(args.output / "requirements.csv", REQUIREMENT_FIELDS, requirements)
    write_csv(args.output / "inputs.csv", INPUT_FIELDS, inputs)
    write_csv(args.output / "anchors.csv", ANCHOR_FIELDS, anchors)
    write_csv(args.output / "xrefs.csv", XREF_FIELDS, xrefs)
    write_csv(args.output / "imports.csv", IMPORT_FIELDS, imports)
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDS, candidates)
    write_html(args.output / "index.html", summary, requirements, inputs, anchors, xrefs, imports, candidates)
    print(
        "VQA runtime loader probe: "
        f"{summary['status']} ({summary['hook_candidates']} hook candidates, "
        f"{summary['createfile_xrefs']} CreateFileA refs)"
    )
    print(f"Summary: {args.output / 'summary.csv'}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
