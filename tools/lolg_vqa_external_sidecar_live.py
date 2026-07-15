#!/usr/bin/env python3
"""Run the external VQA sidecar bridge, optional web viewer, and optional game."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_RUNTIME_DIR = BASE_DIR / "output/vqa_external_sidecar_runtime"
DEFAULT_CACHE_ROOT = BASE_DIR / "output/vqa_external_sidecar_cache"
DEFAULT_INDEX_DIR = BASE_DIR / "output/vqa_external_sidecar_index"
DEFAULT_MANIFEST = DEFAULT_INDEX_DIR / "manifest.json"
INDEX_TOOL = BASE_DIR / "tools/lolg_vqa_external_sidecar_index.py"
BRIDGE_TOOL = BASE_DIR / "tools/lolg_vqa_external_sidecar_trace_bridge.py"
STRACE_BRIDGE_TOOL = BASE_DIR / "tools/lolg_vqa_external_sidecar_strace_bridge.py"
WEB_TOOL = BASE_DIR / "tools/lolg_vqa_external_sidecar_web.py"


@dataclass
class ManagedProcess:
    name: str
    command: list[str]
    log_path: Path
    process: subprocess.Popen[str] | None = None


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def ensure_manifest(args: argparse.Namespace) -> None:
    if args.manifest.is_file() and not args.rebuild_index:
        return
    command = [sys.executable, str(INDEX_TOOL), "--hd-root", "mod_mix_vqa_fullhd", "--output", str(args.index_dir)]
    if args.dry_run:
        print(" ".join(command))
        return
    subprocess.run(command, cwd=BASE_DIR, check=True)


def open_log(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open("a", encoding="utf-8")


def start_process(item: ManagedProcess, dry_run: bool) -> None:
    print(f"{item.name}: {' '.join(item.command)}")
    print(f"{item.name} log: {item.log_path}")
    if dry_run:
        return
    handle = open_log(item.log_path)
    item.process = subprocess.Popen(
        item.command,
        cwd=BASE_DIR,
        stdout=handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    # Keep the handle owned by Popen's fd; closing our Python wrapper is fine.
    handle.close()


def stop_process(item: ManagedProcess) -> None:
    process = item.process
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def open_player(args: argparse.Namespace, player_url: str) -> None:
    if not args.open_player:
        return
    if args.no_web:
        print("Avertissement: --open-player ignore car --no-web est actif.")
        return
    if args.open_player_delay > 0:
        time.sleep(args.open_player_delay)
    command = [args.browser_command, player_url]
    print(f"Ouverture player VQA HD: {' '.join(command)}")
    try:
        subprocess.Popen(command, cwd=BASE_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print(f"Avertissement: commande navigateur introuvable: {args.browser_command}", file=sys.stderr)


def result_mtime(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except FileNotFoundError:
        return 0


def read_result(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def wait_for_result(path: Path, previous_mtime: int, timeout: float) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    latest: dict[str, object] = {}
    while time.monotonic() < deadline:
        if result_mtime(path) > previous_mtime:
            payload = read_result(path)
            if payload:
                latest = payload
                previous_mtime = result_mtime(path)
                if payload.get("status") != "decoding":
                    return payload
        time.sleep(0.2)
    return latest


def prepare_runtime_files(args: argparse.Namespace) -> None:
    args.trace_file.parent.mkdir(parents=True, exist_ok=True)
    args.trace_file.write_text("", encoding="utf-8")
    args.event_log.parent.mkdir(parents=True, exist_ok=True)
    args.event_log.write_text("", encoding="utf-8")
    args.latest_event_file.unlink(missing_ok=True)
    if not args.keep_last_result:
        args.result_file.unlink(missing_ok=True)
    if args.trace_source == "strace":
        args.strace_log.parent.mkdir(parents=True, exist_ok=True)
        args.strace_log.write_text("", encoding="utf-8")


def write_smoke_trace(args: argparse.Namespace) -> None:
    args.trace_file.parent.mkdir(parents=True, exist_ok=True)
    with args.trace_file.open("a", encoding="utf-8") as handle:
        handle.write(args.smoke_line.rstrip() + "\n")
    print(f"Trace smoke ajoutee: {args.smoke_line}")


def write_smoke_strace(args: argparse.Namespace) -> None:
    args.strace_log.parent.mkdir(parents=True, exist_ok=True)
    sample_path = BASE_DIR / "C/LOLG/HERB.MIX"
    lines = [
        f'12345 openat(AT_FDCWD, "{sample_path}", O_RDONLY) = 3',
        "12345 lseek(3, 18021916, SEEK_SET) = 18021916",
        '12345 read(3, "FORM", 4096) = 4096',
    ]
    with args.strace_log.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    print(f"Trace strace smoke ajoutee: {args.strace_log}")


def build_processes(args: argparse.Namespace) -> list[ManagedProcess]:
    log_dir = args.runtime_dir / "logs"
    processes: list[ManagedProcess] = []
    if args.trace_source == "strace":
        strace_bridge_command = [
            sys.executable,
            str(STRACE_BRIDGE_TOOL),
            "--input",
            str(args.strace_log),
            "--output",
            str(args.trace_file),
            "--summary",
            str(args.runtime_dir / "strace_bridge_summary.json"),
            "--watch",
            "--truncate-output",
            "--poll",
            str(args.poll),
        ]
        if args.strace_all_reads:
            strace_bridge_command.append("--all-reads")
        if args.strace_dedupe:
            strace_bridge_command.append("--dedupe")
        processes.append(ManagedProcess("strace-bridge", strace_bridge_command, log_dir / "strace_bridge.log"))

    bridge_command = [
        sys.executable,
        str(BRIDGE_TOOL),
        "--manifest",
        str(args.manifest),
        "--cache-root",
        str(args.cache_root),
        "--runtime-dir",
        str(args.runtime_dir),
        "--trace-file",
        str(args.trace_file),
        "--request-file",
        str(args.request_file),
        "--result-file",
        str(args.result_file),
        "--event-log",
        str(args.event_log),
        "--latest-event-file",
        str(args.latest_event_file),
        "--max-frames",
        str(args.max_frames),
        "--watch",
        "--process",
        "--poll",
        str(args.poll),
    ]
    if args.trace_dedupe_key:
        bridge_command.append("--dedupe-key")
    processes.append(ManagedProcess("bridge", bridge_command, log_dir / "bridge.log"))

    if not args.no_web:
        web_command = [
            sys.executable,
            str(WEB_TOOL),
            "--manifest",
            str(args.manifest),
            "--cache-root",
            str(args.cache_root),
            "--runtime-dir",
            str(args.runtime_dir),
            "--request-file",
            str(args.request_file),
            "--result-file",
            str(args.result_file),
            "--event-log",
            str(args.event_log),
            "--latest-event-file",
            str(args.latest_event_file),
            "--host",
            args.web_host,
            "--port",
            str(args.web_port),
            "--process-requests",
        ]
        processes.append(ManagedProcess("web", web_command, log_dir / "web.log"))

    if not args.no_game:
        game_args = args.game_args
        if game_args and game_args[0] == "--":
            game_args = game_args[1:]
        game_command = [str(BASE_DIR / "LOLG_HD.sh"), "wine-external-sidecar", *game_args]
        if args.trace_source == "strace":
            game_command = [
                args.strace_bin,
                "-f",
                "-ttt",
                "-s",
                "260",
                "-e",
                "trace=open,openat,openat2,close,lseek,_llseek,read,pread64",
                "-o",
                str(args.strace_log),
                *game_command,
            ]
        processes.append(ManagedProcess("game", game_command, log_dir / "game.log"))

    return processes


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the external VQA sidecar live harness.")
    parser.add_argument("--runtime-dir", type=Path, default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--index-dir", type=Path, default=DEFAULT_INDEX_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--trace-file", type=Path)
    parser.add_argument("--trace-source", choices=("manual", "strace"), default="manual")
    parser.add_argument("--strace-log", type=Path)
    parser.add_argument("--strace-bin", default="strace")
    parser.add_argument("--strace-all-reads", action="store_true", help="Emit every MIX read from strace instead of only FORM-starting reads.")
    parser.add_argument("--strace-dedupe", action="store_true", help="Deduplicate strace trace hints by archive/offset/syscall.")
    parser.add_argument("--trace-dedupe-key", action="store_true", help="Decode at most once per ARCHIVE:FILE_ID in one live session.")
    parser.add_argument("--request-file", type=Path)
    parser.add_argument("--result-file", type=Path)
    parser.add_argument("--event-log", type=Path)
    parser.add_argument("--latest-event-file", type=Path)
    parser.add_argument("--web-host", default="127.0.0.1")
    parser.add_argument("--web-port", type=int, default=8765)
    parser.add_argument("--open-player", action="store_true", help="Open the browser player after the web sidecar starts.")
    parser.add_argument("--player-hud", action="store_true", help="Open the player with a compact diagnostic HUD.")
    parser.add_argument("--browser-command", default="xdg-open")
    parser.add_argument("--open-player-delay", type=float, default=1.0)
    parser.add_argument("--max-frames", type=int, default=16, help="Frame limit for live decode; 0 means all frames.")
    parser.add_argument("--poll", type=float, default=0.5)
    parser.add_argument("--timeout", type=float, default=0, help="Stop after N seconds. 0 means wait for the game or Ctrl+C.")
    parser.add_argument("--keep-last-result", action="store_true", help="Keep the previous result.json when starting a new live session.")
    parser.add_argument("--no-web", action="store_true")
    parser.add_argument("--no-game", action="store_true")
    parser.add_argument("--smoke", action="store_true", help="Append a sample trace line and wait for the sidecar result.")
    parser.add_argument("--smoke-line", default="archive=HERB.MIX index=46")
    parser.add_argument("--smoke-timeout", type=float, default=10)
    parser.add_argument("--rebuild-index", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("game_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    args.runtime_dir.mkdir(parents=True, exist_ok=True)
    args.trace_file = args.trace_file or args.runtime_dir / "trace.log"
    args.strace_log = args.strace_log or args.runtime_dir / "strace.log"
    args.request_file = args.request_file or args.runtime_dir / "request.json"
    args.result_file = args.result_file or args.runtime_dir / "result.json"
    args.event_log = args.event_log or args.runtime_dir / "events.jsonl"
    args.latest_event_file = args.latest_event_file or args.runtime_dir / "latest_event.json"

    ensure_manifest(args)
    if not args.dry_run:
        prepare_runtime_files(args)
    processes = build_processes(args)
    engine_mode = os.environ.get("LOLG_HD_EXTERNAL_SIDECAR_ENGINE", "wine-dgvoodoo-win10-safevqa")
    player_path = f"http://{args.web_host}:{args.web_port}/?mode=player"
    if args.player_hud:
        player_path += "&hud=1"

    status = {
        "status": "starting",
        "engine_mode": engine_mode,
        "vqa_mode": "external_sidecar_player",
        "mode_note": "HD VQA are decoded outside the game engine; the Wine game keeps the stable safevqa runtime.",
        "trace_source": args.trace_source,
        "strace_all_reads": args.strace_all_reads,
        "strace_dedupe": args.strace_dedupe,
        "trace_dedupe_key": args.trace_dedupe_key,
        "keep_last_result": args.keep_last_result,
        "runtime_dir": str(args.runtime_dir),
        "trace_file": str(args.trace_file),
        "strace_log": str(args.strace_log),
        "request_file": str(args.request_file),
        "result_file": str(args.result_file),
        "event_log": str(args.event_log),
        "latest_event_file": str(args.latest_event_file),
        "web_url": "" if args.no_web else f"http://{args.web_host}:{args.web_port}/",
        "player_url": "" if args.no_web else player_path,
        "open_player": args.open_player,
        "player_hud": args.player_hud,
        "browser_command": args.browser_command,
        "processes": [{"name": item.name, "log": str(item.log_path), "command": item.command} for item in processes],
    }
    write_json(args.runtime_dir / "live_status.json", status)

    print(f"Mode moteur: {engine_mode} stable.")
    print("Mode VQA HD: sidecar externe synchronise; sortie HD dans le player web.")
    print(f"Trace runtime sidecar: {args.trace_file}")
    if args.trace_source == "strace":
        print(f"Trace strace Wine: {args.strace_log}")
        if args.strace_all_reads:
            print("Capture strace: toutes lectures MIX")
        if args.strace_dedupe:
            print("Capture strace: dedupe archive/offset/syscall")
        if args.trace_dedupe_key:
            print("Bridge trace: dedupe par cle VQA")
    print(f"Requete sidecar: {args.request_file}")
    print(f"Resultat sidecar: {args.result_file}")
    print(f"Evenements sidecar: {args.event_log}")
    if not args.no_web:
        print(f"Lecteur web: http://{args.web_host}:{args.web_port}/")
        print(f"Player VQA HD: {player_path}")
    if args.open_player:
        print(f"Ouverture player demandee: {args.browser_command}")

    previous_mtime = result_mtime(args.result_file)
    try:
        for item in processes:
            start_process(item, args.dry_run)
        if args.dry_run:
            return

        status["status"] = "running"
        status["processes"] = [
            {
                "name": item.name,
                "pid": item.process.pid if item.process else None,
                "log": str(item.log_path),
                "command": item.command,
            }
            for item in processes
        ]
        write_json(args.runtime_dir / "live_status.json", status)
        open_player(args, status["player_url"])

        if args.smoke:
            time.sleep(max(0.2, args.poll))
            if args.trace_source == "strace":
                write_smoke_strace(args)
            else:
                write_smoke_trace(args)
            payload = wait_for_result(args.result_file, previous_mtime, args.smoke_timeout)
            if not payload:
                raise SystemExit(f"Smoke sidecar sans resultat apres {args.smoke_timeout:g}s")
            print(json.dumps({"status": payload.get("status"), "key": payload.get("key"), "decode_dir": payload.get("decode_dir")}, ensure_ascii=True, indent=2))
            if args.no_game:
                return

        deadline = time.monotonic() + args.timeout if args.timeout > 0 else None
        game = next((item for item in processes if item.name == "game"), None)
        while True:
            if game and game.process and game.process.poll() is not None:
                raise SystemExit(game.process.returncode or 0)
            if deadline and time.monotonic() >= deadline:
                return
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Arret sidecar live.")
    finally:
        for item in reversed(processes):
            stop_process(item)
        final_status = read_result(args.result_file)
        write_json(
            args.runtime_dir / "live_status.json",
            {
                **status,
                "status": "stopped",
                "last_result": final_status,
            },
        )


if __name__ == "__main__":
    main()
