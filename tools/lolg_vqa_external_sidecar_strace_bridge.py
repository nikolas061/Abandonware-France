#!/usr/bin/env python3
"""Convert strace file I/O logs into external sidecar trace hints."""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_DIR = BASE_DIR / "output/vqa_external_sidecar_runtime"
DEFAULT_INPUT = DEFAULT_RUNTIME_DIR / "strace.log"
DEFAULT_OUTPUT = DEFAULT_RUNTIME_DIR / "trace.log"
DEFAULT_SUMMARY = DEFAULT_RUNTIME_DIR / "strace_bridge_summary.json"
DEFAULT_ORIGINAL_ROOT = BASE_DIR / "C/LOLG"
DEFAULT_HD_ROOT = BASE_DIR / "mod_mix_vqa_fullhd"

PID_RE = re.compile(r"^\s*(?:(\d+)\s+)?(.+)$")
TIMESTAMP_RE = re.compile(r"^\d+\.\d+\s+(.+)$")
UNFINISHED_RE = re.compile(r"^(.*?)<unfinished \.\.\.>$")
RESUMED_RE = re.compile(r"^<\.\.\. ([A-Za-z0-9_]+) resumed>(.*)$")
OPEN_RE = re.compile(r"\bopen(?:at|at2)?\(")
FD_RESULT_RE = re.compile(r"\)\s+=\s+(\d+)(?:\s|$)")
QUOTED_RE = re.compile(r'"((?:\\.|[^"\\])*)"')
LSEEK_RE = re.compile(r"\blseek\((\d+),\s*(-?\d+),\s*SEEK_(SET|CUR|END)\)\s+=\s+(-?\d+)")
LLSEEK_RE = re.compile(r"\b_llseek\((\d+),\s*(\d+),\s*(\d+),\s*\[(-?\d+)\],\s*SEEK_(SET|CUR|END)\)\s+=\s+(-?\d+)")
LLSEEK_SHORT_RE = re.compile(r"\b_llseek\((\d+),\s*(-?\d+),\s*\[(-?\d+)\],\s*SEEK_(SET|CUR|END)\)\s+=\s+(-?\d+)")
READ_RE = re.compile(r"\bread\((\d+),.*,\s*(\d+)\)\s+=\s+(-?\d+)")
PREAD_RE = re.compile(r"\bpread64\((\d+),.*,\s*(\d+),\s*(-?\d+)\)\s+=\s+(-?\d+)")
READ_DETAIL_RE = re.compile(r'\bread\((\d+),\s*"((?:\\.|[^"\\])*)"(?:\.\.\.)?,\s*(\d+)\)\s+=\s+(-?\d+)')
PREAD_DETAIL_RE = re.compile(r'\bpread64\((\d+),\s*"((?:\\.|[^"\\])*)"(?:\.\.\.)?,\s*(\d+),\s*(-?\d+)\)\s+=\s+(-?\d+)')
CLOSE_RE = re.compile(r"\bclose\((\d+)\)\s+=\s+0")


@dataclass
class FileState:
    path: str
    realpath: str
    layout: str
    offset: int | None = None


def decode_quoted(value: str) -> str:
    return bytes(value, "utf-8").decode("unicode_escape", errors="replace")


def archive_name(path: str) -> str:
    return Path(path.replace("\\", "/")).name.upper()


def is_mix_path(path: str) -> bool:
    return archive_name(path).endswith(".MIX")


def quoted_starts_form(value: str | None) -> bool:
    if value is None:
        return False
    return decode_quoted(value).startswith("FORM")


def path_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def resolve_layout(path: str) -> tuple[str, str]:
    raw = Path(path)
    try:
        real = raw.resolve(strict=True)
    except (OSError, RuntimeError):
        real = raw.resolve(strict=False)

    original_root = DEFAULT_ORIGINAL_ROOT.resolve(strict=False)
    hd_root = DEFAULT_HD_ROOT.resolve(strict=False)
    if path_under(real, original_root):
        return "original", str(real)
    if path_under(real, hd_root):
        return "hd", str(real)

    normalized = str(real).replace("\\", "/")
    if "/C/LOLG/" in normalized:
        return "original", str(real)
    if "/mod_mix_vqa_fullhd/" in normalized:
        return "hd", str(real)
    return "unknown", str(real)


def parse_line_prefix(line: str) -> tuple[str, str]:
    match = PID_RE.match(line)
    if not match:
        return "0", line
    pid, payload = match.groups()
    return pid or "0", payload


def strip_timestamp(payload: str) -> str:
    match = TIMESTAMP_RE.match(payload)
    return match.group(1) if match else payload


def first_path(payload: str) -> str:
    for quoted in QUOTED_RE.findall(payload):
        path = decode_quoted(quoted)
        if is_mix_path(path):
            return path
    return ""


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


class StraceBridge:
    def __init__(self, output: Path, summary: Path, all_reads: bool = False, dedupe: bool = False) -> None:
        self.output = output
        self.summary = summary
        self.all_reads = all_reads
        self.dedupe = dedupe
        self.by_pid_fd: dict[tuple[str, int], FileState] = {}
        self.by_fd: dict[int, FileState] = {}
        self.last_mix_by_pid: dict[str, FileState] = {}
        self.last_mix: FileState | None = None
        self.pending_by_pid: dict[str, tuple[str, str]] = {}
        self.emitted: set[tuple[str, int, str]] = set()
        self.lines = 0
        self.open_hits = 0
        self.read_hits = 0
        self.emitted_hits = 0

    def state_for(self, pid: str, fd: int) -> FileState | None:
        return self.by_pid_fd.get((pid, fd)) or self.by_fd.get(fd)

    def fallback_state_for(self, pid: str, fd: int) -> FileState | None:
        template = self.last_mix_by_pid.get(pid) or self.last_mix
        if template is None:
            return None
        state = FileState(path=template.path, realpath=template.realpath, layout=template.layout, offset=template.offset)
        self.by_pid_fd[(pid, fd)] = state
        self.by_fd[fd] = state
        return state

    def register_open(self, pid: str, payload: str) -> bool:
        if not OPEN_RE.search(payload):
            return False
        path = first_path(payload)
        if not path:
            return False
        fd_match = FD_RESULT_RE.search(payload)
        if not fd_match:
            return False
        fd = int(fd_match.group(1))
        layout, realpath = resolve_layout(path)
        state = FileState(path=path, realpath=realpath, layout=layout, offset=0)
        self.by_pid_fd[(pid, fd)] = state
        self.by_fd[fd] = state
        self.last_mix_by_pid[pid] = state
        self.last_mix = state
        self.open_hits += 1
        return True

    def register_close(self, pid: str, payload: str) -> bool:
        match = CLOSE_RE.search(payload)
        if not match:
            return False
        fd = int(match.group(1))
        self.by_pid_fd.pop((pid, fd), None)
        self.by_fd.pop(fd, None)
        return True

    def register_lseek(self, pid: str, payload: str) -> bool:
        match = LSEEK_RE.search(payload)
        if match:
            fd = int(match.group(1))
            result = int(match.group(4))
            state = self.state_for(pid, fd) or self.fallback_state_for(pid, fd)
            if state and result >= 0:
                state.offset = result
            return bool(state)
        llmatch = LLSEEK_RE.search(payload)
        if llmatch:
            fd = int(llmatch.group(1))
            result_code = int(llmatch.group(6))
            result_offset = int(llmatch.group(4))
            state = self.state_for(pid, fd) or self.fallback_state_for(pid, fd)
            if state and result_code == 0:
                state.offset = result_offset
            return bool(state)
        short_llmatch = LLSEEK_SHORT_RE.search(payload)
        if short_llmatch:
            fd = int(short_llmatch.group(1))
            result_code = int(short_llmatch.group(5))
            result_offset = int(short_llmatch.group(3))
            state = self.state_for(pid, fd) or self.fallback_state_for(pid, fd)
            if state and result_code == 0:
                state.offset = result_offset
            return bool(state)
        return False

    def emit(self, pid: str, fd: int, state: FileState, offset: int, syscall: str, byte_count: int) -> None:
        key = (archive_name(state.path), offset, syscall)
        if self.dedupe and key in self.emitted:
            return
        self.emitted.add(key)
        self.output.parent.mkdir(parents=True, exist_ok=True)
        with self.output.open("a", encoding="utf-8") as handle:
            handle.write(
                f"path={state.path} realpath={state.realpath} layout={state.layout} "
                f"offset={offset} source=strace syscall={syscall} bytes={byte_count} pid={pid} fd={fd}\n"
            )
        self.emitted_hits += 1

    def register_read(self, pid: str, payload: str) -> bool:
        pread_detail = PREAD_DETAIL_RE.search(payload)
        pread = pread_detail or PREAD_RE.search(payload)
        if pread:
            fd = int(pread.group(1))
            if pread_detail:
                buffer = pread_detail.group(2)
                offset = int(pread_detail.group(4))
                result = int(pread_detail.group(5))
            else:
                buffer = None
                offset = int(pread.group(3))
                result = int(pread.group(4))
            state = self.state_for(pid, fd) or (self.fallback_state_for(pid, fd) if self.all_reads or quoted_starts_form(buffer) else None)
            if state and result > 0:
                if self.all_reads or quoted_starts_form(buffer):
                    self.emit(pid, fd, state, offset, "pread64", result)
                self.read_hits += 1
            return bool(state)

        read_detail = READ_DETAIL_RE.search(payload)
        read = read_detail or READ_RE.search(payload)
        if not read:
            return False
        fd = int(read.group(1))
        if read_detail:
            buffer = read_detail.group(2)
            result = int(read_detail.group(4))
        else:
            buffer = None
            result = int(read.group(3))
        starts_form = quoted_starts_form(buffer)
        state = self.state_for(pid, fd) or (self.fallback_state_for(pid, fd) if self.all_reads or starts_form else None)
        if not state:
            return False
        offset = state.offset
        if result > 0 and offset is not None:
            if self.all_reads or starts_form:
                self.emit(pid, fd, state, offset, "read", result)
            state.offset = offset + result
            self.read_hits += 1
        return True

    def process_line(self, line: str) -> None:
        self.lines += 1
        pid, payload = parse_line_prefix(line)
        payload = strip_timestamp(payload)

        unfinished = UNFINISHED_RE.match(payload)
        if unfinished:
            syscall_match = re.search(r"\b([A-Za-z0-9_]+)\(", unfinished.group(1))
            if syscall_match:
                self.pending_by_pid[pid] = (syscall_match.group(1), unfinished.group(1))
            return

        resumed = RESUMED_RE.match(payload)
        if resumed:
            syscall, suffix = resumed.groups()
            pending = self.pending_by_pid.pop(pid, None)
            if not pending or pending[0] != syscall:
                return
            payload = pending[1] + suffix

        if "<unfinished ...>" in payload or " resumed>" in payload:
            return
        if self.register_open(pid, payload):
            return
        if self.register_close(pid, payload):
            return
        if self.register_lseek(pid, payload):
            return
        self.register_read(pid, payload)

    def write_summary(self) -> None:
        write_json(
            self.summary,
            {
                "status": "pass",
                "lines": self.lines,
                "open_mix_hits": self.open_hits,
                "read_mix_hits": self.read_hits,
                "emitted_trace_lines": self.emitted_hits,
                "all_reads": self.all_reads,
                "dedupe": self.dedupe,
                "output": str(self.output),
            },
        )


def process_once(path: Path, bridge: StraceBridge) -> None:
    if not path.is_file():
        return
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            bridge.process_line(line.rstrip("\n"))
    bridge.write_summary()


def watch(path: Path, bridge: StraceBridge, poll: float) -> None:
    offset = 0
    buffer = ""
    print(f"Bridge strace sidecar actif: {path}")
    print(f"Trace sidecar: {bridge.output}")
    while True:
        if not path.is_file():
            time.sleep(poll)
            continue
        with path.open(encoding="utf-8", errors="replace") as handle:
            handle.seek(offset)
            chunk = handle.read()
            offset = handle.tell()
        if chunk:
            buffer += chunk
            lines = buffer.splitlines(keepends=True)
            buffer = ""
            if lines and not lines[-1].endswith(("\n", "\r")):
                buffer = lines.pop()
            for line in lines:
                bridge.process_line(line.rstrip("\r\n"))
            bridge.write_summary()
        time.sleep(poll)


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert strace MIX reads into sidecar trace hints.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--poll", type=float, default=0.25)
    parser.add_argument("--truncate-output", action="store_true")
    parser.add_argument("--all-reads", action="store_true", help="Emit every MIX read instead of only reads whose buffer starts with FORM.")
    parser.add_argument("--dedupe", action="store_true", help="Suppress duplicate archive/offset/syscall trace hints.")
    args = parser.parse_args()

    if args.truncate_output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text("", encoding="utf-8")

    bridge = StraceBridge(args.output, args.summary, all_reads=args.all_reads, dedupe=args.dedupe)
    if args.watch:
        watch(args.input, bridge, args.poll)
    else:
        process_once(args.input, bridge)


if __name__ == "__main__":
    main()
