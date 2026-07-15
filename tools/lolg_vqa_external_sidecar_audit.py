#!/usr/bin/env python3
"""Audit one external VQA sidecar runtime session."""

from __future__ import annotations

import argparse
import json
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = BASE_DIR / "output/vqa_external_sidecar_index/manifest.json"
DEFAULT_RUNTIME_DIR = BASE_DIR / "output/vqa_external_sidecar_runtime"
DEFAULT_CACHE_ROOT = BASE_DIR / "output/vqa_external_sidecar_cache"


def read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {"status": "invalid_json", "path": str(path)}
    return payload if isinstance(payload, dict) else {}


def read_events(path: Path, limit: int) -> list[dict[str, Any]]:
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


def archive_from_key(key: str) -> str:
    return key.split(":", 1)[0].upper() if ":" in key else ""


def count_ready_frames(decode_dir_text: str) -> int:
    if not decode_dir_text:
        return 0
    path = Path(decode_dir_text)
    if not path.is_absolute():
        path = BASE_DIR / path
    frames_dir = path / "frames_fullhd"
    if not frames_dir.is_dir():
        return 0
    return len(list(frames_dir.glob("*.png")))


def ordered_unique(values: list[str]) -> list[str]:
    return list(OrderedDict.fromkeys(value for value in values if value))


def manifest_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    summary = manifest.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}
    archives = manifest.get("archives", [])
    entries = manifest.get("entries", [])
    return {
        "status": summary.get("status", "missing"),
        "archives": int(summary.get("mix_archives") or len(archives) or 0),
        "vqa_entries": int(summary.get("vqa_entries") or len(entries) or 0),
        "hard_2g_archives": summary.get("hard_2g_archives", ""),
        "payload_bytes": summary.get("total_payload_bytes", ""),
    }


def event_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = Counter(str(event.get("status", "unknown")) for event in events)
    decoded = [event for event in events if event.get("status") == "decoded"]
    failed = [event for event in events if event.get("status") == "decode_failed"]
    requested = [event for event in events if event.get("status") == "request_written"]
    decoded_keys = ordered_unique([str(event.get("key", "")) for event in decoded])
    requested_keys = ordered_unique([str(event.get("key", "")) for event in requested])
    failed_keys = ordered_unique([str(event.get("key", "")) for event in failed])
    decoded_archives = ordered_unique([archive_from_key(key) for key in decoded_keys])
    recent: list[dict[str, Any]] = []
    for event in events[-12:]:
        decode_dir = str(event.get("decode_dir", ""))
        recent.append(
            {
                "status": event.get("status", ""),
                "key": event.get("key", ""),
                "source": event.get("source", ""),
                "method": event.get("method", ""),
                "ready_frames": count_ready_frames(decode_dir),
            }
        )
    return {
        "events": len(events),
        "status_counts": dict(status_counts),
        "request_events": len(requested),
        "decoded_events": len(decoded),
        "failed_events": len(failed),
        "requested_keys": requested_keys,
        "decoded_keys": decoded_keys,
        "failed_keys": failed_keys,
        "decoded_archives": decoded_archives,
        "recent": recent,
    }


def build_audit(args: argparse.Namespace) -> dict[str, Any]:
    manifest = read_json(args.manifest)
    runtime_dir = args.runtime_dir
    result = read_json(args.result_file or runtime_dir / "result.json")
    latest_event = read_json(args.latest_event_file or runtime_dir / "latest_event.json")
    live_status = read_json(args.live_status or runtime_dir / "live_status.json")
    strace_summary = read_json(args.strace_summary or runtime_dir / "strace_bridge_summary.json")
    events = read_events(args.event_log or runtime_dir / "events.jsonl", args.events)
    manifest_info = manifest_summary(manifest)
    events_info = event_summary(events)
    total_vqa = manifest_info["vqa_entries"]
    total_archives = manifest_info["archives"]
    unique_decoded = len(events_info["decoded_keys"])
    archives_decoded = len(events_info["decoded_archives"])
    return {
        "sidecar_scope": "external_player_only",
        "scope_note": "Le jeu Wine reste en safevqa; les VQA HD sont affichees dans le player web externe.",
        "manifest": str(args.manifest),
        "manifest_summary": manifest_info,
        "runtime_dir": str(runtime_dir),
        "live_status": {
            "status": live_status.get("status", "unknown"),
            "engine_mode": live_status.get("engine_mode", "wine-dgvoodoo-win10-safevqa"),
            "vqa_mode": live_status.get("vqa_mode", "external_sidecar_player"),
            "trace_source": live_status.get("trace_source", ""),
            "keep_last_result": live_status.get("keep_last_result", False),
            "player_url": live_status.get("player_url", ""),
        },
        "strace_summary": {
            "status": strace_summary.get("status", ""),
            "lines": strace_summary.get("lines", ""),
            "open_mix_hits": strace_summary.get("open_mix_hits", ""),
            "read_mix_hits": strace_summary.get("read_mix_hits", ""),
            "emitted_trace_lines": strace_summary.get("emitted_trace_lines", ""),
        },
        "events": events_info,
        "coverage": {
            "unique_decoded_vqa": unique_decoded,
            "total_vqa": total_vqa,
            "unique_decoded_percent": round((unique_decoded / total_vqa) * 100, 3) if total_vqa else 0,
            "decoded_archives": archives_decoded,
            "total_archives": total_archives,
            "decoded_archive_percent": round((archives_decoded / total_archives) * 100, 3) if total_archives else 0,
        },
        "current_result": {
            "status": result.get("status", ""),
            "message": result.get("message", ""),
            "key": result.get("key", ""),
            "width": result.get("width", ""),
            "height": result.get("height", ""),
            "frames": result.get("frames", ""),
            "ready_frames": count_ready_frames(str(result.get("decode_dir", ""))),
            "decode_dir": result.get("decode_dir", ""),
        },
        "latest_event": {
            "status": latest_event.get("status", ""),
            "key": latest_event.get("key", ""),
            "source": latest_event.get("source", ""),
            "method": latest_event.get("method", ""),
        },
    }


def print_text(audit: dict[str, Any]) -> None:
    manifest = audit["manifest_summary"]
    live = audit["live_status"]
    strace = audit["strace_summary"]
    events = audit["events"]
    coverage = audit["coverage"]
    result = audit["current_result"]
    latest = audit["latest_event"]
    print("Audit sidecar VQA externe")
    print(f"Portee: {audit['sidecar_scope']} - {audit['scope_note']}")
    print(f"Manifest: {manifest['status']} | archives={manifest['archives']} | vqa={manifest['vqa_entries']} | hard_2g={manifest['hard_2g_archives']}")
    print(
        "Runtime: "
        f"{live['status']} | moteur={live['engine_mode']} | vqa={live['vqa_mode']} | "
        f"trace={live['trace_source']} | keep_last={int(bool(live['keep_last_result']))}"
    )
    if live.get("player_url"):
        print(f"Player: {live['player_url']}")
    print(
        "Strace: "
        f"status={strace['status']} | lines={strace['lines']} | "
        f"open_mix={strace['open_mix_hits']} | read_mix={strace['read_mix_hits']} | emitted={strace['emitted_trace_lines']}"
    )
    print(
        "Events: "
        f"total={events['events']} | requests={events['request_events']} | "
        f"decoded={events['decoded_events']} | failed={events['failed_events']} | status={events['status_counts']}"
    )
    print(
        "Couverture session: "
        f"vqa_uniques={coverage['unique_decoded_vqa']}/{coverage['total_vqa']} "
        f"({coverage['unique_decoded_percent']}%) | "
        f"archives={coverage['decoded_archives']}/{coverage['total_archives']} "
        f"({coverage['decoded_archive_percent']}%)"
    )
    if result.get("key"):
        print(
            "Resultat courant: "
            f"{result['key']} | {result['status']} | {result['width']}x{result['height']} | "
            f"frames={result['ready_frames']}/{result['frames']} | {result['message']}"
        )
    if latest.get("key"):
        print(f"Dernier event: {latest['status']} | {latest['key']} | {latest['source']} | {latest['method']}")
    if events["decoded_keys"]:
        print("VQA decodees uniques:")
        for key in events["decoded_keys"][-20:]:
            print(f"  - {key}")
    if events["failed_keys"]:
        print("VQA en echec:")
        for key in events["failed_keys"][-20:]:
            print(f"  - {key}")
    if events["recent"]:
        print("Evenements recents:")
        for event in events["recent"]:
            print(
                "  - "
                f"{event['status']} | {event['key']} | frames={event['ready_frames']} | "
                f"{event['source']} | {event['method']}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit the current external VQA sidecar runtime session.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--runtime-dir", type=Path, default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--result-file", type=Path)
    parser.add_argument("--latest-event-file", type=Path)
    parser.add_argument("--event-log", type=Path)
    parser.add_argument("--live-status", type=Path)
    parser.add_argument("--strace-summary", type=Path)
    parser.add_argument("--events", type=int, default=0, help="Read the last N events. 0 means all events.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    audit = build_audit(args)
    if args.json:
        print(json.dumps(audit, ensure_ascii=True, indent=2))
    else:
        print_text(audit)


if __name__ == "__main__":
    main()
