#!/usr/bin/env python3
"""Build VQA runtime MIX packs from verified WVQA replacement payloads."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import struct
from collections import defaultdict
from pathlib import Path


DEFAULT_REPACK_READINESS = Path("output/vqa_runtime_repack_readiness")
DEFAULT_OUTPUT = Path("output/vqa_runtime_pack_build")
DEFAULT_RUNTIME_PACK = Path("mod_mix_vqa_fullhd")
MAX_MIX_COUNT = 0xFFFF
MAX_MIX_FIELD = 0xFFFFFFFF

SUMMARY_FIELDS = [
    "status",
    "entries",
    "archives",
    "archive_filters",
    "replacement_overlay_roots",
    "replacement_entries",
    "overlay_replacements",
    "applied_replacements",
    "deferred_replacements",
    "missing_replacements",
    "changed_archives",
    "output_archives",
    "output_bytes",
    "runtime_pack",
    "existing_runtime_pack_files",
    "issues",
    "next_step",
]

REQUIREMENT_FIELDS = ["requirement", "status", "evidence", "next_step"]

ARCHIVE_FIELDS = [
    "archive",
    "resolved_archive",
    "output_archive",
    "mix_entries",
    "vqa_entries",
    "replacement_entries",
    "overlay_replacements",
    "applied_replacements",
    "deferred_replacements",
    "missing_replacements",
    "output_written",
    "output_sha256",
    "output_bytes",
    "issues",
]

ENTRY_FIELDS = [
    "archive",
    "index",
    "file_id",
    "replacement_path",
    "base_replacement_path",
    "replacement_source",
    "replacement_overlay_root",
    "replacement_exists",
    "source_size",
    "replacement_size",
    "size_delta",
    "runtime_archive",
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


def form_type(payload: bytes) -> str:
    if len(payload) >= 12 and payload.startswith(b"FORM"):
        return payload[8:12].decode("ascii", errors="replace")
    return ""


def runtime_pack_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    if path.is_file():
        return [path]
    return sorted(item for item in path.rglob("*") if item.is_file())


def normalized_archive_key(value: str) -> str:
    return archive_stem(value).lower()


def archive_stem(value: str) -> str:
    path = Path(value)
    return path.stem or path.name or value


def archive_matches_filters(archive: str, filters: set[str]) -> bool:
    if not filters:
        return True
    path = Path(archive)
    choices = {archive.lower(), path.name.lower(), normalized_archive_key(archive)}
    return bool(choices & filters)


def replacement_overlay_candidate(root: Path, archive: str, file_id: str) -> Path:
    return root / archive_stem(archive) / f"{file_id.lower()}.vqa"


def select_replacement_path(
    row: dict[str, str], overlay_roots: list[Path]
) -> tuple[Path, Path, str, str]:
    base_replacement_path = Path(row.get("replacement_path", ""))
    archive = row.get("archive", "")
    file_id = row.get("file_id", "").lower()
    if archive and file_id:
        for root in overlay_roots:
            candidate = replacement_overlay_candidate(root, archive, file_id)
            if candidate.is_file():
                return candidate, base_replacement_path, "overlay", str(root)
    return base_replacement_path, base_replacement_path, "canonical", ""


def read_mix(path: Path) -> list[dict[str, object]]:
    data = path.read_bytes()
    if len(data) < 6:
        raise ValueError(f"{path}: too small")
    count, body_size = struct.unpack_from("<HI", data, 0)
    table_end = 6 + count * 12
    if table_end > len(data):
        raise ValueError(f"{path}: invalid table")
    if body_size != len(data) - table_end:
        raise ValueError(f"{path}: body size mismatch")
    entries: list[dict[str, object]] = []
    for index in range(count):
        file_id, offset, size = struct.unpack_from("<III", data, 6 + index * 12)
        start = table_end + offset
        end = start + size
        if end > len(data):
            raise ValueError(f"{path}: entry {index} out of bounds")
        entries.append({"index": index, "id": file_id, "data": data[start:end]})
    return entries


def build_mix_bytes(entries: list[dict[str, object]]) -> bytes:
    if len(entries) > MAX_MIX_COUNT:
        raise ValueError(f"mix_entry_count_too_large:{len(entries)}:max:{MAX_MIX_COUNT}")
    body_size = 0
    for entry in entries:
        blob = entry["data"]  # type: ignore[assignment]
        blob_size = len(blob)
        if blob_size > MAX_MIX_FIELD:
            raise ValueError(f"mix_entry_too_large:{blob_size}:max:{MAX_MIX_FIELD}")
        if body_size + blob_size > MAX_MIX_FIELD:
            raise ValueError(f"mix_body_too_large:{body_size + blob_size}:max:{MAX_MIX_FIELD}")
        body_size += blob_size

    table = bytearray()
    payload = bytearray()
    offset = 0
    for entry in entries:
        blob = entry["data"]  # type: ignore[assignment]
        table.extend(struct.pack("<III", int(entry["id"]), offset, len(blob)))
        payload.extend(blob)
        offset += len(blob)
    return struct.pack("<HI", len(entries), body_size) + table + payload


def append_issue(row: dict[str, str], issue: str) -> None:
    row["issues"] = ";".join(part for part in [row.get("issues", ""), issue] if part)


def has_blocking_issue(issue_text: str) -> bool:
    for issue in issue_text.split(";"):
        if issue and not issue.startswith("deferred_oversize"):
            return True
    return False


def select_replacements_under_body_limit(
    mix_entries: list[dict[str, object]], replacements: dict[int, bytes]
) -> tuple[set[int], set[int], int]:
    body_size = sum(len(entry["data"]) for entry in mix_entries)  # type: ignore[arg-type]
    selected: set[int] = set()
    deferred: set[int] = set()
    positive_deltas: list[tuple[int, int]] = []

    for entry in mix_entries:
        index = int(entry["index"])
        replacement = replacements.get(index)
        if replacement is None:
            continue
        original_size = len(entry["data"])  # type: ignore[arg-type]
        delta = len(replacement) - original_size
        if delta <= 0:
            selected.add(index)
            body_size += delta
        else:
            positive_deltas.append((delta, index))

    for delta, index in sorted(positive_deltas):
        if body_size + delta <= MAX_MIX_FIELD:
            selected.add(index)
            body_size += delta
        else:
            deferred.add(index)

    return selected, deferred, body_size


def archive_lookup(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("archive", ""): row for row in rows if row.get("archive")}


def build_reports(args: argparse.Namespace) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    archive_source_rows = read_csv(args.archives)
    entry_source_rows = read_csv(args.entries)
    archive_filters = {normalized_archive_key(item) for item in (getattr(args, "archives_filter", None) or [])}
    if archive_filters:
        archive_source_rows = [
            row for row in archive_source_rows if archive_matches_filters(row.get("archive", ""), archive_filters)
        ]
        entry_source_rows = [
            row for row in entry_source_rows if archive_matches_filters(row.get("archive", ""), archive_filters)
        ]
    overlay_roots = list(getattr(args, "replacement_overlay_roots", None) or [])
    archive_by_name = archive_lookup(archive_source_rows)
    rows_by_archive: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in entry_source_rows:
        archive = row.get("archive", "")
        if archive:
            rows_by_archive[archive].append(row)

    existing_pack_files = runtime_pack_files(args.runtime_pack)
    archive_rows: list[dict[str, str]] = []
    entry_rows: list[dict[str, str]] = []
    requirements: list[dict[str, str]] = []
    issues: list[str] = []
    output_archives = 0
    output_bytes = 0
    changed_archives = 0
    replacement_entries = 0
    overlay_replacements = 0
    applied_replacements = 0
    deferred_replacements = 0
    missing_replacements = 0
    total_entries = len(entry_source_rows)

    for archive, archive_entries in sorted(rows_by_archive.items()):
        archive_info = archive_by_name.get(archive, {})
        resolved_archive = Path(archive_info.get("resolved_archive", "") or archive_entries[0].get("resolved_archive", ""))
        output_archive = args.runtime_pack / Path(archive).name
        archive_issues: list[str] = []
        output_written = "0"
        output_sha = ""
        archive_output_bytes = 0
        replacements_for_archive: dict[int, bytes] = {}
        entry_ids: dict[int, str] = {}
        entry_rows_by_index: dict[int, dict[str, str]] = {}
        archive_applied = 0
        archive_deferred = 0
        archive_overlay = 0

        for row in archive_entries:
            entry_issues: list[str] = []
            index = int_value(row, "index")
            file_id = row.get("file_id", "").lower()
            replacement_path, base_replacement_path, replacement_source, replacement_overlay_root = select_replacement_path(
                row, overlay_roots
            )
            source_size = int_value(row, "mix_size") or int_value(row, "manifest_source_size")
            replacement_exists = replacement_path.is_file()
            replacement_size = 0
            if replacement_exists:
                if replacement_source == "overlay":
                    overlay_replacements += 1
                    archive_overlay += 1
                replacement = replacement_path.read_bytes()
                replacement_size = len(replacement)
                if form_type(replacement) != "WVQA":
                    entry_issues.append(f"replacement_not_wvqa:{form_type(replacement) or 'unknown'}")
                else:
                    replacements_for_archive[index] = replacement
                    entry_ids[index] = file_id
                    replacement_entries += 1
            else:
                missing_replacements += 1
            entry_row = {
                "archive": archive,
                "index": row.get("index", ""),
                "file_id": file_id,
                "replacement_path": str(replacement_path),
                "base_replacement_path": str(base_replacement_path),
                "replacement_source": replacement_source,
                "replacement_overlay_root": replacement_overlay_root,
                "replacement_exists": "1" if replacement_exists else "0",
                "source_size": str(source_size),
                "replacement_size": str(replacement_size),
                "size_delta": str(replacement_size - source_size) if replacement_exists else "",
                "runtime_archive": str(output_archive),
                "status": (
                    "replacement_ready"
                    if replacement_exists and not entry_issues
                    else "replacement_invalid"
                    if replacement_exists
                    else "missing_replacement"
                ),
                "issues": ";".join(entry_issues),
            }
            entry_rows.append(entry_row)
            entry_rows_by_index[index] = entry_row
            archive_issues.extend(entry_issues)

        archive_missing = len(archive_entries) - len(replacements_for_archive)
        if replacements_for_archive:
            changed_archives += 1
            try:
                if not resolved_archive.is_file():
                    raise FileNotFoundError(str(resolved_archive))
                mix_entries = read_mix(resolved_archive)
                entries_by_index = {int(entry["index"]): entry for entry in mix_entries}
                valid_replacements: dict[int, bytes] = {}
                for index, replacement in replacements_for_archive.items():
                    entry = entries_by_index.get(index)
                    if entry is None:
                        archive_issues.append(f"missing_mix_entry:{index}")
                        append_issue(entry_rows_by_index[index], "missing_mix_entry")
                        continue
                    expected_id = entry_ids.get(index, "")
                    actual_id = f"{int(entry['id']):08x}"
                    if expected_id and actual_id != expected_id:
                        archive_issues.append(f"file_id_mismatch:{index}:{actual_id}")
                        append_issue(entry_rows_by_index[index], f"file_id_mismatch:{actual_id}")
                        continue
                    valid_replacements[index] = replacement
                if not has_blocking_issue(";".join(archive_issues)):
                    selected, deferred, projected_body_size = select_replacements_under_body_limit(
                        mix_entries, valid_replacements
                    )
                    for index in selected:
                        entries_by_index[index]["data"] = valid_replacements[index]
                    for index in deferred:
                        entry_rows_by_index[index]["status"] = "replacement_deferred_oversize"
                        append_issue(
                            entry_rows_by_index[index],
                            f"deferred_oversize:projected_body:{projected_body_size}:max:{MAX_MIX_FIELD}",
                        )
                    if deferred:
                        archive_issues.append(
                            f"deferred_oversize_replacements:{len(deferred)}:"
                            f"projected_body:{projected_body_size}:max:{MAX_MIX_FIELD}"
                        )
                    archive_applied = len(selected)
                    archive_deferred = len(deferred)
                    applied_replacements += archive_applied
                    deferred_replacements += archive_deferred
                    data = build_mix_bytes(mix_entries)
                    args.runtime_pack.mkdir(parents=True, exist_ok=True)
                    output_archive.write_bytes(data)
                    output_written = "1"
                    output_sha = sha256_bytes(data)
                    archive_output_bytes = len(data)
                    output_archives += 1
                    output_bytes += archive_output_bytes
            except Exception as exc:  # noqa: BLE001 - keep building other archives and report the failing one
                detail = str(exc).replace("\n", " ").replace(";", ",")
                suffix = f":{detail}" if detail else ""
                archive_issues.append(f"build_failed:{type(exc).__name__}{suffix}")
                if output_archive.exists():
                    archive_issues.append("stale_output_exists")

        archive_rows.append(
            {
                "archive": archive,
                "resolved_archive": str(resolved_archive),
                "output_archive": str(output_archive),
                "mix_entries": archive_info.get("mix_entries", ""),
                "vqa_entries": str(len(archive_entries)),
                "replacement_entries": str(len(replacements_for_archive)),
                "overlay_replacements": str(archive_overlay),
                "applied_replacements": str(archive_applied),
                "deferred_replacements": str(archive_deferred),
                "missing_replacements": str(archive_missing),
                "output_written": output_written,
                "output_sha256": output_sha,
                "output_bytes": str(archive_output_bytes),
                "issues": ";".join(archive_issues),
            }
        )

    archive_issue_rows = [row for row in archive_rows if row["issues"]]
    archive_blocking_issue_rows = [row for row in archive_issue_rows if has_blocking_issue(row["issues"])]
    entry_issue_rows = [row for row in entry_rows if row["issues"]]
    entry_blocking_issue_rows = [row for row in entry_issue_rows if has_blocking_issue(row["issues"])]
    if not entry_source_rows:
        issues.append("missing_repack_readiness_entries")
    if missing_replacements:
        issues.append(f"missing_replacements:{missing_replacements}")
    if deferred_replacements:
        issues.append(f"deferred_oversize_replacements:{deferred_replacements}")
    if archive_blocking_issue_rows:
        issues.append(f"archive_build_issues:{len(archive_blocking_issue_rows)}")
    if entry_blocking_issue_rows:
        issues.append(f"entry_payload_issues:{len(entry_blocking_issue_rows)}")
    if replacement_entries == 0 and existing_pack_files:
        issues.append(f"stale_runtime_pack_files:{len(existing_pack_files)}")
    if replacement_entries and output_archives != changed_archives:
        issues.append(f"missing_output_archives:{changed_archives - output_archives}")
    stale_failed_outputs = sum(
        1
        for row in archive_rows
        if row["output_written"] == "0" and row.get("output_archive") and Path(row["output_archive"]).exists()
    )
    if stale_failed_outputs:
        issues.append(f"stale_failed_output_archives:{stale_failed_outputs}")

    complete_runtime_pack = (
        not archive_filters
        and total_entries > 0
        and replacement_entries == total_entries
        and applied_replacements == total_entries
        and deferred_replacements == 0
        and missing_replacements == 0
        and output_archives == len(rows_by_archive)
        and not archive_issue_rows
        and not entry_issue_rows
    )
    requirements.extend(
        [
            {
                "requirement": "repack_readiness_entries",
                "status": "pass" if entry_source_rows else "gap",
                "evidence": (
                    f"entries={len(entry_source_rows)};archives={len(rows_by_archive)};"
                    f"archive_filters={','.join(sorted(archive_filters)) or 'all'}"
                ),
                "next_step": "run lolg_vqa_runtime_repack_readiness.py before building the runtime pack",
            },
            {
                "requirement": "replacement_payloads",
                "status": "pass" if total_entries and replacement_entries == total_entries else "gap",
                "evidence": (
                    f"replacement_entries={replacement_entries}/{total_entries};"
                    f"missing={missing_replacements};overlay={overlay_replacements};"
                    f"overlay_roots={','.join(str(root) for root in overlay_roots) or 'none'}"
                ),
                "next_step": "encode Full HD WVQA payloads under replacements_vqa_fullhd/<ARCHIVE>/<file_id>.vqa",
            },
            {
                "requirement": "runtime_mix_outputs",
                "status": "pass" if complete_runtime_pack else "gap",
                "evidence": (
                    f"output_archives={output_archives}/{len(rows_by_archive)};"
                    f"applied_replacements={applied_replacements}/{total_entries};"
                    f"deferred_replacements={deferred_replacements};"
                    f"overlay_replacements={overlay_replacements};"
                    f"output_bytes={output_bytes}"
                ),
                "next_step": "materialize all changed MIX archives into mod_mix_vqa_fullhd/",
            },
        ]
    )

    final_pack_files = runtime_pack_files(args.runtime_pack)
    summary = {
        "status": "pass" if complete_runtime_pack and not issues else "gap",
        "entries": str(total_entries),
        "archives": str(len(rows_by_archive)),
        "archive_filters": ",".join(sorted(archive_filters)) or "all",
        "replacement_overlay_roots": ",".join(str(root) for root in overlay_roots) or "none",
        "replacement_entries": str(replacement_entries),
        "overlay_replacements": str(overlay_replacements),
        "applied_replacements": str(applied_replacements),
        "deferred_replacements": str(deferred_replacements),
        "missing_replacements": str(missing_replacements),
        "changed_archives": str(changed_archives),
        "output_archives": str(output_archives),
        "output_bytes": str(output_bytes),
        "runtime_pack": str(args.runtime_pack),
        "existing_runtime_pack_files": str(len(final_pack_files)),
        "issues": ";".join(issues),
        "next_step": (
            "runtime pack complete"
            if complete_runtime_pack and not issues
            else "compact or split deferred WVQA payloads, optionally via --replacement-overlay-root, then rerun this builder"
            if deferred_replacements
            else "rerun without --archive to materialize the complete runtime MIX pack"
            if archive_filters
            else "produce WVQA replacement payloads, then rerun this builder to materialize the runtime MIX pack"
        ),
    }
    return summary, requirements, archive_rows, entry_rows


def render_table(rows: list[dict[str, str]], fields: list[str]) -> str:
    head = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = []
    for row in rows:
        body.append("<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def write_html(path: Path, summary: dict[str, str], requirements: list[dict[str, str]], archives: list[dict[str, str]], entries: list[dict[str, str]]) -> None:
    payload = {
        "summary": summary,
        "requirements": requirements,
        "archives": archives,
        "entries_sample": entries[:200],
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    path.write_text(
        f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LOLG VQA Runtime Pack Build</title>
<style>
:root {{ color-scheme: dark; --bg: #101316; --panel: #171d22; --line: #2f3942; --text: #edf3f6; --muted: #9caab3; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; min-height: 100vh; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, sans-serif; }}
.wrap {{ width: min(1600px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12171b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 700; letter-spacing: 0; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 10px; }}
.stat {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label {{ color: var(--muted); }}
.value {{ font-size: 24px; font-weight: 750; line-height: 1.05; margin-top: 4px; }}
.panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 12px; overflow-x: auto; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
table {{ width: 100%; min-width: 940px; border-collapse: collapse; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
td {{ overflow-wrap: anywhere; }}
</style>
</head>
<body>
<header><div class="wrap"><h1>LOLG VQA Runtime Pack Build</h1></div></header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Status</div><div class="value">{html.escape(summary['status'])}</div></div>
    <div class="stat"><div class="label">Remplacements</div><div class="value">{html.escape(summary['replacement_entries'])}</div></div>
    <div class="stat"><div class="label">Overlay</div><div class="value">{html.escape(summary['overlay_replacements'])}</div></div>
    <div class="stat"><div class="label">Manquants</div><div class="value">{html.escape(summary['missing_replacements'])}</div></div>
    <div class="stat"><div class="label">MIX ecrits</div><div class="value">{html.escape(summary['output_archives'])}</div></div>
  </section>
  <section class="panel"><h2>Synthese</h2>{render_table([summary], SUMMARY_FIELDS)}</section>
  <section class="panel"><h2>Requirements</h2>{render_table(requirements, REQUIREMENT_FIELDS)}</section>
  <section class="panel"><h2>Archives</h2>{render_table(archives, ARCHIVE_FIELDS)}</section>
  <section class="panel"><h2>Entrees VQA sample</h2>{render_table(entries[:200], ENTRY_FIELDS)}</section>
</main>
<script type="application/json" id="vqa-runtime-pack-build">{html.escape(data_json)}</script>
</body>
</html>
""",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build VQA runtime MIX archives from WVQA replacements.")
    parser.add_argument("--entries", type=Path, default=DEFAULT_REPACK_READINESS / "entries.csv")
    parser.add_argument("--archives", type=Path, default=DEFAULT_REPACK_READINESS / "archives.csv")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runtime-pack", type=Path, default=DEFAULT_RUNTIME_PACK)
    parser.add_argument(
        "--replacement-overlay-root",
        action="append",
        type=Path,
        default=[],
        dest="replacement_overlay_roots",
        help="Prefer WVQA payloads from this root as <root>/<ARCHIVE_STEM>/<file_id>.vqa; repeatable.",
    )
    parser.add_argument(
        "--archive",
        action="append",
        default=[],
        dest="archives_filter",
        help="Limit the build/report to one archive name, stem, or path; repeatable.",
    )
    parser.add_argument("--fail-on-gaps", action="store_true")
    args = parser.parse_args()

    summary, requirements, archives, entries = build_reports(args)
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDS, [summary])
    write_csv(args.output / "requirements.csv", REQUIREMENT_FIELDS, requirements)
    write_csv(args.output / "archives.csv", ARCHIVE_FIELDS, archives)
    write_csv(args.output / "entries.csv", ENTRY_FIELDS, entries)
    write_html(args.output / "index.html", summary, requirements, archives, entries)

    print(
        "VQA runtime pack build: "
        f"{summary['status']} ({summary['replacement_entries']}/{summary['entries']} replacements, "
        f"{summary['output_archives']} MIX written)"
    )
    print(f"Summary: {args.output / 'summary.csv'}")
    print(f"HTML: {args.output / 'index.html'}")
    if args.fail_on_gaps and summary["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
