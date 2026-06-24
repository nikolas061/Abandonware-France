#!/usr/bin/env python3
"""Summarize the remaining played-read proof gap for the LOLG95 L20 VQA sidecar."""

from __future__ import annotations

import argparse
import csv
import html
from pathlib import Path


DEFAULT_OUTPUT = Path("output/lolg95_sidecar_played_read_plan")
DEFAULT_LOAD_PLAN_ENTRIES = Path("output/vqa_runtime_sidecar_load_plan/entries.csv")
DEFAULT_REPACK_READINESS_ENTRIES = Path("output/vqa_runtime_repack_readiness/entries.csv")
DEFAULT_SIDECAR_PACK_ENTRIES = Path("output/vqa_runtime_sidecar_pack/entries.csv")
DEFAULT_RUNTIME_ARCHIVES = Path("output/lolg95_runtime_archive_list_l20_sidecar_probe/archives.tsv")
DEFAULT_RUNTIME_TARGETS = Path("output/lolg95_runtime_archive_list_l20_sidecar_probe/targets.tsv")
DEFAULT_LOOKUP_SUMMARY = Path("output/lolg95_winedbg_mix_lookup_l20_additive_attempt/summary.csv")
DEFAULT_STAGE_SUMMARY = Path("output/lolg95_sidecar_runtime_stage/summary.csv")
DEFAULT_FILE_IO_CONTRACT_SUMMARY = Path("output/lolg95_sidecar_file_io_trace_contract/summary.csv")
DEFAULT_FILE_IO_TRACE_ATTEMPT_SUMMARY = Path("output/lolg95_sidecar_file_io_trace_attempt/summary.csv")
DEFAULT_FILE_IO_TRACE_ATTEMPT_ARCHIVES = Path("output/lolg95_sidecar_file_io_trace_attempt/archives.tsv")
DEFAULT_FILE_IO_TRACE_ATTEMPT_TARGETS = Path("output/lolg95_sidecar_file_io_trace_attempt/archive_targets.tsv")

SUMMARY_FIELDS = [
    "status",
    "targets",
    "runtime_evidence_source",
    "load_order_pass",
    "runtime_sidecar_first",
    "runtime_base_first",
    "runtime_missing",
    "runtime_unknown_first",
    "played_lookup_hits",
    "played_sidecar_hits",
    "played_missing",
    "file_backed_targets",
    "resident_payload_targets",
    "stage_status",
    "file_io_contract_status",
    "file_io_tracepoints",
    "file_io_offset_min",
    "file_io_offset_max",
    "file_io_trace_attempt_status",
    "file_io_trace_attempt_session",
    "file_io_archive_scan_phase",
    "file_io_archive_nodes",
    "file_io_archive_names",
    "file_io_sidecar_path_hits",
    "file_io_archive_pointer_mapped_hits",
    "file_io_sidecar_archive_pointer_hits",
    "file_io_target_offset_seek_hits",
    "file_io_unmapped_target_offset_seek_hits",
    "file_io_target_seek_hits",
    "file_io_target_read_hits",
    "file_io_target_read_ids_seen",
    "payload_read_evidence_targets",
    "sidecar_archive",
    "sidecar_body_pointer",
    "issues",
    "next_step",
]

REQUIREMENT_FIELDS = ["requirement", "status", "evidence", "next_step"]

TARGET_FIELDS = [
    "source_archive",
    "index",
    "file_id",
    "source_size",
    "source_width",
    "source_height",
    "declared_frames",
    "fullhd_frames",
    "replacement_path",
    "replacement_size",
    "sidecar_archive",
    "sidecar_offset",
    "sidecar_size",
    "runtime_first_archive",
    "runtime_first_order",
    "load_order_status",
    "played_lookup_status",
    "payload_residency_status",
    "file_io_seek_status",
    "file_io_read_status",
    "firstframe_dir",
    "issues",
    "next_step",
]


def read_delimited(path: Path, delimiter: str = ",") -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def first_row(path: Path) -> dict[str, str]:
    rows = read_delimited(path)
    return rows[0] if rows else {}


def csv_ids(value: str) -> set[str]:
    return {part.strip().lower() for part in value.split(",") if part.strip()}


def by_file_id(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("file_id", "").lower(): row for row in rows if row.get("file_id")}


def pass_if(condition: bool) -> str:
    return "pass" if condition else "gap"


def count_int(value: str) -> int:
    try:
        return int(value or "0")
    except ValueError:
        return 0


def relative_existing(path: Path) -> str:
    return str(path) if path.exists() else ""


def choose_runtime_evidence(
    archive_rows: list[dict[str, str]],
    target_rows: list[dict[str, str]],
    file_io_summary: dict[str, str],
    file_io_archive_rows: list[dict[str, str]],
    file_io_target_rows: list[dict[str, str]],
) -> tuple[str, list[dict[str, str]], list[dict[str, str]]]:
    if file_io_summary.get("archive_scan_phase") and file_io_target_rows:
        return "file_io_trace_attempt", file_io_archive_rows, file_io_target_rows
    return "runtime_archive_list_probe", archive_rows, target_rows


def build_targets(args: argparse.Namespace) -> tuple[list[dict[str, str]], dict[str, str]]:
    load_rows = read_delimited(args.load_plan_entries)
    readiness_by_id = by_file_id(read_delimited(args.repack_readiness_entries))
    pack_by_id = by_file_id(read_delimited(args.sidecar_pack_entries))
    archive_rows = read_delimited(args.runtime_archives, delimiter="\t")
    runtime_target_rows = read_delimited(args.runtime_targets, delimiter="\t")
    lookup_summary = first_row(args.lookup_summary)
    stage_summary = first_row(args.stage_summary)
    file_io_summary = first_row(args.file_io_contract_summary)
    file_io_attempt_summary = first_row(args.file_io_trace_attempt_summary)
    file_io_archive_rows = read_delimited(args.file_io_trace_attempt_archives, delimiter="\t")
    file_io_target_rows = read_delimited(args.file_io_trace_attempt_targets, delimiter="\t")
    runtime_evidence_source, archive_rows, runtime_target_rows = choose_runtime_evidence(
        archive_rows,
        runtime_target_rows,
        file_io_attempt_summary,
        file_io_archive_rows,
        file_io_target_rows,
    )
    runtime_by_id = by_file_id(runtime_target_rows)

    sidecar_archive = next((row for row in archive_rows if row.get("name", "").lower().endswith("_hd.mix")), {})
    sidecar_body_pointer = sidecar_archive.get("body_pointer", "")
    payloads_resident = sidecar_body_pointer not in {"", "0x00000000", "0"}

    sidecar_hit_ids = csv_ids(lookup_summary.get("target_sidecar_ids_seen", ""))
    all_lookup_hit_ids = csv_ids(lookup_summary.get("target_ids_seen", ""))
    target_hit_count = count_int(lookup_summary.get("target_hits", ""))
    sidecar_hit_count = count_int(lookup_summary.get("target_sidecar_hits", ""))
    file_io_seek_ids = csv_ids(file_io_attempt_summary.get("target_ids_seen", ""))
    file_io_read_ids = csv_ids(file_io_attempt_summary.get("target_read_ids_seen", ""))
    file_io_target_read_hits = count_int(file_io_attempt_summary.get("target_read_hits", ""))

    target_rows = []
    for load_row in load_rows:
        file_id = load_row.get("file_id", "").lower()
        readiness = readiness_by_id.get(file_id, {})
        pack = pack_by_id.get(file_id, {})
        runtime = runtime_by_id.get(file_id, {})
        issues = []
        runtime_first_archive = runtime.get("first_archive", load_row.get("runtime_first_archive", ""))
        runtime_first_order = runtime.get("first_order", load_row.get("runtime_first_order", ""))
        runtime_first_size = runtime.get("first_entry_size", "")
        runtime_first_status = runtime.get("first_status", "")

        if load_row.get("load_order_status") != "pass":
            issues.append("load_order_not_pass")
        if runtime_first_status != "sidecar":
            issues.append(f"runtime_first_not_sidecar:{runtime_first_status or 'missing'}")
        if file_id in sidecar_hit_ids:
            played_lookup_status = "sidecar_hit"
        elif file_id in all_lookup_hit_ids:
            played_lookup_status = "non_sidecar_hit"
            issues.append("played_lookup_not_sidecar")
        else:
            played_lookup_status = "missing"
            issues.append("played_lookup_missing")

        file_io_seek_status = "target_seek" if file_id in file_io_seek_ids else "missing"
        file_io_read_status = "target_read" if file_id in file_io_read_ids else "missing"

        if payloads_resident:
            payload_residency_status = "resident"
        elif file_io_read_status == "target_read":
            payload_residency_status = "file_read_observed"
        else:
            payload_residency_status = "file_backed_not_observed"
            issues.append("payload_read_not_observed")

        load_order_status = "pass" if runtime_first_status == "sidecar" else "gap"

        firstframe_dir = Path(
            f"output/vqa_batch_firstframes/L20_BBI_{load_row.get('index', '')}_{file_id}"
        )
        target_rows.append(
            {
                "source_archive": load_row.get("source_archive", ""),
                "index": load_row.get("index", ""),
                "file_id": file_id,
                "source_size": load_row.get("source_size", readiness.get("manifest_source_size", "")),
                "source_width": readiness.get("width", ""),
                "source_height": readiness.get("height", ""),
                "declared_frames": readiness.get("declared_frames", ""),
                "fullhd_frames": readiness.get("fullhd_frames", ""),
                "replacement_path": pack.get("replacement_path", readiness.get("replacement_path", "")),
                "replacement_size": load_row.get("replacement_size", pack.get("replacement_size", "")),
                "sidecar_archive": load_row.get("sidecar_archive", pack.get("sidecar_archive", "")),
                "sidecar_offset": runtime.get("first_entry_offset", load_row.get("sidecar_offset", "")),
                "sidecar_size": load_row.get("sidecar_size", runtime_first_size),
                "runtime_first_archive": runtime_first_archive,
                "runtime_first_order": runtime_first_order,
                "load_order_status": load_order_status,
                "played_lookup_status": played_lookup_status,
                "payload_residency_status": payload_residency_status,
                "file_io_seek_status": file_io_seek_status,
                "file_io_read_status": file_io_read_status,
                "firstframe_dir": relative_existing(firstframe_dir),
                "issues": ";".join(issues),
                "next_step": (
                    "capture a gameplay/requested VQA read for this hash with the file-I/O trace runner"
                    if played_lookup_status == "missing" or file_io_read_status == "missing"
                    else "verify the selected archive and payload bytes"
                ),
            }
        )

    load_order_pass = sum(1 for row in target_rows if row["load_order_status"] == "pass")
    runtime_sidecar_first = sum(1 for row in target_rows if row["runtime_first_archive"].lower().endswith("_hd.mix"))
    runtime_base_first = sum(
        1 for row in target_rows if row["runtime_first_archive"] and not row["runtime_first_archive"].lower().endswith("_hd.mix")
    )
    runtime_missing = sum(1 for row in target_rows if not row["runtime_first_archive"])
    runtime_unknown_first = sum(
        1
        for row in runtime_target_rows
        if row.get("file_id", "").lower() in {target.get("file_id", "") for target in target_rows}
        and row.get("first_status") == "unknown_size"
    )
    file_backed_targets = sum(
        1 for row in target_rows if row["payload_residency_status"].startswith("file_")
    )
    resident_payload_targets = sum(1 for row in target_rows if row["payload_residency_status"] == "resident")
    file_read_observed_targets = sum(
        1 for row in target_rows if row["payload_residency_status"] == "file_read_observed"
    )
    payload_read_evidence_targets = resident_payload_targets + file_read_observed_targets
    played_missing = sum(1 for row in target_rows if row["played_lookup_status"] == "missing")
    played_or_read_hits = max(sidecar_hit_count, file_io_target_read_hits)

    summary = {
        "status": "pass"
        if target_rows
        and load_order_pass == len(target_rows)
        and runtime_sidecar_first == len(target_rows)
        and played_or_read_hits == len(target_rows)
        and payload_read_evidence_targets == len(target_rows)
        else "gap",
        "targets": str(len(target_rows)),
        "runtime_evidence_source": runtime_evidence_source,
        "load_order_pass": str(load_order_pass),
        "runtime_sidecar_first": str(runtime_sidecar_first),
        "runtime_base_first": str(runtime_base_first),
        "runtime_missing": str(runtime_missing),
        "runtime_unknown_first": str(runtime_unknown_first),
        "played_lookup_hits": str(target_hit_count),
        "played_sidecar_hits": str(sidecar_hit_count),
        "played_missing": str(played_missing),
        "file_backed_targets": str(file_backed_targets),
        "resident_payload_targets": str(resident_payload_targets),
        "stage_status": stage_summary.get("status", ""),
        "file_io_contract_status": file_io_summary.get("contract_status", ""),
        "file_io_tracepoints": file_io_summary.get("tracepoints", ""),
        "file_io_offset_min": file_io_summary.get("expected_offset_min", ""),
        "file_io_offset_max": file_io_summary.get("expected_offset_max", ""),
        "file_io_trace_attempt_status": file_io_attempt_summary.get("status", ""),
        "file_io_trace_attempt_session": file_io_attempt_summary.get("session_status", ""),
        "file_io_archive_scan_phase": file_io_attempt_summary.get("archive_scan_phase", ""),
        "file_io_archive_nodes": file_io_attempt_summary.get("archive_nodes", ""),
        "file_io_archive_names": file_io_attempt_summary.get("archive_names", ""),
        "file_io_sidecar_path_hits": file_io_attempt_summary.get("sidecar_path_hits", ""),
        "file_io_archive_pointer_mapped_hits": file_io_attempt_summary.get("archive_pointer_mapped_hits", ""),
        "file_io_sidecar_archive_pointer_hits": file_io_attempt_summary.get(
            "sidecar_archive_pointer_hits", ""
        ),
        "file_io_target_offset_seek_hits": file_io_attempt_summary.get("target_offset_seek_hits", ""),
        "file_io_unmapped_target_offset_seek_hits": file_io_attempt_summary.get(
            "unmapped_target_offset_seek_hits", ""
        ),
        "file_io_target_seek_hits": file_io_attempt_summary.get("target_seek_hits", ""),
        "file_io_target_read_hits": file_io_attempt_summary.get("target_read_hits", ""),
        "file_io_target_read_ids_seen": file_io_attempt_summary.get("target_read_ids_seen", ""),
        "payload_read_evidence_targets": str(payload_read_evidence_targets),
        "sidecar_archive": sidecar_archive.get("name", ""),
        "sidecar_body_pointer": sidecar_body_pointer,
        "issues": ";".join(
            issue
            for issue, present in [
                ("played_lookup_missing", played_missing > 0),
                ("runtime_first_not_sidecar", runtime_sidecar_first < len(target_rows)),
                ("payload_read_not_observed", payload_read_evidence_targets < len(target_rows)),
                ("file_io_trace_attempt_missing", not file_io_attempt_summary),
            ]
            if present
        ),
        "next_step": (
            "change sidecar insertion order so duplicate VQA IDs are found before l20_bbI.MIX"
            if runtime_sidecar_first < len(target_rows)
            else "run tools/run_lolg95_sidecar_file_io_trace_attempt.py under xvfb-run and drive/request one target VQA"
        ),
    }
    return target_rows, summary


def build_requirements(summary: dict[str, str], target_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    target_count = count_int(summary.get("targets", ""))
    return [
        {
            "requirement": "runtime_stage",
            "status": pass_if(summary.get("stage_status") == "pass"),
            "evidence": f"stage_status={summary.get('stage_status', '')}",
            "next_step": "rerun tools/lolg95_sidecar_runtime_stage.py",
        },
        {
            "requirement": "runtime_load_order",
            "status": pass_if(
                target_count > 0
                and count_int(summary.get("load_order_pass", "")) == target_count
                and count_int(summary.get("runtime_sidecar_first", "")) == target_count
            ),
            "evidence": (
                f"source={summary.get('runtime_evidence_source', '')};"
                f"load_order_pass={summary.get('load_order_pass', '')}/{target_count};"
                f"runtime_sidecar_first={summary.get('runtime_sidecar_first', '')}/{target_count};"
                f"runtime_base_first={summary.get('runtime_base_first', '')}/{target_count};"
                f"runtime_missing={summary.get('runtime_missing', '')}/{target_count}"
            ),
            "next_step": "change the additive patch so L20_BBI_HD.MIX is inserted before l20_bbI.MIX",
        },
        {
            "requirement": "file_io_trace_contract",
            "status": pass_if(
                summary.get("file_io_contract_status") == "pass"
                and count_int(summary.get("file_io_tracepoints", "")) == 2
            ),
            "evidence": (
                f"contract_status={summary.get('file_io_contract_status', '')};"
                f"tracepoints={summary.get('file_io_tracepoints', '')};"
                f"offsets={summary.get('file_io_offset_min', '')}..{summary.get('file_io_offset_max', '')}"
            ),
            "next_step": "rerun tools/lolg95_sidecar_file_io_trace_contract.py",
        },
        {
            "requirement": "file_io_trace_attempt",
            "status": pass_if(
                summary.get("file_io_trace_attempt_status") == "pass"
                and count_int(summary.get("file_io_target_read_hits", "")) > 0
            ),
            "evidence": (
                f"attempt_status={summary.get('file_io_trace_attempt_status', '')};"
                f"session={summary.get('file_io_trace_attempt_session', '')};"
                f"archive_scan={summary.get('file_io_archive_scan_phase', '')}/"
                f"{summary.get('file_io_archive_nodes', '')};"
                f"sidecar_path_hits={summary.get('file_io_sidecar_path_hits', '')};"
                f"archive_pointer_mapped_hits={summary.get('file_io_archive_pointer_mapped_hits', '')};"
                f"sidecar_archive_pointer_hits={summary.get('file_io_sidecar_archive_pointer_hits', '')};"
                f"target_offset_seek_hits={summary.get('file_io_target_offset_seek_hits', '')};"
                f"unmapped_target_offset_seek_hits={summary.get('file_io_unmapped_target_offset_seek_hits', '')};"
                f"target_seek_hits={summary.get('file_io_target_seek_hits', '')};"
                f"target_read_hits={summary.get('file_io_target_read_hits', '')}"
            ),
            "next_step": "run tools/run_lolg95_sidecar_file_io_trace_attempt.py under xvfb-run",
        },
        {
            "requirement": "target_metadata",
            "status": pass_if(
                target_count > 0
                and all(row["source_width"] and row["source_height"] and row["replacement_path"] for row in target_rows)
            ),
            "evidence": f"targets={target_count}",
            "next_step": "rerun the VQA repack readiness and sidecar pack reports",
        },
        {
            "requirement": "played_lookup",
            "status": pass_if(
                target_count > 0
                and (
                    count_int(summary.get("played_sidecar_hits", "")) == target_count
                    or count_int(summary.get("file_io_target_read_hits", "")) == target_count
                )
            ),
            "evidence": (
                f"played_lookup_hits={summary.get('played_lookup_hits', '')};"
                f"played_sidecar_hits={summary.get('played_sidecar_hits', '')}/{target_count};"
                f"played_missing={summary.get('played_missing', '')};"
                f"file_io_target_read_hits={summary.get('file_io_target_read_hits', '')}/{target_count}"
            ),
            "next_step": "capture gameplay or targeted file-I/O evidence for the 8 deferred VQA hashes",
        },
        {
            "requirement": "payload_read_evidence",
            "status": pass_if(
                target_count > 0 and count_int(summary.get("payload_read_evidence_targets", "")) == target_count
            ),
            "evidence": (
                f"sidecar_body_pointer={summary.get('sidecar_body_pointer', '')};"
                f"file_backed_targets={summary.get('file_backed_targets', '')}/{target_count};"
                f"payload_read_evidence_targets={summary.get('payload_read_evidence_targets', '')}/{target_count};"
                f"file_io_target_read_ids_seen={summary.get('file_io_target_read_ids_seen', '')}"
            ),
            "next_step": "trace file reads after a target hash is requested",
        },
    ]


def render_html(path: Path, summary: dict[str, str], requirements: list[dict[str, str]], targets: list[dict[str, str]]) -> None:
    def esc(value: str) -> str:
        return html.escape(str(value))

    requirement_rows = "\n".join(
        "<tr>"
        f"<td>{esc(row['requirement'])}</td>"
        f"<td class=\"status-{esc(row['status'])}\">{esc(row['status'])}</td>"
        f"<td>{esc(row['evidence'])}</td>"
        f"<td>{esc(row['next_step'])}</td>"
        "</tr>"
        for row in requirements
    )
    target_rows = "\n".join(
        "<tr>"
        f"<td>{esc(row['index'])}</td>"
        f"<td>{esc(row['file_id'])}</td>"
        f"<td>{esc(row['source_width'])}x{esc(row['source_height'])}</td>"
        f"<td>{esc(row['fullhd_frames'])}</td>"
        f"<td>{esc(row['runtime_first_archive'])}</td>"
        f"<td>{esc(row['sidecar_offset'])}</td>"
        f"<td>{esc(row['sidecar_size'])}</td>"
        f"<td class=\"status-{esc(row['played_lookup_status'])}\">{esc(row['played_lookup_status'])}</td>"
        f"<td>{esc(row['payload_residency_status'])}</td>"
        f"<td>{esc(row['file_io_seek_status'])}</td>"
        f"<td>{esc(row['file_io_read_status'])}</td>"
        f"<td>{esc(row['issues'])}</td>"
        "</tr>"
        for row in targets
    )
    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>LOLG95 Sidecar Played-Read Plan</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; color: #1d2329; background: #f7f7f4; }}
    h1, h2 {{ margin: 0 0 12px; }}
    section {{ margin: 0 0 28px; }}
    table {{ width: 100%; border-collapse: collapse; background: white; }}
    th, td {{ padding: 8px 10px; border-bottom: 1px solid #d9d9d2; text-align: left; vertical-align: top; }}
    th {{ background: #ecece4; }}
    .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; }}
    .metric {{ background: white; border: 1px solid #d9d9d2; padding: 10px; }}
    .metric strong {{ display: block; font-size: 0.86rem; color: #4b5258; }}
    .status-pass {{ color: #176c37; font-weight: 700; }}
    .status-gap, .status-missing, .status-file_backed_not_observed {{ color: #9a4d00; font-weight: 700; }}
    code {{ overflow-wrap: anywhere; }}
  </style>
</head>
<body>
  <h1>LOLG95 Sidecar Played-Read Plan</h1>
  <section class="summary">
    <div class="metric"><strong>Status</strong>{esc(summary['status'])}</div>
    <div class="metric"><strong>Targets</strong>{esc(summary['targets'])}</div>
    <div class="metric"><strong>Runtime evidence</strong>{esc(summary['runtime_evidence_source'])}</div>
    <div class="metric"><strong>Runtime sidecar first</strong>{esc(summary['runtime_sidecar_first'])}</div>
    <div class="metric"><strong>Runtime base first</strong>{esc(summary['runtime_base_first'])}</div>
    <div class="metric"><strong>Played sidecar hits</strong>{esc(summary['played_sidecar_hits'])}</div>
    <div class="metric"><strong>I/O archive scan</strong>{esc(summary['file_io_archive_scan_phase'])}/{esc(summary['file_io_archive_nodes'])}</div>
    <div class="metric"><strong>File-I/O target reads</strong>{esc(summary['file_io_target_read_hits'])}</div>
    <div class="metric"><strong>File-backed targets</strong>{esc(summary['file_backed_targets'])}</div>
    <div class="metric"><strong>Sidecar body pointer</strong><code>{esc(summary['sidecar_body_pointer'])}</code></div>
  </section>
  <section>
    <h2>Requirements</h2>
    <table>
      <thead><tr><th>Requirement</th><th>Status</th><th>Evidence</th><th>Next step</th></tr></thead>
      <tbody>{requirement_rows}</tbody>
    </table>
  </section>
  <section>
    <h2>Targets</h2>
    <table>
      <thead>
        <tr><th>Index</th><th>Hash</th><th>Source geom</th><th>Frames</th><th>Runtime archive</th><th>Offset</th><th>Sidecar size</th><th>Lookup</th><th>Payload</th><th>I/O seek</th><th>I/O read</th><th>Issues</th></tr>
      </thead>
      <tbody>{target_rows}</tbody>
    </table>
  </section>
  <section>
    <h2>Next Step</h2>
    <p>{esc(summary['next_step'])}</p>
  </section>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def build_report(args: argparse.Namespace) -> dict[str, str]:
    targets, summary = build_targets(args)
    requirements = build_requirements(summary, targets)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDS, [summary])
    write_csv(args.output / "requirements.csv", REQUIREMENT_FIELDS, requirements)
    write_csv(args.output / "targets.csv", TARGET_FIELDS, targets)
    render_html(args.output / "index.html", summary, requirements, targets)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a played-read proof gap report for the LOLG95 L20 sidecar.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--load-plan-entries", type=Path, default=DEFAULT_LOAD_PLAN_ENTRIES)
    parser.add_argument("--repack-readiness-entries", type=Path, default=DEFAULT_REPACK_READINESS_ENTRIES)
    parser.add_argument("--sidecar-pack-entries", type=Path, default=DEFAULT_SIDECAR_PACK_ENTRIES)
    parser.add_argument("--runtime-archives", type=Path, default=DEFAULT_RUNTIME_ARCHIVES)
    parser.add_argument("--runtime-targets", type=Path, default=DEFAULT_RUNTIME_TARGETS)
    parser.add_argument("--lookup-summary", type=Path, default=DEFAULT_LOOKUP_SUMMARY)
    parser.add_argument("--stage-summary", type=Path, default=DEFAULT_STAGE_SUMMARY)
    parser.add_argument("--file-io-contract-summary", type=Path, default=DEFAULT_FILE_IO_CONTRACT_SUMMARY)
    parser.add_argument("--file-io-trace-attempt-summary", type=Path, default=DEFAULT_FILE_IO_TRACE_ATTEMPT_SUMMARY)
    parser.add_argument("--file-io-trace-attempt-archives", type=Path, default=DEFAULT_FILE_IO_TRACE_ATTEMPT_ARCHIVES)
    parser.add_argument("--file-io-trace-attempt-targets", type=Path, default=DEFAULT_FILE_IO_TRACE_ATTEMPT_TARGETS)
    args = parser.parse_args()

    summary = build_report(args)
    print(
        "LOLG95 sidecar played-read plan: "
        f"{summary['status']} "
        f"(played sidecar hits {summary['played_sidecar_hits']}/{summary['targets']}, "
        f"file-backed {summary['file_backed_targets']}/{summary['targets']})"
    )


if __name__ == "__main__":
    main()
