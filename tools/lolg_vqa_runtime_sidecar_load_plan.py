#!/usr/bin/env python3
"""Audit the runtime load plan for VQA sidecar MIX archives."""

from __future__ import annotations

import argparse
import csv
import html
import json
import struct
from collections import defaultdict
from pathlib import Path


DEFAULT_SIDECAR_ENTRIES = Path("output/vqa_runtime_sidecar_pack/entries.csv")
DEFAULT_OUTPUT = Path("output/vqa_runtime_sidecar_load_plan")
DEFAULT_GAME_ROOT = Path(".")
DEFAULT_RUNTIME_ARCHIVE_LIST_SUMMARY = Path("output/lolg95_runtime_archive_list_l20_sidecar_probe/summary.csv")
DEFAULT_RUNTIME_ARCHIVE_LIST_TARGETS = Path("output/lolg95_runtime_archive_list_l20_sidecar_probe/targets.tsv")
DEFAULT_PROBES = [
    Path("CDCACHE.LST"),
    Path("CDCACHE.LS_"),
    Path("LOLG95.EXE"),
    Path("LOLG.DAT"),
    Path("LOLG.EXE"),
    Path("RUN_HD.sh"),
    Path("RUN_HD_PCX_FULLHD.sh"),
]

SUMMARY_FIELDS = [
    "status",
    "sidecar_entries",
    "sidecar_archives",
    "base_archives",
    "base_entries_verified",
    "sidecar_entries_verified",
    "cdcache_sidecar_name_hits",
    "cdcache_base_name_hits",
    "loader_candidate_files",
    "runtime_archive_list_status",
    "runtime_archive_list_targets",
    "runtime_sidecar_first",
    "runtime_base_first",
    "runtime_missing",
    "runtime_unknown_first",
    "issues",
    "next_step",
]

REQUIREMENT_FIELDS = ["requirement", "status", "evidence", "next_step"]

ARCHIVE_FIELDS = [
    "source_archive",
    "source_path",
    "source_exists",
    "source_count",
    "source_body_bytes",
    "sidecar_archive",
    "sidecar_path",
    "sidecar_exists",
    "sidecar_count",
    "sidecar_body_bytes",
    "planned_entries",
    "source_verified_entries",
    "sidecar_verified_entries",
    "status",
    "issues",
]

ENTRY_FIELDS = [
    "source_archive",
    "index",
    "file_id",
    "source_size",
    "source_mix_offset",
    "source_mix_size",
    "source_status",
    "sidecar_archive",
    "sidecar_mix_index",
    "sidecar_offset",
    "sidecar_size",
    "replacement_size",
    "sidecar_status",
    "load_order_status",
    "runtime_first_archive",
    "runtime_first_order",
    "runtime_first_entry_size",
    "issues",
]

SOURCE_FIELDS = [
    "path",
    "exists",
    "size_bytes",
    "cdcache_hits",
    "mix_hits",
    "base_mix_hits",
    "sidecar_mix_hits",
    "base_stem_hits",
    "sidecar_stem_hits",
    "interpretation",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_tsv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


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


def archive_stem(value: str) -> str:
    path = Path(value)
    return path.stem or path.name or value


def resolve_game_path(game_root: Path, logical_path: str) -> Path:
    path = Path(logical_path)
    candidates = [
        path,
        game_root / logical_path,
        game_root / path.name,
        game_root / archive_stem(logical_path),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return game_root / path.name


def count_occurrences(data: bytes, needle: bytes) -> int:
    if not needle:
        return 0
    count = 0
    start = 0
    while True:
        index = data.find(needle, start)
        if index < 0:
            return count
        count += 1
        start = index + 1


def read_mix_index(path: Path) -> tuple[dict[str, object], list[dict[str, int | str]], list[str]]:
    if not path.exists():
        return {"exists": "0", "count": "", "body_bytes": ""}, [], ["file_missing"]
    data = path.read_bytes()
    issues: list[str] = []
    if len(data) < 6:
        return {"exists": "1", "count": "", "body_bytes": ""}, [], ["mix_too_small"]
    count, body_size = struct.unpack_from("<HI", data, 0)
    table_end = 6 + count * 12
    if table_end > len(data):
        return {"exists": "1", "count": str(count), "body_bytes": str(body_size)}, [], ["invalid_table"]
    actual_body_size = len(data) - table_end
    if body_size != actual_body_size:
        issues.append(f"body_size_mismatch:{body_size}:{actual_body_size}")
    entries: list[dict[str, int | str]] = []
    for index in range(count):
        file_id, offset, size = struct.unpack_from("<III", data, 6 + index * 12)
        start = table_end + offset
        end = start + size
        if end > len(data):
            issues.append(f"entry_out_of_bounds:{index}")
        entries.append(
            {
                "index": index,
                "file_id": f"{file_id:08x}",
                "offset": offset,
                "size": size,
            }
        )
    meta = {
        "exists": "1",
        "count": str(count),
        "body_bytes": str(body_size),
    }
    return meta, entries, issues


def probe_path(path: Path, base_name: str, sidecar_name: str) -> dict[str, str]:
    row = {
        "path": str(path),
        "exists": "0",
        "size_bytes": "0",
        "cdcache_hits": "0",
        "mix_hits": "0",
        "base_mix_hits": "0",
        "sidecar_mix_hits": "0",
        "base_stem_hits": "0",
        "sidecar_stem_hits": "0",
        "interpretation": "missing",
    }
    if not path.exists():
        return row
    data = path.read_bytes().upper()
    base_stem = Path(base_name).stem.upper().encode("ascii")
    sidecar_stem = Path(sidecar_name).stem.upper().encode("ascii")
    row.update(
        {
            "exists": "1",
            "size_bytes": str(path.stat().st_size),
            "cdcache_hits": str(count_occurrences(data, b"CDCACHE")),
            "mix_hits": str(count_occurrences(data, b".MIX")),
            "base_mix_hits": str(count_occurrences(data, base_name.upper().encode("ascii"))),
            "sidecar_mix_hits": str(count_occurrences(data, sidecar_name.upper().encode("ascii"))),
            "base_stem_hits": str(count_occurrences(data, base_stem)),
            "sidecar_stem_hits": str(count_occurrences(data, sidecar_stem)),
        }
    )
    suffix = path.suffix.lower()
    cdcache_hits = int(row["cdcache_hits"])
    mix_hits = int(row["mix_hits"])
    sidecar_hits = int(row["sidecar_mix_hits"]) + int(row["sidecar_stem_hits"])
    if path.name.upper().startswith("CDCACHE"):
        row["interpretation"] = "no_sidecar_declaration" if sidecar_hits == 0 else "sidecar_name_present"
    elif suffix in {".exe", ".dat"} and cdcache_hits and mix_hits:
        row["interpretation"] = "compiled_loader_candidate"
    elif path.name.startswith("RUN_HD") and sidecar_hits == 0:
        row["interpretation"] = "launch_script_without_sidecar_staging"
    else:
        row["interpretation"] = "no_loader_evidence"
    return row


def split_csv_set(value: str) -> set[str]:
    return {part.strip().lower() for part in value.split(",") if part.strip()}


def archive_names_match(runtime_name: str, planned_name: str) -> bool:
    return Path(runtime_name).name.lower() == Path(planned_name).name.lower()


def load_runtime_archive_list_evidence(
    summary_path: Path,
    targets_path: Path,
    plan_rows: list[dict[str, str]],
) -> tuple[dict[str, str], dict[str, dict[str, str]], list[str]]:
    summary_rows = read_csv(summary_path)
    summary = summary_rows[0] if summary_rows else {}
    target_rows = {row.get("file_id", "").lower(): row for row in read_tsv(targets_path) if row.get("file_id")}
    issues: list[str] = []

    if not summary:
        issues.append("runtime_archive_list_summary_missing")
    elif summary.get("status") != "pass":
        issues.append(f"runtime_archive_list_status:{summary.get('status', '')}")

    if not target_rows:
        issues.append("runtime_archive_list_targets_missing")

    sidecar_first = split_csv_set(summary.get("target_sidecar_first", ""))
    base_first = split_csv_set(summary.get("target_base_first", ""))
    missing = split_csv_set(summary.get("target_missing", ""))
    unknown = split_csv_set(summary.get("target_unknown_first", ""))
    plan_ids = {row.get("file_id", "").lower() for row in plan_rows if row.get("file_id")}
    if summary.get("expected_ids") and summary.get("expected_ids") != str(len(plan_rows)):
        issues.append(f"runtime_archive_list_expected_ids:{summary.get('expected_ids')}:{len(plan_rows)}")
    if plan_ids and sidecar_first != plan_ids:
        issues.append("runtime_archive_list_sidecar_ids_mismatch")
    if base_first:
        issues.append("runtime_archive_list_base_first:" + ",".join(sorted(base_first)))
    if missing:
        issues.append("runtime_archive_list_missing:" + ",".join(sorted(missing)))
    if unknown:
        issues.append("runtime_archive_list_unknown:" + ",".join(sorted(unknown)))

    for row in plan_rows:
        file_id = row.get("file_id", "").lower()
        runtime_row = target_rows.get(file_id)
        if runtime_row is None:
            issues.append(f"runtime_target_missing:{file_id}")
            continue
        if runtime_row.get("first_status") != "sidecar":
            issues.append(f"runtime_target_not_sidecar_first:{file_id}:{runtime_row.get('first_status', '')}")
        if runtime_row.get("first_entry_size") != row.get("replacement_size", ""):
            issues.append(
                "runtime_target_size_mismatch:"
                f"{file_id}:{runtime_row.get('first_entry_size', '')}:{row.get('replacement_size', '')}"
            )
        if not archive_names_match(runtime_row.get("first_archive", ""), row.get("sidecar_archive", "")):
            issues.append(
                "runtime_target_archive_mismatch:"
                f"{file_id}:{runtime_row.get('first_archive', '')}:{row.get('sidecar_archive', '')}"
            )

    return summary, target_rows, list(dict.fromkeys(issues))


def build_reports(args: argparse.Namespace) -> tuple[
    dict[str, str],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    plan_rows = [row for row in read_csv(args.sidecar_entries) if row.get("status") == "sidecar_ready"]
    runtime_summary, runtime_targets, runtime_issues = load_runtime_archive_list_evidence(
        args.runtime_archive_list_summary,
        args.runtime_archive_list_targets,
        plan_rows,
    )
    rows_by_archive: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in plan_rows:
        key = (row.get("source_archive", ""), row.get("sidecar_archive", ""), row.get("sidecar_path", ""))
        rows_by_archive[key].append(row)

    archive_rows: list[dict[str, str]] = []
    entry_rows: list[dict[str, str]] = []
    all_issues: list[str] = []
    base_verified_total = 0
    sidecar_verified_total = 0

    for (source_archive, sidecar_archive, sidecar_path), rows in sorted(rows_by_archive.items()):
        source_path = resolve_game_path(args.game_root, source_archive)
        source_meta, source_entries, source_issues = read_mix_index(source_path)
        sidecar_meta, sidecar_entries, sidecar_issues = read_mix_index(Path(sidecar_path))
        source_by_index = {int(entry["index"]): entry for entry in source_entries}
        sidecar_by_id = {str(entry["file_id"]): entry for entry in sidecar_entries}
        source_verified = 0
        sidecar_verified = 0
        archive_issues = list(source_issues) + [f"sidecar:{issue}" for issue in sidecar_issues]

        for row in rows:
            index = int_value(row, "index")
            expected_id = row.get("file_id", "").lower()
            expected_source_size = int_value(row, "source_size")
            expected_sidecar_size = int_value(row, "replacement_size")
            source_entry = source_by_index.get(index)
            sidecar_entry = sidecar_by_id.get(expected_id)
            row_issues: list[str] = []

            source_status = "gap"
            source_offset = ""
            source_size = ""
            if source_entry is None:
                row_issues.append("source_index_missing")
            else:
                source_offset = str(source_entry["offset"])
                source_size = str(source_entry["size"])
                if str(source_entry["file_id"]) != expected_id:
                    row_issues.append(f"source_file_id_mismatch:{source_entry['file_id']}")
                if int(source_entry["size"]) != expected_source_size:
                    row_issues.append(f"source_size_mismatch:{source_entry['size']}")
                if not row_issues:
                    source_status = "pass"
                    source_verified += 1

            sidecar_status = "gap"
            sidecar_index = ""
            sidecar_offset = ""
            sidecar_size = ""
            if sidecar_entry is None:
                row_issues.append("sidecar_id_missing")
            else:
                sidecar_index = str(sidecar_entry["index"])
                sidecar_offset = str(sidecar_entry["offset"])
                sidecar_size = str(sidecar_entry["size"])
                if int(sidecar_entry["size"]) != expected_sidecar_size:
                    row_issues.append(f"sidecar_size_mismatch:{sidecar_entry['size']}")
                else:
                    sidecar_status = "pass"
                    sidecar_verified += 1

            runtime_row = runtime_targets.get(expected_id, {})
            load_order_status = "gap"
            runtime_first_archive = runtime_row.get("first_archive", "")
            runtime_first_order = runtime_row.get("first_order", "")
            runtime_first_entry_size = runtime_row.get("first_entry_size", "")
            if not runtime_row:
                row_issues.append("runtime_target_missing")
            elif runtime_row.get("first_status") != "sidecar":
                row_issues.append(f"runtime_first_status:{runtime_row.get('first_status', '')}")
            elif runtime_first_entry_size != str(expected_sidecar_size):
                row_issues.append(f"runtime_size_mismatch:{runtime_first_entry_size}")
            elif not archive_names_match(runtime_first_archive, sidecar_archive):
                row_issues.append(f"runtime_archive_mismatch:{runtime_first_archive}")
            else:
                load_order_status = "pass"

            entry_rows.append(
                {
                    "source_archive": source_archive,
                    "index": row.get("index", ""),
                    "file_id": expected_id,
                    "source_size": str(expected_source_size),
                    "source_mix_offset": source_offset,
                    "source_mix_size": source_size,
                    "source_status": source_status,
                    "sidecar_archive": sidecar_archive,
                    "sidecar_mix_index": sidecar_index,
                    "sidecar_offset": sidecar_offset,
                    "sidecar_size": sidecar_size,
                    "replacement_size": str(expected_sidecar_size),
                    "sidecar_status": sidecar_status,
                    "load_order_status": load_order_status,
                    "runtime_first_archive": runtime_first_archive,
                    "runtime_first_order": runtime_first_order,
                    "runtime_first_entry_size": runtime_first_entry_size,
                    "issues": ";".join(row_issues),
                }
            )
            archive_issues.extend(row_issues)

        base_verified_total += source_verified
        sidecar_verified_total += sidecar_verified
        archive_status = "pass" if not archive_issues and source_verified == len(rows) and sidecar_verified == len(rows) else "gap"
        archive_rows.append(
            {
                "source_archive": source_archive,
                "source_path": str(source_path),
                "source_exists": str(source_meta["exists"]),
                "source_count": str(source_meta["count"]),
                "source_body_bytes": str(source_meta["body_bytes"]),
                "sidecar_archive": sidecar_archive,
                "sidecar_path": sidecar_path,
                "sidecar_exists": str(sidecar_meta["exists"]),
                "sidecar_count": str(sidecar_meta["count"]),
                "sidecar_body_bytes": str(sidecar_meta["body_bytes"]),
                "planned_entries": str(len(rows)),
                "source_verified_entries": str(source_verified),
                "sidecar_verified_entries": str(sidecar_verified),
                "status": archive_status,
                "issues": ";".join(dict.fromkeys(archive_issues)),
            }
        )
        all_issues.extend(archive_issues)

    base_name = archive_rows[0]["source_archive"].split("/")[-1] if archive_rows else "L20_BBI.MIX"
    sidecar_name = archive_rows[0]["sidecar_archive"] if archive_rows else "L20_BBI_HD.MIX"
    source_rows = [probe_path(resolve_game_path(args.game_root, str(path)), base_name, sidecar_name) for path in args.probe]
    cdcache_rows = [row for row in source_rows if Path(row["path"]).name.upper().startswith("CDCACHE")]
    cdcache_sidecar_hits = sum(int_value(row, "sidecar_mix_hits") + int_value(row, "sidecar_stem_hits") for row in cdcache_rows)
    cdcache_base_hits = sum(int_value(row, "base_mix_hits") + int_value(row, "base_stem_hits") for row in cdcache_rows)
    loader_candidates = [
        row
        for row in source_rows
        if row.get("interpretation") == "compiled_loader_candidate"
    ]

    runtime_order_ok = bool(plan_rows) and not runtime_issues and all(
        row.get("load_order_status") == "pass" for row in entry_rows
    )

    if not plan_rows:
        all_issues.append("sidecar_plan_empty")
    if cdcache_sidecar_hits == 0 and not runtime_order_ok:
        all_issues.append("cdcache_no_sidecar_declaration")
    all_issues.extend(runtime_issues)

    all_base_ok = bool(plan_rows) and base_verified_total == len(plan_rows)
    all_sidecar_ok = bool(plan_rows) and sidecar_verified_total == len(plan_rows)
    critical_ok = all_base_ok and all_sidecar_ok and runtime_order_ok
    requirements = [
        {
            "requirement": "sidecar_pack_report",
            "status": "pass" if plan_rows else "gap",
            "evidence": f"entries={len(plan_rows)};input={args.sidecar_entries}",
            "next_step": "run tools/lolg_vqa_runtime_sidecar_pack.py after the compact VQA report",
        },
        {
            "requirement": "base_archive_index",
            "status": "pass" if all_base_ok else "gap",
            "evidence": f"verified={base_verified_total}/{len(plan_rows)};archives={len(rows_by_archive)}",
            "next_step": "keep the sidecar rows tied to exact base MIX index/file_id/size triples",
        },
        {
            "requirement": "sidecar_archive_index",
            "status": "pass" if all_sidecar_ok else "gap",
            "evidence": f"verified={sidecar_verified_total}/{len(plan_rows)};archives={len(rows_by_archive)}",
            "next_step": "rerun the sidecar pack without --report-only to materialize missing sidecar MIX files",
        },
        {
            "requirement": "sidecar_declaration_or_runtime_hook",
            "status": "pass" if cdcache_sidecar_hits or runtime_order_ok else "gap",
            "evidence": (
                f"cdcache_sidecar_hits={cdcache_sidecar_hits};"
                f"runtime_archive_list_status={runtime_summary.get('status', '')};"
                f"runtime_sidecar_first={len(split_csv_set(runtime_summary.get('target_sidecar_first', '')))}/"
                f"{len(plan_rows)}"
            ),
            "next_step": "keep the runtime hook proof if CDCACHE.LST does not declare the sidecar name",
        },
        {
            "requirement": "compiled_loader_candidate",
            "status": "pass" if loader_candidates else "gap",
            "evidence": "files=" + ",".join(Path(row["path"]).name for row in loader_candidates),
            "next_step": "inspect the executable/DAT loader path that references CDCACHE and .MIX strings",
        },
        {
            "requirement": "runtime_loader_hook",
            "status": "pass" if runtime_order_ok else "gap",
            "evidence": (
                f"summary={args.runtime_archive_list_summary};"
                f"targets={args.runtime_archive_list_targets};"
                f"archive_nodes={runtime_summary.get('archive_nodes', '')};"
                f"sidecar_first={len(split_csv_set(runtime_summary.get('target_sidecar_first', '')))}/"
                f"{len(plan_rows)}"
            ),
            "next_step": (
                "promote the additive runtime patch into a final staged runtime path"
                if runtime_order_ok
                else "run tools/run_lolg95_runtime_archive_list_probe.py until all planned IDs are sidecar-first"
            ),
        },
    ]

    summary = {
        "status": "pass" if critical_ok and not all_issues else "gap",
        "sidecar_entries": str(len(plan_rows)),
        "sidecar_archives": str(len(rows_by_archive)),
        "base_archives": str(len({row.get("source_archive", "") for row in plan_rows})),
        "base_entries_verified": str(base_verified_total),
        "sidecar_entries_verified": str(sidecar_verified_total),
        "cdcache_sidecar_name_hits": str(cdcache_sidecar_hits),
        "cdcache_base_name_hits": str(cdcache_base_hits),
        "loader_candidate_files": str(len(loader_candidates)),
        "runtime_archive_list_status": runtime_summary.get("status", ""),
        "runtime_archive_list_targets": str(len(runtime_targets)),
        "runtime_sidecar_first": str(len(split_csv_set(runtime_summary.get("target_sidecar_first", "")))),
        "runtime_base_first": str(len(split_csv_set(runtime_summary.get("target_base_first", "")))),
        "runtime_missing": str(len(split_csv_set(runtime_summary.get("target_missing", "")))),
        "runtime_unknown_first": str(len(split_csv_set(runtime_summary.get("target_unknown_first", "")))),
        "issues": ";".join(dict.fromkeys(all_issues)),
        "next_step": (
            "promote the proven additive sidecar stage into a clean user-facing runtime path"
            if critical_ok and not all_issues
            else "patch or wrap the MIX loader so L20_BBI_HD.MIX is queried after L20_BBI.MIX"
        ),
    }
    return summary, requirements, archive_rows, entry_rows, source_rows


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
    sources: list[dict[str, str]],
) -> None:
    payload = {
        "summary": summary,
        "requirements": requirements,
        "archives": archives,
        "entries": entries,
        "sources": sources,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    page = f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>VQA Runtime Sidecar Load Plan</title>
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
  <h1>VQA Runtime Sidecar Load Plan</h1>
  <div class="grid">
    <div class="stat"><div class="label">Statut</div><div class="value">{html.escape(summary['status'])}</div></div>
    <div class="stat"><div class="label">Entrees sidecar</div><div class="value">{html.escape(summary['sidecar_entries'])}</div></div>
    <div class="stat"><div class="label">Base verifiee</div><div class="value">{html.escape(summary['base_entries_verified'])}</div></div>
    <div class="stat"><div class="label">Sidecar verifie</div><div class="value">{html.escape(summary['sidecar_entries_verified'])}</div></div>
  </div>
  <h2>Requirements</h2>
  {render_table(requirements, REQUIREMENT_FIELDS)}
  <h2>Archives</h2>
  {render_table(archives, ARCHIVE_FIELDS)}
  <h2>Entrees</h2>
  {render_table(entries, ENTRY_FIELDS)}
  <h2>Sources inspectees</h2>
  {render_table(sources, SOURCE_FIELDS)}
  <script type="application/json" id="vqa-runtime-sidecar-load-plan">{html.escape(data_json)}</script>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit the runtime load plan for VQA sidecar MIX archives.")
    parser.add_argument("--sidecar-entries", type=Path, default=DEFAULT_SIDECAR_ENTRIES)
    parser.add_argument("--runtime-archive-list-summary", type=Path, default=DEFAULT_RUNTIME_ARCHIVE_LIST_SUMMARY)
    parser.add_argument("--runtime-archive-list-targets", type=Path, default=DEFAULT_RUNTIME_ARCHIVE_LIST_TARGETS)
    parser.add_argument("--game-root", type=Path, default=DEFAULT_GAME_ROOT)
    parser.add_argument("--probe", type=Path, action="append", default=list(DEFAULT_PROBES))
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    summary, requirements, archives, entries, sources = build_reports(args)
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDS, [summary])
    write_csv(args.output / "requirements.csv", REQUIREMENT_FIELDS, requirements)
    write_csv(args.output / "archives.csv", ARCHIVE_FIELDS, archives)
    write_csv(args.output / "entries.csv", ENTRY_FIELDS, entries)
    write_csv(args.output / "sources.csv", SOURCE_FIELDS, sources)
    write_html(args.output / "index.html", summary, requirements, archives, entries, sources)
    print(
        "VQA runtime sidecar load plan: "
        f"{summary['status']} ({summary['base_entries_verified']}/{summary['sidecar_entries']} base, "
        f"{summary['sidecar_entries_verified']}/{summary['sidecar_entries']} sidecar verified)"
    )
    print(f"Summary: {args.output / 'summary.csv'}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
