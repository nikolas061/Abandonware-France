#!/usr/bin/env python3
"""Watch a sidecar request file and process HD VQA cache/decode requests."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
REQUEST_TOOL = BASE_DIR / "tools/lolg_vqa_external_sidecar_request.py"
DEFAULT_MANIFEST = BASE_DIR / "output/vqa_external_sidecar_index/manifest.json"
DEFAULT_CACHE_ROOT = BASE_DIR / "output/vqa_external_sidecar_cache"
DEFAULT_RUNTIME_DIR = BASE_DIR / "output/vqa_external_sidecar_runtime"


def write_example(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "key": "HERB.MIX:98e2ff4f",
        "action": "decode",
        "max_frames": 2,
        "fullhd": True,
        "fit": "stretch",
        "filter": "nearest",
        "fast_png": True,
    }
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def signature(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    return stat.st_mtime_ns, stat.st_size


def run_request(args: argparse.Namespace) -> int:
    command = [
        sys.executable,
        str(REQUEST_TOOL),
        "--manifest",
        str(args.manifest),
        "--cache-root",
        str(args.cache_root),
        "--request-file",
        str(args.request_file),
        "--result-file",
        str(args.result_file),
    ]
    if args.variant:
        command.extend(["--variant", args.variant])
    completed = subprocess.run(command, cwd=BASE_DIR, text=True, capture_output=True, check=False)
    event = {
        "status": "ok" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "request_file": str(args.request_file),
        "result_file": str(args.result_file),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    args.event_file.parent.mkdir(parents=True, exist_ok=True)
    args.event_file.write_text(json.dumps(event, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    return completed.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch output/vqa_external_sidecar_runtime/request.json and process VQA sidecar requests.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--runtime-dir", type=Path, default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--request-file", type=Path)
    parser.add_argument("--result-file", type=Path)
    parser.add_argument("--event-file", type=Path)
    parser.add_argument("--variant")
    parser.add_argument("--poll", type=float, default=0.5)
    parser.add_argument("--once", action="store_true", help="Process the current request and exit.")
    parser.add_argument("--write-example", action="store_true", help="Write a small example request and exit.")
    args = parser.parse_args()

    args.request_file = args.request_file or args.runtime_dir / "request.json"
    args.result_file = args.result_file or args.runtime_dir / "result.json"
    args.event_file = args.event_file or args.runtime_dir / "last_event.json"

    if args.write_example:
        write_example(args.request_file)
        print(f"Exemple de requete sidecar ecrit: {args.request_file}")
        return

    if args.once:
        if not args.request_file.is_file():
            raise SystemExit(f"Requete sidecar introuvable: {args.request_file}")
        raise SystemExit(run_request(args))

    args.runtime_dir.mkdir(parents=True, exist_ok=True)
    print(f"Sidecar watcher actif: {args.request_file}")
    print("Ctrl+C pour arreter.")
    last_signature = None
    while True:
        current_signature = signature(args.request_file)
        if current_signature is not None and current_signature != last_signature:
            last_signature = current_signature
            run_request(args)
        time.sleep(args.poll)


if __name__ == "__main__":
    main()
