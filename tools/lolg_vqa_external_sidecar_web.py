#!/usr/bin/env python3
"""Serve a tiny local web viewer for decoded external sidecar VQA frames."""

from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlparse


BASE_DIR = Path(__file__).resolve().parents[1]
REQUEST_TOOL = BASE_DIR / "tools/lolg_vqa_external_sidecar_request.py"
DEFAULT_RUNTIME_DIR = BASE_DIR / "output/vqa_external_sidecar_runtime"
DEFAULT_CACHE_ROOT = BASE_DIR / "output/vqa_external_sidecar_cache"
DEFAULT_MANIFEST = BASE_DIR / "output/vqa_external_sidecar_index/manifest.json"


HTML = """<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LOLG VQA Sidecar</title>
  <style>
    * { box-sizing: border-box; }
    html, body { margin: 0; height: 100%; background: #08090a; color: #f2f4f5; font-family: system-ui, sans-serif; }
    body { display: grid; grid-template-rows: auto 1fr auto; }
    body.player { grid-template-rows: 1fr; cursor: none; }
    body.player header, body.player footer { display: none; }
    body.hud { cursor: default; }
    header, footer { display: flex; gap: 8px; align-items: center; padding: 8px 10px; background: #171a1c; border-color: #2c3135; }
    header { border-bottom: 1px solid #2c3135; }
    footer { border-top: 1px solid #2c3135; font-size: 12px; color: #b7c0c5; min-height: 34px; }
    input, button, select { height: 32px; border: 1px solid #3a4248; background: #22272b; color: #f2f4f5; border-radius: 4px; padding: 0 8px; }
    button { cursor: pointer; }
    button:hover { background: #2d353b; }
    #key { width: min(360px, 42vw); font-family: ui-monospace, monospace; }
    #stage { min-height: 0; display: grid; place-items: center; overflow: hidden; background: #000; }
    #frame { max-width: 100%; max-height: 100%; image-rendering: auto; }
    body.player #frame { width: 100%; height: 100%; object-fit: fill; }
    #empty { color: #8f989e; }
    body.player #empty { display: none; }
    #hud { position: fixed; left: 10px; bottom: 10px; display: none; max-width: min(720px, calc(100vw - 20px)); padding: 8px 10px; border: 1px solid rgba(255,255,255,0.22); background: rgba(0,0,0,0.68); color: #f2f4f5; font: 12px/1.35 ui-monospace, monospace; white-space: pre-wrap; z-index: 10; }
    body.hud #hud { display: block; }
    .spacer { flex: 1; }
    .metric { white-space: nowrap; }
    @media (max-width: 720px) {
      header { flex-wrap: wrap; }
      #key { width: 100%; }
      .spacer { display: none; }
    }
  </style>
</head>
<body>
  <header>
    <input id="key" value="HERB.MIX:98e2ff4f" aria-label="VQA key">
    <input id="maxFrames" type="number" min="1" max="9999" value="16" aria-label="Max frames">
    <button id="request">Demander</button>
    <button id="toggle">Pause</button>
    <div class="spacer"></div>
    <span class="metric" id="keyInfo">-</span>
    <span class="metric" id="frameInfo">0/0</span>
  </header>
  <main id="stage">
    <img id="frame" alt="" hidden>
    <div id="empty">En attente de frames sidecar</div>
  </main>
  <div id="hud"></div>
  <footer id="status">Connexion au sidecar...</footer>
  <script>
    const frameEl = document.getElementById('frame');
    const emptyEl = document.getElementById('empty');
    const statusEl = document.getElementById('status');
    const frameInfo = document.getElementById('frameInfo');
    const keyInfo = document.getElementById('keyInfo');
    const keyInput = document.getElementById('key');
    const maxFramesInput = document.getElementById('maxFrames');
    const requestButton = document.getElementById('request');
    const toggleButton = document.getElementById('toggle');
    const hudEl = document.getElementById('hud');
    const params = new URLSearchParams(window.location.search);
    const playerMode = params.get('mode') === 'player' || params.has('player');
    const hudMode = params.get('hud') === '1' || params.get('hud') === 'true';

    let frames = [];
    let frameIndex = 0;
    let paused = false;
    let fps = 15;
    let lastSignature = '';
    const refreshDelay = playerMode ? 200 : 1000;

    if (playerMode) {
      document.body.classList.add('player');
    }
    if (hudMode) {
      document.body.classList.add('hud');
    }

    function signature(payload) {
      return `${payload.key || ''}:${payload.frame_count || 0}:${payload.result_mtime || 0}:${payload.event_id || ''}`;
    }

    async function refreshFrames() {
      try {
        const response = await fetch(hudMode ? '/api/status?events=8' : '/api/frames', { cache: 'no-store' });
        const statusPayload = await response.json();
        const payload = hudMode ? statusPayload.frames : statusPayload;
        statusEl.textContent = payload.message || payload.status || 'ok';
        if (payload.key) keyInfo.textContent = payload.key;
        fps = payload.fps || 15;
        if (hudMode) {
          updateHud(statusPayload);
        }
        const nextSignature = signature(payload);
        if (nextSignature !== lastSignature) {
          lastSignature = nextSignature;
          frames = payload.frames || [];
          frameIndex = 0;
          showFrame();
        }
      } catch (error) {
        statusEl.textContent = `Erreur sidecar: ${error}`;
      }
    }

    function updateHud(payload) {
      const frames = payload.frames || {};
      const eventSummary = payload.event_summary || {};
      const live = payload.live_status || {};
      const strace = payload.strace_summary || {};
      const statusCounts = eventSummary.status_counts || {};
      hudEl.textContent = [
        `${frames.key || '-'}  ${frames.frame_count || 0} frames  ${frames.width || '?'}x${frames.height || '?'}`,
        `event ${payload.latest_event_key || '-'}  decoded=${eventSummary.decoded_events || 0} unique=${eventSummary.unique_decoded_keys || 0}`,
        `runtime=${live.status || 'unknown'}  strace=${strace.emitted_trace_lines || 0}/${strace.read_mix_hits || 0}  status=${JSON.stringify(statusCounts)}`
      ].join('\\n');
    }

    function showFrame() {
      if (!frames.length) {
        frameEl.hidden = true;
        emptyEl.hidden = false;
        frameInfo.textContent = '0/0';
        return;
      }
      frameEl.hidden = false;
      emptyEl.hidden = true;
      frameEl.src = frames[frameIndex].url;
      frameInfo.textContent = `${frameIndex + 1}/${frames.length}`;
    }

    function tick() {
      if (!paused && frames.length) {
        frameIndex = (frameIndex + 1) % frames.length;
        showFrame();
      }
      window.setTimeout(tick, Math.max(40, Math.round(1000 / Math.max(1, fps))));
    }

    async function sendRequest() {
      const key = keyInput.value.trim();
      if (!key) return;
      statusEl.textContent = 'Preparation de la requete...';
      const payload = {
        key,
        action: 'decode',
        process: true,
        max_frames: Number(maxFramesInput.value || 16),
        fullhd: true,
        fit: 'stretch',
        filter: 'nearest',
        fast_png: true
      };
      try {
        const response = await fetch('/api/request', {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const result = await response.json();
        statusEl.textContent = result.status || 'requete envoyee';
        await refreshFrames();
      } catch (error) {
        statusEl.textContent = `Erreur requete: ${error}`;
      }
    }

    requestButton.addEventListener('click', sendRequest);
    toggleButton.addEventListener('click', () => {
      paused = !paused;
      toggleButton.textContent = paused ? 'Reprendre' : 'Pause';
    });
    window.setInterval(refreshFrames, refreshDelay);
    refreshFrames();
    tick();
  </script>
</body>
</html>
"""


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {"status": "invalid_json", "message": f"JSON invalide: {path}"}


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def read_events(path: Path, limit: int = 50) -> list[dict[str, Any]]:
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
    return rows[-limit:]


def safe_path(path_text: str) -> Path:
    path = Path(path_text).expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    resolved = path.resolve()
    base = BASE_DIR.resolve()
    if not resolved.is_relative_to(base):
        raise PermissionError(f"path outside project: {resolved}")
    return resolved


def frame_url(path: Path) -> str:
    try:
        mtime = path.stat().st_mtime_ns
    except FileNotFoundError:
        mtime = 0
    return f"/frame?path={quote(str(path))}&v={mtime}"


def summarize_inventory(payload: dict[str, Any]) -> dict[str, Any]:
    frames = payload.get("frames", [])
    first_frame = frames[0] if isinstance(frames, list) and frames else {}
    last_frame = frames[-1] if isinstance(frames, list) and frames else {}
    event = payload.get("event", {})
    if not isinstance(event, dict):
        event = {}
    return {
        "status": payload.get("status", ""),
        "message": payload.get("message", ""),
        "key": payload.get("key", ""),
        "width": payload.get("width", ""),
        "height": payload.get("height", ""),
        "fps": payload.get("fps", ""),
        "frame_count": payload.get("frame_count", 0),
        "result_mtime": payload.get("result_mtime", 0),
        "event_id": payload.get("event_id", ""),
        "event_status": event.get("status", ""),
        "event_key": event.get("key", ""),
        "event_source": event.get("source", ""),
        "first_frame": first_frame.get("path", "") if isinstance(first_frame, dict) else "",
        "last_frame": last_frame.get("path", "") if isinstance(last_frame, dict) else "",
    }


def ready_frames_from_event(event: dict[str, Any]) -> int:
    decode_dir_text = event.get("decode_dir")
    if not isinstance(decode_dir_text, str) or not decode_dir_text:
        return 0
    try:
        decode_dir = safe_path(decode_dir_text)
    except PermissionError:
        return 0
    frames_dir = decode_dir / "frames_fullhd"
    if not frames_dir.is_dir():
        return 0
    return len(sorted(frames_dir.glob("*.png")))


def summarize_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts: dict[str, int] = {}
    decoded_keys: list[str] = []
    recent: list[dict[str, Any]] = []
    for event in events:
        status = str(event.get("status", "unknown"))
        key = str(event.get("key", ""))
        status_counts[status] = status_counts.get(status, 0) + 1
        if status == "decoded" and key and key not in decoded_keys:
            decoded_keys.append(key)
        recent.append(
            {
                "status": status,
                "key": key,
                "source": event.get("source", ""),
                "method": event.get("method", ""),
                "ready_frames": ready_frames_from_event(event),
            }
        )
    return {
        "events": len(events),
        "status_counts": status_counts,
        "decoded_events": sum(1 for event in events if event.get("status") == "decoded"),
        "unique_decoded_keys": len(decoded_keys),
        "decoded_keys": decoded_keys,
        "recent": recent,
    }


def summarize_live_status(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": payload.get("status", "unknown"),
        "engine_mode": payload.get("engine_mode", ""),
        "vqa_mode": payload.get("vqa_mode", ""),
        "trace_source": payload.get("trace_source", ""),
        "strace_all_reads": payload.get("strace_all_reads", False),
        "strace_dedupe": payload.get("strace_dedupe", False),
        "trace_dedupe_key": payload.get("trace_dedupe_key", False),
        "keep_last_result": payload.get("keep_last_result", False),
        "player_hud": payload.get("player_hud", False),
        "web_url": payload.get("web_url", ""),
        "player_url": payload.get("player_url", ""),
        "event_log": payload.get("event_log", ""),
        "latest_event_file": payload.get("latest_event_file", ""),
    }


def summarize_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "event_id": event.get("event_id", ""),
        "event_time": event.get("event_time", ""),
        "status": event.get("status", ""),
        "process_returncode": event.get("process_returncode", ""),
        "key": event.get("key", ""),
        "archive": event.get("archive", ""),
        "file_id": event.get("file_id", ""),
        "index": event.get("index", ""),
        "offset": event.get("offset", ""),
        "method": event.get("method", ""),
        "source": event.get("source", ""),
        "ready_frames": ready_frames_from_event(event),
    }


def rendered_frame_rows(rendered_csv: Path) -> list[dict[str, str]]:
    if not rendered_csv.is_file():
        return []
    with rendered_csv.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def decode_dir_from_key(cache_root: Path, key: str) -> Path | None:
    if ":" not in key:
        return None
    archive, file_id = key.split(":", 1)
    archive = archive.upper()
    if not archive.endswith(".MIX"):
        archive = f"{archive}.MIX"
    file_id = file_id.lower()
    if not archive or not file_id:
        return None
    return cache_root / archive / file_id / "decode"


def collect_frames(result_file: Path, latest_event_file: Path | None = None, cache_root: Path = DEFAULT_CACHE_ROOT) -> dict[str, Any]:
    result = read_json(result_file)
    event = read_json(latest_event_file) if latest_event_file else {}
    event_key = str(event.get("key") or "")
    if not result:
        event_decode_dir = safe_path(str(event["decode_dir"])) if event.get("decode_dir") else decode_dir_from_key(cache_root, event_key) if event_key else None
        if event_decode_dir is not None:
            result = {
                "status": event.get("status", "waiting"),
                "message": "Frames partielles depuis latest_event",
                "key": event_key,
                "decode_dir": str(event_decode_dir),
            }
        else:
            return {
                "status": "waiting",
                "message": f"En attente de {result_file}",
                "frames": [],
                "frame_count": 0,
                "event": event,
                "event_id": event.get("event_id", ""),
            }

    if event_key and event_key != str(result.get("key") or ""):
        event_decode_dir = safe_path(str(event["decode_dir"])) if event.get("decode_dir") else decode_dir_from_key(cache_root, event_key)
        if event_decode_dir is not None:
            result = {
                "status": event.get("status", "waiting"),
                "message": "Frames partielles depuis latest_event",
                "key": event_key,
                "decode_dir": str(event_decode_dir),
            }

    decode_dir_text = result.get("decode_dir")
    if not decode_dir_text:
        return {
            "status": result.get("status", "waiting"),
            "message": "Aucun decode_dir dans le resultat sidecar",
            "key": result.get("key", ""),
            "frames": [],
            "frame_count": 0,
            "event": event,
            "event_id": event.get("event_id", ""),
        }

    decode_dir = safe_path(str(decode_dir_text))
    header = read_json(decode_dir / "header.json")
    rows = rendered_frame_rows(decode_dir / "rendered_frames.csv")
    frame_paths: list[Path] = []
    for row in rows:
        preferred = row.get("fullhd_output") or row.get("native_output") or ""
        if preferred:
            path = safe_path(preferred)
            if path.is_file():
                frame_paths.append(path)
    if not frame_paths:
        fullhd_dir = decode_dir / "frames_fullhd"
        native_dir = decode_dir / "frames_native"
        source_dir = fullhd_dir if fullhd_dir.is_dir() else native_dir
        frame_paths = sorted(source_dir.glob("*.png")) if source_dir.is_dir() else []

    try:
        result_mtime = result_file.stat().st_mtime_ns
    except FileNotFoundError:
        result_mtime = 0

    frames = [
        {
            "index": index,
            "path": str(path),
            "url": frame_url(path),
        }
        for index, path in enumerate(frame_paths)
    ]
    fps = result.get("fps") or header.get("frame_rate") or 15
    return {
        "status": result.get("status", "unknown"),
        "message": f"{len(frames)} frames pretes",
        "key": result.get("key", ""),
        "width": header.get("width") or result.get("width"),
        "height": header.get("height") or result.get("height"),
        "fps": fps,
        "frames": frames,
        "frame_count": len(frames),
        "result_mtime": result_mtime,
        "event": event,
        "event_id": event.get("event_id", ""),
    }


def collect_status(
    runtime_dir: Path,
    result_file: Path,
    latest_event_file: Path,
    event_log: Path,
    cache_root: Path,
    events_limit: int,
) -> dict[str, Any]:
    frames = summarize_inventory(collect_frames(result_file, latest_event_file, cache_root))
    latest_event = read_json(latest_event_file)
    latest_event_summary = summarize_event(latest_event)
    events = read_events(event_log, events_limit)
    live_status = read_json(runtime_dir / "live_status.json")
    strace_summary = read_json(runtime_dir / "strace_bridge_summary.json")
    return {
        "status": frames.get("status", "unknown"),
        "message": frames.get("message", ""),
        "frames": frames,
        "latest_event": latest_event_summary,
        "latest_event_key": latest_event_summary.get("key", ""),
        "event_summary": summarize_events(events),
        "live_status": summarize_live_status(live_status),
        "strace_summary": strace_summary,
        "runtime_dir": str(runtime_dir),
        "cache_root": str(cache_root),
    }


def run_request(server: "SidecarServer", payload: dict[str, Any]) -> dict[str, Any]:
    write_json_atomic(server.request_file, payload)
    if not (server.process_requests or payload.get("process")):
        return {"status": "request_written", "request_file": str(server.request_file)}

    command = [
        sys.executable,
        str(REQUEST_TOOL),
        "--manifest",
        str(server.manifest),
        "--cache-root",
        str(server.cache_root),
        "--request-file",
        str(server.request_file),
        "--result-file",
        str(server.result_file),
    ]
    completed = subprocess.run(command, cwd=BASE_DIR, text=True, capture_output=True, check=False)
    event = {
        "status": "ok" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    write_json_atomic(server.runtime_dir / "last_event.json", event)
    if completed.returncode != 0:
        return {"status": "request_failed", "returncode": completed.returncode, "stderr": completed.stderr}
    result = read_json(server.result_file)
    result["status"] = result.get("status", "decoded")
    event = {
        "event_id": time.time_ns(),
        "event_time": time.time(),
        "status": result.get("status", "decoded"),
        "process_returncode": completed.returncode,
        "key": result.get("key", payload.get("key", "")),
        "source": "web_request",
        "request_file": str(server.request_file),
        "result_file": str(server.result_file),
        "request": payload,
    }
    append_jsonl(server.event_log, event)
    write_json_atomic(server.latest_event_file, event)
    return result


class SidecarServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], args: argparse.Namespace):
        super().__init__(address, SidecarHandler)
        self.runtime_dir: Path = args.runtime_dir
        self.result_file: Path = args.result_file or args.runtime_dir / "result.json"
        self.request_file: Path = args.request_file or args.runtime_dir / "request.json"
        self.event_log: Path = args.event_log or args.runtime_dir / "events.jsonl"
        self.latest_event_file: Path = args.latest_event_file or args.runtime_dir / "latest_event.json"
        self.cache_root: Path = args.cache_root
        self.manifest: Path = args.manifest
        self.process_requests: bool = args.process_requests


class SidecarHandler(BaseHTTPRequestHandler):
    server: SidecarServer

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        return

    def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=True, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json; charset=utf-8")
        self.send_header("cache-control", "no-store")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_text(self, text: str, content_type: str = "text/html; charset=utf-8") -> None:
        data = text.encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", content_type)
        self.send_header("cache-control", "no-store")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_head_only(self, status: int = 200, content_type: str = "application/json; charset=utf-8", length: int = 0) -> None:
        self.send_response(status)
        self.send_header("content-type", content_type)
        self.send_header("cache-control", "no-store")
        self.send_header("content-length", str(length))
        self.end_headers()

    def do_HEAD(self) -> None:  # noqa: N802 - stdlib hook
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.send_head_only(content_type="text/html; charset=utf-8", length=len(HTML.encode("utf-8")))
            return
        if parsed.path in {"/api/result", "/api/event", "/api/events", "/api/status", "/api/frames"}:
            self.send_head_only()
            return
        if parsed.path == "/frame":
            query = parse_qs(parsed.query)
            path_values = query.get("path", [])
            if not path_values:
                self.send_head_only(400)
                return
            try:
                path = safe_path(unquote(path_values[0]))
            except PermissionError:
                self.send_head_only(403)
                return
            if not path.is_file():
                self.send_head_only(404)
                return
            self.send_head_only(
                content_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                length=path.stat().st_size,
            )
            return
        self.send_head_only(404)

    def do_GET(self) -> None:  # noqa: N802 - stdlib hook
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.send_text(HTML)
            return
        if parsed.path == "/api/result":
            self.send_json(read_json(self.server.result_file))
            return
        if parsed.path == "/api/event":
            self.send_json(read_json(self.server.latest_event_file))
            return
        if parsed.path == "/api/events":
            query = parse_qs(parsed.query)
            limit_values = query.get("limit", ["50"])
            try:
                limit = max(1, min(500, int(limit_values[0])))
            except ValueError:
                limit = 50
            self.send_json({"status": "ok", "events": read_events(self.server.event_log, limit), "event_log": str(self.server.event_log)})
            return
        if parsed.path == "/api/status":
            query = parse_qs(parsed.query)
            limit_values = query.get("events", ["20"])
            try:
                limit = max(1, min(500, int(limit_values[0])))
            except ValueError:
                limit = 20
            try:
                self.send_json(
                    collect_status(
                        self.server.runtime_dir,
                        self.server.result_file,
                        self.server.latest_event_file,
                        self.server.event_log,
                        self.server.cache_root,
                        limit,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - report through API
                self.send_json({"status": "error", "message": str(exc)}, 500)
            return
        if parsed.path == "/api/frames":
            try:
                self.send_json(collect_frames(self.server.result_file, self.server.latest_event_file, self.server.cache_root))
            except Exception as exc:  # noqa: BLE001 - report through API
                self.send_json({"status": "error", "message": str(exc), "frames": [], "frame_count": 0}, 500)
            return
        if parsed.path == "/frame":
            query = parse_qs(parsed.query)
            path_values = query.get("path", [])
            if not path_values:
                self.send_json({"status": "error", "message": "missing path"}, 400)
                return
            try:
                path = safe_path(unquote(path_values[0]))
            except PermissionError as exc:
                self.send_json({"status": "error", "message": str(exc)}, 403)
                return
            self.send_file(path)
            return
        self.send_json({"status": "error", "message": "not found"}, 404)

    def do_POST(self) -> None:  # noqa: N802 - stdlib hook
        parsed = urlparse(self.path)
        if parsed.path != "/api/request":
            self.send_json({"status": "error", "message": "not found"}, 404)
            return
        length = int(self.headers.get("content-length", "0") or 0)
        body = self.rfile.read(length)
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            self.send_json({"status": "error", "message": f"invalid json: {exc}"}, 400)
            return
        if not isinstance(payload, dict):
            self.send_json({"status": "error", "message": "object expected"}, 400)
            return
        try:
            self.send_json(run_request(self.server, payload))
        except Exception as exc:  # noqa: BLE001 - report through API
            self.send_json({"status": "error", "message": str(exc)}, 500)

    def send_file(self, path: Path) -> None:
        if not path.is_file():
            self.send_json({"status": "error", "message": f"file not found: {path}"}, 404)
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("content-type", content_type)
        self.send_header("cache-control", "public, max-age=60")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve a local browser viewer for external VQA sidecar frames.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--runtime-dir", type=Path, default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--result-file", type=Path)
    parser.add_argument("--request-file", type=Path)
    parser.add_argument("--event-log", type=Path)
    parser.add_argument("--latest-event-file", type=Path)
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--process-requests", action="store_true", help="Process POST /api/request immediately instead of only writing request.json.")
    parser.add_argument("--check", action="store_true", help="Print the current frame inventory and exit.")
    parser.add_argument("--status", action="store_true", help="Print the compact session/player status and exit.")
    parser.add_argument("--summary", action="store_true", help="With --check, omit the full frame URL list.")
    parser.add_argument("--events", type=int, default=20, help="Event count for --status or /api/status.")
    args = parser.parse_args()

    args.runtime_dir.mkdir(parents=True, exist_ok=True)
    args.result_file = args.result_file or args.runtime_dir / "result.json"
    args.request_file = args.request_file or args.runtime_dir / "request.json"
    args.event_log = args.event_log or args.runtime_dir / "events.jsonl"
    args.latest_event_file = args.latest_event_file or args.runtime_dir / "latest_event.json"

    if args.check:
        payload = collect_frames(args.result_file, args.latest_event_file, args.cache_root)
        if args.summary:
            payload = summarize_inventory(payload)
        print(json.dumps(payload, ensure_ascii=True, indent=2))
        return
    if args.status:
        payload = collect_status(args.runtime_dir, args.result_file, args.latest_event_file, args.event_log, args.cache_root, args.events)
        print(json.dumps(payload, ensure_ascii=True, indent=2))
        return

    server = SidecarServer((args.host, args.port), args)
    print(f"Lecteur web sidecar: http://{args.host}:{args.port}/")
    print("Ctrl+C pour arreter.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
