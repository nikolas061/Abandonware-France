#!/usr/bin/env python3
"""Extract one VQA payload from the external sidecar manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


DEFAULT_MANIFEST = Path("output/vqa_external_sidecar_index/manifest.json")


def parse_key(value: str) -> tuple[str, str]:
    if ":" not in value:
        raise argparse.ArgumentTypeError("key must be ARCHIVE:FILE_ID, for example MOVIES.MIX:b3593d3c")
    archive, file_id = value.split(":", 1)
    archive = archive.upper()
    if not archive.endswith(".MIX"):
        archive = f"{archive}.MIX"
    file_id = file_id.lower()
    if len(file_id) != 8:
        raise argparse.ArgumentTypeError("FILE_ID must be 8 hex characters")
    int(file_id, 16)
    return archive, file_id


def choose_entry(rows: list[dict[str, str]], variant: str | None) -> dict[str, str]:
    if variant:
        for row in rows:
            if row.get("variant") == variant:
                return row
        raise SystemExit(f"Variant introuvable pour cette cle: {variant}")
    return rows[0]


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract a VQA payload by ARCHIVE:FILE_ID from a sidecar manifest.")
    parser.add_argument("key", type=parse_key)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--variant", help="Preferred manifest variant, for example mod_mix_vqa_fullhd")
    parser.add_argument("--output", type=Path, help="Output .vqa path. Defaults to output/vqa_external_sidecar_extract/<archive>/<id>.vqa")
    args = parser.parse_args()

    archive, file_id = args.key
    if not args.manifest.is_file():
        raise SystemExit(f"Manifest introuvable: {args.manifest}")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    key = f"{archive}:{file_id}"
    rows = manifest.get("by_key", {}).get(key, [])
    if not rows:
        raise SystemExit(f"Entree sidecar introuvable: {key}")
    row = choose_entry(rows, args.variant)
    mix_path = Path(row["mix_path"])
    offset = int(row["file_offset"])
    size = int(row["size"])
    output = args.output or Path("output/vqa_external_sidecar_extract") / archive / f"{file_id}.vqa"
    output.parent.mkdir(parents=True, exist_ok=True)
    with mix_path.open("rb") as handle:
        handle.seek(offset)
        payload = handle.read(size)
    if len(payload) != size:
        raise SystemExit(f"Lecture incomplete depuis {mix_path}: {len(payload)}/{size}")
    output.write_bytes(payload)
    print(f"Extracted {key} -> {output} ({size} bytes)")


if __name__ == "__main__":
    main()
