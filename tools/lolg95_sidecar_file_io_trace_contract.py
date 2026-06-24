#!/usr/bin/env python3
"""Build a file-I/O trace contract for the LOLG95 L20 VQA sidecar payloads."""

from __future__ import annotations

import argparse
import csv
import html
from pathlib import Path


DEFAULT_OUTPUT = Path("output/lolg95_sidecar_file_io_trace_contract")
DEFAULT_RUNTIME_ARCHIVES = Path("output/lolg95_runtime_archive_list_l20_sidecar_probe/archives.tsv")
DEFAULT_RUNTIME_TARGETS = Path("output/lolg95_runtime_archive_list_l20_sidecar_probe/targets.tsv")
DEFAULT_LOAD_PLAN_ENTRIES = Path("output/vqa_runtime_sidecar_load_plan/entries.csv")

READFILE_VA = "0x004eb390"
SETFILEPOINTER_VA = "0x004eb7eb"

SUMMARY_FIELDS = [
    "status",
    "contract_status",
    "targets",
    "sidecar_archive",
    "sidecar_base_offset",
    "sidecar_body_pointer",
    "tracepoints",
    "readfile_tracepoint",
    "setfilepointer_tracepoint",
    "expected_offset_min",
    "expected_offset_max",
    "runtime_trace_status",
    "issues",
    "next_step",
]

REQUIREMENT_FIELDS = ["requirement", "status", "evidence", "next_step"]

TRACEPOINT_FIELDS = [
    "tracepoint_id",
    "breakpoint_va",
    "kind",
    "source",
    "capture_registers",
    "capture_stack",
    "expected_signal",
    "notes",
]

TARGET_FIELDS = [
    "source_archive",
    "index",
    "file_id",
    "sidecar_archive",
    "sidecar_base_offset",
    "sidecar_entry_offset",
    "sidecar_size",
    "expected_file_offset_start",
    "expected_file_offset_end",
    "readfile_breakpoint",
    "setfilepointer_breakpoint",
    "expected_signal",
]

COMMAND_FIELDS = ["format", "path", "tracepoints", "purpose", "command_hint"]


def read_rows(path: Path, delimiter: str = ",") -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]], delimiter: str = ",") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter=delimiter)
        writer.writeheader()
        writer.writerows(rows)


def to_int(value: str) -> int:
    text = str(value).strip()
    if not text:
        return 0
    if text.lower().startswith("0x"):
        return int(text, 16)
    return int(text)


def sidecar_archive_row(archives: list[dict[str, str]]) -> dict[str, str]:
    for row in archives:
        name = row.get("name", "").lower()
        if name.endswith("_hd.mix"):
            return row
    return {}


def build_tracepoints() -> list[dict[str, str]]:
    return [
        {
            "tracepoint_id": "sidecar_setfilepointer_01",
            "breakpoint_va": SETFILEPOINTER_VA,
            "kind": "SetFilePointer",
            "source": "LOLG95.EXE",
            "capture_registers": "eip,ebx,ecx,edi,esi,esp",
            "capture_stack": "[esp],[esp+4],[esp+8],[esp+12]",
            "expected_signal": "path at *(ebx+0x18) is l20_bbI_HD.MIX and edi falls inside a target payload range",
            "notes": "At 0x004eb7eb the handle is [ebx+0x10], path pointer is [ebx+0x18], offset low is edi, and move method is esi.",
        },
        {
            "tracepoint_id": "sidecar_readfile_01",
            "breakpoint_va": READFILE_VA,
            "kind": "ReadFile",
            "source": "LOLG95.EXE",
            "capture_registers": "eip,ebx,edi,esi,esp",
            "capture_stack": "[esp]=handle,[esp+4]=buffer,[esp+8]=bytes,[esp+12]=bytes_read_ptr,[esp+16]=overlapped",
            "expected_signal": "path at *(ebx+0x18) is l20_bbI_HD.MIX after a target-range seek",
            "notes": "At 0x004eb390 the requested byte count is [esp+8] and the current file object path remains at [ebx+0x18].",
        },
    ]


def build_targets(args: argparse.Namespace) -> tuple[list[dict[str, str]], dict[str, str]]:
    archives = read_rows(args.runtime_archives, delimiter="\t")
    runtime_targets = {row.get("file_id", "").lower(): row for row in read_rows(args.runtime_targets, delimiter="\t")}
    load_entries = read_rows(args.load_plan_entries)
    sidecar = sidecar_archive_row(archives)
    base_offset = to_int(sidecar.get("base_offset", "0"))
    target_rows: list[dict[str, str]] = []

    for row in load_entries:
        file_id = row.get("file_id", "").lower()
        runtime = runtime_targets.get(file_id, {})
        sidecar_offset = to_int(row.get("sidecar_offset") or runtime.get("first_entry_offset", "0"))
        sidecar_size = to_int(row.get("sidecar_size") or runtime.get("first_entry_size", "0"))
        start = base_offset + sidecar_offset
        end = start + sidecar_size
        target_rows.append(
            {
                "source_archive": row.get("source_archive", ""),
                "index": row.get("index", ""),
                "file_id": file_id,
                "sidecar_archive": row.get("runtime_first_archive") or runtime.get("first_archive", ""),
                "sidecar_base_offset": str(base_offset),
                "sidecar_entry_offset": str(sidecar_offset),
                "sidecar_size": str(sidecar_size),
                "expected_file_offset_start": str(start),
                "expected_file_offset_end": str(end),
                "readfile_breakpoint": READFILE_VA,
                "setfilepointer_breakpoint": SETFILEPOINTER_VA,
                "expected_signal": "SetFilePointer offset inside this range followed by ReadFile on l20_bbI_HD.MIX",
            }
        )
    return target_rows, sidecar


def write_winedbg_commands(path: Path, tracepoints: list[dict[str, str]], capture_stops: int) -> None:
    lines = [
        "# Generated by tools/lolg95_sidecar_file_io_trace_contract.py",
        "# Attach these commands to the staged LOLG95 process after forcing L20.",
    ]
    for row in tracepoints:
        lines.append(f"break *{row['breakpoint_va']}")
    for _index in range(capture_stops):
        lines.extend(
            [
                "cont",
                "info regs",
                "x /x $ebx",
                "x /x ($ebx + 0x10)",
                "x /x ($ebx + 0x18)",
                "x /s *($ebx + 0x18)",
                "x /x $edi",
                "x /x $esi",
                "x /x $esp",
                "x /x ($esp + 4)",
                "x /x ($esp + 8)",
                "x /x ($esp + 12)",
                "x /x ($esp + 16)",
            ]
        )
    lines.append("quit")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_windbg_commands(path: Path, tracepoints: list[dict[str, str]]) -> None:
    lines = [
        "$$ Generated by tools/lolg95_sidecar_file_io_trace_contract.py",
        ".echo tracepoint_id\tbreakpoint_va\tkind\teip\tebx\tpath_ptr\thandle\tedi\tesi\tesp0\tesp4\tesp8\tesp12",
    ]
    for row in tracepoints:
        lines.append(
            f"bp {row['breakpoint_va']} "
            f"\".printf \\\"{row['tracepoint_id']}\\t{row['breakpoint_va']}\\t{row['kind']}\\t"
            "0x%08x\\t0x%08x\\t0x%08x\\t0x%08x\\t0x%08x\\t0x%08x\\t0x%08x\\t0x%08x\\t0x%08x\\t0x%08x\\n\\\", "
            "@eip, @ebx, poi(@ebx+0x18), poi(@ebx+0x10), @edi, @esi, poi(@esp), poi(@esp+4), poi(@esp+8), poi(@esp+12); gc\""
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="ascii")


def build_requirements(summary: dict[str, str]) -> list[dict[str, str]]:
    targets = to_int(summary.get("targets", "0"))
    tracepoints = to_int(summary.get("tracepoints", "0"))
    return [
        {
            "requirement": "sidecar_target_offsets",
            "status": "pass" if targets == 8 else "gap",
            "evidence": f"targets={targets};offset_min={summary.get('expected_offset_min', '')};offset_max={summary.get('expected_offset_max', '')}",
            "next_step": "rerun the runtime archive-list and sidecar load-plan reports",
        },
        {
            "requirement": "file_io_tracepoints",
            "status": "pass" if tracepoints == 2 else "gap",
            "evidence": f"readfile={summary.get('readfile_tracepoint', '')};setfilepointer={summary.get('setfilepointer_tracepoint', '')}",
            "next_step": "keep ReadFile and SetFilePointer breakpoints aligned with LOLG95.EXE",
        },
        {
            "requirement": "runtime_file_io_trace",
            "status": "gap",
            "evidence": f"runtime_trace_status={summary.get('runtime_trace_status', '')}",
            "next_step": "run the generated winedbg commands against the staged Wine process",
        },
        {
            "requirement": "payload_read_evidence",
            "status": "gap",
            "evidence": "no observed SetFilePointer/ReadFile pair for l20_bbI_HD.MIX target ranges yet",
            "next_step": "match a sidecar path seek/read against one target offset range",
        },
    ]


def render_table(rows: list[dict[str, str]], fields: list[str]) -> str:
    head = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def render_html(
    path: Path,
    summary: dict[str, str],
    requirements: list[dict[str, str]],
    tracepoints: list[dict[str, str]],
    targets: list[dict[str, str]],
) -> None:
    path.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>LOLG95 Sidecar File-I/O Trace Contract</title>
<style>
body {{ margin: 24px; font-family: system-ui, sans-serif; color: #20252b; background: #f7f7f3; }}
h1, h2 {{ margin: 0 0 12px; }}
section {{ margin: 0 0 26px; }}
table {{ width: 100%; border-collapse: collapse; background: white; }}
th, td {{ padding: 8px 10px; border-bottom: 1px solid #d8d8d0; text-align: left; vertical-align: top; overflow-wrap: anywhere; }}
th {{ background: #eeeee7; }}
.status-pass {{ color: #176c37; font-weight: 700; }}
.status-gap {{ color: #9a4d00; font-weight: 700; }}
</style>
</head>
<body>
<h1>LOLG95 Sidecar File-I/O Trace Contract</h1>
<section><h2>Summary</h2>{render_table([summary], SUMMARY_FIELDS)}</section>
<section><h2>Requirements</h2>{render_table(requirements, REQUIREMENT_FIELDS)}</section>
<section><h2>Tracepoints</h2>{render_table(tracepoints, TRACEPOINT_FIELDS)}</section>
<section><h2>Target Offset Ranges</h2>{render_table(targets, TARGET_FIELDS)}</section>
</body>
</html>
""",
        encoding="utf-8",
    )


def build_report(args: argparse.Namespace) -> dict[str, str]:
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    targets, sidecar = build_targets(args)
    tracepoints = build_tracepoints()
    offsets = [to_int(row["expected_file_offset_start"]) for row in targets]
    offset_ends = [to_int(row["expected_file_offset_end"]) for row in targets]
    issues: list[str] = []
    if len(targets) != 8:
        issues.append("target_offsets_not_8")
    if not sidecar:
        issues.append("missing_runtime_sidecar_archive")
    issues.append("runtime_file_io_trace_not_executed")

    winedbg_commands = output / "winedbg_commands.txt"
    windbg_breakpoints = output / "windbg_breakpoints.cmd"
    write_winedbg_commands(winedbg_commands, tracepoints, args.capture_stops)
    write_windbg_commands(windbg_breakpoints, tracepoints)

    summary = {
        "status": "gap",
        "contract_status": "pass" if len(targets) == 8 and sidecar and len(tracepoints) == 2 else "gap",
        "targets": str(len(targets)),
        "sidecar_archive": sidecar.get("name", ""),
        "sidecar_base_offset": sidecar.get("base_offset", ""),
        "sidecar_body_pointer": sidecar.get("body_pointer", ""),
        "tracepoints": str(len(tracepoints)),
        "readfile_tracepoint": READFILE_VA,
        "setfilepointer_tracepoint": SETFILEPOINTER_VA,
        "expected_offset_min": str(min(offsets)) if offsets else "",
        "expected_offset_max": str(max(offset_ends)) if offset_ends else "",
        "runtime_trace_status": "not_run",
        "issues": ";".join(dict.fromkeys(issues)),
        "next_step": "attach winedbg to the staged Wine process and match l20_bbI_HD.MIX seeks/reads against target offset ranges",
    }
    requirements = build_requirements(summary)
    commands = [
        {
            "format": "winedbg",
            "path": str(winedbg_commands),
            "tracepoints": str(len(tracepoints)),
            "purpose": "capture ReadFile/SetFilePointer sidecar path and offsets",
            "command_hint": "use after the L20 sidecar stage is launched and forced to level 20",
        },
        {
            "format": "windbg",
            "path": str(windbg_breakpoints),
            "tracepoints": str(len(tracepoints)),
            "purpose": "same contract for a native Windows debugger",
            "command_hint": "load in WinDbg if the target is run outside Wine",
        },
    ]
    write_csv(output / "summary.csv", SUMMARY_FIELDS, [summary])
    write_csv(output / "requirements.csv", REQUIREMENT_FIELDS, requirements)
    write_csv(output / "tracepoints.tsv", TRACEPOINT_FIELDS, tracepoints, delimiter="\t")
    write_csv(output / "targets.csv", TARGET_FIELDS, targets)
    write_csv(output / "commands.csv", COMMAND_FIELDS, commands)
    render_html(output / "index.html", summary, requirements, tracepoints, targets)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a file-I/O trace contract for the LOLG95 sidecar VQA targets.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runtime-archives", type=Path, default=DEFAULT_RUNTIME_ARCHIVES)
    parser.add_argument("--runtime-targets", type=Path, default=DEFAULT_RUNTIME_TARGETS)
    parser.add_argument("--load-plan-entries", type=Path, default=DEFAULT_LOAD_PLAN_ENTRIES)
    parser.add_argument("--capture-stops", type=int, default=256)
    args = parser.parse_args()

    summary = build_report(args)
    print(
        "LOLG95 sidecar file-I/O trace contract: "
        f"{summary['contract_status']} "
        f"(targets {summary['targets']}, status {summary['status']})"
    )


if __name__ == "__main__":
    main()
