#!/usr/bin/env python3
"""Build a sidecar MIX plan for VQA replacements that cannot fit in-place."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import struct
from collections import defaultdict
from pathlib import Path


DEFAULT_ENTRIES = Path("output/vqa_runtime_pack_build_lcw_compact_report/entries.csv")
DEFAULT_OUTPUT = Path("output/vqa_runtime_sidecar_pack")
DEFAULT_SIDECAR_ROOT = Path("mod_mix_vqa_fullhd_sidecar")
MAX_MIX_COUNT = 0xFFFF
MAX_MIX_FIELD = 0xFFFFFFFF

SUMMARY_FIELDS = [
    "status",
    "deferred_entries",
    "source_archives",
    "sidecar_archives",
    "sidecar_entries",
    "report_only",
    "sidecar_root",
    "source_bytes",
    "replacement_bytes",
    "delta_bytes",
    "max_body_bytes",
    "largest_sidecar_body_bytes",
    "output_bytes",
    "issues",
    "next_step",
]

REQUIREMENT_FIELDS = ["requirement", "status", "evidence", "next_step"]

ARCHIVE_FIELDS = [
    "source_archive",
    "sidecar_archive",
    "sidecar_path",
    "entries",
    "body_bytes",
    "output_bytes",
    "output_written",
    "output_sha256",
    "issues",
]

ENTRY_FIELDS = [
    "source_archive",
    "index",
    "file_id",
    "source_size",
    "replacement_path",
    "replacement_size",
    "sidecar_archive",
    "sidecar_path",
    "status",
    "issues",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, str], field: str) -> int:
    try:
        return int(row.get(field, "0") or 0)
    except ValueError:
        return 0


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def archive_stem(value: str) -> str:
    path = Path(value)
    return path.stem or path.name or value


def selected_rows(entries: Path, status_filter: str) -> list[dict[str, str]]:
    rows = []
    for row in read_csv(entries):
        if row.get("status") != status_filter:
            continue
        replacement_path = Path(row.get("replacement_path", ""))
        issues: list[str] = []
        if not replacement_path.is_file():
            issues.append("missing_replacement_payload")
        replacement_size = replacement_path.stat().st_size if replacement_path.is_file() else 0
        rows.append(
            {
                "source_archive": row.get("archive", ""),
                "index": row.get("index", ""),
                "file_id": row.get("file_id", "").lower(),
                "source_size": row.get("source_size", ""),
                "replacement_path": str(replacement_path),
                "replacement_size": str(replacement_size),
                "issues": ";".join(issues),
            }
        )
    rows.sort(key=lambda row: (row["source_archive"], int_value(row, "index"), row["file_id"]))
    return rows


def sidecar_name(source_archive: str, part_index: int) -> str:
    suffix = "_HD" if part_index == 1 else f"_HD{part_index}"
    return f"{archive_stem(source_archive)}{suffix}.MIX"


def make_plan(rows: list[dict[str, str]], root: Path, max_body_bytes: int) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    archive_rows: list[dict[str, str]] = []
    entry_rows: list[dict[str, str]] = []
    rows_by_archive: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        rows_by_archive[row["source_archive"]].append(row)

    for source_archive, source_rows in sorted(rows_by_archive.items()):
        part_index = 1
        current: list[dict[str, str]] = []
        current_body = 0

        def flush_part() -> None:
            nonlocal current, current_body, part_index
            if not current:
                return
            name = sidecar_name(source_archive, part_index)
            path = root / name
            archive_rows.append(
                {
                    "source_archive": source_archive,
                    "sidecar_archive": name,
                    "sidecar_path": str(path),
                    "entries": str(len(current)),
                    "body_bytes": str(current_body),
                    "output_bytes": str(6 + len(current) * 12 + current_body),
                    "output_written": "0",
                    "output_sha256": "",
                    "issues": "",
                }
            )
            for row in current:
                item = dict(row)
                item["sidecar_archive"] = name
                item["sidecar_path"] = str(path)
                item["status"] = "sidecar_ready" if not item.get("issues") else "sidecar_invalid"
                entry_rows.append(item)
            part_index += 1
            current = []
            current_body = 0

        for row in source_rows:
            size = int_value(row, "replacement_size")
            if size > max_body_bytes:
                item = dict(row)
                item["sidecar_archive"] = ""
                item["sidecar_path"] = ""
                item["status"] = "sidecar_invalid"
                item["issues"] = ";".join(part for part in [item.get("issues", ""), "replacement_exceeds_mix_body"] if part)
                entry_rows.append(item)
                continue
            if current and current_body + size > max_body_bytes:
                flush_part()
            current.append(row)
            current_body += size
        flush_part()

    return archive_rows, entry_rows


def build_mix_bytes(entries: list[dict[str, str]]) -> bytes:
    if len(entries) > MAX_MIX_COUNT:
        raise ValueError(f"mix_entry_count_too_large:{len(entries)}:max:{MAX_MIX_COUNT}")
    payloads: list[tuple[int, bytes]] = []
    body_size = 0
    for row in entries:
        file_id = int(row["file_id"], 16)
        payload = Path(row["replacement_path"]).read_bytes()
        if len(payload) > MAX_MIX_FIELD:
            raise ValueError(f"mix_entry_too_large:{len(payload)}:max:{MAX_MIX_FIELD}")
        if body_size + len(payload) > MAX_MIX_FIELD:
            raise ValueError(f"mix_body_too_large:{body_size + len(payload)}:max:{MAX_MIX_FIELD}")
        payloads.append((file_id, payload))
        body_size += len(payload)

    table = bytearray()
    body = bytearray()
    offset = 0
    for file_id, payload in payloads:
        table.extend(struct.pack("<III", file_id, offset, len(payload)))
        body.extend(payload)
        offset += len(payload)
    return struct.pack("<HI", len(payloads), body_size) + table + body


def write_sidecars(archive_rows: list[dict[str, str]], entry_rows: list[dict[str, str]]) -> None:
    entries_by_path: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in entry_rows:
        if row.get("status") == "sidecar_ready":
            entries_by_path[row["sidecar_path"]].append(row)

    archive_by_path = {row["sidecar_path"]: row for row in archive_rows}
    for sidecar_path, rows in entries_by_path.items():
        path = Path(sidecar_path)
        archive_row = archive_by_path[sidecar_path]
        try:
            data = build_mix_bytes(rows)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            archive_row["output_written"] = "1"
            archive_row["output_sha256"] = sha256_bytes(data)
            archive_row["output_bytes"] = str(len(data))
        except Exception as exc:  # noqa: BLE001 - report and keep other sidecars buildable
            detail = str(exc).replace("\n", " ").replace(";", ",")
            archive_row["issues"] = f"write_failed:{type(exc).__name__}:{detail}"


def render_table(rows: list[dict[str, str]], fields: list[str]) -> str:
    head = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def write_html(
    path: Path,
    summary: dict[str, str],
    requirements: list[dict[str, str]],
    archives: list[dict[str, str]],
    entries: list[dict[str, str]],
) -> None:
    payload = {
        "summary": summary,
        "requirements": requirements,
        "archives": archives,
        "entries": entries,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    page = f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>VQA Runtime Sidecar Pack</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; background: #f7f7f3; color: #1f2933; }}
    h1, h2 {{ margin-bottom: 0.4rem; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }}
    .stat {{ background: white; border: 1px solid #d7d7ce; border-radius: 6px; padding: 12px; }}
    .label {{ color: #5f6b76; font-size: 0.85rem; }}
    .value {{ font-size: 1.35rem; font-weight: 700; }}
    table {{ border-collapse: collapse; width: 100%; background: white; margin: 12px 0 24px; }}
    th, td {{ border: 1px solid #d7d7ce; padding: 6px 8px; text-align: left; font-size: 0.86rem; }}
    th {{ background: #ecece4; }}
  </style>
</head>
<body>
  <h1>VQA Runtime Sidecar Pack</h1>
  <div class="grid">
    <div class="stat"><div class="label">Statut</div><div class="value">{html.escape(summary['status'])}</div></div>
    <div class="stat"><div class="label">Entrees sidecar</div><div class="value">{html.escape(summary['sidecar_entries'])}</div></div>
    <div class="stat"><div class="label">Archives sidecar</div><div class="value">{html.escape(summary['sidecar_archives'])}</div></div>
    <div class="stat"><div class="label">Bytes remplacement</div><div class="value">{html.escape(summary['replacement_bytes'])}</div></div>
  </div>
  <h2>Requirements</h2>
  {render_table(requirements, REQUIREMENT_FIELDS)}
  <h2>Archives</h2>
  {render_table(archives, ARCHIVE_FIELDS)}
  <h2>Entrees</h2>
  {render_table(entries, ENTRY_FIELDS)}
  <script type="application/json" id="vqa-runtime-sidecar-pack">{html.escape(data_json)}</script>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")


def build_reports(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    source_rows = selected_rows(args.entries, args.status_filter)
    archive_rows, entry_rows = make_plan(source_rows, args.sidecar_root, args.max_body_bytes)
    if not args.report_only:
        write_sidecars(archive_rows, entry_rows)
    elif archive_rows:
        for row in archive_rows:
            row["output_written"] = "report_only"

    source_bytes = sum(int_value(row, "source_size") for row in entry_rows)
    replacement_bytes = sum(int_value(row, "replacement_size") for row in entry_rows)
    output_bytes = sum(int_value(row, "output_bytes") for row in archive_rows)
    largest_body = max((int_value(row, "body_bytes") for row in archive_rows), default=0)
    invalid_entries = [row for row in entry_rows if row.get("status") != "sidecar_ready"]
    archive_issues = [row for row in archive_rows if row.get("issues")]
    source_archives = {row["source_archive"] for row in source_rows}
    sidecar_pack_ready = bool(source_rows) and not invalid_entries and not archive_issues and bool(archive_rows)
    outputs_written = all(row.get("output_written") == "1" for row in archive_rows) if archive_rows else False

    issues: list[str] = []
    if not source_rows:
        issues.append(f"no_entries_with_status:{args.status_filter}")
    if invalid_entries:
        issues.append(f"invalid_sidecar_entries:{len(invalid_entries)}")
    if archive_issues:
        issues.append(f"sidecar_archive_issues:{len(archive_issues)}")
    issues.append("runtime_loader_missing")

    requirements = [
        {
            "requirement": "deferred_payload_selection",
            "status": "pass" if source_rows else "gap",
            "evidence": f"entries={len(source_rows)};status_filter={args.status_filter}",
            "next_step": "feed the compact runtime pack entries report with replacement_deferred_oversize rows",
        },
        {
            "requirement": "sidecar_mix_body_limits",
            "status": "pass" if sidecar_pack_ready else "gap",
            "evidence": (
                f"sidecar_archives={len(archive_rows)};entries={len(entry_rows)};"
                f"largest_body_bytes={largest_body};max_body_bytes={args.max_body_bytes}"
            ),
            "next_step": "split sidecars further or reduce payloads if any body exceeds the 32-bit MIX field",
        },
        {
            "requirement": "sidecar_outputs",
            "status": "pass" if outputs_written or args.report_only else "gap",
            "evidence": f"report_only={int(args.report_only)};outputs_written={sum(row.get('output_written') == '1' for row in archive_rows)}",
            "next_step": "rerun without --report-only to write the sidecar MIX files",
        },
        {
            "requirement": "runtime_loader_strategy",
            "status": "gap",
            "evidence": "sidecar MIX files are buildable, but the game/runtime still needs a loader hook or archive load-order change",
            "next_step": "teach the runtime to load the sidecar archive after the base archive, then verify the 8 L20_BBI entries are read from it",
        },
    ]

    summary = {
        "status": "gap" if issues else "pass",
        "deferred_entries": str(len(source_rows)),
        "source_archives": str(len(source_archives)),
        "sidecar_archives": str(len(archive_rows)),
        "sidecar_entries": str(len(entry_rows)),
        "report_only": "1" if args.report_only else "0",
        "sidecar_root": str(args.sidecar_root),
        "source_bytes": str(source_bytes),
        "replacement_bytes": str(replacement_bytes),
        "delta_bytes": str(replacement_bytes - source_bytes),
        "max_body_bytes": str(args.max_body_bytes),
        "largest_sidecar_body_bytes": str(largest_body),
        "output_bytes": str(output_bytes),
        "issues": ";".join(issues),
        "next_step": "teach the runtime to load the generated sidecar MIX archives after their base archives",
    }
    return summary, requirements, archive_rows, entry_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Build/report sidecar MIX files for oversized VQA replacements.")
    parser.add_argument("--entries", type=Path, default=DEFAULT_ENTRIES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--sidecar-root", type=Path, default=DEFAULT_SIDECAR_ROOT)
    parser.add_argument("--status-filter", default="replacement_deferred_oversize")
    parser.add_argument("--max-body-bytes", type=int, default=MAX_MIX_FIELD)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()

    summary, requirements, archives, entries = build_reports(args)
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDS, [summary])
    write_csv(args.output / "requirements.csv", REQUIREMENT_FIELDS, requirements)
    write_csv(args.output / "archives.csv", ARCHIVE_FIELDS, archives)
    write_csv(args.output / "entries.csv", ENTRY_FIELDS, entries)
    write_html(args.output / "index.html", summary, requirements, archives, entries)
    print(
        "VQA runtime sidecar pack: "
        f"{summary['status']} ({summary['sidecar_entries']} entries, "
        f"{summary['sidecar_archives']} sidecar MIX {'planned' if args.report_only else 'written'})"
    )
    print(f"Summary: {args.output / 'summary.csv'}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
