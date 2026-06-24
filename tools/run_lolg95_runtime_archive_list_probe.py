#!/usr/bin/env python3
"""Probe the live LOLG95 MIX archive list after the L20 sidecar mount."""

from __future__ import annotations

import argparse
import csv
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_lolg95_winedbg_attach_pilot_attempt import (  # noqa: E402
    parse_lolg95_linux_pid,
    parse_lolg95_pid,
    run_with_timeout,
    stop_process,
    write_process_dwords,
)
from run_lolg95_winedbg_loader_trace_attempt import read_csv, write_csv  # noqa: E402


DEFAULT_OUTPUT = Path("output/lolg95_runtime_archive_list_l20_sidecar_probe")
DEFAULT_EXPECTED_IDS = Path("output/vqa_runtime_loader_trace_contract/expected_sidecar_ids.csv")
ARCHIVE_LIST_HEAD_VA = 0x006A5B34

ARCHIVE_FIELDS = [
    "order",
    "node",
    "next",
    "prev_or_tail",
    "name_pointer",
    "name",
    "flags",
    "table_pointer",
    "body_size",
    "base_offset",
    "entry_count",
    "body_pointer",
    "issues",
]

TARGET_FIELDS = [
    "file_id",
    "expected_source_size",
    "expected_sidecar_size",
    "first_status",
    "first_order",
    "first_archive",
    "first_node",
    "first_entry_offset",
    "first_entry_size",
    "all_matches",
    "issues",
]

SUMMARY_FIELDS = [
    "status",
    "expected_ids",
    "runtime_executable",
    "runtime_args",
    "wineprefix",
    "wine_desktop",
    "startup_wait_seconds",
    "post_pilot_wait_seconds",
    "attach_pid",
    "linux_pid",
    "force_level_index",
    "force_level_slot",
    "force_level_write_status",
    "force_level_write_log",
    "command",
    "info_proc_log",
    "ps_log",
    "archives",
    "targets",
    "archive_nodes",
    "archive_names",
    "target_sidecar_first",
    "target_base_first",
    "target_missing",
    "target_unknown_first",
    "issues",
    "next_step",
]


def hex32(value: int) -> str:
    return f"0x{value & 0xFFFFFFFF:08x}"


def load_expected(path: Path) -> dict[str, dict[str, str]]:
    expected: dict[str, dict[str, str]] = {}
    for row in read_csv(path):
        file_id = row.get("file_id", "").lower()
        if not file_id:
            continue
        expected[file_id] = {
            "source_size": row.get("source_size", ""),
            "sidecar_size": row.get("sidecar_size", ""),
            "source_archive": row.get("source_archive", ""),
            "sidecar_archive": row.get("sidecar_archive", ""),
        }
    return expected


def read_mem(handle, address: int, size: int) -> bytes:
    handle.seek(address)
    data = handle.read(size)
    if len(data) != size:
        raise OSError(f"short_read:{address:#x}:{len(data)}:{size}")
    return data


def read_u32(handle, address: int) -> int:
    return int.from_bytes(read_mem(handle, address, 4), "little")


def read_c_string(handle, address: int, limit: int = 260) -> str:
    if address == 0:
        return ""
    data = read_mem(handle, address, limit)
    data = data.split(b"\0", 1)[0]
    return data.decode("latin-1", errors="replace")


def read_table_entry(handle, table_pointer: int, index: int) -> tuple[int, int, int]:
    data = read_mem(handle, table_pointer + index * 12, 12)
    file_id = int.from_bytes(data[0:4], "little")
    offset = int.from_bytes(data[4:8], "little")
    size = int.from_bytes(data[8:12], "little")
    return file_id, offset, size


def scan_archive_list(pid: str, expected: dict[str, dict[str, str]], max_archives: int) -> tuple[list[dict[str, str]], list[dict[str, str]], list[str]]:
    expected_ids = set(expected)
    archive_rows: list[dict[str, str]] = []
    matches_by_id: dict[str, list[dict[str, str]]] = {file_id: [] for file_id in expected_ids}
    issues: list[str] = []
    try:
        with open(f"/proc/{int(pid)}/mem", "rb", buffering=0) as handle:
            head = read_u32(handle, ARCHIVE_LIST_HEAD_VA)
            node = head
            seen: set[int] = set()
            order = 0
            while node and node not in seen and order < max_archives:
                seen.add(node)
                row_issues: list[str] = []
                try:
                    next_node = read_u32(handle, node)
                    prev_or_tail = read_u32(handle, node + 4)
                    name_pointer = read_u32(handle, node + 8)
                    flags = read_u32(handle, node + 12)
                    entry_count = read_u32(handle, node + 16)
                    body_size = read_u32(handle, node + 20)
                    base_offset = read_u32(handle, node + 24)
                    table_pointer = read_u32(handle, node + 28)
                    body_pointer = read_u32(handle, node + 32)
                    name = read_c_string(handle, name_pointer)
                    if entry_count > 20000:
                        row_issues.append(f"entry_count_too_large:{entry_count}")
                    elif table_pointer:
                        for index in range(entry_count):
                            file_id_value, entry_offset, entry_size = read_table_entry(handle, table_pointer, index)
                            file_id = f"{file_id_value:08x}"
                            if file_id in expected_ids:
                                matches_by_id[file_id].append(
                                    {
                                        "order": str(order),
                                        "archive": name,
                                        "node": hex32(node),
                                        "entry_offset": str(entry_offset),
                                        "entry_size": str(entry_size),
                                    }
                                )
                    else:
                        row_issues.append("missing_table_pointer")
                    archive_rows.append(
                        {
                            "order": str(order),
                            "node": hex32(node),
                            "next": hex32(next_node),
                            "prev_or_tail": hex32(prev_or_tail),
                            "name_pointer": hex32(name_pointer),
                            "name": name,
                            "flags": hex32(flags),
                            "table_pointer": hex32(table_pointer),
                            "body_size": str(body_size),
                            "base_offset": str(base_offset),
                            "entry_count": str(entry_count),
                            "body_pointer": hex32(body_pointer),
                            "issues": ";".join(row_issues),
                        }
                    )
                    node = next_node
                    order += 1
                except OSError as exc:
                    issues.append(f"archive_read_error:{hex32(node)}:{type(exc).__name__}:{exc}")
                    break
            if node in seen:
                issues.append("archive_list_cycle")
            if order >= max_archives:
                issues.append("archive_list_truncated")
    except OSError as exc:
        issues.append(f"proc_mem_error:{type(exc).__name__}:{exc}")
    except ValueError as exc:
        issues.append(f"invalid_linux_pid:{exc}")

    target_rows: list[dict[str, str]] = []
    for file_id in sorted(expected):
        expected_row = expected[file_id]
        matches = matches_by_id[file_id]
        first = matches[0] if matches else {}
        first_size = first.get("entry_size", "")
        if not first:
            first_status = "missing"
        elif first_size == expected_row["sidecar_size"]:
            first_status = "sidecar"
        elif first_size == expected_row["source_size"]:
            first_status = "base"
        else:
            first_status = "unknown_size"
        row_issues: list[str] = []
        if matches and not any(match.get("entry_size") == expected_row["source_size"] for match in matches):
            row_issues.append("base_match_missing")
        if matches and not any(match.get("entry_size") == expected_row["sidecar_size"] for match in matches):
            row_issues.append("sidecar_match_missing")
        target_rows.append(
            {
                "file_id": file_id,
                "expected_source_size": expected_row["source_size"],
                "expected_sidecar_size": expected_row["sidecar_size"],
                "first_status": first_status,
                "first_order": first.get("order", ""),
                "first_archive": first.get("archive", ""),
                "first_node": first.get("node", ""),
                "first_entry_offset": first.get("entry_offset", ""),
                "first_entry_size": first_size,
                "all_matches": "|".join(
                    f"{match['order']}:{match['archive']}:{match['entry_size']}" for match in matches
                ),
                "issues": ";".join(row_issues),
            }
        )
    return archive_rows, target_rows, issues


def run_attempt(args: argparse.Namespace) -> dict[str, str]:
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    info_proc_log = output / "info_proc.log"
    ps_log = output / "ps.txt"
    force_level_log = output / "force_level_write.log"
    game_stdout = output / "game.out"
    game_stderr = output / "game.err"
    xdotool_log = output / "xdotool.log"
    pilot_key_log = output / "pilot_keys.log"
    archives_path = output / "archives.tsv"
    targets_path = output / "targets.tsv"

    expected = load_expected(args.expected_ids)
    expected_ids = sorted(expected)
    issues: list[str] = []
    if not expected:
        issues.append("missing_expected_ids")

    wine = args.wine or shutil.which("wine") or ""
    winedbg = args.winedbg or shutil.which("winedbg") or ""
    xdotool = args.xdotool or shutil.which("xdotool") or ""
    if not wine:
        issues.append("missing_wine")
    if not winedbg:
        issues.append("missing_winedbg")
    if args.click and not xdotool:
        issues.append("missing_xdotool")
    if not args.runtime_executable.is_file():
        issues.append("missing_runtime_executable")

    env = os.environ.copy()
    env["WINEPREFIX"] = str(args.wineprefix.resolve())
    env["WINEDEBUG"] = args.winedebug
    if args.xdotool_library_path:
        env["LD_LIBRARY_PATH"] = (
            args.xdotool_library_path
            if not env.get("LD_LIBRARY_PATH")
            else f"{args.xdotool_library_path}:{env['LD_LIBRARY_PATH']}"
        )

    runtime_args = args.runtime_arg or ["-CD", r"D:\WESTWOOD\LOLG"]
    game_command = [
        wine or "wine",
        "explorer",
        f"/desktop={args.wine_desktop}",
        str(args.runtime_executable),
        *runtime_args,
    ]
    attach_pid = ""
    linux_pid = ""
    force_level_write_status = ""
    game_process: subprocess.Popen[str] | None = None

    if not any(issue.startswith("missing_") for issue in issues):
        try:
            with game_stdout.open("w", encoding="utf-8", errors="replace") as stdout_handle, game_stderr.open(
                "w", encoding="utf-8", errors="replace"
            ) as stderr_handle:
                game_process = subprocess.Popen(
                    game_command,
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                    text=True,
                    env=env,
                    cwd=args.cwd,
                )
            time.sleep(args.startup_wait)

            info_stdout, info_stderr, _info_returncode, _info_timeout = run_with_timeout(
                [winedbg or "winedbg", "--command", "info proc"],
                args.info_timeout,
                env,
                args.cwd,
            )
            info_proc_text = info_stdout + info_stderr
            info_proc_log.write_text(info_proc_text, encoding="utf-8", errors="replace")
            attach_pid = parse_lolg95_pid(info_proc_text, args.runtime_executable.name)

            ps_stdout, ps_stderr, _ps_returncode, _ps_timeout = run_with_timeout(
                ["ps", "-eo", "pid=,comm=,args="],
                8,
                env,
                args.cwd,
            )
            ps_text = ps_stdout + ps_stderr
            ps_log.write_text(ps_text, encoding="utf-8", errors="replace")
            linux_pid = parse_lolg95_linux_pid(ps_text, args.runtime_executable.name)
            if not linux_pid:
                issues.append("missing_lolg95_linux_process")

            if linux_pid and (args.force_level_index is not None or args.force_level_slot is not None):
                writes = []
                if args.force_level_index is not None:
                    writes.append((0x005B0948, args.force_level_index))
                if args.force_level_slot is not None:
                    writes.append((0x005B094C, args.force_level_slot))
                force_log_text, force_issues = write_process_dwords(linux_pid, writes)
                force_level_log.write_text(force_log_text, encoding="utf-8", errors="replace")
                if force_issues:
                    force_level_write_status = "failed"
                    issues.extend(force_issues)
                else:
                    force_level_write_status = "pass"

            if args.click and xdotool:
                click_command = [
                    xdotool,
                    "search",
                    "--name",
                    args.click_window_name,
                    "mousemove",
                    "--window",
                    "%@",
                    str(args.click_x),
                    str(args.click_y),
                    "click",
                    "1",
                ]
                click_results = []
                time.sleep(args.click_delay)
                for _index in range(args.click_count):
                    click_stdout, click_stderr, click_returncode, click_timeout = run_with_timeout(
                        click_command,
                        args.click_timeout,
                        env,
                        args.cwd,
                    )
                    click_results.append(
                        f"returncode={click_returncode if click_returncode is not None else 'timeout'} "
                        f"timeout={click_timeout}\n"
                        f"{click_stdout}{click_stderr}"
                    )
                    if args.click_interval:
                        time.sleep(args.click_interval)
                xdotool_log.write_text("\n--- click ---\n".join(click_results), encoding="utf-8")

            if args.pilot_key and xdotool:
                key_results = []
                for key_name in args.pilot_key:
                    if args.pilot_key_delay:
                        time.sleep(args.pilot_key_delay)
                    key_command = [
                        xdotool,
                        "search",
                        "--name",
                        args.click_window_name,
                        "key",
                        "--window",
                        "%@",
                        key_name,
                    ]
                    key_stdout, key_stderr, key_returncode, key_timeout = run_with_timeout(
                        key_command,
                        args.click_timeout,
                        env,
                        args.cwd,
                    )
                    key_results.append(
                        f"key={key_name} "
                        f"returncode={key_returncode if key_returncode is not None else 'timeout'} "
                        f"timeout={key_timeout}\n"
                        f"{key_stdout}{key_stderr}"
                    )
                pilot_key_log.write_text("\n--- key ---\n".join(key_results), encoding="utf-8")

            time.sleep(args.post_pilot_wait)
        finally:
            pass

    archive_rows: list[dict[str, str]] = []
    target_rows: list[dict[str, str]] = []
    if linux_pid:
        archive_rows, target_rows, scan_issues = scan_archive_list(linux_pid, expected, args.max_archives)
        issues.extend(scan_issues)
    else:
        issues.append("missing_runtime_memory_probe_pid")

    stop_process(game_process)

    write_csv(archives_path, ARCHIVE_FIELDS, archive_rows, delimiter="\t")
    write_csv(targets_path, TARGET_FIELDS, target_rows, delimiter="\t")

    sidecar_first = [row["file_id"] for row in target_rows if row["first_status"] == "sidecar"]
    base_first = [row["file_id"] for row in target_rows if row["first_status"] == "base"]
    missing = [row["file_id"] for row in target_rows if row["first_status"] == "missing"]
    unknown = [row["file_id"] for row in target_rows if row["first_status"] == "unknown_size"]
    incomplete_duplicate = [row["file_id"] for row in target_rows if row.get("issues")]

    if incomplete_duplicate:
        issues.append("incomplete_duplicate_order:" + ",".join(incomplete_duplicate))

    if incomplete_duplicate:
        status = "gap"
        next_step = "scan while both base and HD archives are loaded so duplicate-ID order is proven"
    elif len(sidecar_first) == len(expected_ids):
        status = "pass"
        next_step = "wire the proven sidecar-first archive order into the final runtime fallback path"
    elif base_first:
        status = "gap"
        next_step = "change sidecar insertion order so duplicate IDs are found before the base L20_BBI archive"
    elif missing:
        status = "gap"
        next_step = "wait longer or fix the sidecar mount because some expected IDs are not present in the live archive list"
    else:
        status = "gap"
        next_step = "inspect unknown target sizes and archive-list traversal before patching fallback"

    summary = {
        "status": status,
        "expected_ids": str(len(expected_ids)),
        "runtime_executable": str(args.runtime_executable),
        "runtime_args": shlex.join(runtime_args),
        "wineprefix": str(args.wineprefix),
        "wine_desktop": args.wine_desktop,
        "startup_wait_seconds": str(args.startup_wait),
        "post_pilot_wait_seconds": str(args.post_pilot_wait),
        "attach_pid": attach_pid,
        "linux_pid": linux_pid,
        "force_level_index": "" if args.force_level_index is None else str(args.force_level_index),
        "force_level_slot": "" if args.force_level_slot is None else str(args.force_level_slot),
        "force_level_write_status": force_level_write_status,
        "force_level_write_log": str(force_level_log) if force_level_write_status else "",
        "command": shlex.join(game_command),
        "info_proc_log": str(info_proc_log),
        "ps_log": str(ps_log),
        "archives": str(archives_path),
        "targets": str(targets_path),
        "archive_nodes": str(len(archive_rows)),
        "archive_names": ",".join(row["name"] for row in archive_rows if row.get("name")),
        "target_sidecar_first": ",".join(sidecar_first),
        "target_base_first": ",".join(base_first),
        "target_missing": ",".join(missing),
        "target_unknown_first": ",".join(unknown),
        "issues": ";".join(dict.fromkeys(issues)),
        "next_step": next_step,
    }
    write_csv(output / "summary.csv", SUMMARY_FIELDS, [summary])
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe the live LOLG95 runtime archive list.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--expected-ids", type=Path, default=DEFAULT_EXPECTED_IDS)
    parser.add_argument("--runtime-executable", type=Path, default=Path("LOLG95.EXE"))
    parser.add_argument("--runtime-arg", action="append", default=[])
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("--wineprefix", type=Path, required=True)
    parser.add_argument("--wine", default="")
    parser.add_argument("--winedbg", default="")
    parser.add_argument("--winedebug", default="-all")
    parser.add_argument("--wine-desktop", default="LOLG,1280x1024")
    parser.add_argument("--startup-wait", type=int, default=35)
    parser.add_argument("--post-pilot-wait", type=int, default=45)
    parser.add_argument("--info-timeout", type=int, default=12)
    parser.add_argument("--xdotool", default="/tmp/xdotool-local/usr/bin/xdotool")
    parser.add_argument("--xdotool-library-path", default="/tmp/xdotool-local/usr/lib/x86_64-linux-gnu")
    parser.add_argument("--click", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--click-window-name", default="Lands Of Lore Guardians")
    parser.add_argument("--click-x", type=int, default=95)
    parser.add_argument("--click-y", type=int, default=116)
    parser.add_argument("--click-delay", type=int, default=6)
    parser.add_argument("--click-timeout", type=int, default=8)
    parser.add_argument("--click-count", type=int, default=2)
    parser.add_argument("--click-interval", type=float, default=2.0)
    parser.add_argument("--pilot-key", action="append", default=[])
    parser.add_argument("--pilot-key-delay", type=float, default=8.0)
    parser.add_argument("--force-level-index", type=lambda value: int(value, 0))
    parser.add_argument("--force-level-slot", type=lambda value: int(value, 0))
    parser.add_argument("--max-archives", type=int, default=128)
    args = parser.parse_args()

    summary = run_attempt(args)
    print(f"LOLG95 archive-list probe: {summary['status']}")
    print(f"Summary: {args.output / 'summary.csv'}")
    print(f"Archive nodes: {summary['archive_nodes']}")
    print(f"Sidecar-first IDs: {summary['target_sidecar_first'] or '-'}")
    print(f"Base-first IDs: {summary['target_base_first'] or '-'}")
    print(f"Missing IDs: {summary['target_missing'] or '-'}")


if __name__ == "__main__":
    main()
