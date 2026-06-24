#!/usr/bin/env python3
"""Summarize what is still required for runtime Full HD VQA playback."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path


DEFAULT_BATCH_DIR = Path("output/vqa_batch_window_lcw_transparent0_allframes")
DEFAULT_OUTPUT = Path("output/vqa_runtime_feasibility")
DEFAULT_RUNTIME_PACK = Path("mod_mix_vqa_fullhd")
DEFAULT_REPACK_READINESS_SUMMARY = Path("output/vqa_runtime_repack_readiness/summary.csv")
DEFAULT_RUNTIME_PACK_BUILD_SUMMARY = Path("output/vqa_runtime_pack_build/summary.csv")
DEFAULT_RUNTIME_OVERSIZE_SUMMARY = Path("output/vqa_runtime_oversize_budget/summary.csv")
DEFAULT_LCW_LITERAL_PROBE_SUMMARY = Path("output/vqa_lcw_literal_probe/summary.csv")
DEFAULT_LCW_COMPRESSION_PROBE_SUMMARY = Path("output/vqa_lcw_compression_probe/summary.csv")
DEFAULT_NATIVE_EXACT_FIXTURE_SUMMARY = Path("output/vqa_native_exact_fixture_writer/summary.csv")
DEFAULT_FULLHD_REPLACEMENT_SUMMARY = Path("output/vqa_fullhd_replacement_writer/summary.csv")

SUMMARY_FIELDS = [
    "status",
    "entries",
    "archives",
    "declared_frames",
    "fullhd_frames",
    "source_bytes",
    "issue_rows",
    "resolutions",
    "pointer_chunks",
    "pointer_decode_statuses",
    "render_status_counts",
    "render_notes",
    "cbp_decode_statuses",
    "partial_codebook_update_entries",
    "codebook_update_vectors",
    "encoder_tools",
    "runtime_pack_files",
    "runtime_pack_entries",
    "repack_readiness_status",
    "repack_mapped_entries",
    "repack_entry_issues",
    "repack_roundtrip_archives",
    "repack_roundtrip_failures",
    "runtime_pack_build_status",
    "runtime_pack_build_replacements",
    "runtime_pack_build_applied_replacements",
    "runtime_pack_build_deferred_replacements",
    "runtime_pack_build_missing_replacements",
    "runtime_pack_build_output_archives",
    "runtime_oversize_status",
    "runtime_oversize_archives",
    "runtime_oversize_deferred_replacements",
    "runtime_oversize_headroom_bytes",
    "runtime_oversize_required_reduction_bytes",
    "lcw_literal_probe_status",
    "lcw_literal_encoder_status",
    "lcw_literal_roundtrip_cases",
    "lcw_literal_roundtrip_failures",
    "lcw_native_exact_block_entries",
    "lcw_fullhd_naive_exact_block_entries",
    "lcw_compression_probe_status",
    "lcw_compression_probe_mode",
    "lcw_compression_probe_entries",
    "lcw_compression_probe_frames",
    "lcw_compression_probe_saved_bytes",
    "lcw_compression_probe_saved_ratio",
    "native_exact_fixture_status",
    "native_exact_fixture_frames",
    "native_exact_fixture_matched_frames",
    "native_exact_fixture_payload_bytes",
    "fullhd_replacement_writer_status",
    "fullhd_replacement_writer_frames",
    "fullhd_replacement_writer_validated_frames",
    "fullhd_replacement_writer_payload_bytes",
    "fullhd_replacement_writer_exact_block_ratio",
    "fullhd_replacement_writer_changed_pixel_ratio",
    "fullhd_replacement_writer_path",
    "requirements",
    "issues",
    "next_step",
]

REQUIREMENT_FIELDS = ["requirement", "status", "evidence", "next_step"]

ARCHIVE_FIELDS = [
    "archive_tag",
    "archive",
    "entries",
    "declared_frames",
    "fullhd_frames",
    "source_bytes",
    "resolutions",
    "pointer_chunks",
    "pointer_decode_statuses",
    "issue_rows",
]

RESOLUTION_FIELDS = [
    "resolution",
    "entries",
    "archives",
    "declared_frames",
    "fullhd_frames",
    "source_bytes",
    "pointer_chunks",
]

POINTER_FIELDS = [
    "pointer_chunk",
    "pointer_decode_status",
    "entries",
    "archives",
    "declared_frames",
    "fullhd_frames",
    "source_bytes",
    "resolutions",
    "cbp_decode_statuses",
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


def ratio_value(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "0.000000"
    return f"{numerator / denominator:.6f}"


def key_for(row: dict[str, str]) -> tuple[str, str, str]:
    return (row.get("archive", ""), row.get("index", ""), row.get("file_id", ""))


def archive_tag(path_text: str) -> str:
    return Path(path_text).stem.upper() if path_text else "UNKNOWN"


def split_counts(text: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for part in text.split(";"):
        if not part:
            continue
        key, _, raw_count = part.partition(":")
        if not key:
            continue
        try:
            counts[key] += int(raw_count)
        except ValueError:
            counts[key] += 1
    return counts


def count_text(counter: Counter[str]) -> str:
    return ";".join(f"{key}:{count}" for key, count in sorted(counter.items()))


def note_category(note: str) -> str:
    if note.startswith("CBP appended"):
        return "CBP appended vectors"
    if note.startswith("CBP partial codebook update failed"):
        return "CBP partial codebook update failed"
    return note


def encoder_candidates() -> list[Path]:
    candidates = set(Path("tools").glob("*vqa*encode*.py"))
    candidates.update(Path("tools").glob("*encode*vqa*.py"))
    replacement_writer = Path("tools/lolg_vqa_fullhd_replacement_writer.py")
    if replacement_writer.exists():
        candidates.add(replacement_writer)
    return sorted(candidates)


def runtime_pack_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    if path.is_file():
        return [path]
    return sorted(item for item in path.rglob("*") if item.is_file())


def writer_summary_paths(summary_path: Path) -> list[Path]:
    paths = {summary_path}
    parent = summary_path.parent
    if parent.parent.exists():
        paths.update(parent.parent.glob(f"{parent.name}*/summary.csv"))
    return sorted(paths)


def aggregate_fullhd_replacement_summaries(summary_path: Path) -> dict[str, str]:
    main_rows = read_csv(summary_path)
    main_summary = main_rows[0] if main_rows else {}
    runtime_path = main_summary.get("runtime_replacement_path", "")
    aggregate_rows: list[dict[str, str]] = []
    for path in writer_summary_paths(summary_path):
        rows = read_csv(path)
        if not rows:
            continue
        row = dict(rows[0])
        frames = int_value(row, "frames")
        validated = int_value(row, "validated_frames")
        payload_bytes = int_value(row, "payload_bytes")
        row_runtime_path = row.get("runtime_replacement_path", "")
        if row.get("status") != "pass":
            continue
        if frames <= 0 or validated != frames or payload_bytes <= 0:
            continue
        if row.get("issues", ""):
            continue
        if runtime_path and row_runtime_path != runtime_path:
            continue
        if Path(row_runtime_path).is_absolute():
            continue
        aggregate_rows.append(row)

    if not aggregate_rows:
        return main_summary
    if len(aggregate_rows) == 1:
        return aggregate_rows[0]

    frames = sum(int_value(row, "frames") for row in aggregate_rows)
    validated = sum(int_value(row, "validated_frames") for row in aggregate_rows)
    payload_bytes = sum(int_value(row, "payload_bytes") for row in aggregate_rows)
    exact_blocks = sum(int_value(row, "exact_blocks") for row in aggregate_rows)
    fallback_blocks = sum(int_value(row, "fallback_blocks") for row in aggregate_rows)
    changed_pixels = sum(int_value(row, "changed_pixels") for row in aggregate_rows)
    block_count = max((int_value(row, "block_count") for row in aggregate_rows), default=0)
    width = max((int_value(row, "width") for row in aggregate_rows), default=0)
    height = max((int_value(row, "height") for row in aggregate_rows), default=0)
    max_codebook_entries = max((int_value(row, "max_codebook_entries") for row in aggregate_rows), default=0)
    max_vectors_used = max((int_value(row, "max_vectors_used") for row in aggregate_rows), default=0)
    aggregate = dict(aggregate_rows[0])
    aggregate.update(
        {
            "status": "pass" if validated == frames else "gap",
            "archive": f"aggregate:{len(aggregate_rows)}",
            "index": "",
            "file_id": "",
            "source_dir": str(summary_path.parent.parent),
            "frames": str(frames),
            "validated_frames": str(validated),
            "width": str(width),
            "height": str(height),
            "block_count": str(block_count),
            "max_codebook_entries": str(max_codebook_entries),
            "max_vectors_used": str(max_vectors_used),
            "exact_blocks": str(exact_blocks),
            "fallback_blocks": str(fallback_blocks),
            "exact_block_ratio": ratio_value(exact_blocks, block_count * frames),
            "changed_pixels": str(changed_pixels),
            "changed_pixel_ratio": ratio_value(changed_pixels, width * height * frames),
            "payload_bytes": str(payload_bytes),
            "payload_sha256": "",
            "issues": "",
        }
    )
    return aggregate


class Totals:
    def __init__(self) -> None:
        self.entries = 0
        self.archives: set[str] = set()
        self.declared_frames = 0
        self.fullhd_frames = 0
        self.source_bytes = 0
        self.issue_rows = 0
        self.resolutions: Counter[str] = Counter()
        self.pointer_chunks: Counter[str] = Counter()
        self.pointer_decode_statuses: Counter[str] = Counter()
        self.render_status_counts: Counter[str] = Counter()
        self.render_notes: Counter[str] = Counter()
        self.cbp_decode_statuses: Counter[str] = Counter()
        self.partial_codebook_update_entries = 0
        self.codebook_update_vectors = 0

    def add(self, manifest_row: dict[str, str], verify_row: dict[str, str]) -> None:
        archive = manifest_row.get("archive") or verify_row.get("archive", "")
        self.entries += 1
        if archive:
            self.archives.add(archive)
        self.declared_frames += int_value(manifest_row, "declared_frames") or int_value(
            verify_row, "declared_frames"
        )
        self.fullhd_frames += int_value(verify_row, "fullhd_frames") or int_value(
            manifest_row, "fullhd_frames"
        )
        self.source_bytes += int_value(manifest_row, "source_size")
        if verify_row.get("issues") or manifest_row.get("error"):
            self.issue_rows += 1

        width = manifest_row.get("width", "")
        height = manifest_row.get("height", "")
        if width and height:
            self.resolutions[f"{width}x{height}"] += 1
        self.pointer_chunks[manifest_row.get("pointer_chunk", "") or "unknown"] += 1
        self.pointer_decode_statuses[manifest_row.get("pointer_decode_status", "") or "unknown"] += 1
        self.render_status_counts.update(split_counts(verify_row.get("render_status_counts", "")))

        note = manifest_row.get("render_note", "")
        if note:
            for part in note.split(";"):
                clean = part.strip()
                if clean:
                    self.render_notes[note_category(clean)] += 1

        cbp_status = manifest_row.get("cbp_decode_status", "") or "none"
        self.cbp_decode_statuses[cbp_status] += 1
        if (manifest_row.get("partial_codebook_update", "") or "").lower() == "yes":
            self.partial_codebook_update_entries += 1
        self.codebook_update_vectors += int_value(manifest_row, "codebook_update_vectors")

    def common_row(self) -> dict[str, str]:
        return {
            "entries": str(self.entries),
            "archives": str(len(self.archives)),
            "declared_frames": str(self.declared_frames),
            "fullhd_frames": str(self.fullhd_frames),
            "source_bytes": str(self.source_bytes),
            "issue_rows": str(self.issue_rows),
            "resolutions": count_text(self.resolutions),
            "pointer_chunks": count_text(self.pointer_chunks),
            "pointer_decode_statuses": count_text(self.pointer_decode_statuses),
            "render_status_counts": count_text(self.render_status_counts),
            "render_notes": count_text(self.render_notes),
            "cbp_decode_statuses": count_text(self.cbp_decode_statuses),
            "partial_codebook_update_entries": str(self.partial_codebook_update_entries),
            "codebook_update_vectors": str(self.codebook_update_vectors),
        }


def build_requirement_rows(
    totals: Totals,
    encoders: list[Path],
    pack_files: list[Path],
    repack_summary: dict[str, str],
    pack_build_summary: dict[str, str],
    oversize_summary: dict[str, str],
    lcw_summary: dict[str, str],
    lcw_compression_summary: dict[str, str],
    native_fixture_summary: dict[str, str],
    fullhd_replacement_summary: dict[str, str],
) -> list[dict[str, str]]:
    repack_mapped_entries = int_value(repack_summary, "mapped_entries") if repack_summary else 0
    repack_entry_issues = int_value(repack_summary, "entry_issues") if repack_summary else 0
    repack_roundtrip_archives = int_value(repack_summary, "roundtrip_archives") if repack_summary else 0
    repack_roundtrip_failures = int_value(repack_summary, "roundtrip_failures") if repack_summary else 0
    repack_roundtrip_ready = (
        bool(repack_summary)
        and totals.entries > 0
        and len(totals.archives) > 0
        and repack_mapped_entries == totals.entries
        and repack_entry_issues == 0
        and repack_roundtrip_archives == len(totals.archives)
        and repack_roundtrip_failures == 0
    )
    pack_build_status = pack_build_summary.get("status", "missing") if pack_build_summary else "missing"
    pack_build_replacements = int_value(pack_build_summary, "replacement_entries") if pack_build_summary else 0
    pack_build_applied = int_value(pack_build_summary, "applied_replacements") if pack_build_summary else 0
    pack_build_deferred = int_value(pack_build_summary, "deferred_replacements") if pack_build_summary else 0
    pack_build_missing = int_value(pack_build_summary, "missing_replacements") if pack_build_summary else 0
    pack_build_outputs = int_value(pack_build_summary, "output_archives") if pack_build_summary else 0
    oversize_status = oversize_summary.get("status", "missing") if oversize_summary else "missing"
    oversize_archives = int_value(oversize_summary, "oversize_archives") if oversize_summary else 0
    oversize_deferred = int_value(oversize_summary, "deferred_replacements") if oversize_summary else 0
    oversize_headroom = int_value(oversize_summary, "headroom_bytes") if oversize_summary else 0
    oversize_required_reduction = (
        int_value(oversize_summary, "required_reduction_bytes") if oversize_summary else 0
    )
    materialized_runtime_pack = (
        pack_build_status == "pass"
        and pack_build_replacements == totals.entries
        and pack_build_applied == totals.entries
        and pack_build_deferred == 0
        and pack_build_missing == 0
        and pack_build_outputs == len(totals.archives)
        and len(pack_files) >= pack_build_outputs
    )
    lcw_roundtrip_cases = int_value(lcw_summary, "roundtrip_cases") if lcw_summary else 0
    lcw_roundtrip_failures = int_value(lcw_summary, "roundtrip_failures") if lcw_summary else 0
    lcw_native_exact_entries = int_value(lcw_summary, "native_exact_block_entries") if lcw_summary else 0
    lcw_literal_ready = bool(lcw_summary) and lcw_roundtrip_cases > 0 and lcw_roundtrip_failures == 0
    lcw_compression_status = (
        lcw_compression_summary.get("status", "missing") if lcw_compression_summary else "missing"
    )
    lcw_compression_saved = (
        int_value(lcw_compression_summary, "sample_saved_bytes") if lcw_compression_summary else 0
    )
    lcw_compression_ratio = lcw_compression_summary.get("sample_saved_ratio", "") if lcw_compression_summary else ""
    native_fixture_status = native_fixture_summary.get("status", "missing") if native_fixture_summary else "missing"
    native_fixture_frames = int_value(native_fixture_summary, "frames") if native_fixture_summary else 0
    native_fixture_matched = int_value(native_fixture_summary, "matched_frames") if native_fixture_summary else 0
    native_fixture_payload_bytes = int_value(native_fixture_summary, "payload_bytes") if native_fixture_summary else 0
    native_fixture_ready = (
        native_fixture_status == "pass"
        and native_fixture_frames > 0
        and native_fixture_matched == native_fixture_frames
        and native_fixture_payload_bytes > 0
    )
    fullhd_replacement_status = (
        fullhd_replacement_summary.get("status", "missing") if fullhd_replacement_summary else "missing"
    )
    fullhd_replacement_frames = int_value(fullhd_replacement_summary, "frames") if fullhd_replacement_summary else 0
    fullhd_replacement_validated = (
        int_value(fullhd_replacement_summary, "validated_frames") if fullhd_replacement_summary else 0
    )
    fullhd_replacement_payload_bytes = (
        int_value(fullhd_replacement_summary, "payload_bytes") if fullhd_replacement_summary else 0
    )
    fullhd_replacement_ready = (
        fullhd_replacement_status == "pass"
        and fullhd_replacement_frames > 0
        and fullhd_replacement_validated == fullhd_replacement_frames
        and fullhd_replacement_payload_bytes > 0
        and bool(fullhd_replacement_summary.get("runtime_replacement_path", ""))
    )
    rows = [
        {
            "requirement": "wvqa_encoder",
            "status": "pass" if fullhd_replacement_ready else "gap",
            "evidence": (
                f"tools={','.join(str(path) for path in encoders)};"
                f"fullhd_writer_status={fullhd_replacement_status};"
                f"validated_frames={fullhd_replacement_validated}/{fullhd_replacement_frames};"
                f"payload_bytes={fullhd_replacement_payload_bytes}"
                if fullhd_replacement_ready or encoders
                else "no encoder candidate in tools/"
            ),
            "next_step": "expand the Full HD WVQA replacement writer beyond the first validated payload",
        },
        {
            "requirement": "mix_repack",
            "status": "pass" if materialized_runtime_pack else "gap",
            "evidence": (
                f"pack_build_status={pack_build_status};"
                f"replacement_entries={pack_build_replacements}/{totals.entries};"
                f"applied_replacements={pack_build_applied}/{totals.entries};"
                f"deferred_replacements={pack_build_deferred};"
                f"missing_replacements={pack_build_missing};"
                f"output_archives={pack_build_outputs}/{len(totals.archives)};"
                f"runtime_pack_files={len(pack_files)};"
                f"oversize_status={oversize_status};"
                f"oversize_archives={oversize_archives};"
                f"oversize_deferred_replacements={oversize_deferred};"
                f"oversize_headroom_bytes={oversize_headroom};"
                f"oversize_required_reduction_bytes={oversize_required_reduction}"
            ),
            "next_step": "reduce oversized WVQA payloads enough to fit the 32-bit MIX body field, or provide a runtime override",
        },
        {
            "requirement": "mix_repack_roundtrip",
            "status": "pass" if repack_roundtrip_ready else "gap",
            "evidence": (
                f"mapped_entries={repack_mapped_entries}/{totals.entries};"
                f"entry_issues={repack_entry_issues};"
                f"roundtrip_archives={repack_roundtrip_archives}/{len(totals.archives)};"
                f"roundtrip_failures={repack_roundtrip_failures}"
            ),
            "next_step": "keep the verified VQA MIX mapping current before materializing the runtime pack",
        },
        {
            "requirement": "lcw_literal_encoder",
            "status": "pass" if lcw_literal_ready else "gap",
            "evidence": (
                f"roundtrip_cases={lcw_roundtrip_cases};"
                f"roundtrip_failures={lcw_roundtrip_failures};"
                f"native_exact_block_entries={lcw_native_exact_entries}"
            ),
            "next_step": "use the literal LCW primitive in a first WVQA fixture writer",
        },
        {
            "requirement": "lcw_format80_encoder",
            "status": "gap",
            "evidence": (
                f"pointer_decode_statuses={count_text(totals.pointer_decode_statuses)};"
                f"literal_lcw_roundtrip_cases={lcw_roundtrip_cases};"
                f"literal_lcw_native_exact_block_entries={lcw_native_exact_entries};"
                f"compression_probe_status={lcw_compression_status};"
                f"compression_probe_saved_bytes={lcw_compression_saved};"
                f"compression_probe_saved_ratio={lcw_compression_ratio}"
            ),
            "next_step": "connect literal LCW to CBFZ/VPTZ output, then add optimized/windowed variants where size limits require them",
        },
        {
            "requirement": "wvqa_native_fixture_writer",
            "status": "pass" if native_fixture_ready else "gap",
            "evidence": (
                f"status={native_fixture_status};"
                f"matched_frames={native_fixture_matched}/{native_fixture_frames};"
                f"payload_bytes={native_fixture_payload_bytes}"
            ),
            "next_step": "promote the native fixture writer into replacement payload generation, then add Full HD quantization",
        },
        {
            "requirement": "palette_codebook_pointer_encoder",
            "status": "pass" if fullhd_replacement_ready else "gap",
            "evidence": (
                f"resolutions={count_text(totals.resolutions)};"
                f"pointer_chunks={count_text(totals.pointer_chunks)};"
                f"fullhd_exact_block_ratio={fullhd_replacement_summary.get('exact_block_ratio', '')};"
                f"fullhd_changed_pixel_ratio={fullhd_replacement_summary.get('changed_pixel_ratio', '')}"
            ),
            "next_step": "improve quantizer quality and generalize palette/codebook/pointer encoding to all VQA entries",
        },
        {
            "requirement": "audio_handling",
            "status": "gap",
            "evidence": "decoder notes mark audio handling as future work",
            "next_step": "preserve or regenerate audio chunks before replacing movie payloads",
        },
    ]
    if totals.partial_codebook_update_entries or totals.codebook_update_vectors:
        rows.append(
            {
                "requirement": "cbp_update_encoder",
                "status": "gap",
                "evidence": (
                    f"partial_codebook_update_entries={totals.partial_codebook_update_entries};"
                    f"codebook_update_vectors={totals.codebook_update_vectors};"
                    f"cbp_decode_statuses={count_text(totals.cbp_decode_statuses)}"
                ),
                "next_step": "encode and validate CBPZ/CBP0 update forms instead of relying on first-frame-only export logic",
            }
        )
    return rows


def build_reports(
    batch_dir: Path,
    runtime_pack: Path,
    repack_readiness_summary: Path,
    runtime_pack_build_summary: Path,
    runtime_oversize_summary: Path,
    lcw_literal_probe_summary: Path,
    lcw_compression_probe_summary: Path,
    native_exact_fixture_summary: Path,
    fullhd_replacement_summary: Path,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    manifest_rows = read_csv(batch_dir / "manifest.csv")
    verify_rows = read_csv(batch_dir / "verification.csv")
    verify_by_key = {key_for(row): row for row in verify_rows}
    repack_summary_rows = read_csv(repack_readiness_summary)
    repack_summary = repack_summary_rows[0] if repack_summary_rows else {}
    pack_build_summary_rows = read_csv(runtime_pack_build_summary)
    pack_build_summary = pack_build_summary_rows[0] if pack_build_summary_rows else {}
    oversize_summary_rows = read_csv(runtime_oversize_summary)
    oversize_summary = oversize_summary_rows[0] if oversize_summary_rows else {}
    lcw_summary_rows = read_csv(lcw_literal_probe_summary)
    lcw_summary = lcw_summary_rows[0] if lcw_summary_rows else {}
    lcw_compression_summary_rows = read_csv(lcw_compression_probe_summary)
    lcw_compression_summary = lcw_compression_summary_rows[0] if lcw_compression_summary_rows else {}
    native_fixture_summary_rows = read_csv(native_exact_fixture_summary)
    native_fixture_summary = native_fixture_summary_rows[0] if native_fixture_summary_rows else {}
    fullhd_replacement = aggregate_fullhd_replacement_summaries(fullhd_replacement_summary)

    totals = Totals()
    by_archive: dict[str, Totals] = defaultdict(Totals)
    archive_paths: dict[str, str] = {}
    by_resolution: dict[str, Totals] = defaultdict(Totals)
    by_pointer: dict[tuple[str, str], Totals] = defaultdict(Totals)

    for manifest_row in manifest_rows:
        verify_row = verify_by_key.get(key_for(manifest_row), {})
        totals.add(manifest_row, verify_row)

        tag = archive_tag(manifest_row.get("archive", ""))
        archive_paths[tag] = manifest_row.get("archive", "")
        by_archive[tag].add(manifest_row, verify_row)

        width = manifest_row.get("width", "")
        height = manifest_row.get("height", "")
        resolution = f"{width}x{height}" if width and height else "unknown"
        by_resolution[resolution].add(manifest_row, verify_row)

        pointer_key = (
            manifest_row.get("pointer_chunk", "") or "unknown",
            manifest_row.get("pointer_decode_status", "") or "unknown",
        )
        by_pointer[pointer_key].add(manifest_row, verify_row)

    encoders = encoder_candidates()
    pack_files = runtime_pack_files(runtime_pack)
    requirement_rows = build_requirement_rows(
        totals,
        encoders,
        pack_files,
        repack_summary,
        pack_build_summary,
        oversize_summary,
        lcw_summary,
        lcw_compression_summary,
        native_fixture_summary,
        fullhd_replacement,
    )
    gap_requirements = [row["requirement"] for row in requirement_rows if row["status"] == "gap"]
    lcw_literal_encoder_status = next(
        (row["status"] for row in requirement_rows if row["requirement"] == "lcw_literal_encoder"),
        "missing",
    )
    issues = []
    if not manifest_rows:
        issues.append("missing_vqa_manifest")
    if not verify_rows:
        issues.append("missing_vqa_verification")
    if totals.issue_rows:
        issues.append("vqa_export_verification_has_issues")
    issues.extend(f"requirement_gap:{requirement}" for requirement in gap_requirements)

    summary = totals.common_row()
    summary.update(
        {
            "status": "pass" if manifest_rows and verify_rows and not issues else "gap",
            "encoder_tools": str(len(encoders)),
            "runtime_pack_files": str(len(pack_files)),
            "runtime_pack_entries": str(len(pack_files)),
            "repack_readiness_status": repack_summary.get("status", "missing") if repack_summary else "missing",
            "repack_mapped_entries": repack_summary.get("mapped_entries", ""),
            "repack_entry_issues": repack_summary.get("entry_issues", ""),
            "repack_roundtrip_archives": repack_summary.get("roundtrip_archives", ""),
            "repack_roundtrip_failures": repack_summary.get("roundtrip_failures", ""),
            "runtime_pack_build_status": pack_build_summary.get("status", "missing") if pack_build_summary else "missing",
            "runtime_pack_build_replacements": pack_build_summary.get("replacement_entries", ""),
            "runtime_pack_build_applied_replacements": pack_build_summary.get("applied_replacements", ""),
            "runtime_pack_build_deferred_replacements": pack_build_summary.get("deferred_replacements", ""),
            "runtime_pack_build_missing_replacements": pack_build_summary.get("missing_replacements", ""),
            "runtime_pack_build_output_archives": pack_build_summary.get("output_archives", ""),
            "runtime_oversize_status": oversize_summary.get("status", "missing") if oversize_summary else "missing",
            "runtime_oversize_archives": oversize_summary.get("oversize_archives", ""),
            "runtime_oversize_deferred_replacements": oversize_summary.get("deferred_replacements", ""),
            "runtime_oversize_headroom_bytes": oversize_summary.get("headroom_bytes", ""),
            "runtime_oversize_required_reduction_bytes": oversize_summary.get("required_reduction_bytes", ""),
            "lcw_literal_probe_status": lcw_summary.get("status", "missing") if lcw_summary else "missing",
            "lcw_literal_encoder_status": lcw_literal_encoder_status,
            "lcw_literal_roundtrip_cases": lcw_summary.get("roundtrip_cases", ""),
            "lcw_literal_roundtrip_failures": lcw_summary.get("roundtrip_failures", ""),
            "lcw_native_exact_block_entries": lcw_summary.get("native_exact_block_entries", ""),
            "lcw_fullhd_naive_exact_block_entries": lcw_summary.get("fullhd_naive_exact_block_entries", ""),
            "lcw_compression_probe_status": (
                lcw_compression_summary.get("status", "missing") if lcw_compression_summary else "missing"
            ),
            "lcw_compression_probe_mode": lcw_compression_summary.get("mode", ""),
            "lcw_compression_probe_entries": lcw_compression_summary.get("entries_sampled", ""),
            "lcw_compression_probe_frames": lcw_compression_summary.get("frames_sampled", ""),
            "lcw_compression_probe_saved_bytes": lcw_compression_summary.get("sample_saved_bytes", ""),
            "lcw_compression_probe_saved_ratio": lcw_compression_summary.get("sample_saved_ratio", ""),
            "native_exact_fixture_status": native_fixture_summary.get("status", "missing") if native_fixture_summary else "missing",
            "native_exact_fixture_frames": native_fixture_summary.get("frames", ""),
            "native_exact_fixture_matched_frames": native_fixture_summary.get("matched_frames", ""),
            "native_exact_fixture_payload_bytes": native_fixture_summary.get("payload_bytes", ""),
            "fullhd_replacement_writer_status": (
                fullhd_replacement.get("status", "missing") if fullhd_replacement else "missing"
            ),
            "fullhd_replacement_writer_frames": fullhd_replacement.get("frames", ""),
            "fullhd_replacement_writer_validated_frames": fullhd_replacement.get("validated_frames", ""),
            "fullhd_replacement_writer_payload_bytes": fullhd_replacement.get("payload_bytes", ""),
            "fullhd_replacement_writer_exact_block_ratio": fullhd_replacement.get("exact_block_ratio", ""),
            "fullhd_replacement_writer_changed_pixel_ratio": fullhd_replacement.get("changed_pixel_ratio", ""),
            "fullhd_replacement_writer_path": fullhd_replacement.get("runtime_replacement_path", ""),
            "requirements": ",".join(row["requirement"] for row in requirement_rows),
            "issues": ";".join(issues),
            "next_step": "build a WVQA encoder/repack path, then validate playback from a staged runtime pack",
        }
    )

    archive_rows = []
    for tag, stats in sorted(by_archive.items(), key=lambda item: item[0].lower()):
        row = stats.common_row()
        archive_rows.append(
            {
                "archive_tag": tag,
                "archive": archive_paths.get(tag, ""),
                "entries": row["entries"],
                "declared_frames": row["declared_frames"],
                "fullhd_frames": row["fullhd_frames"],
                "source_bytes": row["source_bytes"],
                "resolutions": row["resolutions"],
                "pointer_chunks": row["pointer_chunks"],
                "pointer_decode_statuses": row["pointer_decode_statuses"],
                "issue_rows": row["issue_rows"],
            }
        )

    resolution_rows = []
    for resolution, stats in sorted(by_resolution.items(), key=lambda item: (-item[1].fullhd_frames, item[0])):
        row = stats.common_row()
        resolution_rows.append(
            {
                "resolution": resolution,
                "entries": row["entries"],
                "archives": row["archives"],
                "declared_frames": row["declared_frames"],
                "fullhd_frames": row["fullhd_frames"],
                "source_bytes": row["source_bytes"],
                "pointer_chunks": row["pointer_chunks"],
            }
        )

    pointer_rows = []
    for (pointer_chunk, pointer_status), stats in sorted(
        by_pointer.items(), key=lambda item: (-item[1].fullhd_frames, item[0][0], item[0][1])
    ):
        row = stats.common_row()
        pointer_rows.append(
            {
                "pointer_chunk": pointer_chunk,
                "pointer_decode_status": pointer_status,
                "entries": row["entries"],
                "archives": row["archives"],
                "declared_frames": row["declared_frames"],
                "fullhd_frames": row["fullhd_frames"],
                "source_bytes": row["source_bytes"],
                "resolutions": row["resolutions"],
                "cbp_decode_statuses": row["cbp_decode_statuses"],
            }
        )

    return summary, requirement_rows, archive_rows, resolution_rows, pointer_rows


def render_table(rows: list[dict[str, str]], columns: list[str]) -> str:
    header = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(row.get(column, ''))}</td>" for column in columns)
        body.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_html(
    summary: dict[str, str],
    requirement_rows: list[dict[str, str]],
    archive_rows: list[dict[str, str]],
    resolution_rows: list[dict[str, str]],
    pointer_rows: list[dict[str, str]],
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "requirements": requirement_rows,
        "archives": archive_rows,
        "resolutions": resolution_rows,
        "pointers": pointer_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    top_archives = sorted(archive_rows, key=lambda row: int(row["fullhd_frames"]), reverse=True)[:24]
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme: dark; --bg: #101316; --panel: #171d22; --line: #2f3942; --text: #edf3f6; --muted: #9caab3; --accent: #74d3ae; }}
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
table {{ width: 100%; min-width: 860px; border-collapse: collapse; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
td {{ overflow-wrap: anywhere; }}
</style>
</head>
<body>
<header><div class="wrap"><h1>{html.escape(title)}</h1></div></header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Status</div><div class="value">{html.escape(summary['status'])}</div></div>
    <div class="stat"><div class="label">Entrees</div><div class="value">{html.escape(summary['entries'])}</div></div>
    <div class="stat"><div class="label">Frames Full HD</div><div class="value">{html.escape(summary['fullhd_frames'])}</div></div>
    <div class="stat"><div class="label">Encodeurs</div><div class="value">{html.escape(summary['encoder_tools'])}</div></div>
  </section>
  <section class="panel"><h2>Synthese</h2>{render_table([summary], SUMMARY_FIELDS)}</section>
  <section class="panel"><h2>Requirements runtime</h2>{render_table(requirement_rows, REQUIREMENT_FIELDS)}</section>
  <section class="panel"><h2>Archives principales</h2>{render_table(top_archives, ARCHIVE_FIELDS)}</section>
  <section class="panel"><h2>Resolutions</h2>{render_table(resolution_rows, RESOLUTION_FIELDS)}</section>
  <section class="panel"><h2>Pointeurs</h2>{render_table(pointer_rows, POINTER_FIELDS)}</section>
</main>
<script type="application/json" id="vqa-runtime-feasibility">{html.escape(data_json)}</script>
</body>
</html>
"""


def write_reports(
    batch_dir: Path,
    output: Path,
    runtime_pack: Path,
    repack_readiness_summary: Path,
    runtime_pack_build_summary: Path,
    runtime_oversize_summary: Path,
    lcw_literal_probe_summary: Path,
    lcw_compression_probe_summary: Path,
    native_exact_fixture_summary: Path,
    fullhd_replacement_summary: Path,
    title: str,
) -> dict[str, str]:
    summary, requirement_rows, archive_rows, resolution_rows, pointer_rows = build_reports(
        batch_dir,
        runtime_pack,
        repack_readiness_summary,
        runtime_pack_build_summary,
        runtime_oversize_summary,
        lcw_literal_probe_summary,
        lcw_compression_probe_summary,
        native_exact_fixture_summary,
        fullhd_replacement_summary,
    )
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "summary.csv", SUMMARY_FIELDS, [summary])
    write_csv(output / "requirements.csv", REQUIREMENT_FIELDS, requirement_rows)
    write_csv(output / "by_archive.csv", ARCHIVE_FIELDS, archive_rows)
    write_csv(output / "by_resolution.csv", RESOLUTION_FIELDS, resolution_rows)
    write_csv(output / "by_pointer.csv", POINTER_FIELDS, pointer_rows)
    (output / "index.html").write_text(
        build_html(summary, requirement_rows, archive_rows, resolution_rows, pointer_rows, title),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit VQA runtime Full HD feasibility.")
    parser.add_argument("--batch-dir", type=Path, default=DEFAULT_BATCH_DIR)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--runtime-pack", type=Path, default=DEFAULT_RUNTIME_PACK)
    parser.add_argument("--repack-readiness-summary", type=Path, default=DEFAULT_REPACK_READINESS_SUMMARY)
    parser.add_argument("--runtime-pack-build-summary", type=Path, default=DEFAULT_RUNTIME_PACK_BUILD_SUMMARY)
    parser.add_argument("--runtime-oversize-summary", type=Path, default=DEFAULT_RUNTIME_OVERSIZE_SUMMARY)
    parser.add_argument("--lcw-literal-probe-summary", type=Path, default=DEFAULT_LCW_LITERAL_PROBE_SUMMARY)
    parser.add_argument("--lcw-compression-probe-summary", type=Path, default=DEFAULT_LCW_COMPRESSION_PROBE_SUMMARY)
    parser.add_argument("--native-exact-fixture-summary", type=Path, default=DEFAULT_NATIVE_EXACT_FIXTURE_SUMMARY)
    parser.add_argument("--fullhd-replacement-summary", type=Path, default=DEFAULT_FULLHD_REPLACEMENT_SUMMARY)
    parser.add_argument("--title", default="Lands of Lore II VQA Runtime Feasibility")
    parser.add_argument("--fail-on-gaps", action="store_true")
    args = parser.parse_args()

    summary = write_reports(
        args.batch_dir,
        args.output,
        args.runtime_pack,
        args.repack_readiness_summary,
        args.runtime_pack_build_summary,
        args.runtime_oversize_summary,
        args.lcw_literal_probe_summary,
        args.lcw_compression_probe_summary,
        args.native_exact_fixture_summary,
        args.fullhd_replacement_summary,
        args.title,
    )
    print(f"VQA runtime feasibility: {summary['status']} ({summary['entries']} entries)")
    print(f"Requirements: {args.output / 'requirements.csv'}")
    print(f"Summary: {args.output / 'summary.csv'}")
    print(f"HTML: {args.output / 'index.html'}")
    if args.fail_on_gaps and summary["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
