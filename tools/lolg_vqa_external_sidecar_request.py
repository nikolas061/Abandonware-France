#!/usr/bin/env python3
"""Resolve, cache, and optionally decode one HD VQA from the external sidecar index."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = BASE_DIR / "output/vqa_external_sidecar_index/manifest.json"
DEFAULT_CACHE_ROOT = BASE_DIR / "output/vqa_external_sidecar_cache"
DECODE_TOOL = BASE_DIR / "tools/lolg_vqa_decode.py"


def parse_key(value: str) -> tuple[str, str]:
    if ":" not in value:
        raise argparse.ArgumentTypeError("key must be ARCHIVE:FILE_ID, for example HERB.MIX:98e2ff4f")
    archive, file_id = value.split(":", 1)
    archive = archive.upper()
    if not archive.endswith(".MIX"):
        archive = f"{archive}.MIX"
    file_id = file_id.lower()
    if len(file_id) != 8:
        raise argparse.ArgumentTypeError("FILE_ID must be 8 hex characters")
    int(file_id, 16)
    return archive, file_id


def key_string(key: tuple[str, str]) -> str:
    return f"{key[0]}:{key[1]}"


def existing_file(value: str) -> Path:
    path = Path(value)
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"file not found: {path}")
    return path


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"JSON invalide dans {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"JSON invalide dans {path}: objet attendu")
    return payload


def resolve_repo_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return BASE_DIR / path


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SystemExit(f"Manifest sidecar introuvable: {path}")
    return load_json(path)


def choose_entry(rows: list[dict[str, str]], variant: str | None) -> dict[str, str]:
    if variant:
        for row in rows:
            if row.get("variant") == variant:
                return row
        raise SystemExit(f"Variant introuvable pour cette cle: {variant}")
    return rows[0]


def choose_smallest_entry(manifest: dict[str, Any], variant: str | None) -> dict[str, str]:
    entries = manifest.get("entries", [])
    if not isinstance(entries, list):
        raise SystemExit("Manifest invalide: liste entries absente")
    candidates: list[dict[str, str]] = []
    for row in entries:
        if not isinstance(row, dict):
            continue
        if variant and row.get("variant") != variant:
            continue
        if row.get("form_type") != "WVQA":
            continue
        if not str(row.get("size", "")).isdigit():
            continue
        candidates.append(row)
    if not candidates:
        raise SystemExit("Aucune VQA externe trouvee dans le manifest")
    return min(candidates, key=lambda row: int(row["size"]))


def find_entry(manifest: dict[str, Any], key: tuple[str, str] | None, variant: str | None, smallest: bool) -> dict[str, str]:
    if smallest:
        return choose_smallest_entry(manifest, variant)
    if key is None:
        raise SystemExit("Cle sidecar manquante: utilisez ARCHIVE:FILE_ID ou --smallest")
    rows = manifest.get("by_key", {}).get(key_string(key), [])
    if not rows:
        raise SystemExit(f"Entree sidecar introuvable: {key_string(key)}")
    return choose_entry(rows, variant)


def cache_paths(cache_root: Path, entry: dict[str, str]) -> tuple[Path, Path, Path]:
    archive = entry["archive"].upper()
    file_id = entry["file_id"].lower()
    key_dir = cache_root / archive / file_id
    return key_dir, key_dir / f"{file_id}.vqa", key_dir / "decode"


def copy_span(source: Path, offset: int, size: int, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(output.suffix + ".tmp")
    remaining = size
    with source.open("rb") as src, tmp.open("wb") as dst:
        src.seek(offset)
        while remaining:
            chunk = src.read(min(1024 * 1024, remaining))
            if not chunk:
                tmp.unlink(missing_ok=True)
                raise SystemExit(f"Lecture incomplete depuis {source}: reste {remaining} octets")
            dst.write(chunk)
            remaining -= len(chunk)
    tmp.replace(output)


def ensure_cached(entry: dict[str, str], cache_root: Path, force: bool) -> tuple[Path, str]:
    _key_dir, vqa_path, _decode_dir = cache_paths(cache_root, entry)
    expected_size = int(entry["size"])
    if not force and vqa_path.is_file() and vqa_path.stat().st_size == expected_size:
        return vqa_path, "hit"
    mix_path = resolve_repo_path(entry["mix_path"])
    if not mix_path.is_file():
        raise SystemExit(f"MIX source introuvable: {mix_path}")
    copy_span(mix_path, int(entry["file_offset"]), expected_size, vqa_path)
    return vqa_path, "written"


def decoder_args(vqa_path: Path, decode_dir: Path, args: argparse.Namespace, request: dict[str, Any]) -> list[str]:
    command = [sys.executable, str(DECODE_TOOL), str(vqa_path), "-o", str(decode_dir)]
    max_frames = args.max_frames if args.max_frames is not None else request.get("max_frames")
    if max_frames is not None:
        try:
            max_frame_count = int(max_frames)
        except (TypeError, ValueError):
            max_frame_count = 0
        if max_frame_count > 0:
            command.extend(["--max-frames", str(max_frame_count)])
    if args.dump_payloads or request.get("dump_payloads"):
        command.append("--dump-payloads")
    render_frames = args.render_frames or args.fullhd or bool(request.get("render_frames")) or bool(request.get("fullhd"))
    if render_frames:
        command.append("--render-frames")
    if args.fullhd or request.get("fullhd"):
        command.append("--fullhd")
    width = args.width if args.width is not None else request.get("width")
    height = args.height if args.height is not None else request.get("height")
    if width is not None:
        command.extend(["--width", str(width)])
    if height is not None:
        command.extend(["--height", str(height)])
    fit = args.fit or request.get("fit")
    if fit:
        command.extend(["--fit", str(fit)])
    filter_name = args.filter or request.get("filter")
    if filter_name:
        command.extend(["--filter", str(filter_name)])
    if args.fast_png or request.get("fast_png"):
        command.append("--fast-png")
    if args.experimental_window_lcw or request.get("experimental_window_lcw"):
        command.append("--experimental-window-lcw")
    return command


def requested_max_frames(args: argparse.Namespace, request: dict[str, Any]) -> int | None:
    max_frames = args.max_frames if args.max_frames is not None else request.get("max_frames")
    if max_frames is None:
        return None
    try:
        value = int(max_frames)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def rendered_frame_count(decode_dir: Path, fullhd: bool) -> int:
    rendered_csv = decode_dir / "rendered_frames.csv"
    if rendered_csv.is_file():
        with rendered_csv.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        output_key = "fullhd_output" if fullhd else "native_output"
        return sum(1 for row in rows if row.get(output_key) or row.get("native_output"))
    frame_dir = decode_dir / ("frames_fullhd" if fullhd else "frames_native")
    return len(list(frame_dir.glob("*.png"))) if frame_dir.is_dir() else 0


def decode_ready(entry: dict[str, str], decode_dir: Path, args: argparse.Namespace, request: dict[str, Any]) -> bool:
    if args.force or not decode_dir.is_dir():
        return False
    fullhd = bool(args.fullhd or request.get("fullhd"))
    expected_total = int(entry["frames"]) if str(entry.get("frames", "")).isdigit() else None
    requested = requested_max_frames(args, request)
    required = requested if requested is not None else expected_total
    if required is None:
        return False
    return rendered_frame_count(decode_dir, fullhd) >= required


def should_decode(args: argparse.Namespace, request: dict[str, Any]) -> bool:
    if args.decode:
        return True
    action = str(request.get("action", "")).lower()
    return action in {"decode", "render", "prepare_frames"} or bool(request.get("decode"))


def should_preserve_decode_dir(args: argparse.Namespace, request: dict[str, Any]) -> bool:
    if args.force:
        return False
    return args.preserve_decode_dir or bool(request.get("preserve_decode_dir"))


def write_result(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cache and optionally decode an HD VQA entry from the external sidecar index.")
    parser.add_argument("key", nargs="?", type=parse_key, help="ARCHIVE:FILE_ID, for example HERB.MIX:98e2ff4f")
    parser.add_argument("--smallest", action="store_true", help="Use the smallest VQA in the manifest, useful for smoke tests.")
    parser.add_argument("--request-file", type=existing_file, help="JSON request file. Supports key/action/max_frames/fullhd.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--variant", help="Preferred manifest variant, for example mod_mix_vqa_fullhd")
    parser.add_argument("--force", action="store_true", help="Refresh the cached VQA even if the size already matches.")
    parser.add_argument("--decode", action="store_true", help="Run the VQA decoder after caching.")
    parser.add_argument("--max-frames", type=int, help="Maximum frames to decode; 0 means decode all frames.")
    parser.add_argument("--render-frames", action="store_true")
    parser.add_argument("--fullhd", action="store_true")
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--fit", choices=("contain", "cover", "stretch"))
    parser.add_argument("--filter", choices=("nearest", "bilinear", "bicubic", "lanczos"))
    parser.add_argument("--fast-png", action="store_true")
    parser.add_argument("--dump-payloads", action="store_true")
    parser.add_argument("--experimental-window-lcw", action="store_true")
    parser.add_argument("--preserve-decode-dir", action="store_true", help="Keep existing decoded frames while extending or refreshing a decode.")
    parser.add_argument("--result-file", type=Path, help="Where to write the JSON result. Defaults to the cache entry directory.")
    args = parser.parse_args()

    request: dict[str, Any] = {}
    key = args.key
    if args.request_file:
        request = load_json(args.request_file)
        if key is None and request.get("key"):
            key = parse_key(str(request["key"]))

    manifest = load_manifest(args.manifest)
    entry = find_entry(manifest, key, args.variant or request.get("variant"), args.smallest)
    key_dir, vqa_path, decode_dir = cache_paths(args.cache_root, entry)
    cached_vqa, cache_status = ensure_cached(entry, args.cache_root, args.force)
    result_file = args.result_file or key_dir / "result.json"

    result: dict[str, Any] = {
        "status": "cached",
        "key": f"{entry['archive']}:{entry['file_id']}",
        "variant": entry.get("variant", ""),
        "archive": entry["archive"],
        "file_id": entry["file_id"],
        "size": int(entry["size"]),
        "width": int(entry["width"]) if str(entry.get("width", "")).isdigit() else None,
        "height": int(entry["height"]) if str(entry.get("height", "")).isdigit() else None,
        "frames": int(entry["frames"]) if str(entry.get("frames", "")).isdigit() else None,
        "risk": entry.get("risk", ""),
        "cache_status": cache_status,
        "cached_vqa": str(cached_vqa),
        "decode_dir": str(decode_dir),
    }

    decode_requested = should_decode(args, request)
    if decode_requested and decode_ready(entry, decode_dir, args, request):
        result["status"] = "decoded"
        result["decode_cache_status"] = "hit"
        result["decoder_returncode"] = 0
        result["decoder_command"] = ["cached_decode_reused"]
    elif decode_requested:
        result_file.unlink(missing_ok=True)
        preserve_decode = should_preserve_decode_dir(args, request)
        if decode_dir.exists() and not preserve_decode:
            shutil.rmtree(decode_dir)
        decode_dir.mkdir(parents=True, exist_ok=True)
        command = decoder_args(vqa_path, decode_dir, args, request)
        result["decoder_command"] = command
        result["decode_dir_preserved"] = preserve_decode
        result["decode_started_at"] = time.time()
        result["status"] = "decoding"
        result["message"] = "Decodage VQA en cours"
        write_result(result_file, result)
        completed = subprocess.run(command, cwd=BASE_DIR, check=False)
        result["decode_finished_at"] = time.time()
        result["decoder_returncode"] = completed.returncode
        result["status"] = "decoded" if completed.returncode == 0 else "decode_failed"
        result["message"] = "Decodage VQA termine" if completed.returncode == 0 else "Echec du decodage VQA"
        if completed.returncode != 0:
            write_result(result_file, result)
            print(json.dumps(result, ensure_ascii=True, indent=2))
            raise SystemExit(completed.returncode)

    (key_dir / "entry.json").write_text(json.dumps(entry, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    write_result(result_file, result)
    if args.request_file:
        shutil.copyfile(args.request_file, key_dir / "request.json")
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
