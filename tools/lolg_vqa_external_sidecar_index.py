#!/usr/bin/env python3
"""Build an external sidecar index for HD VQA payloads kept outside LOLG95."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import struct
from pathlib import Path


DEFAULT_HD_ROOT = Path("mod_mix_vqa_fullhd")
DEFAULT_ORIGINAL_ROOT = Path("C/LOLG")
DEFAULT_OUTPUT = Path("output/vqa_external_sidecar_index")

SUMMARY_FIELDS = [
    "status",
    "hd_roots",
    "original_root",
    "mix_archives",
    "entries",
    "vqa_entries",
    "total_payload_bytes",
    "hard_2g_archives",
    "risky_vqa_entries",
    "scan_chunks",
    "issues",
    "next_step",
]

ENTRY_FIELDS = [
    "variant",
    "archive",
    "index",
    "file_id",
    "mix_path",
    "file_offset",
    "size",
    "sha256_head",
    "form_type",
    "width",
    "height",
    "frames",
    "fps",
    "blocks",
    "max_vqfr_size",
    "max_vptz_size",
    "original_size",
    "original_width",
    "original_height",
    "original_blocks",
    "risk",
    "status",
    "issues",
]

ARCHIVE_FIELDS = [
    "variant",
    "archive",
    "mix_path",
    "file_size",
    "body_size",
    "entry_count",
    "vqa_entries",
    "hard_2g",
    "issues",
]


def be32(data: bytes) -> int:
    return struct.unpack(">I", data)[0]


def le16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_exact(handle, offset: int, size: int) -> bytes:
    handle.seek(offset)
    data = handle.read(size)
    if len(data) != size:
        raise EOFError(f"short read at {offset}: wanted {size}, got {len(data)}")
    return data


def mix_table(path: Path) -> tuple[int, int, int, list[tuple[int, int, int, int]]]:
    with path.open("rb") as handle:
        header = handle.read(6)
        if len(header) != 6:
            raise ValueError("short MIX header")
        count, body_size = struct.unpack("<HI", header)
        table_end = 6 + count * 12
        rows: list[tuple[int, int, int, int]] = []
        for index in range(count):
            raw = handle.read(12)
            if len(raw) != 12:
                raise ValueError("short MIX table")
            file_id, offset, size = struct.unpack("<III", raw)
            rows.append((index, file_id, offset, size))
    return count, body_size, table_end, rows


def parse_vqhd(payload: bytes) -> dict[str, int]:
    return {
        "frames": le16(payload, 4),
        "width": le16(payload, 6),
        "height": le16(payload, 8),
        "block_width": payload[10],
        "block_height": payload[11],
        "fps": payload[12],
    }


def scan_vqa_metadata(path: Path, absolute_offset: int, size: int, scan_chunks: bool) -> tuple[dict[str, str], str]:
    metadata = {
        "form_type": "",
        "width": "",
        "height": "",
        "frames": "",
        "fps": "",
        "blocks": "",
        "max_vqfr_size": "",
        "max_vptz_size": "",
    }
    with path.open("rb") as handle:
        if size < 12:
            return metadata, ""
        first = read_exact(handle, absolute_offset, 12)
        if first[:4] != b"FORM":
            return metadata, ""
        form_type = first[8:12].decode("ascii", errors="replace")
        metadata["form_type"] = form_type
        if form_type != "WVQA":
            return metadata, form_type

        limit = min(size, 8 + be32(first[4:8]))
        pos = 12
        max_vqfr = 0
        max_vptz = 0
        while pos + 8 <= limit:
            chunk_header = read_exact(handle, absolute_offset + pos, 8)
            chunk_id = chunk_header[:4].decode("ascii", errors="replace")
            chunk_size = be32(chunk_header[4:8])
            payload_start = pos + 8
            payload_end = payload_start + chunk_size
            if payload_end > limit:
                break
            if chunk_id == "VQHD" and chunk_size == 42:
                header = parse_vqhd(read_exact(handle, absolute_offset + payload_start, 42))
                block_width = header["block_width"]
                block_height = header["block_height"]
                blocks = 0
                if block_width and block_height:
                    blocks = (header["width"] // block_width) * (header["height"] // block_height)
                metadata.update(
                    {
                        "width": str(header["width"]),
                        "height": str(header["height"]),
                        "frames": str(header["frames"]),
                        "fps": str(header["fps"]),
                        "blocks": str(blocks),
                    }
                )
                if not scan_chunks:
                    break
            if scan_chunks and chunk_id == "VQFR":
                max_vqfr = max(max_vqfr, chunk_size)
                sub_pos = payload_start
                while sub_pos + 8 <= payload_end:
                    sub_header = read_exact(handle, absolute_offset + sub_pos, 8)
                    sub_id = sub_header[:4].decode("ascii", errors="replace")
                    sub_size = be32(sub_header[4:8])
                    sub_end = sub_pos + 8 + sub_size
                    if sub_end > payload_end:
                        break
                    if sub_id == "VPTZ":
                        max_vptz = max(max_vptz, sub_size)
                    sub_pos = sub_end + (sub_size & 1)
            pos = payload_end + (chunk_size & 1)
        if scan_chunks:
            metadata["max_vqfr_size"] = str(max_vqfr) if max_vqfr else ""
            metadata["max_vptz_size"] = str(max_vptz) if max_vptz else ""
    return metadata, metadata["form_type"]


def sha256_head(path: Path, absolute_offset: int, size: int, limit: int = 65536) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        handle.seek(absolute_offset)
        digest.update(handle.read(min(size, limit)))
    return digest.hexdigest()


def archive_name(path: Path) -> str:
    return path.name.upper()


def archive_risk(file_size: int, body_size: int, table: list[tuple[int, int, int, int]]) -> bool:
    max_end = max((offset + size for _, _, offset, size in table), default=0)
    return file_size >= 0x80000000 or body_size >= 0x80000000 or max_end >= 0x80000000


def make_risk(row: dict[str, str], hard_2g: bool) -> str:
    risks: list[str] = []
    size = int(row["size"])
    blocks = int(row["blocks"] or 0)
    max_vptz = int(row["max_vptz_size"] or 0)
    if hard_2g:
        risks.append("mix_2g")
    if size >= 512 * 1024 * 1024:
        risks.append("entry_512m")
    elif size >= 128 * 1024 * 1024:
        risks.append("entry_128m")
    if blocks > 64000:
        risks.append("blocks_hd")
    if max_vptz > 65535:
        risks.append("vptz_gt_16bit")
    return ",".join(risks)


def scan_root(root: Path, variant: str, original_by_key: dict[tuple[str, str], dict[str, str]], scan_chunks: bool) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    archive_rows: list[dict[str, str]] = []
    entry_rows: list[dict[str, str]] = []
    for path in sorted(root.glob("*.MIX")):
        issues: list[str] = []
        try:
            count, body_size, table_end, table = mix_table(path)
        except Exception as exc:  # noqa: BLE001 - report and continue
            archive_rows.append(
                {
                    "variant": variant,
                    "archive": archive_name(path),
                    "mix_path": str(path),
                    "file_size": str(path.stat().st_size if path.exists() else 0),
                    "body_size": "",
                    "entry_count": "",
                    "vqa_entries": "0",
                    "hard_2g": "0",
                    "issues": f"scan_failed:{type(exc).__name__}:{exc}",
                }
            )
            continue

        file_size = path.stat().st_size
        hard_2g = archive_risk(file_size, body_size, table)
        vqa_count = 0
        for index, file_id, offset, size in table:
            absolute_offset = table_end + offset
            try:
                metadata, form_type = scan_vqa_metadata(path, absolute_offset, size, scan_chunks)
            except Exception as exc:  # noqa: BLE001 - keep the bad entry visible
                metadata = {
                    "form_type": "",
                    "width": "",
                    "height": "",
                    "frames": "",
                    "fps": "",
                    "blocks": "",
                    "max_vqfr_size": "",
                    "max_vptz_size": "",
                }
                form_type = ""
                entry_issues = f"metadata_failed:{type(exc).__name__}:{exc}"
            else:
                entry_issues = ""
            if form_type != "WVQA":
                continue
            vqa_count += 1
            file_id_hex = f"{file_id:08x}"
            key = (archive_name(path), file_id_hex)
            original = original_by_key.get(key, {})
            row = {
                "variant": variant,
                "archive": archive_name(path),
                "index": str(index),
                "file_id": file_id_hex,
                "mix_path": str(path),
                "file_offset": str(absolute_offset),
                "size": str(size),
                "sha256_head": sha256_head(path, absolute_offset, size),
                **metadata,
                "original_size": original.get("size", ""),
                "original_width": original.get("width", ""),
                "original_height": original.get("height", ""),
                "original_blocks": original.get("blocks", ""),
                "risk": "",
                "status": "external_ready",
                "issues": entry_issues,
            }
            row["risk"] = make_risk(row, hard_2g)
            entry_rows.append(row)
        archive_rows.append(
            {
                "variant": variant,
                "archive": archive_name(path),
                "mix_path": str(path),
                "file_size": str(file_size),
                "body_size": str(body_size),
                "entry_count": str(count),
                "vqa_entries": str(vqa_count),
                "hard_2g": "1" if hard_2g else "0",
                "issues": ";".join(issues),
            }
        )
    return archive_rows, entry_rows


def scan_original(root: Path) -> dict[tuple[str, str], dict[str, str]]:
    original: dict[tuple[str, str], dict[str, str]] = {}
    for path in sorted(root.glob("*.MIX")):
        try:
            _, _, table_end, table = mix_table(path)
        except Exception:
            continue
        for index, file_id, offset, size in table:
            absolute_offset = table_end + offset
            try:
                metadata, form_type = scan_vqa_metadata(path, absolute_offset, size, False)
            except Exception:
                continue
            if form_type != "WVQA":
                continue
            key = (archive_name(path), f"{file_id:08x}")
            original[key] = {
                "archive": archive_name(path),
                "index": str(index),
                "file_id": f"{file_id:08x}",
                "size": str(size),
                **metadata,
            }
    return original


def write_manifest(path: Path, summary: dict[str, str], archives: list[dict[str, str]], entries: list[dict[str, str]]) -> None:
    by_key: dict[str, list[dict[str, str]]] = {}
    for row in entries:
        key = f"{row['archive']}:{row['file_id']}"
        by_key.setdefault(key, []).append(row)
    payload = {
        "summary": summary,
        "archives": archives,
        "entries": entries,
        "by_key": by_key,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def render_table(rows: list[dict[str, str]], fields: list[str]) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def write_html(path: Path, summary: dict[str, str], archives: list[dict[str, str]], entries: list[dict[str, str]]) -> None:
    risky = [row for row in entries if row.get("risk")]
    sample = sorted(risky, key=lambda row: int(row["size"]), reverse=True)[:100]
    data_json = json.dumps({"summary": summary, "archives": archives, "risky_entries": sample}, ensure_ascii=True)
    page = f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>LOLG95 VQA External Sidecar Index</title>
  <style>
    body {{ font-family: sans-serif; margin: 24px; color: #1d1d1f; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
    th, td {{ border: 1px solid #ddd; padding: 4px 6px; text-align: left; }}
    th {{ background: #f1f3f5; position: sticky; top: 0; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px; margin: 16px 0; }}
    .stat {{ border: 1px solid #ddd; padding: 10px; border-radius: 4px; }}
    .label {{ color: #666; font-size: 12px; }}
    .value {{ font-size: 20px; font-weight: 700; }}
  </style>
</head>
<body>
  <h1>LOLG95 VQA External Sidecar Index</h1>
  <div class="grid">
    <div class="stat"><div class="label">Status</div><div class="value">{html.escape(summary['status'])}</div></div>
    <div class="stat"><div class="label">Archives</div><div class="value">{html.escape(summary['mix_archives'])}</div></div>
    <div class="stat"><div class="label">VQA externes</div><div class="value">{html.escape(summary['vqa_entries'])}</div></div>
    <div class="stat"><div class="label">Payload bytes</div><div class="value">{html.escape(summary['total_payload_bytes'])}</div></div>
  </div>
  <h2>Archives</h2>
  {render_table(archives, ARCHIVE_FIELDS)}
  <h2>Entrees a risque / prioritaires</h2>
  {render_table(sample, ENTRY_FIELDS)}
  <script type="application/json" id="lolg-vqa-external-sidecar-index">{html.escape(data_json)}</script>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an external VQA sidecar index for LOLG95 HD assets.")
    parser.add_argument("--hd-root", action="append", type=Path, default=[], help="Directory containing HD MIX files. Can be repeated.")
    parser.add_argument("--original-root", type=Path, default=DEFAULT_ORIGINAL_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--scan-chunks", action="store_true", help="Also scan VQFR/VPTZ chunk maxima. Slower, but useful for risk reports.")
    args = parser.parse_args()

    hd_roots = args.hd_root or [DEFAULT_HD_ROOT]
    original = scan_original(args.original_root)

    archive_rows: list[dict[str, str]] = []
    entry_rows: list[dict[str, str]] = []
    issues: list[str] = []
    for root in hd_roots:
        if not root.exists():
            issues.append(f"missing_hd_root:{root}")
            continue
        variant = root.name
        archives, entries = scan_root(root, variant, original, args.scan_chunks)
        archive_rows.extend(archives)
        entry_rows.extend(entries)

    hard_2g = [row for row in archive_rows if row.get("hard_2g") == "1"]
    risky = [row for row in entry_rows if row.get("risk")]
    total_payload = sum(int(row["size"]) for row in entry_rows)
    status = "pass" if entry_rows and not issues else "gap"
    summary = {
        "status": status,
        "hd_roots": ",".join(str(root) for root in hd_roots),
        "original_root": str(args.original_root),
        "mix_archives": str(len(archive_rows)),
        "entries": str(sum(int(row.get("entry_count", "0") or 0) for row in archive_rows)),
        "vqa_entries": str(len(entry_rows)),
        "total_payload_bytes": str(total_payload),
        "hard_2g_archives": str(len(hard_2g)),
        "risky_vqa_entries": str(len(risky)),
        "scan_chunks": "1" if args.scan_chunks else "0",
        "issues": ";".join(issues),
        "next_step": "connect a DirectDraw/window hook to this manifest and request entries by ARCHIVE:FILE_ID",
    }

    write_csv(args.output / "summary.csv", SUMMARY_FIELDS, [summary])
    write_csv(args.output / "archives.csv", ARCHIVE_FIELDS, archive_rows)
    write_csv(args.output / "entries.csv", ENTRY_FIELDS, entry_rows)
    write_manifest(args.output / "manifest.json", summary, archive_rows, entry_rows)
    write_html(args.output / "index.html", summary, archive_rows, entry_rows)
    print(f"VQA external sidecar index: {summary['status']} ({summary['vqa_entries']} VQA entries)")


if __name__ == "__main__":
    main()
