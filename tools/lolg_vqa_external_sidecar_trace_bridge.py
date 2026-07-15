#!/usr/bin/env python3
"""Convert VQA/MIX trace hints into external sidecar requests."""

from __future__ import annotations

import argparse
import csv
import json
import re
import struct
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = BASE_DIR / "output/vqa_external_sidecar_index/manifest.json"
DEFAULT_ORIGINAL_ROOT = BASE_DIR / "C/LOLG"
DEFAULT_RUNTIME_DIR = BASE_DIR / "output/vqa_external_sidecar_runtime"
DEFAULT_CACHE_ROOT = BASE_DIR / "output/vqa_external_sidecar_cache"
DEFAULT_OUTPUT = BASE_DIR / "output/vqa_external_sidecar_trace_bridge"
REQUEST_TOOL = BASE_DIR / "tools/lolg_vqa_external_sidecar_request.py"

MATCH_FIELDS = [
    "status",
    "source",
    "key",
    "archive",
    "file_id",
    "index",
    "offset",
    "size",
    "method",
    "message",
]

ARCHIVE_RE = re.compile(r"([A-Za-z0-9_]+\.MIX)", re.IGNORECASE)
KEY_RE = re.compile(r"([A-Za-z0-9_]+\.MIX):([0-9a-fA-F]{8})", re.IGNORECASE)
FILE_ID_RE = re.compile(r"(?:file[_-]?id|id|hash)\s*[=:]\s*(?:0x)?([0-9a-fA-F]{8})", re.IGNORECASE)
INDEX_RE = re.compile(r"(?:index|entry)\s*[=:]\s*(\d+)", re.IGNORECASE)
BRACKET_INDEX_RE = re.compile(r"([A-Za-z0-9_]+\.MIX)\[(\d+)\]", re.IGNORECASE)
OFFSET_RE = re.compile(r"(?:offset|seek|pos|file_offset)\s*[=:]\s*(0x[0-9a-fA-F]+|\d+)", re.IGNORECASE)
LAYOUT_RE = re.compile(r"(?:layout|source_layout|mix_layout)\s*[=:]\s*([A-Za-z0-9_-]+)", re.IGNORECASE)


@dataclass(frozen=True)
class OriginalEntry:
    archive: str
    index: int
    file_id: str
    file_offset: int
    body_offset: int
    size: int


def archive_name(value: str) -> str:
    name = Path(str(value).replace("\\", "/")).name.upper()
    if not name.endswith(".MIX"):
        name = f"{name}.MIX"
    return name


def parse_int(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text, 16) if text.lower().startswith("0x") else int(text)
    except ValueError:
        return None


def parse_key(value: str) -> tuple[str, str]:
    if ":" not in value:
        raise argparse.ArgumentTypeError("key must be ARCHIVE.MIX:FILE_ID")
    archive, file_id = value.split(":", 1)
    file_id = file_id.lower()
    if len(file_id) != 8:
        raise argparse.ArgumentTypeError("FILE_ID must be 8 hex characters")
    int(file_id, 16)
    return archive_name(archive), file_id


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"Fichier introuvable: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit(f"JSON invalide: {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MATCH_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def mix_table(path: Path) -> list[OriginalEntry]:
    with path.open("rb") as handle:
        header = handle.read(6)
        if len(header) < 6:
            return []
        count, body_size = struct.unpack("<HI", header)
        table = handle.read(count * 12)
    table_end = 6 + count * 12
    if len(table) != count * 12:
        return []
    rows: list[OriginalEntry] = []
    for index in range(count):
        file_id, offset, size = struct.unpack_from("<III", table, index * 12)
        if offset + size > body_size:
            continue
        rows.append(
            OriginalEntry(
                archive=archive_name(path.name),
                index=index,
                file_id=f"{file_id:08x}",
                file_offset=table_end + offset,
                body_offset=offset,
                size=size,
            )
        )
    return rows


def original_maps(root: Path) -> tuple[dict[tuple[str, int], OriginalEntry], dict[str, list[OriginalEntry]]]:
    by_index: dict[tuple[str, int], OriginalEntry] = {}
    by_archive: dict[str, list[OriginalEntry]] = {}
    if not root.is_dir():
        return by_index, by_archive
    for path in sorted(root.glob("*.MIX")):
        rows = mix_table(path)
        if not rows:
            continue
        by_archive[archive_name(path.name)] = rows
        for row in rows:
            by_index[(row.archive, row.index)] = row
    return by_index, by_archive


def manifest_indexes(
    manifest: dict[str, Any],
) -> tuple[
    dict[tuple[str, int], dict[str, str]],
    dict[str, dict[str, str]],
    dict[str, list[dict[str, str]]],
]:
    by_index: dict[tuple[str, int], dict[str, str]] = {}
    by_key: dict[str, dict[str, str]] = {}
    by_archive: dict[str, list[dict[str, str]]] = {}
    for row in manifest.get("entries", []):
        if not isinstance(row, dict):
            continue
        archive = archive_name(str(row.get("archive", "")))
        index = parse_int(row.get("index"))
        file_id = str(row.get("file_id", "")).lower()
        if len(file_id) != 8:
            continue
        if index is not None:
            by_index[(archive, index)] = row
        by_key[f"{archive}:{file_id}"] = row
        by_archive.setdefault(archive, []).append(row)
    for rows in by_archive.values():
        rows.sort(key=lambda item: parse_int(item.get("file_offset")) or 0)
    return by_index, by_key, by_archive


def find_by_offset(archive: str, offset: int, originals_by_archive: dict[str, list[OriginalEntry]]) -> OriginalEntry | None:
    rows = originals_by_archive.get(archive, [])
    for row in rows:
        if row.file_offset <= offset < row.file_offset + row.size:
            return row
    for row in rows:
        if row.body_offset <= offset < row.body_offset + row.size:
            return row
    return None


def manifest_row_for_key(manifest_by_key: dict[str, dict[str, str]], archive: str, file_id: str) -> dict[str, str] | None:
    return manifest_by_key.get(f"{archive}:{file_id.lower()}")


def manifest_row_for_offset(manifest_by_archive: dict[str, list[dict[str, str]]], archive: str, offset: int) -> dict[str, str] | None:
    for row in manifest_by_archive.get(archive, []):
        file_offset = parse_int(row.get("file_offset"))
        size = parse_int(row.get("size"))
        if file_offset is None or size is None:
            continue
        if file_offset <= offset < file_offset + size:
            return row
    return None


def infer_layout_from_text(line: str) -> str | None:
    layout_match = LAYOUT_RE.search(line)
    if layout_match:
        return layout_match.group(1).lower()
    normalized = line.replace("\\", "/")
    if "/C/LOLG/" in normalized:
        return "original"
    if "/mod_mix_vqa_fullhd/" in normalized:
        return "hd"
    return None


def make_match(
    status: str,
    source: str,
    archive: str = "",
    file_id: str = "",
    index: int | None = None,
    offset: int | None = None,
    size: int | None = None,
    method: str = "",
    message: str = "",
) -> dict[str, str]:
    key = f"{archive}:{file_id}" if archive and file_id else ""
    return {
        "status": status,
        "source": source,
        "key": key,
        "archive": archive,
        "file_id": file_id,
        "index": "" if index is None else str(index),
        "offset": "" if offset is None else str(offset),
        "size": "" if size is None else str(size),
        "method": method,
        "message": message,
    }


def resolve_hint(
    source: str,
    manifest_by_index: dict[tuple[str, int], dict[str, str]],
    manifest_by_key: dict[str, dict[str, str]],
    manifest_by_archive: dict[str, list[dict[str, str]]],
    originals_by_index: dict[tuple[str, int], OriginalEntry],
    originals_by_archive: dict[str, list[OriginalEntry]],
    archive: str | None = None,
    file_id: str | None = None,
    index: int | None = None,
    offset: int | None = None,
    layout: str | None = None,
) -> dict[str, str]:
    if archive:
        archive = archive_name(archive)
    if file_id:
        file_id = file_id.lower()
    if layout:
        layout = layout.lower()

    if archive and file_id:
        row = manifest_row_for_key(manifest_by_key, archive, file_id)
        if row:
            return make_match("pass", source, archive, file_id, parse_int(row.get("index")), offset, parse_int(row.get("size")), "archive_file_id")
        return make_match("gap", source, archive, file_id, index, offset, None, "archive_file_id", "cle absente du manifest sidecar")

    if archive and index is not None:
        original = originals_by_index.get((archive, index))
        if original:
            row = manifest_row_for_key(manifest_by_key, archive, original.file_id)
            if row:
                return make_match("pass", source, archive, original.file_id, index, offset, parse_int(row.get("size")), "original_archive_index")
        row = manifest_by_index.get((archive, index))
        if row:
            return make_match("pass", source, archive, str(row["file_id"]).lower(), index, offset, parse_int(row.get("size")), "manifest_archive_index")
        return make_match("gap", source, archive, "", index, offset, None, "archive_index", "index absent du manifest sidecar")

    if archive and offset is not None:
        prefer_original = layout in ("original", "orig")
        if prefer_original:
            original = find_by_offset(archive, offset, originals_by_archive)
            if original:
                row = manifest_row_for_key(manifest_by_key, archive, original.file_id)
                if row:
                    return make_match("pass", source, archive, original.file_id, original.index, offset, parse_int(row.get("size")), "original_archive_offset")
                return make_match("gap", source, archive, original.file_id, original.index, offset, original.size, "original_archive_offset", "id original absent du manifest sidecar")

        manifest_row = manifest_row_for_offset(manifest_by_archive, archive, offset)
        if manifest_row:
            file_id = str(manifest_row.get("file_id", "")).lower()
            return make_match(
                "pass",
                source,
                archive,
                file_id,
                parse_int(manifest_row.get("index")),
                offset,
                parse_int(manifest_row.get("size")),
                "manifest_archive_offset",
            )
        if not prefer_original:
            original = find_by_offset(archive, offset, originals_by_archive)
            if original:
                row = manifest_row_for_key(manifest_by_key, archive, original.file_id)
                if row:
                    return make_match("pass", source, archive, original.file_id, original.index, offset, parse_int(row.get("size")), "original_archive_offset")
                return make_match("gap", source, archive, original.file_id, original.index, offset, original.size, "original_archive_offset", "id original absent du manifest sidecar")
        return make_match("gap", source, archive, "", None, offset, None, "archive_offset", "offset hors des entrees sidecar/originales")

    return make_match("gap", source, archive or "", file_id or "", index, offset, None, "unknown", "indice insuffisant")


def parse_line_hint(line: str) -> dict[str, str | int | None]:
    archive: str | None = None
    file_id: str | None = None
    index: int | None = None
    offset: int | None = None
    layout = infer_layout_from_text(line)

    key_match = KEY_RE.search(line)
    if key_match:
        archive = archive_name(key_match.group(1))
        file_id = key_match.group(2).lower()

    bracket_match = BRACKET_INDEX_RE.search(line)
    if bracket_match:
        archive = archive_name(bracket_match.group(1))
        index = parse_int(bracket_match.group(2))

    archive_match = ARCHIVE_RE.search(line)
    if archive_match and not archive:
        archive = archive_name(archive_match.group(1))

    id_match = FILE_ID_RE.search(line)
    if id_match and not file_id:
        file_id = id_match.group(1).lower()

    index_match = INDEX_RE.search(line)
    if index_match and index is None:
        index = parse_int(index_match.group(1))

    offset_match = OFFSET_RE.search(line)
    if offset_match:
        offset = parse_int(offset_match.group(1))

    return {"archive": archive, "file_id": file_id, "index": index, "offset": offset, "layout": layout}


def parse_row_hint(row: dict[str, str]) -> dict[str, str | int | None]:
    merged = " ".join(f"{key}={value}" for key, value in row.items() if value)
    hint = parse_line_hint(merged)
    archive_keys = ["archive", "source_archive", "runtime_first_archive", "name", "path", "mix", "mix_path"]
    for key in archive_keys:
        if row.get(key) and not hint["archive"]:
            match = ARCHIVE_RE.search(row[key])
            if match:
                hint["archive"] = archive_name(match.group(1))
                break
    for key in ["file_id", "id", "hash"]:
        value = row.get(key, "").strip()
        if value and not hint["file_id"]:
            value = value.removeprefix("0x").lower()
            if re.fullmatch(r"[0-9a-f]{8}", value):
                hint["file_id"] = value
                break
    for key in ["index", "entry"]:
        if row.get(key) and hint["index"] is None:
            hint["index"] = parse_int(row[key])
            break
    for key in ["offset", "seek", "pos", "file_offset"]:
        if row.get(key) and hint["offset"] is None:
            hint["offset"] = parse_int(row[key])
            break
    for key in ["layout", "source_layout", "mix_layout"]:
        if row.get(key) and not hint["layout"]:
            hint["layout"] = row[key].strip().lower()
            break
    return hint


def read_trace_file(path: Path) -> list[tuple[str, dict[str, str | int | None]]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []

    if ("," in lines[0] or "\t" in lines[0]) and any(name in lines[0].lower() for name in ("archive", "file_id", "index", "offset")):
        delimiter = "\t" if "\t" in lines[0] else ","
        rows = list(csv.DictReader(lines, delimiter=delimiter))
        return [(f"{path}:{idx + 2}", parse_row_hint(row)) for idx, row in enumerate(rows)]

    return [(f"{path}:{idx + 1}", parse_line_hint(line)) for idx, line in enumerate(lines)]


def make_request(match: dict[str, str], args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "key": match["key"],
        "action": "decode",
        "fullhd": True,
        "fit": args.fit,
        "filter": args.filter,
        "fast_png": True,
        "preserve_decode_dir": True,
        "source": "trace_bridge",
        "trace_match": match,
    }
    if args.max_frames and args.max_frames > 0:
        payload["max_frames"] = args.max_frames
    if args.width:
        payload["width"] = args.width
    if args.height:
        payload["height"] = args.height
    return payload


def process_request(args: argparse.Namespace) -> int:
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
    completed = subprocess.run(command, cwd=BASE_DIR, check=False)
    return completed.returncode


def write_event(args: argparse.Namespace, selected: dict[str, str], payload: dict[str, Any], returncode: int | None) -> None:
    decode_dir = args.cache_root / selected["archive"].upper() / selected["file_id"].lower() / "decode"
    event = {
        "event_id": time.time_ns(),
        "event_time": time.time(),
        "status": "decoded" if returncode == 0 else "request_written" if returncode is None else "decode_failed",
        "process_returncode": returncode,
        "key": selected["key"],
        "archive": selected["archive"],
        "file_id": selected["file_id"],
        "offset": selected["offset"],
        "index": selected["index"],
        "method": selected["method"],
        "source": selected["source"],
        "request_file": str(args.request_file),
        "result_file": str(args.result_file),
        "decode_dir": str(decode_dir),
        "request": payload,
        "match": selected,
    }
    append_jsonl(args.event_log, event)
    write_json(args.latest_event_file, event)


def resolution_context(args: argparse.Namespace) -> tuple[
    dict[tuple[str, int], dict[str, str]],
    dict[str, dict[str, str]],
    dict[str, list[dict[str, str]]],
    dict[tuple[str, int], OriginalEntry],
    dict[str, list[OriginalEntry]],
]:
    manifest = read_json(args.manifest)
    manifest_by_index, manifest_by_key, manifest_by_archive = manifest_indexes(manifest)
    originals_by_index, originals_by_archive = original_maps(args.original_root)
    return manifest_by_index, manifest_by_key, manifest_by_archive, originals_by_index, originals_by_archive


def cli_hints(args: argparse.Namespace) -> list[tuple[str, dict[str, str | int | None]]]:
    hints: list[tuple[str, dict[str, str | int | None]]] = []
    if args.key:
        archive, file_id = args.key
        hints.append(("cli:key", {"archive": archive, "file_id": file_id, "index": None, "offset": None}))
    if args.archive:
        hints.append(
            (
                "cli:archive",
                {
                    "archive": archive_name(args.archive),
                    "file_id": args.file_id.lower() if args.file_id else None,
                    "index": args.index,
                    "offset": args.offset,
                    "layout": args.layout,
                },
            )
        )
    for line in args.line:
        hints.append(("cli:line", parse_line_hint(line)))
    if args.trace_file:
        hints.extend(read_trace_file(args.trace_file))
    return hints


def resolve_hint_rows(
    hints: list[tuple[str, dict[str, str | int | None]]],
    context: tuple[
        dict[tuple[str, int], dict[str, str]],
        dict[str, dict[str, str]],
        dict[str, list[dict[str, str]]],
        dict[tuple[str, int], OriginalEntry],
        dict[str, list[OriginalEntry]],
    ],
) -> list[dict[str, str]]:
    manifest_by_index, manifest_by_key, manifest_by_archive, originals_by_index, originals_by_archive = context
    matches = [
        resolve_hint(
            source,
            manifest_by_index,
            manifest_by_key,
            manifest_by_archive,
            originals_by_index,
            originals_by_archive,
            archive=hint.get("archive") if isinstance(hint.get("archive"), str) else None,
            file_id=hint.get("file_id") if isinstance(hint.get("file_id"), str) else None,
            index=hint.get("index") if isinstance(hint.get("index"), int) else None,
            offset=hint.get("offset") if isinstance(hint.get("offset"), int) else None,
            layout=hint.get("layout") if isinstance(hint.get("layout"), str) else None,
        )
        for source, hint in hints
    ]
    return [match for match in matches if match["status"] == "pass"] or matches


def resolve_matches(args: argparse.Namespace) -> list[dict[str, str]]:
    return resolve_hint_rows(cli_hints(args), resolution_context(args))


def emit(args: argparse.Namespace, matches: list[dict[str, str]]) -> int:
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "matches.csv", matches)
    pass_matches = [match for match in matches if match["status"] == "pass"]
    if not pass_matches:
        print(json.dumps({"status": "gap", "matches": matches}, ensure_ascii=True, indent=2))
        return 2

    selected = pass_matches[-1] if args.latest else pass_matches[0]
    payload = make_request(selected, args)
    write_json(args.request_file, payload)
    write_json(args.output / "last_request.json", payload)
    print(json.dumps({"status": "pass", "selected": selected, "request_file": str(args.request_file)}, ensure_ascii=True, indent=2))
    write_event(args, selected, payload, None)
    if args.process:
        returncode = process_request(args)
        write_event(args, selected, payload, returncode)
        return returncode
    return 0


def watch(args: argparse.Namespace) -> int:
    if not args.trace_file:
        raise SystemExit("--watch demande --trace-file")
    print(f"Bridge trace sidecar actif: {args.trace_file}")
    print(f"Requete sidecar: {args.request_file}")
    context = resolution_context(args)
    offset = 0
    line_no = 0
    buffer = ""
    last_event = ""
    seen_keys: set[str] = set()
    while True:
        try:
            stat = args.trace_file.stat()
        except FileNotFoundError:
            time.sleep(args.poll)
            continue
        if stat.st_size < offset:
            offset = 0
            line_no = 0
            buffer = ""
            last_event = ""
            seen_keys.clear()
        with args.trace_file.open(encoding="utf-8", errors="replace") as handle:
            handle.seek(offset)
            chunk = handle.read()
            offset = handle.tell()
        if not chunk:
            time.sleep(args.poll)
            continue
        buffer += chunk
        lines = buffer.splitlines(keepends=True)
        buffer = ""
        if lines and not lines[-1].endswith(("\n", "\r")):
            buffer = lines.pop()
        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            line_no += 1
            matches = resolve_hint_rows([(f"{args.trace_file}:{line_no}", parse_line_hint(line))], context)
            pass_matches = [match for match in matches if match["status"] == "pass"]
            if pass_matches:
                selected = pass_matches[-1]
                if args.dedupe_key and selected["key"] in seen_keys:
                    continue
                seen_keys.add(selected["key"])
                event = f"{selected['key']}|{selected['source']}|{selected['offset']}"
                if event != last_event:
                    last_event = event
                    emit(args, [selected])
        time.sleep(args.poll)


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve VQA trace hints into external sidecar requests.")
    parser.add_argument("--key", type=parse_key, help="Direct key, for example HERB.MIX:98e2ff4f.")
    parser.add_argument("--archive", help="MIX archive name used with --file-id, --index, or --offset.")
    parser.add_argument("--file-id", help="8 hex character Westwood file id.")
    parser.add_argument("--index", type=int, help="MIX entry index.")
    parser.add_argument("--offset", type=parse_int, help="Absolute or body-relative MIX file offset.")
    parser.add_argument("--layout", choices=("original", "hd", "unknown"), help="Offset layout when --offset is ambiguous.")
    parser.add_argument("--line", action="append", default=[], help="One trace line to parse. Can be repeated.")
    parser.add_argument("--trace-file", type=Path, help="Trace/log/CSV/TSV file to parse.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--original-root", type=Path, default=DEFAULT_ORIGINAL_ROOT)
    parser.add_argument("--runtime-dir", type=Path, default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--request-file", type=Path)
    parser.add_argument("--result-file", type=Path)
    parser.add_argument("--event-log", type=Path)
    parser.add_argument("--latest-event-file", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--max-frames", type=int, default=16, help="Frame limit for decode; 0 means all frames.")
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--fit", choices=("contain", "cover", "stretch"), default="stretch")
    parser.add_argument("--filter", choices=("nearest", "bilinear", "bicubic", "lanczos"), default="nearest")
    parser.add_argument("--latest", action="store_true", help="Use the latest passing match instead of the first.")
    parser.add_argument("--process", action="store_true", help="Immediately run the sidecar request decoder.")
    parser.add_argument("--watch", action="store_true", help="Watch --trace-file and emit/process new requests.")
    parser.add_argument("--dedupe-key", action="store_true", help="In watch mode, emit at most one request per ARCHIVE:FILE_ID key.")
    parser.add_argument("--poll", type=float, default=0.5)
    args = parser.parse_args()

    args.request_file = args.request_file or args.runtime_dir / "request.json"
    args.result_file = args.result_file or args.runtime_dir / "result.json"
    args.event_log = args.event_log or args.runtime_dir / "events.jsonl"
    args.latest_event_file = args.latest_event_file or args.runtime_dir / "latest_event.json"

    if args.watch:
        raise SystemExit(watch(args))

    matches = resolve_matches(args)
    raise SystemExit(emit(args, matches))


if __name__ == "__main__":
    main()
