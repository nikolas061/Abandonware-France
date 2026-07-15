#!/usr/bin/env python3
"""Summarize the current external VQA sidecar state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = BASE_DIR / "output/vqa_external_sidecar_index/manifest.json"
DEFAULT_RUNTIME_DIR = BASE_DIR / "output/vqa_external_sidecar_runtime"
DEFAULT_CACHE_ROOT = BASE_DIR / "output/vqa_external_sidecar_cache"
DEFAULT_EVENT_LOG = DEFAULT_RUNTIME_DIR / "events.jsonl"
CRITICAL_VQA_KEYS = [
    ("LOCALLNG.MIX", "fca4e133", "LOCALLNG"),
    ("MOVIES.MIX", "4d6efa8e", "MOVIES"),
]


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {"status": "invalid_json", "path": str(path)}
    return payload if isinstance(payload, dict) else {}


def read_events(path: Path, limit: int = 0) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows[-limit:] if limit > 0 else rows


def resolve_project_path(path_text: str) -> Path:
    path = Path(path_text)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path


def count_ready_frames_from_dir(decode_dir: str) -> int:
    if not decode_dir:
        return 0
    frames_dir = resolve_project_path(decode_dir) / "frames_fullhd"
    if not frames_dir.is_dir():
        return 0
    return len(sorted(frames_dir.glob("*.png")))


def count_ready_frames(result: dict[str, Any]) -> int:
    decode_dir = result.get("decode_dir")
    return count_ready_frames_from_dir(decode_dir) if isinstance(decode_dir, str) else 0


def critical_result_status(cache_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for archive, file_id, label in CRITICAL_VQA_KEYS:
        result_path = cache_root / archive / file_id / "result.json"
        result = read_json(result_path)
        rows.append(
            {
                "label": label,
                "key": f"{archive}:{file_id}",
                "result_file": str(result_path),
                "status": result.get("status", "missing"),
                "width": result.get("width", ""),
                "height": result.get("height", ""),
                "frames": result.get("frames", ""),
                "ready_frames": count_ready_frames(result),
                "decode_dir": result.get("decode_dir", ""),
            }
        )
    return rows


def critical_ready(rows: list[dict[str, Any]]) -> bool:
    return all(
        row.get("status") == "decoded"
        and str(row.get("width", "")) == "1920"
        and str(row.get("height", "")) == "1080"
        and int(row.get("ready_frames") or 0) > 0
        for row in rows
    )


def summarize_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    decoded_keys: list[str] = []
    unique_decoded_keys: list[str] = []
    recent: list[dict[str, Any]] = []
    for event in events:
        status = str(event.get("status", "unknown"))
        key = str(event.get("key", ""))
        status_counts[status] = status_counts.get(status, 0) + 1
        if status == "decoded" and key:
            decoded_keys.append(key)
            if key not in unique_decoded_keys:
                unique_decoded_keys.append(key)
        recent.append(
            {
                "status": status,
                "key": key,
                "source": event.get("source", ""),
                "method": event.get("method", ""),
                "ready_frames": count_ready_frames_from_dir(str(event.get("decode_dir", ""))),
            }
        )
    return {
        "events": len(events),
        "status_counts": status_counts,
        "decoded_events": len(decoded_keys),
        "unique_decoded_keys": len(unique_decoded_keys),
        "decoded_keys": unique_decoded_keys,
        "recent": recent,
    }


def build_status(args: argparse.Namespace) -> dict[str, Any]:
    runtime_dir = args.runtime_dir
    manifest = read_json(args.manifest)
    result = read_json(args.result_file or runtime_dir / "result.json")
    live_status = read_json(args.live_status or runtime_dir / "live_status.json")
    latest_event = read_json(args.latest_event or runtime_dir / "latest_event.json")
    events = read_events(args.event_log, args.events)

    manifest_summary = manifest.get("summary", {})
    if not isinstance(manifest_summary, dict):
        manifest_summary = {}

    ready_frames = count_ready_frames(result)
    default_player_url = f"http://{args.host}:{args.port}/?mode=player"
    if live_status.get("player_hud"):
        default_player_url += "&hud=1"
    player_url = live_status.get("player_url") or default_player_url

    critical_results = critical_result_status(args.cache_root) if args.critical else []
    return {
        "manifest": str(args.manifest),
        "manifest_status": manifest_summary.get("status", "missing"),
        "archives": manifest_summary.get("mix_archives", len(manifest.get("archives", []))),
        "vqa_entries": manifest_summary.get("vqa_entries", len(manifest.get("entries", []))),
        "payload_bytes": manifest_summary.get("total_payload_bytes", ""),
        "hard_2g_archives": manifest_summary.get("hard_2g_archives", ""),
        "engine_mode": live_status.get("engine_mode", "wine-dgvoodoo-win10-safevqa"),
        "vqa_mode": live_status.get("vqa_mode", "external_sidecar_player"),
        "strace_all_reads": live_status.get("strace_all_reads", False),
        "strace_dedupe": live_status.get("strace_dedupe", False),
        "trace_dedupe_key": live_status.get("trace_dedupe_key", False),
        "keep_last_result": live_status.get("keep_last_result", False),
        "player_hud": live_status.get("player_hud", False),
        "live_status": live_status.get("status", "unknown"),
        "last_key": result.get("key", ""),
        "last_status": result.get("status", ""),
        "last_width": result.get("width", ""),
        "last_height": result.get("height", ""),
        "last_frames": result.get("frames", ""),
        "ready_frames": ready_frames,
        "latest_event_status": latest_event.get("status", ""),
        "latest_event_key": latest_event.get("key", ""),
        "event_summary": summarize_events(events) if args.events else {},
        "critical_ready": critical_ready(critical_results) if args.critical else None,
        "critical_results": critical_results,
        "player_url": player_url,
        "runtime_dir": str(runtime_dir),
        "cache_root": str(args.cache_root),
    }


def print_text(status: dict[str, Any]) -> None:
    print("Sidecar VQA externe")
    print(f"Manifest: {status['manifest']}")
    print(
        "Index: "
        f"{status['manifest_status']} | archives={status['archives']} | "
        f"vqa={status['vqa_entries']} | hard_2g={status['hard_2g_archives']}"
    )
    print(f"Mode moteur: {status['engine_mode']}")
    print(f"Mode VQA: {status['vqa_mode']}")
    if status["strace_all_reads"] or status["strace_dedupe"] or status["trace_dedupe_key"]:
        print(
            "Capture: "
            f"all_reads={int(bool(status['strace_all_reads']))} | "
            f"strace_dedupe={int(bool(status['strace_dedupe']))} | "
            f"trace_dedupe_key={int(bool(status['trace_dedupe_key']))}"
        )
    if status["keep_last_result"]:
        print("Resultat precedent conserve au lancement live")
    if status["player_hud"]:
        print("Player HUD: actif")
    print(f"Runtime: {status['live_status']} | dossier={status['runtime_dir']}")
    if status["last_key"]:
        print(
            "Derniere VQA: "
            f"{status['last_key']} | {status['last_status']} | "
            f"{status['last_width']}x{status['last_height']} | "
            f"frames={status['ready_frames']}/{status['last_frames']}"
        )
    if status["latest_event_key"]:
        print(f"Dernier event: {status['latest_event_status']} | {status['latest_event_key']}")
    critical_results = status.get("critical_results", [])
    if critical_results:
        print(f"VQA critiques pretes: {int(bool(status.get('critical_ready')))}")
        for row in critical_results:
            if not isinstance(row, dict):
                continue
            print(
                "  - "
                f"{row.get('key', '')} | {row.get('status', '')} | "
                f"{row.get('width', '')}x{row.get('height', '')} | "
                f"frames={row.get('ready_frames', 0)}/{row.get('frames', '')}"
            )
    event_summary = status.get("event_summary", {})
    if isinstance(event_summary, dict) and event_summary:
        print(
            "Events: "
            f"total={event_summary.get('events', 0)} | "
            f"decoded={event_summary.get('decoded_events', 0)} | "
            f"unique={event_summary.get('unique_decoded_keys', 0)} | "
            f"status={event_summary.get('status_counts', {})}"
        )
        for event in event_summary.get("recent", []):
            if not isinstance(event, dict):
                continue
            print(
                "  - "
                f"{event.get('status', '')} | {event.get('key', '')} | "
                f"frames={event.get('ready_frames', 0)} | {event.get('source', '')}"
            )
    print(f"Player: {status['player_url']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Show the external VQA sidecar state.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--runtime-dir", type=Path, default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--result-file", type=Path)
    parser.add_argument("--live-status", type=Path)
    parser.add_argument("--latest-event", type=Path)
    parser.add_argument("--event-log", type=Path, default=DEFAULT_EVENT_LOG)
    parser.add_argument("--events", type=int, default=0, help="Print the last N runtime events in the status summary.")
    parser.add_argument("--critical", action="store_true", help="Also summarize LOCALLNG/MOVIES sidecar critical decode readiness.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    status = build_status(args)
    if args.json:
        print(json.dumps(status, ensure_ascii=True, indent=2))
    else:
        print_text(status)


if __name__ == "__main__":
    main()
