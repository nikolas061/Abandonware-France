#!/usr/bin/env python3
"""Build a static dashboard for generated Full HD game assets and reports."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
from pathlib import Path


DEFAULT_OUTPUT = Path("output/fullhd_dashboard/index.html")
DEFAULT_AUDIT = Path("output/fullhd_audit/audit.csv")
DEFAULT_AUDIT_SUMMARY = Path("output/fullhd_audit/summary.csv")
DEFAULT_RUNTIME_AUDIT = Path("output/fullhd_runtime_audit/index.html")
DEFAULT_RUNTIME_AUDIT_SUMMARY = Path("output/fullhd_runtime_audit/summary.csv")
DEFAULT_RUNTIME_AUDIT_DETAILS = Path("output/fullhd_runtime_audit/details.csv")
DEFAULT_PCX_SENTINEL_PROOF = Path("output/fullhd_pcx_runtime_sentinel/proof.tsv")
DEFAULT_PCX_SENTINEL_REPORT = Path("output/fullhd_pcx_runtime_sentinel/report.csv")
DEFAULT_PCX_SENTINEL_SMOKE = Path("output/fullhd_pcx_runtime_sentinel_smoke/runtime_smoke.tsv")
DEFAULT_INVENTORY_SUMMARY = Path("output/fullhd_inventory/summary.csv")
DEFAULT_PROJECT_LEGACY_INVENTORY = Path("output/project_legacy_inventory/index.html")
DEFAULT_PROJECT_LEGACY_MANIFEST = Path("output/project_legacy_inventory/manifest.csv")
DEFAULT_EXTERNAL_LEGACY_MEDIA_REVIEW = Path("output/external_legacy_media_review/index.html")
DEFAULT_VQA_GALLERY = Path("output/vqa_batch_window_lcw_transparent0_allframes/index.html")
DEFAULT_VQA_GALLERY_MANIFEST = Path(
    "output/vqa_batch_window_lcw_transparent0_allframes/gallery_manifest.csv"
)
DEFAULT_VQA_STATUS = Path("output/vqa_batch_window_lcw_transparent0_allframes/status.html")
DEFAULT_VQA_RUNTIME_FEASIBILITY = Path("output/vqa_runtime_feasibility/index.html")
DEFAULT_VQA_RUNTIME_FEASIBILITY_SUMMARY = Path("output/vqa_runtime_feasibility/summary.csv")
DEFAULT_VQA_RUNTIME_FEASIBILITY_REQUIREMENTS = Path("output/vqa_runtime_feasibility/requirements.csv")
DEFAULT_VQA_RUNTIME_REPACK_READINESS = Path("output/vqa_runtime_repack_readiness/index.html")
DEFAULT_VQA_RUNTIME_REPACK_READINESS_SUMMARY = Path("output/vqa_runtime_repack_readiness/summary.csv")
DEFAULT_VQA_RUNTIME_REPACK_READINESS_REQUIREMENTS = Path("output/vqa_runtime_repack_readiness/requirements.csv")
DEFAULT_VQA_RUNTIME_REPACK_READINESS_ARCHIVES = Path("output/vqa_runtime_repack_readiness/archives.csv")
DEFAULT_VQA_RUNTIME_REPACK_READINESS_ENTRIES = Path("output/vqa_runtime_repack_readiness/entries.csv")
DEFAULT_VQA_RUNTIME_PACK_BUILD = Path("output/vqa_runtime_pack_build/index.html")
DEFAULT_VQA_RUNTIME_PACK_BUILD_SUMMARY = Path("output/vqa_runtime_pack_build/summary.csv")
DEFAULT_VQA_RUNTIME_PACK_BUILD_REQUIREMENTS = Path("output/vqa_runtime_pack_build/requirements.csv")
DEFAULT_VQA_RUNTIME_PACK_BUILD_ARCHIVES = Path("output/vqa_runtime_pack_build/archives.csv")
DEFAULT_VQA_RUNTIME_PACK_BUILD_ENTRIES = Path("output/vqa_runtime_pack_build/entries.csv")
DEFAULT_VQA_RUNTIME_PACK_BUILD_LCW_COMPACT_SAMPLE = Path(
    "output/vqa_runtime_pack_build_lcw_compact_sample/index.html"
)
DEFAULT_VQA_RUNTIME_PACK_BUILD_LCW_COMPACT_SAMPLE_SUMMARY = Path(
    "output/vqa_runtime_pack_build_lcw_compact_sample/summary.csv"
)
DEFAULT_VQA_RUNTIME_PACK_BUILD_LCW_COMPACT_SAMPLE_ARCHIVES = Path(
    "output/vqa_runtime_pack_build_lcw_compact_sample/archives.csv"
)
DEFAULT_VQA_RUNTIME_PACK_BUILD_LCW_COMPACT_SAMPLE_ENTRIES = Path(
    "output/vqa_runtime_pack_build_lcw_compact_sample/entries.csv"
)
DEFAULT_VQA_RUNTIME_PACK_BUILD_L4_HJI_LCW_COMPACT_SAMPLE = Path(
    "output/vqa_runtime_pack_build_l4_hji_lcw_compact_sample/index.html"
)
DEFAULT_VQA_RUNTIME_PACK_BUILD_L4_HJI_LCW_COMPACT_SAMPLE_SUMMARY = Path(
    "output/vqa_runtime_pack_build_l4_hji_lcw_compact_sample/summary.csv"
)
DEFAULT_VQA_RUNTIME_PACK_BUILD_L4_HJI_LCW_COMPACT_SAMPLE_ARCHIVES = Path(
    "output/vqa_runtime_pack_build_l4_hji_lcw_compact_sample/archives.csv"
)
DEFAULT_VQA_RUNTIME_PACK_BUILD_L4_HJI_LCW_COMPACT_SAMPLE_ENTRIES = Path(
    "output/vqa_runtime_pack_build_l4_hji_lcw_compact_sample/entries.csv"
)
DEFAULT_VQA_RUNTIME_PACK_BUILD_LCW_COMPACT_REPORT = Path(
    "output/vqa_runtime_pack_build_lcw_compact_report/index.html"
)
DEFAULT_VQA_RUNTIME_PACK_BUILD_LCW_COMPACT_REPORT_SUMMARY = Path(
    "output/vqa_runtime_pack_build_lcw_compact_report/summary.csv"
)
DEFAULT_VQA_RUNTIME_PACK_BUILD_LCW_COMPACT_REPORT_ARCHIVES = Path(
    "output/vqa_runtime_pack_build_lcw_compact_report/archives.csv"
)
DEFAULT_VQA_RUNTIME_PACK_BUILD_LCW_COMPACT_REPORT_ENTRIES = Path(
    "output/vqa_runtime_pack_build_lcw_compact_report/entries.csv"
)
DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET = Path("output/vqa_runtime_oversize_budget/index.html")
DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_SUMMARY = Path("output/vqa_runtime_oversize_budget/summary.csv")
DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_ARCHIVES = Path("output/vqa_runtime_oversize_budget/archives.csv")
DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_ENTRIES = Path("output/vqa_runtime_oversize_budget/entries.csv")
DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_LCW_COMPACT_SAMPLE = Path(
    "output/vqa_runtime_oversize_budget_lcw_compact_sample/index.html"
)
DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_LCW_COMPACT_SAMPLE_SUMMARY = Path(
    "output/vqa_runtime_oversize_budget_lcw_compact_sample/summary.csv"
)
DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_LCW_COMPACT_SAMPLE_ARCHIVES = Path(
    "output/vqa_runtime_oversize_budget_lcw_compact_sample/archives.csv"
)
DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_LCW_COMPACT_SAMPLE_ENTRIES = Path(
    "output/vqa_runtime_oversize_budget_lcw_compact_sample/entries.csv"
)
DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_L4_HJI_LCW_COMPACT_SAMPLE = Path(
    "output/vqa_runtime_oversize_budget_l4_hji_lcw_compact_sample/index.html"
)
DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_L4_HJI_LCW_COMPACT_SAMPLE_SUMMARY = Path(
    "output/vqa_runtime_oversize_budget_l4_hji_lcw_compact_sample/summary.csv"
)
DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_L4_HJI_LCW_COMPACT_SAMPLE_ARCHIVES = Path(
    "output/vqa_runtime_oversize_budget_l4_hji_lcw_compact_sample/archives.csv"
)
DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_L4_HJI_LCW_COMPACT_SAMPLE_ENTRIES = Path(
    "output/vqa_runtime_oversize_budget_l4_hji_lcw_compact_sample/entries.csv"
)
DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_LCW_COMPACT_REPORT = Path(
    "output/vqa_runtime_oversize_budget_lcw_compact_report/index.html"
)
DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_LCW_COMPACT_REPORT_SUMMARY = Path(
    "output/vqa_runtime_oversize_budget_lcw_compact_report/summary.csv"
)
DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_LCW_COMPACT_REPORT_ARCHIVES = Path(
    "output/vqa_runtime_oversize_budget_lcw_compact_report/archives.csv"
)
DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_LCW_COMPACT_REPORT_ENTRIES = Path(
    "output/vqa_runtime_oversize_budget_lcw_compact_report/entries.csv"
)
DEFAULT_VQA_RUNTIME_SIDECAR_PACK = Path("output/vqa_runtime_sidecar_pack/index.html")
DEFAULT_VQA_RUNTIME_SIDECAR_PACK_SUMMARY = Path("output/vqa_runtime_sidecar_pack/summary.csv")
DEFAULT_VQA_RUNTIME_SIDECAR_PACK_REQUIREMENTS = Path("output/vqa_runtime_sidecar_pack/requirements.csv")
DEFAULT_VQA_RUNTIME_SIDECAR_PACK_ARCHIVES = Path("output/vqa_runtime_sidecar_pack/archives.csv")
DEFAULT_VQA_RUNTIME_SIDECAR_PACK_ENTRIES = Path("output/vqa_runtime_sidecar_pack/entries.csv")
DEFAULT_VQA_RUNTIME_SIDECAR_LOAD_PLAN = Path("output/vqa_runtime_sidecar_load_plan/index.html")
DEFAULT_VQA_RUNTIME_SIDECAR_LOAD_PLAN_SUMMARY = Path("output/vqa_runtime_sidecar_load_plan/summary.csv")
DEFAULT_VQA_RUNTIME_SIDECAR_LOAD_PLAN_REQUIREMENTS = Path("output/vqa_runtime_sidecar_load_plan/requirements.csv")
DEFAULT_VQA_RUNTIME_SIDECAR_LOAD_PLAN_ARCHIVES = Path("output/vqa_runtime_sidecar_load_plan/archives.csv")
DEFAULT_VQA_RUNTIME_SIDECAR_LOAD_PLAN_ENTRIES = Path("output/vqa_runtime_sidecar_load_plan/entries.csv")
DEFAULT_VQA_RUNTIME_SIDECAR_LOAD_PLAN_SOURCES = Path("output/vqa_runtime_sidecar_load_plan/sources.csv")
DEFAULT_VQA_RUNTIME_LOADER_PROBE = Path("output/vqa_runtime_loader_probe/index.html")
DEFAULT_VQA_RUNTIME_LOADER_PROBE_SUMMARY = Path("output/vqa_runtime_loader_probe/summary.csv")
DEFAULT_VQA_RUNTIME_LOADER_PROBE_REQUIREMENTS = Path("output/vqa_runtime_loader_probe/requirements.csv")
DEFAULT_VQA_RUNTIME_LOADER_PROBE_INPUTS = Path("output/vqa_runtime_loader_probe/inputs.csv")
DEFAULT_VQA_RUNTIME_LOADER_PROBE_ANCHORS = Path("output/vqa_runtime_loader_probe/anchors.csv")
DEFAULT_VQA_RUNTIME_LOADER_PROBE_XREFS = Path("output/vqa_runtime_loader_probe/xrefs.csv")
DEFAULT_VQA_RUNTIME_LOADER_PROBE_IMPORTS = Path("output/vqa_runtime_loader_probe/imports.csv")
DEFAULT_VQA_RUNTIME_LOADER_PROBE_CANDIDATES = Path("output/vqa_runtime_loader_probe/candidates.csv")
DEFAULT_VQA_RUNTIME_LOADER_TRACE_CONTRACT = Path("output/vqa_runtime_loader_trace_contract/index.html")
DEFAULT_VQA_RUNTIME_LOADER_TRACE_CONTRACT_SUMMARY = Path(
    "output/vqa_runtime_loader_trace_contract/summary.csv"
)
DEFAULT_VQA_RUNTIME_LOADER_TRACE_CONTRACT_REQUIREMENTS = Path(
    "output/vqa_runtime_loader_trace_contract/requirements.csv"
)
DEFAULT_VQA_RUNTIME_LOADER_TRACE_CONTRACT_TRACEPOINTS = Path(
    "output/vqa_runtime_loader_trace_contract/tracepoints.tsv"
)
DEFAULT_VQA_RUNTIME_LOADER_TRACE_CONTRACT_EXPECTED_IDS = Path(
    "output/vqa_runtime_loader_trace_contract/expected_sidecar_ids.csv"
)
DEFAULT_VQA_RUNTIME_LOADER_TRACE_CONTRACT_COMMANDS = Path(
    "output/vqa_runtime_loader_trace_contract/commands.csv"
)
DEFAULT_VQA_RUNTIME_LOADER_TRACE_CONTRACT_WINEDBG = Path(
    "output/vqa_runtime_loader_trace_contract/winedbg_commands.txt"
)
DEFAULT_VQA_RUNTIME_LOADER_TRACE_CONTRACT_WINDBG = Path(
    "output/vqa_runtime_loader_trace_contract/windbg_breakpoints.cmd"
)
DEFAULT_LOLG95_WINEDBG_LOADER_TRACE_ATTEMPT = Path("output/lolg95_winedbg_loader_trace_attempt/index.html")
DEFAULT_LOLG95_WINEDBG_LOADER_TRACE_ATTEMPT_SUMMARY = Path(
    "output/lolg95_winedbg_loader_trace_attempt/summary.csv"
)
DEFAULT_LOLG95_WINEDBG_LOADER_TRACE_ATTEMPT_TRACE = Path("output/lolg95_winedbg_loader_trace_attempt/trace.tsv")
DEFAULT_LOLG95_WINEDBG_LOADER_TRACE_ATTEMPT_COMMANDS = Path(
    "output/lolg95_winedbg_loader_trace_attempt/winedbg_commands.txt"
)
DEFAULT_LOLG95_WINEDBG_LOADER_TRACE_ATTEMPT_RAW = Path("output/lolg95_winedbg_loader_trace_attempt/raw.log")
DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_ESCAPE_SUMMARY = Path(
    "output/lolg95_winedbg_attach_pilot_escape_attempt/summary.csv"
)
DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_ESCAPE_TRACE = Path(
    "output/lolg95_winedbg_attach_pilot_escape_attempt/trace.tsv"
)
DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_ESCAPE_COMMANDS = Path(
    "output/lolg95_winedbg_attach_pilot_escape_attempt/winedbg_attach_commands.txt"
)
DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_ESCAPE_RAW = Path(
    "output/lolg95_winedbg_attach_pilot_escape_attempt/raw.log"
)
DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_AUTOSAVE_SUMMARY = Path(
    "output/lolg95_winedbg_attach_pilot_autosave_attempt/summary.csv"
)
DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_AUTOSAVE_TRACE = Path(
    "output/lolg95_winedbg_attach_pilot_autosave_attempt/trace.tsv"
)
DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_AUTOSAVE_COMMANDS = Path(
    "output/lolg95_winedbg_attach_pilot_autosave_attempt/winedbg_attach_commands.txt"
)
DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_AUTOSAVE_RAW = Path(
    "output/lolg95_winedbg_attach_pilot_autosave_attempt/raw.log"
)
DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_L20_FORCED_SUMMARY = Path(
    "output/lolg95_winedbg_attach_pilot_l20_forced_attempt/summary.csv"
)
DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_L20_FORCED_TRACE = Path(
    "output/lolg95_winedbg_attach_pilot_l20_forced_attempt/trace.tsv"
)
DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_L20_FORCED_COMMANDS = Path(
    "output/lolg95_winedbg_attach_pilot_l20_forced_attempt/winedbg_attach_commands.txt"
)
DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_L20_FORCED_RAW = Path(
    "output/lolg95_winedbg_attach_pilot_l20_forced_attempt/raw.log"
)
DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_L20_FORCED_FORCE_LOG = Path(
    "output/lolg95_winedbg_attach_pilot_l20_forced_attempt/force_level_write.log"
)
DEFAULT_LOLG95_SIDECAR_SUFFIX_PATCH_PROBE_SUMMARY = Path(
    "output/lolg95_sidecar_suffix_patch_probe/summary.csv"
)
DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_L20_SUFFIX_PATCH_SUMMARY = Path(
    "output/lolg95_winedbg_attach_pilot_l20_suffix_patch_attempt/summary.csv"
)
DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_L20_SUFFIX_PATCH_TRACE = Path(
    "output/lolg95_winedbg_attach_pilot_l20_suffix_patch_attempt/trace.tsv"
)
DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_L20_SUFFIX_PATCH_RAW = Path(
    "output/lolg95_winedbg_attach_pilot_l20_suffix_patch_attempt/raw.log"
)
DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_L20_SUFFIX_PATCH_FORCE_LOG = Path(
    "output/lolg95_winedbg_attach_pilot_l20_suffix_patch_attempt/force_level_write.log"
)
DEFAULT_LOLG95_SIDECAR_ADDITIVE_PATCH_PROBE_SUMMARY = Path(
    "output/lolg95_sidecar_additive_patch_probe/summary.csv"
)
DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_L20_ADDITIVE_PATCH_SUMMARY = Path(
    "output/lolg95_winedbg_attach_pilot_l20_additive_patch_attempt/summary.csv"
)
DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_L20_ADDITIVE_PATCH_TRACE = Path(
    "output/lolg95_winedbg_attach_pilot_l20_additive_patch_attempt/trace.tsv"
)
DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_L20_ADDITIVE_PATCH_RAW = Path(
    "output/lolg95_winedbg_attach_pilot_l20_additive_patch_attempt/raw.log"
)
DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_L20_ADDITIVE_PATCH_FORCE_LOG = Path(
    "output/lolg95_winedbg_attach_pilot_l20_additive_patch_attempt/force_level_write.log"
)
DEFAULT_LOLG95_WINEDBG_MIX_LOOKUP_L20_ADDITIVE_SUMMARY = Path(
    "output/lolg95_winedbg_mix_lookup_l20_additive_attempt/summary.csv"
)
DEFAULT_LOLG95_WINEDBG_MIX_LOOKUP_L20_ADDITIVE_TRACE = Path(
    "output/lolg95_winedbg_mix_lookup_l20_additive_attempt/trace.tsv"
)
DEFAULT_LOLG95_WINEDBG_MIX_LOOKUP_L20_ADDITIVE_RAW = Path(
    "output/lolg95_winedbg_mix_lookup_l20_additive_attempt/raw.log"
)
DEFAULT_LOLG95_WINEDBG_MIX_LOOKUP_L20_ADDITIVE_FORCE_LOG = Path(
    "output/lolg95_winedbg_mix_lookup_l20_additive_attempt/force_level_write.log"
)
DEFAULT_LOLG95_RUNTIME_ARCHIVE_LIST_L20_SIDECAR_SUMMARY = Path(
    "output/lolg95_runtime_archive_list_l20_sidecar_probe/summary.csv"
)
DEFAULT_LOLG95_RUNTIME_ARCHIVE_LIST_L20_SIDECAR_ARCHIVES = Path(
    "output/lolg95_runtime_archive_list_l20_sidecar_probe/archives.tsv"
)
DEFAULT_LOLG95_RUNTIME_ARCHIVE_LIST_L20_SIDECAR_TARGETS = Path(
    "output/lolg95_runtime_archive_list_l20_sidecar_probe/targets.tsv"
)
DEFAULT_LOLG95_RUNTIME_ARCHIVE_LIST_L20_SIDECAR_FORCE_LOG = Path(
    "output/lolg95_runtime_archive_list_l20_sidecar_probe/force_level_write.log"
)
DEFAULT_LOLG95_SIDECAR_RUNTIME_STAGE_SUMMARY = Path("output/lolg95_sidecar_runtime_stage/summary.csv")
DEFAULT_LOLG95_SIDECAR_RUNTIME_STAGE_REQUIREMENTS = Path("output/lolg95_sidecar_runtime_stage/requirements.csv")
DEFAULT_LOLG95_SIDECAR_RUNTIME_STAGE_README = Path("output/lolg95_sidecar_runtime_stage/README.txt")
DEFAULT_LOLG95_SIDECAR_RUNTIME_STAGE_RUN_SCRIPT = Path(
    "output/lolg95_sidecar_runtime_stage/run_lolg95_sidecar_fullhd_wine.sh"
)
DEFAULT_LOLG95_SIDECAR_PLAYED_READ_PLAN = Path("output/lolg95_sidecar_played_read_plan/index.html")
DEFAULT_LOLG95_SIDECAR_PLAYED_READ_PLAN_SUMMARY = Path("output/lolg95_sidecar_played_read_plan/summary.csv")
DEFAULT_LOLG95_SIDECAR_PLAYED_READ_PLAN_REQUIREMENTS = Path(
    "output/lolg95_sidecar_played_read_plan/requirements.csv"
)
DEFAULT_LOLG95_SIDECAR_PLAYED_READ_PLAN_TARGETS = Path("output/lolg95_sidecar_played_read_plan/targets.csv")
DEFAULT_LOLG95_SIDECAR_FILE_IO_TRACE_CONTRACT = Path("output/lolg95_sidecar_file_io_trace_contract/index.html")
DEFAULT_LOLG95_SIDECAR_FILE_IO_TRACE_CONTRACT_SUMMARY = Path(
    "output/lolg95_sidecar_file_io_trace_contract/summary.csv"
)
DEFAULT_LOLG95_SIDECAR_FILE_IO_TRACE_CONTRACT_REQUIREMENTS = Path(
    "output/lolg95_sidecar_file_io_trace_contract/requirements.csv"
)
DEFAULT_LOLG95_SIDECAR_FILE_IO_TRACE_CONTRACT_TARGETS = Path(
    "output/lolg95_sidecar_file_io_trace_contract/targets.csv"
)
DEFAULT_LOLG95_SIDECAR_FILE_IO_TRACE_CONTRACT_TRACEPOINTS = Path(
    "output/lolg95_sidecar_file_io_trace_contract/tracepoints.tsv"
)
DEFAULT_LOLG95_SIDECAR_FILE_IO_TRACE_CONTRACT_COMMANDS = Path(
    "output/lolg95_sidecar_file_io_trace_contract/commands.csv"
)
DEFAULT_LOLG95_SIDECAR_FILE_IO_TRACE_CONTRACT_WINEDBG = Path(
    "output/lolg95_sidecar_file_io_trace_contract/winedbg_commands.txt"
)
DEFAULT_LOLG95_SIDECAR_FILE_IO_TRACE_CONTRACT_WINDBG = Path(
    "output/lolg95_sidecar_file_io_trace_contract/windbg_breakpoints.cmd"
)
DEFAULT_LOLG95_SIDECAR_FILE_IO_TRACE_ATTEMPT = Path("output/lolg95_sidecar_file_io_trace_attempt/index.html")
DEFAULT_LOLG95_SIDECAR_FILE_IO_TRACE_ATTEMPT_SUMMARY = Path(
    "output/lolg95_sidecar_file_io_trace_attempt/summary.csv"
)
DEFAULT_LOLG95_SIDECAR_FILE_IO_TRACE_ATTEMPT_TRACE = Path(
    "output/lolg95_sidecar_file_io_trace_attempt/trace.tsv"
)
DEFAULT_LOLG95_SIDECAR_FILE_IO_TRACE_ATTEMPT_RAW = Path(
    "output/lolg95_sidecar_file_io_trace_attempt/raw.log"
)
DEFAULT_LOLG95_SIDECAR_FILE_IO_TRACE_ATTEMPT_COMMANDS = Path(
    "output/lolg95_sidecar_file_io_trace_attempt/winedbg_file_io_commands.txt"
)
DEFAULT_LOLG95_SIDECAR_FILE_IO_TRACE_ATTEMPT_FORCE_LOG = Path(
    "output/lolg95_sidecar_file_io_trace_attempt/force_level_write.log"
)
DEFAULT_VQA_RUNTIME_ARCHIVE_SEED_WRITER = Path("output/vqa_runtime_archive_seed_writer/index.html")
DEFAULT_VQA_RUNTIME_ARCHIVE_SEED_WRITER_SUMMARY = Path("output/vqa_runtime_archive_seed_writer/summary.csv")
DEFAULT_VQA_RUNTIME_ARCHIVE_SEED_WRITER_REQUIREMENTS = Path(
    "output/vqa_runtime_archive_seed_writer/requirements.csv"
)
DEFAULT_VQA_RUNTIME_ARCHIVE_SEED_WRITER_TARGETS = Path("output/vqa_runtime_archive_seed_writer/targets.csv")
DEFAULT_VQA_LCW_LITERAL_PROBE = Path("output/vqa_lcw_literal_probe/index.html")
DEFAULT_VQA_LCW_LITERAL_PROBE_SUMMARY = Path("output/vqa_lcw_literal_probe/summary.csv")
DEFAULT_VQA_LCW_LITERAL_PROBE_REQUIREMENTS = Path("output/vqa_lcw_literal_probe/requirements.csv")
DEFAULT_VQA_LCW_LITERAL_PROBE_CANDIDATES = Path("output/vqa_lcw_literal_probe/candidates.csv")
DEFAULT_VQA_LCW_COMPRESSION_PROBE = Path("output/vqa_lcw_compression_probe/index.html")
DEFAULT_VQA_LCW_COMPRESSION_PROBE_SUMMARY = Path("output/vqa_lcw_compression_probe/summary.csv")
DEFAULT_VQA_LCW_COMPRESSION_PROBE_ENTRIES = Path("output/vqa_lcw_compression_probe/entries.csv")
DEFAULT_VQA_LCW_COMPRESSION_PROBE_CHUNKS = Path("output/vqa_lcw_compression_probe/chunks.csv")
DEFAULT_VQA_LCW_COMPACT_PAYLOADS = Path("output/vqa_lcw_compact_payloads/index.html")
DEFAULT_VQA_LCW_COMPACT_PAYLOADS_SUMMARY = Path("output/vqa_lcw_compact_payloads/summary.csv")
DEFAULT_VQA_LCW_COMPACT_PAYLOADS_ENTRIES = Path("output/vqa_lcw_compact_payloads/entries.csv")
DEFAULT_VQA_LCW_COMPACT_PAYLOADS_CHUNKS = Path("output/vqa_lcw_compact_payloads/chunks.csv")
DEFAULT_VQA_LCW_COMPACT_PAYLOADS_L4_HJI = Path("output/vqa_lcw_compact_payloads_l4_hji/index.html")
DEFAULT_VQA_LCW_COMPACT_PAYLOADS_L4_HJI_SUMMARY = Path(
    "output/vqa_lcw_compact_payloads_l4_hji/summary.csv"
)
DEFAULT_VQA_LCW_COMPACT_PAYLOADS_L4_HJI_ENTRIES = Path(
    "output/vqa_lcw_compact_payloads_l4_hji/entries.csv"
)
DEFAULT_VQA_LCW_COMPACT_PAYLOADS_L4_HJI_CHUNKS = Path("output/vqa_lcw_compact_payloads_l4_hji/chunks.csv")
DEFAULT_VQA_NATIVE_EXACT_FIXTURE = Path("output/vqa_native_exact_fixture_writer/index.html")
DEFAULT_VQA_NATIVE_EXACT_FIXTURE_SUMMARY = Path("output/vqa_native_exact_fixture_writer/summary.csv")
DEFAULT_VQA_NATIVE_EXACT_FIXTURE_REQUIREMENTS = Path("output/vqa_native_exact_fixture_writer/requirements.csv")
DEFAULT_VQA_NATIVE_EXACT_FIXTURE_FRAMES = Path("output/vqa_native_exact_fixture_writer/frames.csv")
DEFAULT_VQA_FULLHD_REPLACEMENT_WRITER = Path("output/vqa_fullhd_replacement_writer/index.html")
DEFAULT_VQA_FULLHD_REPLACEMENT_WRITER_SUMMARY = Path("output/vqa_fullhd_replacement_writer/summary.csv")
DEFAULT_VQA_FULLHD_REPLACEMENT_WRITER_REQUIREMENTS = Path(
    "output/vqa_fullhd_replacement_writer/requirements.csv"
)
DEFAULT_VQA_FULLHD_REPLACEMENT_WRITER_FRAMES = Path("output/vqa_fullhd_replacement_writer/frames.csv")
DEFAULT_TEX_REAL_CAPTURE_READINESS = Path("output/tex_runtime_real_capture_readiness/index.html")
DEFAULT_TEX_REAL_CAPTURE_READINESS_SUMMARY = Path("output/tex_runtime_real_capture_readiness/summary.csv")
DEFAULT_TEX_REAL_CAPTURE_READINESS_REQUIREMENTS = Path("output/tex_runtime_real_capture_readiness/requirements.csv")
DEFAULT_TEX_REAL_CAPTURE_ATTEMPT = Path("output/tex_runtime_real_capture_attempt/index.html")
DEFAULT_TEX_REAL_CAPTURE_ATTEMPT_SUMMARY = Path("output/tex_runtime_real_capture_attempt/summary.csv")
DEFAULT_TEX_REAL_CAPTURE_ATTEMPT_TARGETS = Path("output/tex_runtime_real_capture_attempt/targets.csv")
DEFAULT_TEX_REAL_CAPTURE_ATTEMPT_NO3D = Path("output/tex_runtime_real_capture_attempt_no3d/index.html")
DEFAULT_TEX_REAL_CAPTURE_ATTEMPT_NO3D_SUMMARY = Path("output/tex_runtime_real_capture_attempt_no3d/summary.csv")
DEFAULT_LOLG95_WINEDBG_PAYLOAD_TRACE = Path("output/lolg95_winedbg_payload_trace_attempt/index.html")
DEFAULT_LOLG95_WINEDBG_PAYLOAD_TRACE_SUMMARY = Path("output/lolg95_winedbg_payload_trace_attempt/summary.csv")
DEFAULT_LOLG95_WINEDBG_PAYLOAD_TRACE_RAW = Path("output/lolg95_winedbg_payload_trace_attempt/raw.log")
DEFAULT_LOLG95_WINEDBG_PAYLOAD_TRACE_TSV = Path("output/lolg95_winedbg_payload_trace_attempt/trace.tsv")
DEFAULT_LOLG95_WINEDBG_PAYLOAD_TRACE_NO3D = Path("output/lolg95_winedbg_payload_trace_attempt_no3d/index.html")
DEFAULT_LOLG95_WINEDBG_PAYLOAD_TRACE_NO3D_SUMMARY = Path(
    "output/lolg95_winedbg_payload_trace_attempt_no3d/summary.csv"
)
DEFAULT_LOLG95_WINEDBG_PAYLOAD_TRACE_NO3D_RAW = Path("output/lolg95_winedbg_payload_trace_attempt_no3d/raw.log")
DEFAULT_LOLG95_WINEDBG_PAYLOAD_TRACE_NO3D_TSV = Path("output/lolg95_winedbg_payload_trace_attempt_no3d/trace.tsv")
DEFAULT_ARCHIVE_COVERAGE = Path("output/fullhd_archive_coverage/index.html")
DEFAULT_CDCACHE_GALLERY = Path("output/cdcache_hd_asset_pack/index.html")
DEFAULT_CDCACHE_PACK_SUMMARY = Path("output/cdcache_hd_asset_pack/summary.csv")
DEFAULT_TEX_COVERAGE = Path("output/tex_hd_coverage/index.html")
DEFAULT_TEX_REFERENCE_COVERAGE = Path("output/tex_reference_coverage/index.html")
DEFAULT_TEX_MISSING_EVIDENCE = Path("output/tex_missing_reference_evidence/index.html")
DEFAULT_RAW_REFERENCE_PROBE = Path("output/cdcache_raw_reference_probe/index.html")
DEFAULT_ALIAS_CANDIDATES = Path("output/cdcache_alias_candidates/index.html")
DEFAULT_TEX_ALIAS_PACK = Path("output/cdcache_tex_alias_pack/index.html")
DEFAULT_TEX_AUGMENTED_COVERAGE = Path("output/tex_augmented_coverage/index.html")
DEFAULT_TEX_UNRESOLVED_PROBE = Path("output/tex_unresolved_material_probe_render/index.html")
DEFAULT_TEX_PROBE_ANALYSIS = Path("output/tex_unresolved_material_probe_render/analysis.html")
DEFAULT_TEX_LARGE_UNRESOLVED_PROBE = Path("output/tex_large_unresolved_probe_render/index.html")
DEFAULT_TEX_LARGE_PROBE_ANALYSIS = Path("output/tex_large_unresolved_probe_render/analysis.html")
DEFAULT_TEX_LARGE_PROBE_REVIEW = Path("output/tex_large_unresolved_probe_review/index.html")
DEFAULT_TEX_LARGE_REJECTED_DECODER_PROFILE = Path("output/tex_large_rejected_decoder_profile/index.html")
DEFAULT_TEX_LARGE_SHIFTED_2A30_STANDARD_PROBE = Path("output/tex_large_shifted_2a30_standard_probe/index.html")
DEFAULT_TEX_LARGE_SHIFTED_2A30_FIELD16_PROBE = Path("output/tex_large_shifted_2a30_field16_probe/index.html")
DEFAULT_TEX_LARGE_SHIFTED_2A30_FIELD16_REPLAY_PROBE = Path(
    "output/tex_large_shifted_2a30_field16_replay_probe/index.html"
)
DEFAULT_TEX_LARGE_SHIFTED_2A30_FIELD16_TRANSFORM_PROBE = Path(
    "output/tex_large_shifted_2a30_field16_transform_probe/index.html"
)
DEFAULT_TEX_LARGE_SHIFTED_2A30_FIELD16_SELECTOR_PROBE = Path(
    "output/tex_large_shifted_2a30_field16_selector_probe/index.html"
)
DEFAULT_TEX_LARGE_SHIFTED_2A30_FIELD16_DELTA_SPLIT_PROBE = Path(
    "output/tex_large_shifted_2a30_field16_delta_split_probe/index.html"
)
DEFAULT_TEX_LARGE_SHIFTED_2A30_FIELD16_SMALL_DELTA_GUARD_PROBE = Path(
    "output/tex_large_shifted_2a30_field16_small_delta_guard_probe/index.html"
)
DEFAULT_TEX_LARGE_SHIFTED_2A30_FIELD16_SMALL_DELTA_GUARD_REVIEW = Path(
    "output/tex_large_shifted_2a30_field16_small_delta_guard_review/index.html"
)
DEFAULT_TEX_LARGE_SHIFTED_2A30_FIELD16_SMALL_DELTA_GUARD_PROMOTED_REPLAY = Path(
    "output/tex_large_shifted_2a30_field16_small_delta_guard_promoted_replay/index.html"
)
DEFAULT_TEX_LARGE_SHIFTED_2A30_FIELD16_DECODER_INTEGRATION = Path(
    "output/tex_large_shifted_2a30_field16_decoder_integration/index.html"
)
DEFAULT_TEX_LARGE_SHIFTED_2A30_FIELD16_DECODER_ROUTE = Path(
    "output/tex_large_shifted_2a30_field16_decoder_route/index.html"
)
DEFAULT_TEX_LARGE_SHIFTED_2A30_FIELD16_DECODER_PREVIEWS = Path(
    "output/tex_large_shifted_2a30_field16_decoder_previews/index.html"
)
DEFAULT_TEX_LARGE_SHIFTED_2A30_FIELD16_DECODER_PREVIEWS_REVIEW = Path(
    "output/tex_large_shifted_2a30_field16_decoder_previews_review/index.html"
)
DEFAULT_TEX_LARGE_SHIFTED_2A30_FIELD16_DECODER_PROMOTED_PACK = Path(
    "output/tex_large_shifted_2a30_field16_decoder_promoted_pack/index.html"
)
DEFAULT_TEX_MATERIAL_DECODE_PACK = Path("output/tex_material_decode_pack/index.html")
DEFAULT_TEX_MATERIAL_DECODER_QUEUE = Path("output/tex_material_decoder_queue/index.html")
DEFAULT_TEX_REMAINING_REFERENCE_PROFILE = Path("output/tex_remaining_reference_profile/index.html")
DEFAULT_TEX_RAW_SAME_ARCHIVE_PROMOTED_PACK = Path("output/tex_raw_same_archive_promoted_pack/index.html")
DEFAULT_TEX_RAW_SAME_ARCHIVE_PENDING_REVIEW = Path("output/tex_raw_same_archive_pending_review/index.html")
DEFAULT_TEX_EXACT_CDCACHE_COMPARE = Path("output/tex_exact_cdcache_compare/index.html")
DEFAULT_TEX_EXACT_CHUNK_EVIDENCE = Path("output/tex_exact_chunk_evidence/index.html")
DEFAULT_TEX_EXACT_MATCH_OVERLAYS = Path("output/tex_exact_match_overlays/index.html")
DEFAULT_TEX_DECODER_SEED_REPORT = Path("output/tex_decoder_seed_report/index.html")
DEFAULT_TEX_EXACT_CHUNK_SCAN = Path("output/tex_exact_chunk_scan/index.html")
DEFAULT_TEX_EXACT_CHUNK_CLUSTERS = Path("output/tex_exact_chunk_clusters/index.html")
DEFAULT_TEX_EXACT_CLUSTER_OVERLAYS = Path("output/tex_exact_cluster_overlays/index.html")
DEFAULT_TEX_DECODER_RUN_CORPUS = Path("output/tex_decoder_run_corpus/index.html")
DEFAULT_TEX_PARTIAL_RAW_DECODER = Path("output/tex_partial_raw_decoder/index.html")
DEFAULT_TEX_PARTIAL_RAW_COVERAGE = Path("output/tex_partial_raw_coverage/index.html")
DEFAULT_TEX_GAP_FRONTIER_REPORT = Path("output/tex_gap_frontier_report/index.html")
DEFAULT_TEX_GAP_OPCODE_PROBE = Path("output/tex_gap_opcode_probe/index.html")
DEFAULT_TEX_GAP_RLE_PROBE = Path("output/tex_gap_rle_probe/index.html")
DEFAULT_TEX_GAP_RULE_QUEUE = Path("output/tex_gap_rule_queue/index.html")
DEFAULT_TEX_GAP_RULE_FIXTURES = Path("output/tex_gap_rule_fixtures/index.html")
DEFAULT_TEX_GAP_RULE_FIXTURES_EXPANDED = Path("output/tex_gap_rule_fixtures_expanded/index.html")
DEFAULT_TEX_OLD_CLEAN_BYTE_SEARCH = Path("output/tex_old_clean_byte_search/index.html")
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_PROMOTED_REPLAY = Path(
    "output/tex_old_clean_byte_union_promoted_replay/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_SOURCE_DEPENDENCY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_old_clean_byte_union_promoted_replay/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_RESIDUAL_CORE = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_old_clean_byte_union_promoted_replay_residual_core/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_EXPANDED_SOURCE_BYTE_GUARD = Path(
    "output/tex_old_clean_byte_union_expanded_source_byte_guard_review/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_EXPANDED_SOURCE_BYTE_GUARD_PROMOTED_REPLAY = Path(
    "output/tex_old_clean_byte_union_expanded_source_byte_guard_promoted_replay/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_EXPANDED_SOURCE_BYTE_GUARD_SOURCE_DEPENDENCY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_old_clean_byte_union_expanded_source_byte_guard_promoted_replay/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_EXPANDED_SOURCE_BYTE_GUARD_RESIDUAL_CORE = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_old_clean_byte_union_expanded_source_byte_guard_promoted_replay_residual_core/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_SECOND_EXPANDED_SOURCE_BYTE_GUARD = Path(
    "output/tex_old_clean_byte_union_second_expanded_source_byte_guard_review/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_SECOND_EXPANDED_SOURCE_BYTE_GUARD_PROMOTED_REPLAY = Path(
    "output/tex_old_clean_byte_union_second_expanded_source_byte_guard_promoted_replay/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_SECOND_EXPANDED_SOURCE_BYTE_GUARD_SOURCE_DEPENDENCY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_old_clean_byte_union_second_expanded_source_byte_guard_promoted_replay/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_SECOND_EXPANDED_SOURCE_BYTE_GUARD_RESIDUAL_CORE = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_old_clean_byte_union_second_expanded_source_byte_guard_promoted_replay_residual_core/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_THIRD_EXPANDED_SOURCE_BYTE_GUARD = Path(
    "output/tex_old_clean_byte_union_third_expanded_source_byte_guard_review/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_THIRD_EXPANDED_SOURCE_BYTE_GUARD_PROMOTED_REPLAY = Path(
    "output/tex_old_clean_byte_union_third_expanded_source_byte_guard_promoted_replay/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_THIRD_EXPANDED_SOURCE_BYTE_GUARD_SOURCE_DEPENDENCY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_old_clean_byte_union_third_expanded_source_byte_guard_promoted_replay/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_THIRD_EXPANDED_SOURCE_BYTE_GUARD_RESIDUAL_CORE = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_old_clean_byte_union_third_expanded_source_byte_guard_promoted_replay_residual_core/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_FOURTH_EXPANDED_SOURCE_BYTE_GUARD = Path(
    "output/tex_old_clean_byte_union_fourth_expanded_source_byte_guard_review/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_TERMINAL_SOURCE_BYTE_GUARD = Path(
    "output/tex_old_clean_byte_union_terminal_source_byte_guard_review/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_TERMINAL_SOURCE_BYTE_GUARD_PROMOTED_REPLAY = Path(
    "output/tex_old_clean_byte_union_terminal_source_byte_guard_promoted_replay/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_SECOND_TERMINAL_SOURCE_BYTE_GUARD = Path(
    "output/tex_old_clean_byte_union_second_terminal_source_byte_guard_review/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_SECOND_TERMINAL_SOURCE_BYTE_GUARD_PROMOTED_REPLAY = Path(
    "output/tex_old_clean_byte_union_second_terminal_source_byte_guard_promoted_replay/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_THIRD_TERMINAL_SOURCE_BYTE_GUARD = Path(
    "output/tex_old_clean_byte_union_third_terminal_source_byte_guard_review/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_THIRD_TERMINAL_SOURCE_BYTE_GUARD_PROMOTED_REPLAY = Path(
    "output/tex_old_clean_byte_union_third_terminal_source_byte_guard_promoted_replay/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_CONTROL_PREFIX_FILL_GUARD = Path(
    "output/tex_old_clean_byte_union_control_prefix_fill_guard_review/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_CONTROL_PREFIX_FILL_GUARD_PROMOTED_REPLAY = Path(
    "output/tex_old_clean_byte_union_control_prefix_fill_guard_promoted_replay/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_CONTROL_PREFIX_FILL_GUARD_SOURCE_DEPENDENCY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_old_clean_byte_union_control_prefix_fill_guard_promoted_replay/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_CONTROL_PREFIX_FILL_GUARD_RESIDUAL_CORE = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_old_clean_byte_union_control_prefix_fill_guard_promoted_replay_residual_core/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_OUTSIDE_SOURCE_DEPENDENCY_REVIEW = Path(
    "output/tex_old_clean_byte_union_outside_source_dependency_review/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_OUTSIDE_SOURCE_DEPENDENCY_PROMOTED_REPLAY = Path(
    "output/tex_old_clean_byte_union_outside_source_dependency_promoted_replay/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_OUTSIDE_SOURCE_DEPENDENCY_SOURCE_DEPENDENCY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_old_clean_byte_union_outside_source_dependency_promoted_replay/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_OUTSIDE_SOURCE_DEPENDENCY_RESIDUAL_CORE = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_old_clean_byte_union_outside_source_dependency_promoted_replay_residual_core/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_OUTSIDE_SOURCE_DEPENDENCY_CASCADE = Path(
    "output/tex_old_clean_byte_union_outside_source_dependency_cascade/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_THIRTEENTH_OUTSIDE_SOURCE_DEPENDENCY_PROMOTED_REPLAY = Path(
    "output/tex_old_clean_byte_union_thirteenth_outside_source_dependency_promoted_replay/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_THIRTEENTH_OUTSIDE_SOURCE_DEPENDENCY_SOURCE_DEPENDENCY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_old_clean_byte_union_thirteenth_outside_source_dependency_promoted_replay/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_THIRTEENTH_OUTSIDE_SOURCE_DEPENDENCY_RESIDUAL_CORE = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_old_clean_byte_union_thirteenth_outside_source_dependency_promoted_replay_residual_core/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_FOURTEENTH_OUTSIDE_SOURCE_DEPENDENCY_REVIEW = Path(
    "output/tex_old_clean_byte_union_fourteenth_outside_source_dependency_review/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_FRONTIER80_TAIL_SOURCE_SUPPORT_REVIEW = Path(
    "output/tex_old_clean_byte_union_frontier80_tail_source_support_review/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_FRONTIER80_TAIL_PRERUN_DELTA_REVIEW = Path(
    "output/tex_old_clean_byte_union_frontier80_tail_prerun_delta_review/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_FRONTIER80_TAIL_COMPACT_TOKEN_REVIEW = Path(
    "output/tex_old_clean_byte_union_frontier80_tail_compact_token_review/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_FRONTIER80_TAIL_COMPACT_TOKEN_GUARD_SPLIT_REVIEW = Path(
    "output/tex_old_clean_byte_union_frontier80_tail_compact_token_guard_split_review/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_FRONTIER80_TAIL_COMPACT_TOKEN_INDEPENDENT_SUPPORT_REVIEW = Path(
    "output/tex_old_clean_byte_union_frontier80_tail_compact_token_independent_support_review/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_FRONTIER80_TAIL_COMPACT_TOKEN_TRANSFER_GUARD_REVIEW = Path(
    "output/tex_old_clean_byte_union_frontier80_tail_compact_token_transfer_guard_review/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_FRONTIER80_TAIL_COMPACT_TOKEN_TRANSFER_GUARD_PROMOTED_REPLAY = Path(
    "output/tex_old_clean_byte_union_frontier80_tail_compact_token_transfer_guard_promoted_replay/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_FRONTIER80_TAIL_COMPACT_TOKEN_TRANSFER_GUARD_SOURCE_DEPENDENCY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_old_clean_byte_union_frontier80_tail_compact_token_transfer_guard_promoted_replay/index.html"
)
DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_FRONTIER80_TAIL_COMPACT_TOKEN_TRANSFER_GUARD_RESIDUAL_CORE = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_old_clean_byte_union_frontier80_tail_compact_token_transfer_guard_promoted_replay_residual_core/index.html"
)
DEFAULT_TEX_GAP_DECODER_CLEAN_GAP_QUEUE_FRONTIER80_TRANSFER_GUARD = Path(
    "output/tex_gap_decoder_clean_gap_queue_frontier80_transfer_guard_promoted_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_UNRESOLVED_RUN_PROBE_FRONTIER80_TRANSFER_GUARD = Path(
    "output/tex_gap_decoder_unresolved_run_probe_frontier80_transfer_guard_promoted_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_CLEAN_GAP_QUEUE_FRONTIER80_CONTEXT_SPLIT_RESIDUAL = Path(
    "output/tex_gap_decoder_clean_gap_queue_frontier80_context_split_residual_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_UNRESOLVED_RUN_PROBE_FRONTIER80_CONTEXT_SPLIT_RESIDUAL = Path(
    "output/tex_gap_decoder_unresolved_run_probe_frontier80_context_split_residual_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_SECOND_FIXTURE_REPLAY = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_second_fixture_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_CLEAN_GAP_QUEUE_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_SECOND = Path(
    "output/tex_gap_decoder_clean_gap_queue_frontier80_context_split_residual_second_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_UNRESOLVED_RUN_PROBE_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_SECOND = Path(
    "output/tex_gap_decoder_unresolved_run_probe_frontier80_context_split_residual_second_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_LOW_PAYLOAD_NEIGHBORHOOD = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_neighborhood_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_LOW_PAYLOAD_CORPUS_SOURCE = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_corpus_source_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_LOW_PAYLOAD_ROLE_PAIR_TRANSFORM = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_role_pair_transform_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_LOW_PAYLOAD_ROLE_PAIR_SELECTOR = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_role_pair_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_LOW_PAYLOAD_OPCODE_CONTEXT = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_opcode_context_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_LOW_PAYLOAD_ROW_STATE = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_LOW_PAYLOAD_ROW_STATE_SOURCE_PREREQ = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_prereq_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_LOW_PAYLOAD_ROW_STATE_SOURCE_TRANSFORM = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_transform_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_LOW_PAYLOAD_ROW_STATE_SOURCE_DELTA_SELECTOR = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_delta_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_LOW_PAYLOAD_ROW_STATE_SOURCE_DELTA_GUARD = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_delta_guard_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_LOW_PAYLOAD_ROW_STATE_SOURCE_DELTA_GUARD_PROMOTED = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_delta_guard_promoted_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_LOW_PAYLOAD_ROW_STATE_SOURCE_DELTA_GUARD_RESIDUAL = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_delta_guard_residual_review/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_LOW_PAYLOAD_ROW_STATE_SOURCE_SINGLE_ROW_DELTA_GUARD = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_single_row_delta_guard_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_LOW_PAYLOAD_ROW_STATE_SOURCE_SINGLE_ROW_DELTA_NON_ORACLE_SELECTOR = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_single_row_delta_non_oracle_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_LOW_PAYLOAD_ROW_STATE_SOURCE_SINGLE_ROW_DELTA_NON_ORACLE_SELECTOR_PROMOTED = Path(
    "output/tex_gap_decoder_frontier80_context_split_residual_low_payload_row_state_source_single_row_delta_non_oracle_selector_promoted_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_CLEAN_GAP_QUEUE_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED = Path(
    "output/tex_gap_decoder_clean_gap_queue_frontier80_single_row_non_oracle_selector_promoted_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_UNRESOLVED_RUN_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED = Path(
    "output/tex_gap_decoder_unresolved_run_probe_frontier80_single_row_non_oracle_selector_promoted_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED_RUN_REVIEW = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_run_review/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED_STRIDE320_PAIR_SELECTOR = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_pair_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED_STRIDE320_LOCAL_DELTA_TRANSFORM = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_local_delta_transform_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED_STRIDE320_SOURCE_DEPENDENCY = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_source_dependency_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED_STRIDE320_TAIL_SOURCE_SELECTOR = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_tail_source_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED_STRIDE320_SOURCE_PREFIX_TAIL_CANDIDATE = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_source_prefix_tail_candidate_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED_STRIDE320_TARGET_PREFIX_DELTA_CANDIDATE = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_target_prefix_delta_candidate_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED_STRIDE320_REMAINING_SOURCE_DEPENDENCY = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_remaining_source_dependency_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED_STRIDE320_REMAINING_SOURCE_FALLBACK = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_remaining_source_fallback_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED_STRIDE320_REMAINING_SOURCE_VALUE_CANDIDATE = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_remaining_source_value_candidate_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED_STRIDE320_REMAINING_TARGET_DELTA_CANDIDATE = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_remaining_target_delta_candidate_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED_STRIDE320_OUTLIER_TARGET_VALUE_DEPENDENCY = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_outlier_target_value_dependency_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED_STRIDE320_OUTLIER_TARGET_CROSS_PCX_GUARD = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_outlier_target_cross_pcx_guard_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_REPLAY = Path(
    "output/tex_gap_decoder_frontier80_single_row_non_oracle_selector_promoted_stride320_outlier_target_value_guarded_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_CLEAN_GAP_QUEUE_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_REPLAY = Path(
    "output/tex_gap_decoder_clean_gap_queue_frontier80_stride320_outlier_target_value_guarded_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_UNRESOLVED_RUN_PROBE_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_REPLAY = Path(
    "output/tex_gap_decoder_unresolved_run_probe_frontier80_stride320_outlier_target_value_guarded_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_LARGEST_RUN_SELECTOR_REVIEW = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_largest_run_selector_review/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_LARGEST_RUN_STRUCTURAL_PROFILE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_largest_run_structural_profile/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_WIDTH32_DELTA_NEIGHBORHOOD = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_width32_delta_neighborhood_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_SUPPORT_REVIEW = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_support_review/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_COMPACT_SELECTOR_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_compact_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_SIGNED_DELTA_SELECTOR_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_signed_delta_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_OUTLIER_FALLBACK_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_outlier_fallback_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_BYTE_LOCAL_START_SELECTOR_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_byte_local_start_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_BYTE_LOCAL_START_NON_ORACLE_GUARD_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_byte_local_start_non_oracle_guard_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_SUPPORT_ONLY_GUARD_PROMOTED_REPLAY = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_support_only_guard_promoted_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_SUPPORT_ONLY_GUARD_INTEGRATED_REPLAY = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_support_only_guard_integrated_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_CORRECTION_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_correction_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_PROMOTED_REPLAY = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_promoted_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_FIXTURE_REPLAY = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_fixture_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_OFFSET_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_offset_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_PROMOTED_REPLAY = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_promoted_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_FIXTURE_REPLAY = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_fixture_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_CLEAN_GAP_QUEUE_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_FIXTURE_REPLAY = Path(
    "output/tex_gap_decoder_clean_gap_queue_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_fixture_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_UNRESOLVED_RUN_PROBE_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_FIXTURE_REPLAY = Path(
    "output/tex_gap_decoder_unresolved_run_probe_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_fixture_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_LARGEST_RUN_SELECTOR_REVIEW = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_largest_run_selector_review/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_LARGEST_RUN_STRUCTURAL_PROFILE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_largest_run_structural_profile/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_PRODUCER_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_producer_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_SOURCE_TERMINAL_SPLIT_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_source_terminal_split_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_EXTERNAL_SOURCE_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_external_source_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_GENERATED_SEQUENCE_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_generated_sequence_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_DELTA_STATE_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_delta_state_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_SPLIT_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_split_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_REPLAY_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_replay_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_VALUE_PRODUCER_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_value_producer_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_FIXTURE_REPLAY = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_fixture_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_CLEAN_GAP_QUEUE_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_FIXTURE_REPLAY = Path(
    "output/tex_gap_decoder_clean_gap_queue_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_fixture_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_UNRESOLVED_RUN_PROBE_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_FIXTURE_REPLAY = Path(
    "output/tex_gap_decoder_unresolved_run_probe_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_fixture_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_LARGEST_RUN_SELECTOR_REVIEW = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_largest_run_selector_review/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_LARGEST_RUN_STRUCTURAL_PROFILE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_largest_run_structural_profile/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_PRODUCER_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_producer_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_RLE_DELTA_PARSER_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_rle_delta_parser_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_CONTROL_BRIDGE_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_control_bridge_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_COMPACT_CONTROL_GRAMMAR_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_grammar_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_COMPACT_CONTROL_GRAMMAR_VALIDATION_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_grammar_validation_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_COMPACT_CONTROL_RESIDUAL_VALUE_FAMILY_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_residual_value_family_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_COMPACT_CONTROL_ZERO_GAP_ANCHOR_BRIDGE_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_zero_gap_anchor_bridge_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_COMPACT_CONTROL_ZERO_GAP_ANCHOR_GUARD_RULE_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_zero_gap_anchor_guard_rule_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_COMPACT_CONTROL_ZERO_GAP_ANCHOR_PROMOTED_GRAMMAR_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_zero_gap_anchor_promoted_grammar_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_COMPACT_CONTROL_EXTENDED_LOCAL_SEED_TRANSFORM_VALIDATION_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_extended_local_seed_transform_validation_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_COMPACT_CONTROL_NEAR_ANCHOR_SOURCE_RULE_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_near_anchor_source_rule_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_COMPACT_CONTROL_NEAR_ANCHOR_PROMOTED_GRAMMAR_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_near_anchor_promoted_grammar_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_COMPACT_CONTROL_INTEGRATED_REPLAY_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_compact_control_integrated_replay_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_NO_BRIDGE_ANCHOR_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_anchor_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_NO_BRIDGE_ANCHOR_PROMOTED_REPLAY_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_anchor_promoted_replay_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_NO_BRIDGE_WEAK_GAP_GRAMMAR_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_weak_gap_grammar_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_NO_BRIDGE_WEAK_GAP_PROMOTED_REPLAY_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_weak_gap_promoted_replay_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_NO_BRIDGE_RESIDUAL_SOURCE_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_residual_source_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_NO_BRIDGE_RUN_LOCAL_RESIDUAL_GRAMMAR_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_run_local_residual_grammar_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_NO_BRIDGE_RUN_LOCAL_RESIDUAL_PROMOTED_REPLAY_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_run_local_residual_promoted_replay_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_NO_BRIDGE_RUN_LOCAL_RESIDUAL_REMAINING_PROFILE_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_run_local_residual_remaining_profile_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_NO_BRIDGE_BRIDGE_RESIDUAL_INTERVAL_MAP_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_bridge_residual_interval_map_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_NO_BRIDGE_BRIDGE_RESIDUAL_SOURCE_GRAMMAR_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_bridge_residual_source_grammar_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_NO_BRIDGE_BRIDGE_RESIDUAL_SOURCE_PROMOTED_REPLAY_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_bridge_residual_source_promoted_replay_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_NO_BRIDGE_BRIDGE_RESIDUAL_FINAL_COVERAGE_VALIDATION_PROBE = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_no_bridge_bridge_residual_final_coverage_validation_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_FINAL_FIXTURE_REPLAY = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_final_fixture_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_CLEAN_GAP_QUEUE_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_FINAL_FIXTURE_REPLAY = Path(
    "output/tex_gap_decoder_clean_gap_queue_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_final_fixture_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_UNRESOLVED_RUN_PROBE_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_FINAL_FIXTURE_REPLAY = Path(
    "output/tex_gap_decoder_unresolved_run_probe_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_final_fixture_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_FINAL_ZERO_GAP_FIXTURE_REPLAY = Path(
    "output/tex_gap_decoder_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_final_zero_gap_fixture_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_CLEAN_GAP_QUEUE_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_FINAL_ZERO_GAP_FIXTURE_REPLAY = Path(
    "output/tex_gap_decoder_clean_gap_queue_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_final_zero_gap_fixture_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_UNRESOLVED_RUN_PROBE_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_FINAL_ZERO_GAP_FIXTURE_REPLAY = Path(
    "output/tex_gap_decoder_unresolved_run_probe_frontier80_stride320_outlier_target_value_guarded_prior_high_row_exact_residual_compact_target_delta_guard_nonzero_palette_walk_low_tail_anchor_guard_structural_nonzero_final_zero_gap_fixture_replay/index.html"
)
DEFAULT_TEX_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_SOURCE_DEPENDENCY_FRONTIER80_STRUCTURAL_NONZERO_FINAL_ZERO_GAP_FIXTURE_REPLAY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_frontier80_structural_nonzero_final_zero_gap_fixture_replay/index.html"
)
DEFAULT_TEX_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_SOURCE_DEPENDENCY_FRONTIER80_STRUCTURAL_NONZERO_FINAL_ZERO_GAP_FIXTURE_REPLAY_RESIDUAL_CORE = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_frontier80_structural_nonzero_final_zero_gap_fixture_replay_residual_core/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_LARGEST_RUN_SELECTOR_REVIEW = Path(
    "output/tex_gap_decoder_frontier80_clean_largest_run_selector_review/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_LARGEST_RUN_STRUCTURAL_PROFILE = Path(
    "output/tex_gap_decoder_frontier80_clean_largest_run_structural_profile/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_WIDTH32_DELTA_NEIGHBORHOOD_PROBE = Path(
    "output/tex_gap_decoder_frontier80_clean_width32_delta_neighborhood_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_SUPPORT_REVIEW = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_support_review/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_COMPACT_SELECTOR_PROBE = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_compact_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_SIGNED_DELTA_SELECTOR_PROBE = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_signed_delta_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_OUTLIER_FALLBACK_PROBE = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_outlier_fallback_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_BYTE_LOCAL_START_SELECTOR_PROBE = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_byte_local_start_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_BYTE_LOCAL_START_NON_ORACLE_GUARD_PROBE = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_byte_local_start_non_oracle_guard_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_BYTE_LOCAL_START_FALSE_POSITIVE_SPLIT_PROBE = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_byte_local_start_false_positive_split_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_BYTE_LOCAL_START_SOURCE_SPLIT_PROBE = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_byte_local_start_source_split_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_SOURCE_BYTE_PREREQ_PROBE = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_source_byte_prereq_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_THRESHOLD_SOURCE_GUARD_PROBE = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_threshold_source_guard_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_THRESHOLD_SOURCE_GUARD_PROMOTED_REPLAY = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_threshold_source_guard_promoted_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_THRESHOLD_SOURCE_GUARD_INTEGRATED_REPLAY = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_threshold_source_guard_integrated_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_EXACT_RESIDUAL_CORRECTION_PROBE = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_exact_residual_correction_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_EXACT_RESIDUAL_CONSENSUS_VALIDATION_PROBE = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_exact_residual_consensus_validation_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_EXACT_RESIDUAL_CONTEXT_SPLIT_PROBE = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_exact_residual_context_split_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_EXACT_RESIDUAL_CONTEXT_SPLIT_PROMOTED_REPLAY = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_exact_residual_context_split_promoted_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_EXACT_RESIDUAL_CONTEXT_SPLIT_FIXTURE_REPLAY = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_exact_residual_context_split_fixture_replay/index.html"
)
DEFAULT_TEX_GAP_ZERO_RUN_PROBE = Path("output/tex_gap_zero_run_probe/index.html")
DEFAULT_TEX_GAP_GEOMETRY_REPLAY = Path("output/tex_gap_geometry_replay/index.html")
DEFAULT_TEX_GAP_NONZERO_STREAM_PROBE = Path("output/tex_gap_nonzero_stream_probe/index.html")
DEFAULT_TEX_GAP_CONTROL_WORD_PROBE = Path("output/tex_gap_control_word_probe/index.html")
DEFAULT_TEX_GAP_HEADER_SCHEMA_PROBE = Path("output/tex_gap_header_schema_probe/index.html")
DEFAULT_TEX_GAP_ROW_STRIDE_PROBE = Path("output/tex_gap_row_stride_probe/index.html")
DEFAULT_TEX_GAP_ROW_STRIDE_MISMATCH_PROBE = Path("output/tex_gap_row_stride_mismatch_probe/index.html")
DEFAULT_TEX_GAP_ROW_DELTA_PROBE = Path("output/tex_gap_row_delta_probe/index.html")
DEFAULT_TEX_GAP_ROW_TRANSFORM_PROBE = Path("output/tex_gap_row_transform_probe/index.html")
DEFAULT_TEX_GAP_ROW_CONTROL_PROBE = Path("output/tex_gap_row_control_probe/index.html")
DEFAULT_TEX_GAP_ROW_SEQUENCE_PROBE = Path("output/tex_gap_row_sequence_probe/index.html")
DEFAULT_TEX_GAP_ROW_LITERAL_SCAN_PROBE = Path("output/tex_gap_row_literal_scan_probe/index.html")
DEFAULT_TEX_GAP_ROW_FILL_RUN_PROBE = Path("output/tex_gap_row_fill_run_probe/index.html")
DEFAULT_TEX_GAP_CONTROL_GRAMMAR_PROBE = Path("output/tex_gap_control_grammar_probe/index.html")
DEFAULT_TEX_GAP_MISMATCH_TRACE_PROBE = Path("output/tex_gap_mismatch_trace_probe/index.html")
DEFAULT_TEX_GAP_ZERO_LITERAL_SWITCH_PROBE = Path("output/tex_gap_zero_literal_switch_probe/index.html")
DEFAULT_TEX_GAP_ZERO_LITERAL_SEGMENTATION_PROBE = Path("output/tex_gap_zero_literal_segmentation_probe/index.html")
DEFAULT_TEX_GAP_SEGMENTATION_CONTROL_CORRELATION_PROBE = Path(
    "output/tex_gap_segmentation_control_correlation_probe/index.html"
)
DEFAULT_TEX_GAP_LITERAL_TOKEN_PROBE = Path("output/tex_gap_literal_token_probe/index.html")
DEFAULT_TEX_GAP_LITERAL_TOKEN_CLASSIFIER_PROBE = Path(
    "output/tex_gap_literal_token_classifier_probe/index.html"
)
DEFAULT_TEX_GAP_LITERAL_FP_REJECTION_PROBE = Path("output/tex_gap_literal_fp_rejection_probe/index.html")
DEFAULT_TEX_GAP_ZERO_RUN_ALIGNMENT_PROBE = Path("output/tex_gap_zero_run_alignment_probe/index.html")
DEFAULT_TEX_GAP_ZERO_CONTROL_RISK_PROBE = Path("output/tex_gap_zero_control_risk_probe/index.html")
DEFAULT_TEX_GAP_DECODER_SKELETON_CANDIDATE_PROBE = Path(
    "output/tex_gap_decoder_skeleton_candidate_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_RISK_ADJUSTED_PROBE = Path(
    "output/tex_gap_decoder_risk_adjusted_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_SEED_REPLAY = Path("output/tex_gap_decoder_seed_replay/index.html")
DEFAULT_TEX_GAP_DECODER_CONTROL_PROMOTION_PROBE = Path(
    "output/tex_gap_decoder_control_promotion_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FALSE_RISK_QUEUE = Path("output/tex_gap_decoder_false_risk_queue/index.html")
DEFAULT_TEX_GAP_DECODER_CLEAN_REPLAY = Path("output/tex_gap_decoder_clean_replay/index.html")
DEFAULT_TEX_GAP_DECODER_CLEAN_GAP_QUEUE = Path("output/tex_gap_decoder_clean_gap_queue/index.html")
DEFAULT_TEX_GAP_DECODER_UNRESOLVED_RUN_PROBE = Path(
    "output/tex_gap_decoder_unresolved_run_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_UNRESOLVED_ZERO_QUEUE = Path(
    "output/tex_gap_decoder_unresolved_zero_queue/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_INTERNAL_PROBE = Path(
    "output/tex_gap_decoder_len64_internal_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_SOURCE_PROBE = Path(
    "output/tex_gap_decoder_len64_source_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_SELECTOR_PROBE = Path(
    "output/tex_gap_decoder_len64_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_REPLAY = Path(
    "output/tex_gap_decoder_len64_promoted_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_GAP_QUEUE = Path(
    "output/tex_gap_decoder_len64_promoted_gap_queue/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_RUN_PROBE = Path(
    "output/tex_gap_decoder_len64_promoted_run_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_ZERO_QUEUE = Path(
    "output/tex_gap_decoder_len64_promoted_zero_queue/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_ZERO_SOURCE_PROBE = Path(
    "output/tex_gap_decoder_len64_promoted_zero_source_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_SELECTOR_PROBE = Path(
    "output/tex_gap_decoder_len64_promoted_large32_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_REPLAY = Path(
    "output/tex_gap_decoder_len64_promoted_large32_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_GAP_QUEUE = Path(
    "output/tex_gap_decoder_len64_promoted_large32_gap_queue/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_RUN_PROBE = Path(
    "output/tex_gap_decoder_len64_promoted_large32_run_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_ZERO_QUEUE = Path(
    "output/tex_gap_decoder_len64_promoted_large32_zero_queue/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_ZERO_SOURCE_PROBE = Path(
    "output/tex_gap_decoder_len64_promoted_large32_zero_source_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_SELECTOR_PROBE = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_REPLAY = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_GAP_QUEUE = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_gap_queue/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_RUN_PROBE = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_run_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_ZERO_QUEUE = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_zero_queue/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_ZERO_SOURCE_PROBE = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_zero_source_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_REMAINING_SELECTOR_PROBE = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_remaining_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_REMAINING_SELECTOR_PROBE = Path(
    "output/tex_gap_decoder_len64_promoted_large32_remaining_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_TRAILING_LARGE32_SELECTOR_PROBE = Path(
    "output/tex_gap_decoder_len64_promoted_trailing_large32_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LEADING_LEN64_SELECTOR_PROBE = Path(
    "output/tex_gap_decoder_len64_promoted_leading_len64_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_INTERNAL_SMALL_SELECTOR_PROBE = Path(
    "output/tex_gap_decoder_len64_promoted_internal_small_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LEADING_LARGE32_SELECTOR_PROBE = Path(
    "output/tex_gap_decoder_len64_promoted_leading_large32_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_TRAILING_MEDIUM8_SELECTOR_PROBE = Path(
    "output/tex_gap_decoder_len64_promoted_trailing_medium8_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_REMAINING_REPLAY = Path(
    "output/tex_gap_decoder_len64_promoted_remaining_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_REMAINING_GAP_QUEUE = Path(
    "output/tex_gap_decoder_len64_promoted_remaining_gap_queue/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_REMAINING_RUN_PROBE = Path(
    "output/tex_gap_decoder_len64_promoted_remaining_run_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_REMAINING_ZERO_QUEUE = Path(
    "output/tex_gap_decoder_len64_promoted_remaining_zero_queue/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_REMAINING_ZERO_SOURCE_PROBE = Path(
    "output/tex_gap_decoder_len64_promoted_remaining_zero_source_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MICRO_INTERNAL_MEDIUM8_SELECTOR_PROBE = Path(
    "output/tex_gap_decoder_len64_promoted_micro_internal_medium8_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MICRO_INTERNAL_LARGE32_SELECTOR_PROBE = Path(
    "output/tex_gap_decoder_len64_promoted_micro_internal_large32_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MICRO_INTERNAL_SMALL_SELECTOR_PROBE = Path(
    "output/tex_gap_decoder_len64_promoted_micro_internal_small_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MICRO_LEADING_LARGE32_SELECTOR_PROBE = Path(
    "output/tex_gap_decoder_len64_promoted_micro_leading_large32_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MICRO_TRAILING_MEDIUM8_SELECTOR_PROBE = Path(
    "output/tex_gap_decoder_len64_promoted_micro_trailing_medium8_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MICRO_TRAILING_LARGE32_SELECTOR_PROBE = Path(
    "output/tex_gap_decoder_len64_promoted_micro_trailing_large32_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MICRO_REPLAY = Path(
    "output/tex_gap_decoder_len64_promoted_micro_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MICRO_GAP_QUEUE = Path(
    "output/tex_gap_decoder_len64_promoted_micro_gap_queue/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MICRO_RUN_PROBE = Path(
    "output/tex_gap_decoder_len64_promoted_micro_run_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MICRO_ZERO_QUEUE = Path(
    "output/tex_gap_decoder_len64_promoted_micro_zero_queue/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MICRO_ZERO_SOURCE_PROBE = Path(
    "output/tex_gap_decoder_len64_promoted_micro_zero_source_probe/index.html"
)
DEFAULT_TEX_GAP_FIXTURE_REPLAY = Path("output/tex_gap_fixture_replay/index.html")
DEFAULT_STILL_MANIFEST = Path("output/fullhd_images/manifest.csv")
DEFAULT_STILL_GALLERY = Path("output/fullhd_images/index.html")
DEFAULT_STILL_GALLERY_MANIFEST = Path("output/fullhd_images/gallery_manifest.csv")
DEFAULT_RUN_HD = Path("RUN_HD.sh")
DEFAULT_DOC = Path("HD_TEXTURES.md")
DEFAULT_PROJECT_STATUS = Path("MISE_AU_POINT_PROJET.md")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def first_row(path: Path) -> dict[str, str]:
    rows = read_csv(path)
    return rows[0] if rows else {}


def comma_count(text: str) -> str:
    return str(len([part for part in text.split(",") if part]))


def relative_href(path_text: str | Path, base_dir: Path) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    try:
        relative = path.relative_to(base_dir)
    except ValueError:
        relative = Path(os.path.relpath(path, base_dir))
    return relative.as_posix()


def choose_existing(paths: list[Path]) -> Path:
    for path in paths:
        if path.exists():
            return path
    return paths[0]


TERMINAL_SOURCE_BYTE_DASHBOARD_STAGES = [
    ("", "Garde terminal-source"),
    ("second_", "Deuxieme garde terminal-source"),
    ("third_", "Troisieme garde terminal-source"),
    ("fourth_", "Quatrieme garde terminal-source"),
    ("fifth_", "Cinquieme garde terminal-source"),
    ("sixth_", "Sixieme garde terminal-source"),
    ("seventh_", "Septieme garde terminal-source"),
    ("eighth_", "Huitieme garde terminal-source"),
    ("ninth_", "Neuvieme garde terminal-source"),
    ("tenth_", "Dixieme garde terminal-source"),
    ("eleventh_", "Onzieme garde terminal-source"),
]


def terminal_source_byte_review_dir(prefix: str) -> Path:
    return Path(
        f"output/tex_gradient_sequence_high_safe_low_exception_{prefix}"
        "terminal_source_byte_guard_after_terminal_root_source_byte_cascade"
    )


def terminal_source_byte_dependency_dir(prefix: str) -> Path:
    return Path(
        "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_"
        f"{prefix}terminal_source_byte_guard_after_terminal_root_source_byte_cascade_promoted"
    )


def terminal_source_byte_dashboard_links() -> list[tuple[str, Path]]:
    links: list[tuple[str, Path]] = []
    for prefix, label in TERMINAL_SOURCE_BYTE_DASHBOARD_STAGES:
        review_dir = terminal_source_byte_review_dir(prefix)
        dependency_dir = terminal_source_byte_dependency_dir(prefix)
        links.extend(
            [
                (f"{label} apres cascade source-byte terminal/root .tex", review_dir / "index.html"),
                (f"Promotion {label.lower()} .tex", Path(f"{review_dir}_promoted/index.html")),
                (f"Dependances source apres promotion {label.lower()} .tex", dependency_dir / "index.html"),
                (f"Noyau residuel apres promotion {label.lower()} .tex", Path(f"{dependency_dir}_residual_core/index.html")),
            ]
        )
    links.append(
        (
            "Douzieme revue garde terminal-source apres cascade source-byte terminal/root .tex",
            terminal_source_byte_review_dir("twelfth_") / "index.html",
        )
    )
    return links


def dashboard_payload(output: Path) -> dict[str, object]:
    base_dir = output.parent
    audit_summary = first_row(DEFAULT_AUDIT_SUMMARY)
    audit_rows = read_csv(DEFAULT_AUDIT) if DEFAULT_AUDIT.exists() else []
    runtime_summary = first_row(DEFAULT_RUNTIME_AUDIT_SUMMARY)
    vqa_runtime_summary = first_row(DEFAULT_VQA_RUNTIME_FEASIBILITY_SUMMARY)
    vqa_repack_summary = first_row(DEFAULT_VQA_RUNTIME_REPACK_READINESS_SUMMARY)
    vqa_pack_build_summary = first_row(DEFAULT_VQA_RUNTIME_PACK_BUILD_SUMMARY)
    vqa_pack_build_lcw_sample_summary = first_row(DEFAULT_VQA_RUNTIME_PACK_BUILD_LCW_COMPACT_SAMPLE_SUMMARY)
    vqa_pack_build_l4_hji_lcw_sample_summary = first_row(
        DEFAULT_VQA_RUNTIME_PACK_BUILD_L4_HJI_LCW_COMPACT_SAMPLE_SUMMARY
    )
    vqa_pack_build_lcw_report_summary = first_row(DEFAULT_VQA_RUNTIME_PACK_BUILD_LCW_COMPACT_REPORT_SUMMARY)
    vqa_oversize_summary = first_row(DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_SUMMARY)
    vqa_oversize_lcw_sample_summary = first_row(DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_LCW_COMPACT_SAMPLE_SUMMARY)
    vqa_oversize_l4_hji_lcw_sample_summary = first_row(
        DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_L4_HJI_LCW_COMPACT_SAMPLE_SUMMARY
    )
    vqa_oversize_lcw_report_summary = first_row(DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_LCW_COMPACT_REPORT_SUMMARY)
    vqa_sidecar_summary = first_row(DEFAULT_VQA_RUNTIME_SIDECAR_PACK_SUMMARY)
    vqa_sidecar_load_summary = first_row(DEFAULT_VQA_RUNTIME_SIDECAR_LOAD_PLAN_SUMMARY)
    vqa_loader_probe_summary = first_row(DEFAULT_VQA_RUNTIME_LOADER_PROBE_SUMMARY)
    vqa_loader_trace_summary = first_row(DEFAULT_VQA_RUNTIME_LOADER_TRACE_CONTRACT_SUMMARY)
    lolg95_loader_trace_attempt_summary = first_row(DEFAULT_LOLG95_WINEDBG_LOADER_TRACE_ATTEMPT_SUMMARY)
    lolg95_attach_l20_summary = first_row(DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_L20_FORCED_SUMMARY)
    lolg95_suffix_patch_summary = first_row(DEFAULT_LOLG95_SIDECAR_SUFFIX_PATCH_PROBE_SUMMARY)
    lolg95_suffix_patch_trace_summary = first_row(DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_L20_SUFFIX_PATCH_SUMMARY)
    lolg95_additive_patch_summary = first_row(DEFAULT_LOLG95_SIDECAR_ADDITIVE_PATCH_PROBE_SUMMARY)
    lolg95_additive_patch_trace_summary = first_row(
        DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_L20_ADDITIVE_PATCH_SUMMARY
    )
    lolg95_mix_lookup_trace_summary = first_row(DEFAULT_LOLG95_WINEDBG_MIX_LOOKUP_L20_ADDITIVE_SUMMARY)
    lolg95_archive_list_probe_summary = first_row(DEFAULT_LOLG95_RUNTIME_ARCHIVE_LIST_L20_SIDECAR_SUMMARY)
    lolg95_sidecar_runtime_stage_summary = first_row(DEFAULT_LOLG95_SIDECAR_RUNTIME_STAGE_SUMMARY)
    lolg95_sidecar_played_read_summary = first_row(DEFAULT_LOLG95_SIDECAR_PLAYED_READ_PLAN_SUMMARY)
    lolg95_sidecar_file_io_summary = first_row(DEFAULT_LOLG95_SIDECAR_FILE_IO_TRACE_CONTRACT_SUMMARY)
    lolg95_sidecar_file_io_attempt_summary = first_row(DEFAULT_LOLG95_SIDECAR_FILE_IO_TRACE_ATTEMPT_SUMMARY)
    vqa_archive_seed_summary = first_row(DEFAULT_VQA_RUNTIME_ARCHIVE_SEED_WRITER_SUMMARY)
    vqa_lcw_summary = first_row(DEFAULT_VQA_LCW_LITERAL_PROBE_SUMMARY)
    vqa_lcw_compression_summary = first_row(DEFAULT_VQA_LCW_COMPRESSION_PROBE_SUMMARY)
    vqa_lcw_compact_summary = first_row(DEFAULT_VQA_LCW_COMPACT_PAYLOADS_SUMMARY)
    vqa_lcw_compact_l4_hji_summary = first_row(DEFAULT_VQA_LCW_COMPACT_PAYLOADS_L4_HJI_SUMMARY)
    vqa_fixture_summary = first_row(DEFAULT_VQA_NATIVE_EXACT_FIXTURE_SUMMARY)
    vqa_fullhd_writer_summary = first_row(DEFAULT_VQA_FULLHD_REPLACEMENT_WRITER_SUMMARY)
    inventory_rows = read_csv(DEFAULT_INVENTORY_SUMMARY) if DEFAULT_INVENTORY_SUMMARY.exists() else []
    vqa_rows = read_csv(DEFAULT_VQA_GALLERY_MANIFEST) if DEFAULT_VQA_GALLERY_MANIFEST.exists() else []
    still_manifest = (
        DEFAULT_STILL_GALLERY_MANIFEST
        if DEFAULT_STILL_GALLERY_MANIFEST.exists()
        else DEFAULT_STILL_MANIFEST
    )
    still_rows = read_csv(still_manifest) if still_manifest.exists() else []
    cdcache_summary = first_row(DEFAULT_CDCACHE_PACK_SUMMARY)

    first_vqa = next((row for row in vqa_rows if row.get("representative_fullhd_path")), {})
    first_still = next((row for row in still_rows if row.get("output_path")), {})
    cdcache_preview = choose_existing(
        [
            Path("output/cdcache_hd_asset_pack/contact_sheet_linked_descriptors.png"),
            Path("output/cdcache_hd_asset_pack/contact_sheet_all_descriptors.png"),
        ]
    )
    vqa_writer_validated = (
        vqa_runtime_summary.get("fullhd_replacement_writer_validated_frames")
        or vqa_fullhd_writer_summary.get("validated_frames", "")
    )
    vqa_writer_frames = (
        vqa_runtime_summary.get("fullhd_replacement_writer_frames")
        or vqa_fullhd_writer_summary.get("frames", "")
    )

    cards = [
        {
            "title": "VQA Full HD",
            "stat": audit_summary.get("vqa_fullhd_frames", ""),
            "label": "frames",
            "description": f"{audit_summary.get('vqa_gallery_entries', '')} entrees rendues",
            "href": relative_href(DEFAULT_VQA_GALLERY, base_dir),
            "image": relative_href(first_vqa.get("representative_fullhd_path", ""), base_dir),
        },
        {
            "title": "VQA Runtime",
            "stat": vqa_runtime_summary.get("status", ""),
            "label": "runtime",
            "description": (
                f"{vqa_runtime_summary.get('encoder_tools', '')} encodeurs, "
                f"{vqa_runtime_summary.get('runtime_pack_entries', '')} entrees pack, "
                f"repack {vqa_repack_summary.get('mapped_entries', '')}/{vqa_repack_summary.get('vqa_entries', '')}, "
                f"build {vqa_pack_build_summary.get('output_archives', '')} MIX, "
                f"oversize {vqa_oversize_summary.get('deferred_replacements', '')} diff/"
                f"{vqa_oversize_summary.get('required_reduction_bytes', '')} bytes, "
                f"seed {vqa_archive_seed_summary.get('encoded_archives', '')}/"
                f"{vqa_archive_seed_summary.get('target_archives', '')}, "
                f"LCW {vqa_lcw_summary.get('roundtrip_cases', '')} tests, "
                f"LCW comp {vqa_lcw_compression_summary.get('sample_saved_ratio', '')}, "
                f"compact {vqa_lcw_compact_summary.get('entries_written', '')}/"
                f"{vqa_lcw_compact_summary.get('saved_ratio', '')}, "
                f"sample overlay {vqa_pack_build_lcw_sample_summary.get('overlay_replacements', '')}/"
                f"{vqa_pack_build_lcw_sample_summary.get('applied_replacements', '')} appl, "
                f"sample diff {vqa_pack_build_lcw_sample_summary.get('deferred_replacements', '')}/"
                f"{vqa_oversize_lcw_sample_summary.get('required_reduction_bytes', '')} bytes, "
                f"L4 compact {vqa_lcw_compact_l4_hji_summary.get('entries_written', '')}/"
                f"{vqa_lcw_compact_l4_hji_summary.get('saved_ratio', '')}, "
                f"L4 overlay {vqa_pack_build_l4_hji_lcw_sample_summary.get('overlay_replacements', '')}/"
                f"{vqa_pack_build_l4_hji_lcw_sample_summary.get('applied_replacements', '')} appl, "
                f"L4 diff {vqa_pack_build_l4_hji_lcw_sample_summary.get('deferred_replacements', '')}/"
                f"{vqa_oversize_l4_hji_lcw_sample_summary.get('required_reduction_bytes', '')} bytes, "
                f"global compact {vqa_pack_build_lcw_report_summary.get('applied_replacements', '')}/"
                f"{vqa_pack_build_lcw_report_summary.get('entries', '')}, "
                f"global diff {vqa_pack_build_lcw_report_summary.get('deferred_replacements', '')}/"
                f"{vqa_oversize_lcw_report_summary.get('required_reduction_bytes', '')} bytes, "
                f"sidecar {vqa_sidecar_summary.get('sidecar_entries', '')}/"
                f"{vqa_sidecar_summary.get('replacement_bytes', '')} bytes, "
                f"load {vqa_sidecar_load_summary.get('base_entries_verified', '')}/"
                f"{vqa_sidecar_load_summary.get('sidecar_entries_verified', '')} verif, "
                f"loader {vqa_loader_probe_summary.get('hook_candidates', '')}/"
                f"{vqa_loader_probe_summary.get('createfile_xrefs', '')} refs, "
                f"trace {vqa_loader_trace_summary.get('tracepoints', '')}/"
                f"{vqa_loader_trace_summary.get('expected_sidecar_ids', '')} ids, "
                f"attempt {lolg95_loader_trace_attempt_summary.get('breakpoint_hits', '')}/"
                f"{lolg95_loader_trace_attempt_summary.get('contract_tracepoints', '')} bp, "
                f"rows {lolg95_loader_trace_attempt_summary.get('extracted_rows', '')}, "
                f"paths {lolg95_loader_trace_attempt_summary.get('path_rows', '')}/"
                f"{lolg95_loader_trace_attempt_summary.get('unique_paths', '')}, "
                f"L20 trace {lolg95_attach_l20_summary.get('breakpoint_hits', '')}/"
                f"{lolg95_attach_l20_summary.get('unique_paths', '')} paths, "
                f"L20_BBI {lolg95_attach_l20_summary.get('l20_bbi_mentions', '')}/"
                f"HD {lolg95_attach_l20_summary.get('l20_bbi_hd_mentions', '')}, "
                f"suffix patch {lolg95_suffix_patch_summary.get('status', '')}, "
                f"HD trace {lolg95_suffix_patch_trace_summary.get('breakpoint_hits', '')}/"
                f"{lolg95_suffix_patch_trace_summary.get('l20_bbi_hd_mentions', '')}, "
                f"add patch {lolg95_additive_patch_summary.get('status', '')}, "
                f"add trace {lolg95_additive_patch_trace_summary.get('breakpoint_hits', '')}/"
                f"{lolg95_additive_patch_trace_summary.get('l20_bbi_hd_mentions', '')}, "
                f"lookup {lolg95_mix_lookup_trace_summary.get('target_sidecar_hits', '')}/"
                f"{lolg95_mix_lookup_trace_summary.get('expected_ids', '')} ids, "
                f"load evidence {vqa_sidecar_load_summary.get('runtime_evidence_source', '')}, "
                f"sidecar-first {vqa_sidecar_load_summary.get('runtime_sidecar_first', '')}/"
                f"{vqa_sidecar_load_summary.get('sidecar_entries', '')}, "
                f"base-first {vqa_sidecar_load_summary.get('runtime_base_first', '')}/"
                f"{vqa_sidecar_load_summary.get('sidecar_entries', '')}, "
                f"stage {lolg95_sidecar_runtime_stage_summary.get('status', '')}/"
                f"{lolg95_sidecar_runtime_stage_summary.get('runtime_sidecar_first', '')}, "
                f"played {lolg95_sidecar_played_read_summary.get('status', '')}/"
                f"{lolg95_sidecar_played_read_summary.get('played_sidecar_hits', '')}/"
                f"{lolg95_sidecar_played_read_summary.get('targets', '')}, "
                f"runtime evidence {lolg95_sidecar_played_read_summary.get('runtime_evidence_source', '')}, "
                f"base-first {lolg95_sidecar_played_read_summary.get('runtime_base_first', '')}, "
                f"payload file-backed {lolg95_sidecar_played_read_summary.get('file_backed_targets', '')}, "
                f"io contract {lolg95_sidecar_file_io_summary.get('contract_status', '')}/"
                f"{lolg95_sidecar_file_io_summary.get('targets', '')} targets, "
                f"io attempt {lolg95_sidecar_file_io_attempt_summary.get('status', '')}/"
                f"scan {lolg95_sidecar_file_io_attempt_summary.get('archive_scan_phase', '')}/"
                f"{lolg95_sidecar_file_io_attempt_summary.get('archive_nodes', '')}, "
                f"{lolg95_sidecar_file_io_attempt_summary.get('target_read_hits', '')} reads/"
                f"{lolg95_sidecar_file_io_attempt_summary.get('target_seek_hits', '')} seeks/"
                f"{lolg95_sidecar_file_io_attempt_summary.get('target_offset_seek_hits', '')} offsets/"
                f"{lolg95_sidecar_file_io_attempt_summary.get('runtime_base_first', '')} base-first, "
                f"fixture {vqa_fixture_summary.get('matched_frames', '')}/{vqa_fixture_summary.get('frames', '')}, "
                f"writer {vqa_writer_validated}/{vqa_writer_frames}"
            ),
            "href": relative_href(DEFAULT_VQA_RUNTIME_FEASIBILITY, base_dir),
            "image": "",
        },
        {
            "title": "Textures CDCACHE",
            "stat": audit_summary.get("cdcache_pack_assets", ""),
            "label": "assets",
            "description": f"{audit_summary.get('cdcache_pack_linked_assets', '')} lies aux .tex",
            "href": relative_href(DEFAULT_CDCACHE_GALLERY, base_dir),
            "image": relative_href(cdcache_preview, base_dir),
        },
        {
            "title": "Images statiques",
            "stat": audit_summary.get("still_fullhd_images", ""),
            "label": "images",
            "description": "PCX, icones et ressources Windows",
            "href": relative_href(DEFAULT_STILL_GALLERY, base_dir),
            "image": relative_href(first_still.get("output_path", ""), base_dir),
        },
        {
            "title": "Audit Full HD",
            "stat": f"{audit_summary.get('passed', '')}/{audit_summary.get('gates', '')}",
            "label": "gates",
            "description": f"{audit_summary.get('total_fullhd_pngs', '')} PNG verifies",
            "href": relative_href(DEFAULT_AUDIT, base_dir),
            "image": "",
        },
        {
            "title": "Audit runtime",
            "stat": runtime_summary.get("status", ""),
            "label": "runtime",
            "description": f"{runtime_summary.get('runtime_gap_components', '')} gaps runtime",
            "href": relative_href(DEFAULT_RUNTIME_AUDIT, base_dir),
            "image": "",
        },
    ]

    links = [
        ("Audit CSV", DEFAULT_AUDIT),
        ("Audit summary", DEFAULT_AUDIT_SUMMARY),
        ("Audit runtime", DEFAULT_RUNTIME_AUDIT),
        ("Audit runtime summary", DEFAULT_RUNTIME_AUDIT_SUMMARY),
        ("Audit runtime details", DEFAULT_RUNTIME_AUDIT_DETAILS),
        ("Preuve PCX runtime sentinelle", DEFAULT_PCX_SENTINEL_PROOF),
        ("Rapport PCX sentinelle", DEFAULT_PCX_SENTINEL_REPORT),
        ("Smoke PCX sentinelle", DEFAULT_PCX_SENTINEL_SMOKE),
        ("Inventaire Full HD", DEFAULT_INVENTORY_SUMMARY),
        ("Inventaire fichiers projet", DEFAULT_PROJECT_LEGACY_INVENTORY),
        ("Manifest fichiers projet", DEFAULT_PROJECT_LEGACY_MANIFEST),
        ("Revue ancien travail media externe", DEFAULT_EXTERNAL_LEGACY_MEDIA_REVIEW),
        ("Galerie images fixes", DEFAULT_STILL_GALLERY),
        ("Manifest images fixes", DEFAULT_STILL_MANIFEST),
        ("Galerie VQA", DEFAULT_VQA_GALLERY),
        ("Rapport VQA", DEFAULT_VQA_STATUS),
        ("Faisabilite runtime VQA", DEFAULT_VQA_RUNTIME_FEASIBILITY),
        ("Synthese faisabilite runtime VQA", DEFAULT_VQA_RUNTIME_FEASIBILITY_SUMMARY),
        ("Requirements runtime VQA", DEFAULT_VQA_RUNTIME_FEASIBILITY_REQUIREMENTS),
        ("Readiness repack runtime VQA", DEFAULT_VQA_RUNTIME_REPACK_READINESS),
        ("Synthese readiness repack VQA", DEFAULT_VQA_RUNTIME_REPACK_READINESS_SUMMARY),
        ("Requirements readiness repack VQA", DEFAULT_VQA_RUNTIME_REPACK_READINESS_REQUIREMENTS),
        ("Archives readiness repack VQA", DEFAULT_VQA_RUNTIME_REPACK_READINESS_ARCHIVES),
        ("Entrees readiness repack VQA", DEFAULT_VQA_RUNTIME_REPACK_READINESS_ENTRIES),
        ("Build pack runtime VQA", DEFAULT_VQA_RUNTIME_PACK_BUILD),
        ("Synthese build pack runtime VQA", DEFAULT_VQA_RUNTIME_PACK_BUILD_SUMMARY),
        ("Requirements build pack runtime VQA", DEFAULT_VQA_RUNTIME_PACK_BUILD_REQUIREMENTS),
        ("Archives build pack runtime VQA", DEFAULT_VQA_RUNTIME_PACK_BUILD_ARCHIVES),
        ("Entrees build pack runtime VQA", DEFAULT_VQA_RUNTIME_PACK_BUILD_ENTRIES),
        ("Sample build pack runtime VQA LCW compact", DEFAULT_VQA_RUNTIME_PACK_BUILD_LCW_COMPACT_SAMPLE),
        (
            "Synthese sample build VQA LCW compact",
            DEFAULT_VQA_RUNTIME_PACK_BUILD_LCW_COMPACT_SAMPLE_SUMMARY,
        ),
        (
            "Archives sample build VQA LCW compact",
            DEFAULT_VQA_RUNTIME_PACK_BUILD_LCW_COMPACT_SAMPLE_ARCHIVES,
        ),
        (
            "Entrees sample build VQA LCW compact",
            DEFAULT_VQA_RUNTIME_PACK_BUILD_LCW_COMPACT_SAMPLE_ENTRIES,
        ),
        (
            "Sample build pack runtime VQA LCW compact L4_HJI",
            DEFAULT_VQA_RUNTIME_PACK_BUILD_L4_HJI_LCW_COMPACT_SAMPLE,
        ),
        (
            "Synthese sample build VQA LCW compact L4_HJI",
            DEFAULT_VQA_RUNTIME_PACK_BUILD_L4_HJI_LCW_COMPACT_SAMPLE_SUMMARY,
        ),
        (
            "Archives sample build VQA LCW compact L4_HJI",
            DEFAULT_VQA_RUNTIME_PACK_BUILD_L4_HJI_LCW_COMPACT_SAMPLE_ARCHIVES,
        ),
        (
            "Entrees sample build VQA LCW compact L4_HJI",
            DEFAULT_VQA_RUNTIME_PACK_BUILD_L4_HJI_LCW_COMPACT_SAMPLE_ENTRIES,
        ),
        ("Rapport global build VQA LCW compact", DEFAULT_VQA_RUNTIME_PACK_BUILD_LCW_COMPACT_REPORT),
        (
            "Synthese rapport global build VQA LCW compact",
            DEFAULT_VQA_RUNTIME_PACK_BUILD_LCW_COMPACT_REPORT_SUMMARY,
        ),
        (
            "Archives rapport global build VQA LCW compact",
            DEFAULT_VQA_RUNTIME_PACK_BUILD_LCW_COMPACT_REPORT_ARCHIVES,
        ),
        (
            "Entrees rapport global build VQA LCW compact",
            DEFAULT_VQA_RUNTIME_PACK_BUILD_LCW_COMPACT_REPORT_ENTRIES,
        ),
        ("Budget oversized runtime VQA", DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET),
        ("Synthese budget oversized VQA", DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_SUMMARY),
        ("Archives budget oversized VQA", DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_ARCHIVES),
        ("Entrees budget oversized VQA", DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_ENTRIES),
        ("Sample budget oversized VQA LCW compact", DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_LCW_COMPACT_SAMPLE),
        (
            "Synthese sample budget VQA LCW compact",
            DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_LCW_COMPACT_SAMPLE_SUMMARY,
        ),
        (
            "Archives sample budget VQA LCW compact",
            DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_LCW_COMPACT_SAMPLE_ARCHIVES,
        ),
        (
            "Entrees sample budget VQA LCW compact",
            DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_LCW_COMPACT_SAMPLE_ENTRIES,
        ),
        (
            "Sample budget oversized VQA LCW compact L4_HJI",
            DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_L4_HJI_LCW_COMPACT_SAMPLE,
        ),
        (
            "Synthese sample budget VQA LCW compact L4_HJI",
            DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_L4_HJI_LCW_COMPACT_SAMPLE_SUMMARY,
        ),
        (
            "Archives sample budget VQA LCW compact L4_HJI",
            DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_L4_HJI_LCW_COMPACT_SAMPLE_ARCHIVES,
        ),
        (
            "Entrees sample budget VQA LCW compact L4_HJI",
            DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_L4_HJI_LCW_COMPACT_SAMPLE_ENTRIES,
        ),
        ("Budget global oversized VQA LCW compact", DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_LCW_COMPACT_REPORT),
        (
            "Synthese budget global VQA LCW compact",
            DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_LCW_COMPACT_REPORT_SUMMARY,
        ),
        (
            "Archives budget global VQA LCW compact",
            DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_LCW_COMPACT_REPORT_ARCHIVES,
        ),
        (
            "Entrees budget global VQA LCW compact",
            DEFAULT_VQA_RUNTIME_OVERSIZE_BUDGET_LCW_COMPACT_REPORT_ENTRIES,
        ),
        ("Plan sidecar runtime VQA", DEFAULT_VQA_RUNTIME_SIDECAR_PACK),
        ("Synthese sidecar runtime VQA", DEFAULT_VQA_RUNTIME_SIDECAR_PACK_SUMMARY),
        ("Requirements sidecar runtime VQA", DEFAULT_VQA_RUNTIME_SIDECAR_PACK_REQUIREMENTS),
        ("Archives sidecar runtime VQA", DEFAULT_VQA_RUNTIME_SIDECAR_PACK_ARCHIVES),
        ("Entrees sidecar runtime VQA", DEFAULT_VQA_RUNTIME_SIDECAR_PACK_ENTRIES),
        ("Plan chargement sidecar runtime VQA", DEFAULT_VQA_RUNTIME_SIDECAR_LOAD_PLAN),
        ("Synthese chargement sidecar runtime VQA", DEFAULT_VQA_RUNTIME_SIDECAR_LOAD_PLAN_SUMMARY),
        ("Requirements chargement sidecar runtime VQA", DEFAULT_VQA_RUNTIME_SIDECAR_LOAD_PLAN_REQUIREMENTS),
        ("Archives chargement sidecar runtime VQA", DEFAULT_VQA_RUNTIME_SIDECAR_LOAD_PLAN_ARCHIVES),
        ("Entrees chargement sidecar runtime VQA", DEFAULT_VQA_RUNTIME_SIDECAR_LOAD_PLAN_ENTRIES),
        ("Sources chargement sidecar runtime VQA", DEFAULT_VQA_RUNTIME_SIDECAR_LOAD_PLAN_SOURCES),
        ("Probe loader sidecar runtime VQA", DEFAULT_VQA_RUNTIME_LOADER_PROBE),
        ("Synthese probe loader sidecar runtime VQA", DEFAULT_VQA_RUNTIME_LOADER_PROBE_SUMMARY),
        ("Requirements probe loader sidecar runtime VQA", DEFAULT_VQA_RUNTIME_LOADER_PROBE_REQUIREMENTS),
        ("Inputs probe loader sidecar runtime VQA", DEFAULT_VQA_RUNTIME_LOADER_PROBE_INPUTS),
        ("Ancres probe loader sidecar runtime VQA", DEFAULT_VQA_RUNTIME_LOADER_PROBE_ANCHORS),
        ("Xrefs probe loader sidecar runtime VQA", DEFAULT_VQA_RUNTIME_LOADER_PROBE_XREFS),
        ("Imports probe loader sidecar runtime VQA", DEFAULT_VQA_RUNTIME_LOADER_PROBE_IMPORTS),
        ("Candidats probe loader sidecar runtime VQA", DEFAULT_VQA_RUNTIME_LOADER_PROBE_CANDIDATES),
        ("Contrat trace loader sidecar runtime VQA", DEFAULT_VQA_RUNTIME_LOADER_TRACE_CONTRACT),
        ("Synthese contrat trace loader sidecar runtime VQA", DEFAULT_VQA_RUNTIME_LOADER_TRACE_CONTRACT_SUMMARY),
        (
            "Requirements contrat trace loader sidecar runtime VQA",
            DEFAULT_VQA_RUNTIME_LOADER_TRACE_CONTRACT_REQUIREMENTS,
        ),
        (
            "Tracepoints contrat trace loader sidecar runtime VQA",
            DEFAULT_VQA_RUNTIME_LOADER_TRACE_CONTRACT_TRACEPOINTS,
        ),
        (
            "IDs attendus contrat trace loader sidecar runtime VQA",
            DEFAULT_VQA_RUNTIME_LOADER_TRACE_CONTRACT_EXPECTED_IDS,
        ),
        ("Commandes contrat trace loader sidecar runtime VQA", DEFAULT_VQA_RUNTIME_LOADER_TRACE_CONTRACT_COMMANDS),
        ("Commandes winedbg trace loader sidecar runtime VQA", DEFAULT_VQA_RUNTIME_LOADER_TRACE_CONTRACT_WINEDBG),
        ("Breakpoints WinDbg trace loader sidecar runtime VQA", DEFAULT_VQA_RUNTIME_LOADER_TRACE_CONTRACT_WINDBG),
        ("Tentative winedbg trace loader LOLG95", DEFAULT_LOLG95_WINEDBG_LOADER_TRACE_ATTEMPT),
        ("Synthese tentative winedbg trace loader LOLG95", DEFAULT_LOLG95_WINEDBG_LOADER_TRACE_ATTEMPT_SUMMARY),
        ("Trace tentative winedbg trace loader LOLG95", DEFAULT_LOLG95_WINEDBG_LOADER_TRACE_ATTEMPT_TRACE),
        ("Commandes tentative winedbg trace loader LOLG95", DEFAULT_LOLG95_WINEDBG_LOADER_TRACE_ATTEMPT_COMMANDS),
        ("Log brut tentative winedbg trace loader LOLG95", DEFAULT_LOLG95_WINEDBG_LOADER_TRACE_ATTEMPT_RAW),
        ("Synthese trace attachee menu nouvelle partie", DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_ESCAPE_SUMMARY),
        ("Trace attachee menu nouvelle partie", DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_ESCAPE_TRACE),
        ("Commandes trace attachee menu nouvelle partie", DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_ESCAPE_COMMANDS),
        ("Log brut trace attachee menu nouvelle partie", DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_ESCAPE_RAW),
        ("Synthese trace attachee sauvegarde auto", DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_AUTOSAVE_SUMMARY),
        ("Trace attachee sauvegarde auto", DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_AUTOSAVE_TRACE),
        ("Commandes trace attachee sauvegarde auto", DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_AUTOSAVE_COMMANDS),
        ("Log brut trace attachee sauvegarde auto", DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_AUTOSAVE_RAW),
        ("Synthese trace attachee L20 force", DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_L20_FORCED_SUMMARY),
        ("Trace attachee L20 force", DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_L20_FORCED_TRACE),
        ("Commandes trace attachee L20 force", DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_L20_FORCED_COMMANDS),
        ("Log brut trace attachee L20 force", DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_L20_FORCED_RAW),
        ("Ecriture memoire trace L20 force", DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_L20_FORCED_FORCE_LOG),
        ("Synthese patch suffixe sidecar LOLG95", DEFAULT_LOLG95_SIDECAR_SUFFIX_PATCH_PROBE_SUMMARY),
        ("Synthese trace suffixe sidecar L20", DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_L20_SUFFIX_PATCH_SUMMARY),
        ("Trace suffixe sidecar L20", DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_L20_SUFFIX_PATCH_TRACE),
        ("Log brut suffixe sidecar L20", DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_L20_SUFFIX_PATCH_RAW),
        ("Ecriture memoire suffixe sidecar L20", DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_L20_SUFFIX_PATCH_FORCE_LOG),
        ("Synthese patch additif sidecar LOLG95", DEFAULT_LOLG95_SIDECAR_ADDITIVE_PATCH_PROBE_SUMMARY),
        ("Synthese trace additive sidecar L20", DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_L20_ADDITIVE_PATCH_SUMMARY),
        ("Trace additive sidecar L20", DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_L20_ADDITIVE_PATCH_TRACE),
        ("Log brut additive sidecar L20", DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_L20_ADDITIVE_PATCH_RAW),
        ("Ecriture memoire additive sidecar L20", DEFAULT_LOLG95_WINEDBG_ATTACH_PILOT_L20_ADDITIVE_PATCH_FORCE_LOG),
        ("Synthese lookup MIX sidecar L20", DEFAULT_LOLG95_WINEDBG_MIX_LOOKUP_L20_ADDITIVE_SUMMARY),
        ("Trace lookup MIX sidecar L20", DEFAULT_LOLG95_WINEDBG_MIX_LOOKUP_L20_ADDITIVE_TRACE),
        ("Log brut lookup MIX sidecar L20", DEFAULT_LOLG95_WINEDBG_MIX_LOOKUP_L20_ADDITIVE_RAW),
        ("Ecriture memoire lookup MIX sidecar L20", DEFAULT_LOLG95_WINEDBG_MIX_LOOKUP_L20_ADDITIVE_FORCE_LOG),
        ("Synthese liste runtime sidecar L20", DEFAULT_LOLG95_RUNTIME_ARCHIVE_LIST_L20_SIDECAR_SUMMARY),
        ("Archives liste runtime sidecar L20", DEFAULT_LOLG95_RUNTIME_ARCHIVE_LIST_L20_SIDECAR_ARCHIVES),
        ("IDs liste runtime sidecar L20", DEFAULT_LOLG95_RUNTIME_ARCHIVE_LIST_L20_SIDECAR_TARGETS),
        ("Ecriture memoire liste runtime sidecar L20", DEFAULT_LOLG95_RUNTIME_ARCHIVE_LIST_L20_SIDECAR_FORCE_LOG),
        ("Synthese stage runtime sidecar L20", DEFAULT_LOLG95_SIDECAR_RUNTIME_STAGE_SUMMARY),
        ("Requirements stage runtime sidecar L20", DEFAULT_LOLG95_SIDECAR_RUNTIME_STAGE_REQUIREMENTS),
        ("README stage runtime sidecar L20", DEFAULT_LOLG95_SIDECAR_RUNTIME_STAGE_README),
        ("Script Wine stage runtime sidecar L20", DEFAULT_LOLG95_SIDECAR_RUNTIME_STAGE_RUN_SCRIPT),
        ("Plan lecture jouee sidecar L20", DEFAULT_LOLG95_SIDECAR_PLAYED_READ_PLAN),
        ("Synthese lecture jouee sidecar L20", DEFAULT_LOLG95_SIDECAR_PLAYED_READ_PLAN_SUMMARY),
        ("Requirements lecture jouee sidecar L20", DEFAULT_LOLG95_SIDECAR_PLAYED_READ_PLAN_REQUIREMENTS),
        ("Cibles lecture jouee sidecar L20", DEFAULT_LOLG95_SIDECAR_PLAYED_READ_PLAN_TARGETS),
        ("Contrat I/O fichier sidecar L20", DEFAULT_LOLG95_SIDECAR_FILE_IO_TRACE_CONTRACT),
        ("Synthese contrat I/O fichier sidecar L20", DEFAULT_LOLG95_SIDECAR_FILE_IO_TRACE_CONTRACT_SUMMARY),
        ("Requirements contrat I/O fichier sidecar L20", DEFAULT_LOLG95_SIDECAR_FILE_IO_TRACE_CONTRACT_REQUIREMENTS),
        ("Cibles contrat I/O fichier sidecar L20", DEFAULT_LOLG95_SIDECAR_FILE_IO_TRACE_CONTRACT_TARGETS),
        ("Tracepoints contrat I/O fichier sidecar L20", DEFAULT_LOLG95_SIDECAR_FILE_IO_TRACE_CONTRACT_TRACEPOINTS),
        ("Commandes contrat I/O fichier sidecar L20", DEFAULT_LOLG95_SIDECAR_FILE_IO_TRACE_CONTRACT_COMMANDS),
        ("Commandes winedbg I/O fichier sidecar L20", DEFAULT_LOLG95_SIDECAR_FILE_IO_TRACE_CONTRACT_WINEDBG),
        ("Breakpoints WinDbg I/O fichier sidecar L20", DEFAULT_LOLG95_SIDECAR_FILE_IO_TRACE_CONTRACT_WINDBG),
        ("Tentative I/O fichier sidecar L20", DEFAULT_LOLG95_SIDECAR_FILE_IO_TRACE_ATTEMPT),
        ("Synthese tentative I/O fichier sidecar L20", DEFAULT_LOLG95_SIDECAR_FILE_IO_TRACE_ATTEMPT_SUMMARY),
        ("Trace tentative I/O fichier sidecar L20", DEFAULT_LOLG95_SIDECAR_FILE_IO_TRACE_ATTEMPT_TRACE),
        ("Log brut tentative I/O fichier sidecar L20", DEFAULT_LOLG95_SIDECAR_FILE_IO_TRACE_ATTEMPT_RAW),
        ("Commandes winedbg tentative I/O fichier sidecar L20", DEFAULT_LOLG95_SIDECAR_FILE_IO_TRACE_ATTEMPT_COMMANDS),
        ("Ecriture memoire tentative I/O fichier sidecar L20", DEFAULT_LOLG95_SIDECAR_FILE_IO_TRACE_ATTEMPT_FORCE_LOG),
        ("Seed archives runtime VQA", DEFAULT_VQA_RUNTIME_ARCHIVE_SEED_WRITER),
        ("Synthese seed archives runtime VQA", DEFAULT_VQA_RUNTIME_ARCHIVE_SEED_WRITER_SUMMARY),
        ("Requirements seed archives runtime VQA", DEFAULT_VQA_RUNTIME_ARCHIVE_SEED_WRITER_REQUIREMENTS),
        ("Cibles seed archives runtime VQA", DEFAULT_VQA_RUNTIME_ARCHIVE_SEED_WRITER_TARGETS),
        ("Probe LCW literal VQA", DEFAULT_VQA_LCW_LITERAL_PROBE),
        ("Synthese probe LCW literal VQA", DEFAULT_VQA_LCW_LITERAL_PROBE_SUMMARY),
        ("Requirements probe LCW literal VQA", DEFAULT_VQA_LCW_LITERAL_PROBE_REQUIREMENTS),
        ("Candidats probe LCW literal VQA", DEFAULT_VQA_LCW_LITERAL_PROBE_CANDIDATES),
        ("Probe compression LCW VQA", DEFAULT_VQA_LCW_COMPRESSION_PROBE),
        ("Synthese compression LCW VQA", DEFAULT_VQA_LCW_COMPRESSION_PROBE_SUMMARY),
        ("Entrees compression LCW VQA", DEFAULT_VQA_LCW_COMPRESSION_PROBE_ENTRIES),
        ("Chunks compression LCW VQA", DEFAULT_VQA_LCW_COMPRESSION_PROBE_CHUNKS),
        ("Payloads compacts LCW VQA", DEFAULT_VQA_LCW_COMPACT_PAYLOADS),
        ("Synthese payloads compacts LCW VQA", DEFAULT_VQA_LCW_COMPACT_PAYLOADS_SUMMARY),
        ("Entrees payloads compacts LCW VQA", DEFAULT_VQA_LCW_COMPACT_PAYLOADS_ENTRIES),
        ("Chunks payloads compacts LCW VQA", DEFAULT_VQA_LCW_COMPACT_PAYLOADS_CHUNKS),
        ("Payloads compacts LCW VQA L4_HJI", DEFAULT_VQA_LCW_COMPACT_PAYLOADS_L4_HJI),
        (
            "Synthese payloads compacts LCW VQA L4_HJI",
            DEFAULT_VQA_LCW_COMPACT_PAYLOADS_L4_HJI_SUMMARY,
        ),
        ("Entrees payloads compacts LCW VQA L4_HJI", DEFAULT_VQA_LCW_COMPACT_PAYLOADS_L4_HJI_ENTRIES),
        ("Chunks payloads compacts LCW VQA L4_HJI", DEFAULT_VQA_LCW_COMPACT_PAYLOADS_L4_HJI_CHUNKS),
        ("Fixture WVQA native exact-block", DEFAULT_VQA_NATIVE_EXACT_FIXTURE),
        ("Synthese fixture WVQA native", DEFAULT_VQA_NATIVE_EXACT_FIXTURE_SUMMARY),
        ("Requirements fixture WVQA native", DEFAULT_VQA_NATIVE_EXACT_FIXTURE_REQUIREMENTS),
        ("Frames fixture WVQA native", DEFAULT_VQA_NATIVE_EXACT_FIXTURE_FRAMES),
        ("Writer remplacement WVQA Full HD", DEFAULT_VQA_FULLHD_REPLACEMENT_WRITER),
        ("Synthese writer WVQA Full HD", DEFAULT_VQA_FULLHD_REPLACEMENT_WRITER_SUMMARY),
        ("Requirements writer WVQA Full HD", DEFAULT_VQA_FULLHD_REPLACEMENT_WRITER_REQUIREMENTS),
        ("Frames writer WVQA Full HD", DEFAULT_VQA_FULLHD_REPLACEMENT_WRITER_FRAMES),
        ("Readiness capture runtime .tex", DEFAULT_TEX_REAL_CAPTURE_READINESS),
        ("Synthese readiness capture .tex", DEFAULT_TEX_REAL_CAPTURE_READINESS_SUMMARY),
        ("Requirements capture .tex", DEFAULT_TEX_REAL_CAPTURE_READINESS_REQUIREMENTS),
        ("Essai Xvfb capture .tex", DEFAULT_TEX_REAL_CAPTURE_ATTEMPT),
        ("Synthese essai Xvfb capture .tex", DEFAULT_TEX_REAL_CAPTURE_ATTEMPT_SUMMARY),
        ("Cibles essai Xvfb capture .tex", DEFAULT_TEX_REAL_CAPTURE_ATTEMPT_TARGETS),
        ("Essai Xvfb capture .tex no3d", DEFAULT_TEX_REAL_CAPTURE_ATTEMPT_NO3D),
        ("Synthese essai Xvfb capture .tex no3d", DEFAULT_TEX_REAL_CAPTURE_ATTEMPT_NO3D_SUMMARY),
        ("Trace winedbg payload .tex", DEFAULT_LOLG95_WINEDBG_PAYLOAD_TRACE),
        ("Synthese trace winedbg payload .tex", DEFAULT_LOLG95_WINEDBG_PAYLOAD_TRACE_SUMMARY),
        ("Log brut trace winedbg payload .tex", DEFAULT_LOLG95_WINEDBG_PAYLOAD_TRACE_RAW),
        ("TSV trace winedbg payload .tex", DEFAULT_LOLG95_WINEDBG_PAYLOAD_TRACE_TSV),
        ("Trace winedbg payload .tex no3d", DEFAULT_LOLG95_WINEDBG_PAYLOAD_TRACE_NO3D),
        ("Synthese trace winedbg payload .tex no3d", DEFAULT_LOLG95_WINEDBG_PAYLOAD_TRACE_NO3D_SUMMARY),
        ("Log brut trace winedbg payload .tex no3d", DEFAULT_LOLG95_WINEDBG_PAYLOAD_TRACE_NO3D_RAW),
        ("TSV trace winedbg payload .tex no3d", DEFAULT_LOLG95_WINEDBG_PAYLOAD_TRACE_NO3D_TSV),
        ("Couverture archives", DEFAULT_ARCHIVE_COVERAGE),
        ("Galerie CDCACHE", DEFAULT_CDCACHE_GALLERY),
        ("Couverture .tex", DEFAULT_TEX_COVERAGE),
        ("Références .tex", DEFAULT_TEX_REFERENCE_COVERAGE),
        ("Preuves références .tex", DEFAULT_TEX_MISSING_EVIDENCE),
        ("Sonde CDCACHE brute", DEFAULT_RAW_REFERENCE_PROBE),
        ("Alias CDCACHE", DEFAULT_ALIAS_CANDIDATES),
        ("Pack alias .tex", DEFAULT_TEX_ALIAS_PACK),
        ("Couverture augmentée .tex", DEFAULT_TEX_AUGMENTED_COVERAGE),
        ("Sondes matériaux .tex", DEFAULT_TEX_UNRESOLVED_PROBE),
        ("Analyse sondes .tex", DEFAULT_TEX_PROBE_ANALYSIS),
        ("Sondes gros segments .tex", DEFAULT_TEX_LARGE_UNRESOLVED_PROBE),
        ("Analyse gros segments .tex", DEFAULT_TEX_LARGE_PROBE_ANALYSIS),
        ("Revue gros segments .tex", DEFAULT_TEX_LARGE_PROBE_REVIEW),
        ("Profil decodeur gros segments .tex", DEFAULT_TEX_LARGE_REJECTED_DECODER_PROFILE),
        ("Probe 2a30 standard gros segments .tex", DEFAULT_TEX_LARGE_SHIFTED_2A30_STANDARD_PROBE),
        ("Probe field16 2a30 gros segments .tex", DEFAULT_TEX_LARGE_SHIFTED_2A30_FIELD16_PROBE),
        ("Probe replay field16 2a30 gros segments .tex", DEFAULT_TEX_LARGE_SHIFTED_2A30_FIELD16_REPLAY_PROBE),
        (
            "Probe transform field16 2a30 gros segments .tex",
            DEFAULT_TEX_LARGE_SHIFTED_2A30_FIELD16_TRANSFORM_PROBE,
        ),
        (
            "Probe selecteur field16 2a30 gros segments .tex",
            DEFAULT_TEX_LARGE_SHIFTED_2A30_FIELD16_SELECTOR_PROBE,
        ),
        (
            "Probe split delta field16 2a30 gros segments .tex",
            DEFAULT_TEX_LARGE_SHIFTED_2A30_FIELD16_DELTA_SPLIT_PROBE,
        ),
        (
            "Probe garde small-delta field16 2a30 gros segments .tex",
            DEFAULT_TEX_LARGE_SHIFTED_2A30_FIELD16_SMALL_DELTA_GUARD_PROBE,
        ),
        (
            "Revue garde small-delta field16 2a30 gros segments .tex",
            DEFAULT_TEX_LARGE_SHIFTED_2A30_FIELD16_SMALL_DELTA_GUARD_REVIEW,
        ),
        (
            "Replay promu garde small-delta field16 2a30 gros segments .tex",
            DEFAULT_TEX_LARGE_SHIFTED_2A30_FIELD16_SMALL_DELTA_GUARD_PROMOTED_REPLAY,
        ),
        (
            "Integration decodeur field16 2a30 gros segments .tex",
            DEFAULT_TEX_LARGE_SHIFTED_2A30_FIELD16_DECODER_INTEGRATION,
        ),
        (
            "Routage decodeur field16 2a30 gros segments .tex",
            DEFAULT_TEX_LARGE_SHIFTED_2A30_FIELD16_DECODER_ROUTE,
        ),
        (
            "Previews decodeur field16 2a30 gros segments .tex",
            DEFAULT_TEX_LARGE_SHIFTED_2A30_FIELD16_DECODER_PREVIEWS,
        ),
        (
            "Revue previews decodeur field16 2a30 gros segments .tex",
            DEFAULT_TEX_LARGE_SHIFTED_2A30_FIELD16_DECODER_PREVIEWS_REVIEW,
        ),
        (
            "Pack promu decodeur field16 2a30 gros segments .tex",
            DEFAULT_TEX_LARGE_SHIFTED_2A30_FIELD16_DECODER_PROMOTED_PACK,
        ),
        ("Pack decode matériaux .tex", DEFAULT_TEX_MATERIAL_DECODE_PACK),
        ("File décodeur .tex", DEFAULT_TEX_MATERIAL_DECODER_QUEUE),
        ("Profil références restantes .tex", DEFAULT_TEX_REMAINING_REFERENCE_PROFILE),
        ("Pack raw same-archive .tex", DEFAULT_TEX_RAW_SAME_ARCHIVE_PROMOTED_PACK),
        ("Revue raw same-archive .tex", DEFAULT_TEX_RAW_SAME_ARCHIVE_PENDING_REVIEW),
        ("Comparaison exact .tex", DEFAULT_TEX_EXACT_CDCACHE_COMPARE),
        ("Preuves chunks .tex", DEFAULT_TEX_EXACT_CHUNK_EVIDENCE),
        ("Overlays chunks .tex", DEFAULT_TEX_EXACT_MATCH_OVERLAYS),
        ("Seeds décodeur .tex", DEFAULT_TEX_DECODER_SEED_REPORT),
        ("Scan chunks .tex", DEFAULT_TEX_EXACT_CHUNK_SCAN),
        ("Clusters chunks .tex", DEFAULT_TEX_EXACT_CHUNK_CLUSTERS),
        ("Overlays clusters .tex", DEFAULT_TEX_EXACT_CLUSTER_OVERLAYS),
        ("Corpus runs .tex", DEFAULT_TEX_DECODER_RUN_CORPUS),
        ("Décodeur raw .tex", DEFAULT_TEX_PARTIAL_RAW_DECODER),
        ("Coverage raw .tex", DEFAULT_TEX_PARTIAL_RAW_COVERAGE),
        ("Frontières gaps .tex", DEFAULT_TEX_GAP_FRONTIER_REPORT),
        ("Probe opcodes gaps .tex", DEFAULT_TEX_GAP_OPCODE_PROBE),
        ("Probe RLE gaps .tex", DEFAULT_TEX_GAP_RLE_PROBE),
        ("File règles gaps .tex", DEFAULT_TEX_GAP_RULE_QUEUE),
        ("Fixtures règles gaps .tex", DEFAULT_TEX_GAP_RULE_FIXTURES),
        ("Fixtures regles gaps etendues .tex", DEFAULT_TEX_GAP_RULE_FIXTURES_EXPANDED),
        ("Recherche anciens octets propres .tex", DEFAULT_TEX_OLD_CLEAN_BYTE_SEARCH),
        ("Promotion union anciens octets propres .tex", DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_PROMOTED_REPLAY),
        ("Dependances source apres union anciens octets propres .tex", DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_SOURCE_DEPENDENCY),
        ("Noyau residuel apres union anciens octets propres .tex", DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_RESIDUAL_CORE),
        (
            "Revue garde source-byte elargie apres union anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_EXPANDED_SOURCE_BYTE_GUARD,
        ),
        (
            "Promotion garde source-byte elargie apres union anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_EXPANDED_SOURCE_BYTE_GUARD_PROMOTED_REPLAY,
        ),
        (
            "Dependances source apres garde source-byte elargie anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_EXPANDED_SOURCE_BYTE_GUARD_SOURCE_DEPENDENCY,
        ),
        (
            "Noyau residuel apres garde source-byte elargie anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_EXPANDED_SOURCE_BYTE_GUARD_RESIDUAL_CORE,
        ),
        (
            "Deuxieme revue garde source-byte elargie apres union anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_SECOND_EXPANDED_SOURCE_BYTE_GUARD,
        ),
        (
            "Deuxieme promotion garde source-byte elargie apres union anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_SECOND_EXPANDED_SOURCE_BYTE_GUARD_PROMOTED_REPLAY,
        ),
        (
            "Dependances source apres deuxieme garde source-byte elargie anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_SECOND_EXPANDED_SOURCE_BYTE_GUARD_SOURCE_DEPENDENCY,
        ),
        (
            "Noyau residuel apres deuxieme garde source-byte elargie anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_SECOND_EXPANDED_SOURCE_BYTE_GUARD_RESIDUAL_CORE,
        ),
        (
            "Troisieme revue garde source-byte elargie apres union anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_THIRD_EXPANDED_SOURCE_BYTE_GUARD,
        ),
        (
            "Troisieme promotion garde source-byte elargie apres union anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_THIRD_EXPANDED_SOURCE_BYTE_GUARD_PROMOTED_REPLAY,
        ),
        (
            "Dependances source apres troisieme garde source-byte elargie anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_THIRD_EXPANDED_SOURCE_BYTE_GUARD_SOURCE_DEPENDENCY,
        ),
        (
            "Noyau residuel apres troisieme garde source-byte elargie anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_THIRD_EXPANDED_SOURCE_BYTE_GUARD_RESIDUAL_CORE,
        ),
        (
            "Quatrieme revue garde source-byte elargie apres union anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_FOURTH_EXPANDED_SOURCE_BYTE_GUARD,
        ),
        (
            "Revue garde terminal-source apres union anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_TERMINAL_SOURCE_BYTE_GUARD,
        ),
        (
            "Promotion garde terminal-source apres union anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_TERMINAL_SOURCE_BYTE_GUARD_PROMOTED_REPLAY,
        ),
        (
            "Deuxieme revue garde terminal-source apres union anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_SECOND_TERMINAL_SOURCE_BYTE_GUARD,
        ),
        (
            "Deuxieme promotion garde terminal-source apres union anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_SECOND_TERMINAL_SOURCE_BYTE_GUARD_PROMOTED_REPLAY,
        ),
        (
            "Troisieme revue garde terminal-source apres union anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_THIRD_TERMINAL_SOURCE_BYTE_GUARD,
        ),
        (
            "Troisieme promotion garde terminal-source apres union anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_THIRD_TERMINAL_SOURCE_BYTE_GUARD_PROMOTED_REPLAY,
        ),
        (
            "Revue garde fill control-prefix apres union anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_CONTROL_PREFIX_FILL_GUARD,
        ),
        (
            "Promotion garde fill control-prefix apres union anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_CONTROL_PREFIX_FILL_GUARD_PROMOTED_REPLAY,
        ),
        (
            "Dependances source apres fill control-prefix anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_CONTROL_PREFIX_FILL_GUARD_SOURCE_DEPENDENCY,
        ),
        (
            "Noyau residuel apres fill control-prefix anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_CONTROL_PREFIX_FILL_GUARD_RESIDUAL_CORE,
        ),
        (
            "Revue dependances source hors high-safe apres union anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_OUTSIDE_SOURCE_DEPENDENCY_REVIEW,
        ),
        (
            "Promotion dependances source hors high-safe apres union anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_OUTSIDE_SOURCE_DEPENDENCY_PROMOTED_REPLAY,
        ),
        (
            "Dependances source apres promotion hors high-safe anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_OUTSIDE_SOURCE_DEPENDENCY_SOURCE_DEPENDENCY,
        ),
        (
            "Noyau residuel apres promotion hors high-safe anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_OUTSIDE_SOURCE_DEPENDENCY_RESIDUAL_CORE,
        ),
        (
            "Cascade dependances source hors high-safe anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_OUTSIDE_SOURCE_DEPENDENCY_CASCADE,
        ),
        (
            "Treizieme promotion dependances source hors high-safe anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_THIRTEENTH_OUTSIDE_SOURCE_DEPENDENCY_PROMOTED_REPLAY,
        ),
        (
            "Dependances source apres treizieme promotion hors high-safe anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_THIRTEENTH_OUTSIDE_SOURCE_DEPENDENCY_SOURCE_DEPENDENCY,
        ),
        (
            "Noyau residuel apres treizieme promotion hors high-safe anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_THIRTEENTH_OUTSIDE_SOURCE_DEPENDENCY_RESIDUAL_CORE,
        ),
        (
            "Revue blocage frontier80 hors high-safe anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_FOURTEENTH_OUTSIDE_SOURCE_DEPENDENCY_REVIEW,
        ),
        (
            "Support source tail frontier80 hors high-safe anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_FRONTIER80_TAIL_SOURCE_SUPPORT_REVIEW,
        ),
        (
            "Delta pre-run tail frontier80 hors high-safe anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_FRONTIER80_TAIL_PRERUN_DELTA_REVIEW,
        ),
        (
            "Token compact tail frontier80 hors high-safe anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_FRONTIER80_TAIL_COMPACT_TOKEN_REVIEW,
        ),
        (
            "Garde token compact tail frontier80 hors high-safe anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_FRONTIER80_TAIL_COMPACT_TOKEN_GUARD_SPLIT_REVIEW,
        ),
        (
            "Support independant token compact tail frontier80 hors high-safe anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_FRONTIER80_TAIL_COMPACT_TOKEN_INDEPENDENT_SUPPORT_REVIEW,
        ),
        (
            "Garde transfert token compact tail frontier80 hors high-safe anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_FRONTIER80_TAIL_COMPACT_TOKEN_TRANSFER_GUARD_REVIEW,
        ),
        (
            "Replay garde transfert token compact tail frontier80 hors high-safe anciens octets propres .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_FRONTIER80_TAIL_COMPACT_TOKEN_TRANSFER_GUARD_PROMOTED_REPLAY,
        ),
        (
            "Dependances apres replay garde transfert token compact tail frontier80 .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_FRONTIER80_TAIL_COMPACT_TOKEN_TRANSFER_GUARD_SOURCE_DEPENDENCY,
        ),
        (
            "Noyau residuel apres replay garde transfert token compact tail frontier80 .tex",
            DEFAULT_TEX_OLD_CLEAN_BYTE_UNION_FRONTIER80_TAIL_COMPACT_TOKEN_TRANSFER_GUARD_RESIDUAL_CORE,
        ),
        (
            "File gaps clean apres replay garde transfert token compact tail frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_CLEAN_GAP_QUEUE_FRONTIER80_TRANSFER_GUARD,
        ),
        (
            "Runs gaps clean apres replay garde transfert token compact tail frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_UNRESOLVED_RUN_PROBE_FRONTIER80_TRANSFER_GUARD,
        ),
        (
            "File gaps clean apres residuel context-split frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_CLEAN_GAP_QUEUE_FRONTIER80_CONTEXT_SPLIT_RESIDUAL,
        ),
        (
            "Runs gaps clean apres residuel context-split frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_UNRESOLVED_RUN_PROBE_FRONTIER80_CONTEXT_SPLIT_RESIDUAL,
        ),
        (
            "Second replay fixtures residuel context-split frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_SECOND_FIXTURE_REPLAY,
        ),
        (
            "File gaps clean apres second replay residuel context-split frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_CLEAN_GAP_QUEUE_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_SECOND,
        ),
        (
            "Runs gaps clean apres second replay residuel context-split frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_UNRESOLVED_RUN_PROBE_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_SECOND,
        ),
        (
            "Probe low-payload residuel context-split frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_LOW_PAYLOAD_NEIGHBORHOOD,
        ),
        (
            "Probe sources corpus low-payload residuel context-split frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_LOW_PAYLOAD_CORPUS_SOURCE,
        ),
        (
            "Probe transform role-pair low-payload residuel context-split frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_LOW_PAYLOAD_ROLE_PAIR_TRANSFORM,
        ),
        (
            "Probe selector role-pair low-payload residuel context-split frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_LOW_PAYLOAD_ROLE_PAIR_SELECTOR,
        ),
        (
            "Probe contexte opcode low-payload residuel context-split frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_LOW_PAYLOAD_OPCODE_CONTEXT,
        ),
        (
            "Probe row-state low-payload residuel context-split frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_LOW_PAYLOAD_ROW_STATE,
        ),
        (
            "Probe prerequis source row-state low-payload residuel context-split frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_LOW_PAYLOAD_ROW_STATE_SOURCE_PREREQ,
        ),
        (
            "Probe transform source row-state low-payload residuel context-split frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_LOW_PAYLOAD_ROW_STATE_SOURCE_TRANSFORM,
        ),
        (
            "Probe selector delta source row-state low-payload residuel context-split frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_LOW_PAYLOAD_ROW_STATE_SOURCE_DELTA_SELECTOR,
        ),
        (
            "Probe garde delta source row-state low-payload residuel context-split frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_LOW_PAYLOAD_ROW_STATE_SOURCE_DELTA_GUARD,
        ),
        (
            "Replay promu garde delta source row-state low-payload residuel context-split frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_LOW_PAYLOAD_ROW_STATE_SOURCE_DELTA_GUARD_PROMOTED,
        ),
        (
            "Revue residu garde delta source row-state low-payload residuel context-split frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_LOW_PAYLOAD_ROW_STATE_SOURCE_DELTA_GUARD_RESIDUAL,
        ),
        (
            "Probe garde delta single-row source row-state low-payload residuel context-split frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_LOW_PAYLOAD_ROW_STATE_SOURCE_SINGLE_ROW_DELTA_GUARD,
        ),
        (
            "Probe selector non-oracle garde delta single-row source row-state low-payload residuel context-split frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_LOW_PAYLOAD_ROW_STATE_SOURCE_SINGLE_ROW_DELTA_NON_ORACLE_SELECTOR,
        ),
        (
            "Replay promu selector non-oracle garde delta single-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CONTEXT_SPLIT_RESIDUAL_LOW_PAYLOAD_ROW_STATE_SOURCE_SINGLE_ROW_DELTA_NON_ORACLE_SELECTOR_PROMOTED,
        ),
        (
            "File gaps clean apres replay promu selector non-oracle single-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_CLEAN_GAP_QUEUE_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED,
        ),
        (
            "Runs gaps clean apres replay promu selector non-oracle single-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_UNRESOLVED_RUN_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED,
        ),
        (
            "Revue runs apres replay promu selector non-oracle single-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED_RUN_REVIEW,
        ),
        (
            "Probe selector paired-run stride-320 apres promotion single-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED_STRIDE320_PAIR_SELECTOR,
        ),
        (
            "Probe transform local stride-320 apres promotion single-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED_STRIDE320_LOCAL_DELTA_TRANSFORM,
        ),
        (
            "Probe dependance source stride-320 apres promotion single-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED_STRIDE320_SOURCE_DEPENDENCY,
        ),
        (
            "Probe selector tail source stride-320 apres promotion single-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED_STRIDE320_TAIL_SOURCE_SELECTOR,
        ),
        (
            "Replay candidat source-prefix tail stride-320 apres promotion single-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED_STRIDE320_SOURCE_PREFIX_TAIL_CANDIDATE,
        ),
        (
            "Replay candidat target-prefix delta stride-320 apres promotion single-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED_STRIDE320_TARGET_PREFIX_DELTA_CANDIDATE,
        ),
        (
            "Probe dependance source restante stride-320 apres replay target-prefix frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED_STRIDE320_REMAINING_SOURCE_DEPENDENCY,
        ),
        (
            "Probe fallback source restante stride-320 apres replay target-prefix frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED_STRIDE320_REMAINING_SOURCE_FALLBACK,
        ),
        (
            "Replay candidat valeurs source restantes stride-320 frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED_STRIDE320_REMAINING_SOURCE_VALUE_CANDIDATE,
        ),
        (
            "Replay candidat target restante delta stride-320 frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED_STRIDE320_REMAINING_TARGET_DELTA_CANDIDATE,
        ),
        (
            "Probe dependance valeurs target outliers stride-320 frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED_STRIDE320_OUTLIER_TARGET_VALUE_DEPENDENCY,
        ),
        (
            "Probe guard cross-PCX valeurs target outliers stride-320 frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED_STRIDE320_OUTLIER_TARGET_CROSS_PCX_GUARD,
        ),
        (
            "Replay garde valeurs target outliers stride-320 frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_SINGLE_ROW_NON_ORACLE_SELECTOR_PROMOTED_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_REPLAY,
        ),
        (
            "File gaps clean apres replay target outliers stride-320 frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_CLEAN_GAP_QUEUE_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_REPLAY,
        ),
        (
            "Runs gaps clean apres replay target outliers stride-320 frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_UNRESOLVED_RUN_PROBE_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_REPLAY,
        ),
        (
            "Revue selector run residuel 96 apres replay target outliers stride-320 frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_LARGEST_RUN_SELECTOR_REVIEW,
        ),
        (
            "Profil structurel run residuel 96 apres replay target outliers stride-320 frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_LARGEST_RUN_STRUCTURAL_PROFILE,
        ),
        (
            "Probe delta width32 run residuel apres replay target outliers stride-320 frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_WIDTH32_DELTA_NEIGHBORHOOD,
        ),
        (
            "Revue support prior high-row width32 apres replay target outliers stride-320 frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_SUPPORT_REVIEW,
        ),
        (
            "Probe selector compact prior high-row apres replay target outliers stride-320 frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_COMPACT_SELECTOR_PROBE,
        ),
        (
            "Probe selector signed-delta prior high-row apres replay target outliers stride-320 frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_SIGNED_DELTA_SELECTOR_PROBE,
        ),
        (
            "Probe fallback outliers prior high-row apres replay target outliers stride-320 frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_OUTLIER_FALLBACK_PROBE,
        ),
        (
            "Probe selector byte-local start prior high-row apres replay target outliers stride-320 frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_BYTE_LOCAL_START_SELECTOR_PROBE,
        ),
        (
            "Probe guard non-oracle selector byte-local prior high-row apres replay target outliers stride-320 frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_BYTE_LOCAL_START_NON_ORACLE_GUARD_PROBE,
        ),
        (
            "Replay promu guard support-only prior high-row apres replay target outliers stride-320 frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_SUPPORT_ONLY_GUARD_PROMOTED_REPLAY,
        ),
        (
            "Replay integre guard support-only prior high-row apres replay target outliers stride-320 frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_SUPPORT_ONLY_GUARD_INTEGRATED_REPLAY,
        ),
        (
            "Probe correction residuelle exacte support-only prior high-row apres replay target outliers stride-320 frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_CORRECTION_PROBE,
        ),
        (
            "Replay promu correction compacte exacte support-only prior high-row apres replay target outliers stride-320 frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_PROMOTED_REPLAY,
        ),
        (
            "Replay fixture correction compacte exacte support-only prior high-row apres replay target outliers stride-320 frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_FIXTURE_REPLAY,
        ),
        (
            "Probe target-offset correction compacte exacte support-only prior high-row apres replay target outliers stride-320 frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_OFFSET_PROBE,
        ),
        (
            "Replay promu garde target-delta correction compacte exacte support-only prior high-row apres replay target outliers stride-320 frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_PROMOTED_REPLAY,
        ),
        (
            "Replay fixture garde target-delta correction compacte exacte support-only prior high-row apres replay target outliers stride-320 frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_FIXTURE_REPLAY,
        ),
        (
            "File gaps clean apres replay fixture target-delta compact high-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_CLEAN_GAP_QUEUE_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_FIXTURE_REPLAY,
        ),
        (
            "Runs gaps clean apres replay fixture target-delta compact high-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_UNRESOLVED_RUN_PROBE_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_FIXTURE_REPLAY,
        ),
        (
            "Revue selector largest run apres replay fixture target-delta compact high-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_LARGEST_RUN_SELECTOR_REVIEW,
        ),
        (
            "Profil structurel largest run apres replay fixture target-delta compact high-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_LARGEST_RUN_STRUCTURAL_PROFILE,
        ),
        (
            "Probe producteur palette-walk nonzero apres replay fixture target-delta compact high-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_PRODUCER_PROBE,
        ),
        (
            "Probe split source-terminal palette-walk nonzero apres replay fixture target-delta compact high-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_SOURCE_TERMINAL_SPLIT_PROBE,
        ),
        (
            "Probe source externe palette-walk nonzero apres replay fixture target-delta compact high-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_EXTERNAL_SOURCE_PROBE,
        ),
        (
            "Probe sequence generee palette-walk nonzero apres replay fixture target-delta compact high-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_GENERATED_SEQUENCE_PROBE,
        ),
        (
            "Probe delta-state palette-walk nonzero apres replay fixture target-delta compact high-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_DELTA_STATE_PROBE,
        ),
        (
            "Probe split anchors low-tail palette-walk nonzero apres replay fixture target-delta compact high-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_SPLIT_PROBE,
        ),
        (
            "Probe replay guard anchors low-tail palette-walk nonzero apres replay fixture target-delta compact high-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_REPLAY_PROBE,
        ),
        (
            "Probe producteur valeurs guard low-tail palette-walk nonzero apres replay fixture target-delta compact high-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_VALUE_PRODUCER_PROBE,
        ),
        (
            "Replay fixture guard low-tail palette-walk nonzero apres replay fixture target-delta compact high-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_FIXTURE_REPLAY,
        ),
        (
            "File gaps clean apres replay fixture guard low-tail palette-walk frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_CLEAN_GAP_QUEUE_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_FIXTURE_REPLAY,
        ),
        (
            "Runs gaps clean apres replay fixture guard low-tail palette-walk frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_UNRESOLVED_RUN_PROBE_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_FIXTURE_REPLAY,
        ),
        (
            "Revue selector largest run apres replay fixture guard low-tail palette-walk frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_LARGEST_RUN_SELECTOR_REVIEW,
        ),
        (
            "Profil structurel largest run apres replay fixture guard low-tail palette-walk frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_LARGEST_RUN_STRUCTURAL_PROFILE,
        ),
        (
            "Probe producteur structurel nonzero apres replay fixture guard low-tail palette-walk frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_PRODUCER_PROBE,
        ),
        (
            "Probe parser rle-delta structurel nonzero apres replay fixture guard low-tail palette-walk frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_RLE_DELTA_PARSER_PROBE,
        ),
        (
            "Probe pont controle structurel nonzero apres parser rle-delta guard low-tail palette-walk frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_CONTROL_BRIDGE_PROBE,
        ),
        (
            "Probe grammaire compact-control structurelle nonzero apres pont controle frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_COMPACT_CONTROL_GRAMMAR_PROBE,
        ),
        (
            "Validation grammaire compact-control structurelle nonzero frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_COMPACT_CONTROL_GRAMMAR_VALIDATION_PROBE,
        ),
        (
            "Probe familles valeurs residuelles compact-control structurelles nonzero frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_COMPACT_CONTROL_RESIDUAL_VALUE_FAMILY_PROBE,
        ),
        (
            "Probe pont ancre zero-gap compact-control structurel nonzero frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_COMPACT_CONTROL_ZERO_GAP_ANCHOR_BRIDGE_PROBE,
        ),
        (
            "Probe regle guardee ancre zero-gap compact-control structurel nonzero frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_COMPACT_CONTROL_ZERO_GAP_ANCHOR_GUARD_RULE_PROBE,
        ),
        (
            "Probe promotion grammaire ancre zero-gap compact-control structurel nonzero frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_COMPACT_CONTROL_ZERO_GAP_ANCHOR_PROMOTED_GRAMMAR_PROBE,
        ),
        (
            "Validation transforms seed locaux etendus compact-control structurel nonzero frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_COMPACT_CONTROL_EXTENDED_LOCAL_SEED_TRANSFORM_VALIDATION_PROBE,
        ),
        (
            "Probe regle source near-anchor compact-control structurel nonzero frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_COMPACT_CONTROL_NEAR_ANCHOR_SOURCE_RULE_PROBE,
        ),
        (
            "Probe promotion grammaire near-anchor compact-control structurel nonzero frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_COMPACT_CONTROL_NEAR_ANCHOR_PROMOTED_GRAMMAR_PROBE,
        ),
        (
            "Probe integration replay compact-control structurel nonzero frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_COMPACT_CONTROL_INTEGRATED_REPLAY_PROBE,
        ),
        (
            "Probe ancres no-bridge structurel nonzero frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_NO_BRIDGE_ANCHOR_PROBE,
        ),
        (
            "Probe replay promu ancres no-bridge structurel nonzero frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_NO_BRIDGE_ANCHOR_PROMOTED_REPLAY_PROBE,
        ),
        (
            "Probe grammaire weak-gap no-bridge structurel nonzero frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_NO_BRIDGE_WEAK_GAP_GRAMMAR_PROBE,
        ),
        (
            "Probe replay promu weak-gap no-bridge structurel nonzero frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_NO_BRIDGE_WEAK_GAP_PROMOTED_REPLAY_PROBE,
        ),
        (
            "Probe sources residuelles no-bridge structurel nonzero frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_NO_BRIDGE_RESIDUAL_SOURCE_PROBE,
        ),
        (
            "Probe grammaire run-local residuelle no-bridge structurel nonzero frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_NO_BRIDGE_RUN_LOCAL_RESIDUAL_GRAMMAR_PROBE,
        ),
        (
            "Probe replay promu grammaire run-local residuelle no-bridge structurel nonzero frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_NO_BRIDGE_RUN_LOCAL_RESIDUAL_PROMOTED_REPLAY_PROBE,
        ),
        (
            "Probe profil restant apres run-local residuel no-bridge structurel nonzero frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_NO_BRIDGE_RUN_LOCAL_RESIDUAL_REMAINING_PROFILE_PROBE,
        ),
        (
            "Probe carte intervalles residuels bridge apres run-local no-bridge structurel nonzero frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_NO_BRIDGE_BRIDGE_RESIDUAL_INTERVAL_MAP_PROBE,
        ),
        (
            "Probe grammaire source residus bridge apres run-local no-bridge structurel nonzero frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_NO_BRIDGE_BRIDGE_RESIDUAL_SOURCE_GRAMMAR_PROBE,
        ),
        (
            "Probe replay promu grammaire source residus bridge structurel nonzero frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_NO_BRIDGE_BRIDGE_RESIDUAL_SOURCE_PROMOTED_REPLAY_PROBE,
        ),
        (
            "Validation couverture finale apres promotion residus bridge structurel nonzero frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_NO_BRIDGE_BRIDGE_RESIDUAL_FINAL_COVERAGE_VALIDATION_PROBE,
        ),
        (
            "Replay fixture final structurel nonzero frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_FINAL_FIXTURE_REPLAY,
        ),
        (
            "File gaps clean apres replay fixture final structurel nonzero frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_CLEAN_GAP_QUEUE_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_FINAL_FIXTURE_REPLAY,
        ),
        (
            "Runs gaps clean apres replay fixture final structurel nonzero frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_UNRESOLVED_RUN_PROBE_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_FINAL_FIXTURE_REPLAY,
        ),
        (
            "Replay fixture final gaps zero apres structurel nonzero frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_FINAL_ZERO_GAP_FIXTURE_REPLAY,
        ),
        (
            "File gaps clean apres replay fixture final gaps zero frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_CLEAN_GAP_QUEUE_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_FINAL_ZERO_GAP_FIXTURE_REPLAY,
        ),
        (
            "Runs gaps clean apres replay fixture final gaps zero frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_UNRESOLVED_RUN_PROBE_FRONTIER80_STRIDE320_OUTLIER_TARGET_VALUE_GUARDED_PRIOR_HIGH_ROW_EXACT_RESIDUAL_COMPACT_TARGET_DELTA_GUARD_NONZERO_PALETTE_WALK_LOW_TAIL_ANCHOR_GUARD_STRUCTURAL_NONZERO_FINAL_ZERO_GAP_FIXTURE_REPLAY,
        ),
        (
            "Dependances source aval apres base clean finale frontier80 .tex",
            DEFAULT_TEX_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_SOURCE_DEPENDENCY_FRONTIER80_STRUCTURAL_NONZERO_FINAL_ZERO_GAP_FIXTURE_REPLAY,
        ),
        (
            "Noyau residuel aval apres base clean finale frontier80 .tex",
            DEFAULT_TEX_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_SOURCE_DEPENDENCY_FRONTIER80_STRUCTURAL_NONZERO_FINAL_ZERO_GAP_FIXTURE_REPLAY_RESIDUAL_CORE,
        ),
        (
            "Revue selector run 96 apres clean frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_LARGEST_RUN_SELECTOR_REVIEW,
        ),
        (
            "Profil structurel run 96 apres clean frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_LARGEST_RUN_STRUCTURAL_PROFILE,
        ),
        (
            "Probe delta voisinage width32 apres clean frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_WIDTH32_DELTA_NEIGHBORHOOD_PROBE,
        ),
        (
            "Revue support prior high-row width32 apres clean frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_SUPPORT_REVIEW,
        ),
        (
            "Probe selector compact prior high-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_COMPACT_SELECTOR_PROBE,
        ),
        (
            "Probe selector signed-delta prior high-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_SIGNED_DELTA_SELECTOR_PROBE,
        ),
        (
            "Probe fallback outliers prior high-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_OUTLIER_FALLBACK_PROBE,
        ),
        (
            "Probe selector byte-local start prior high-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_BYTE_LOCAL_START_SELECTOR_PROBE,
        ),
        (
            "Probe guard non-oracle selector byte-local prior high-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_BYTE_LOCAL_START_NON_ORACLE_GUARD_PROBE,
        ),
        (
            "Probe split faux positifs selector byte-local prior high-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_BYTE_LOCAL_START_FALSE_POSITIVE_SPLIT_PROBE,
        ),
        (
            "Probe split source selector byte-local prior high-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_BYTE_LOCAL_START_SOURCE_SPLIT_PROBE,
        ),
        (
            "Probe prerequis source-byte prior high-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_SOURCE_BYTE_PREREQ_PROBE,
        ),
        (
            "Probe guard seuil source prior high-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_THRESHOLD_SOURCE_GUARD_PROBE,
        ),
        (
            "Replay promu guard seuil source prior high-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_THRESHOLD_SOURCE_GUARD_PROMOTED_REPLAY,
        ),
        (
            "Replay integre guard seuil source prior high-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_THRESHOLD_SOURCE_GUARD_INTEGRATED_REPLAY,
        ),
        (
            "Probe correction residuelle exacte prior high-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_EXACT_RESIDUAL_CORRECTION_PROBE,
        ),
        (
            "Validation consensus residuel exact prior high-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_EXACT_RESIDUAL_CONSENSUS_VALIDATION_PROBE,
        ),
        (
            "Split contexte residuel exact prior high-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_EXACT_RESIDUAL_CONTEXT_SPLIT_PROBE,
        ),
        (
            "Replay promu contexte residuel exact prior high-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_EXACT_RESIDUAL_CONTEXT_SPLIT_PROMOTED_REPLAY,
        ),
        (
            "Replay fixtures contexte residuel exact prior high-row frontier80 .tex",
            DEFAULT_TEX_GAP_DECODER_FRONTIER80_CLEAN_PRIOR_HIGH_ROW_EXACT_RESIDUAL_CONTEXT_SPLIT_FIXTURE_REPLAY,
        ),
        ("Probe zero-runs gaps .tex", DEFAULT_TEX_GAP_ZERO_RUN_PROBE),
        ("Replay géométrie gaps .tex", DEFAULT_TEX_GAP_GEOMETRY_REPLAY),
        ("Probe flux nonzero gaps .tex", DEFAULT_TEX_GAP_NONZERO_STREAM_PROBE),
        ("Probe mots contrôle gaps .tex", DEFAULT_TEX_GAP_CONTROL_WORD_PROBE),
        ("Probe schéma header gaps .tex", DEFAULT_TEX_GAP_HEADER_SCHEMA_PROBE),
        ("Probe stride lignes gaps .tex", DEFAULT_TEX_GAP_ROW_STRIDE_PROBE),
        ("Mismatch stride lignes gaps .tex", DEFAULT_TEX_GAP_ROW_STRIDE_MISMATCH_PROBE),
        ("Probe delta lignes gaps .tex", DEFAULT_TEX_GAP_ROW_DELTA_PROBE),
        ("Probe transform lignes gaps .tex", DEFAULT_TEX_GAP_ROW_TRANSFORM_PROBE),
        ("Probe controle lignes gaps .tex", DEFAULT_TEX_GAP_ROW_CONTROL_PROBE),
        ("Probe sequence lignes gaps .tex", DEFAULT_TEX_GAP_ROW_SEQUENCE_PROBE),
        ("Scan literal lignes gaps .tex", DEFAULT_TEX_GAP_ROW_LITERAL_SCAN_PROBE),
        ("Probe fill-runs lignes gaps .tex", DEFAULT_TEX_GAP_ROW_FILL_RUN_PROBE),
        ("Probe grammaire controle gaps .tex", DEFAULT_TEX_GAP_CONTROL_GRAMMAR_PROBE),
        ("Trace mismatches gaps .tex", DEFAULT_TEX_GAP_MISMATCH_TRACE_PROBE),
        ("Switch zero-literal gaps .tex", DEFAULT_TEX_GAP_ZERO_LITERAL_SWITCH_PROBE),
        ("Segmentation zero-literal gaps .tex", DEFAULT_TEX_GAP_ZERO_LITERAL_SEGMENTATION_PROBE),
        ("Correlation controle segmentation gaps .tex", DEFAULT_TEX_GAP_SEGMENTATION_CONTROL_CORRELATION_PROBE),
        ("Probe token literal gaps .tex", DEFAULT_TEX_GAP_LITERAL_TOKEN_PROBE),
        ("Classifier token literal gaps .tex", DEFAULT_TEX_GAP_LITERAL_TOKEN_CLASSIFIER_PROBE),
        ("Rejet faux positifs literal gaps .tex", DEFAULT_TEX_GAP_LITERAL_FP_REJECTION_PROBE),
        ("Alignement zero-runs gaps .tex", DEFAULT_TEX_GAP_ZERO_RUN_ALIGNMENT_PROBE),
        ("Risque controle zero gaps .tex", DEFAULT_TEX_GAP_ZERO_CONTROL_RISK_PROBE),
        ("Squelette decodeur gaps .tex", DEFAULT_TEX_GAP_DECODER_SKELETON_CANDIDATE_PROBE),
        ("Squelette risque decodeur gaps .tex", DEFAULT_TEX_GAP_DECODER_RISK_ADJUSTED_PROBE),
        ("Replay seed decodeur gaps .tex", DEFAULT_TEX_GAP_DECODER_SEED_REPLAY),
        ("Promotion controle decodeur gaps .tex", DEFAULT_TEX_GAP_DECODER_CONTROL_PROMOTION_PROBE),
        ("Rejet risques decodeur gaps .tex", DEFAULT_TEX_GAP_DECODER_FALSE_RISK_QUEUE),
        ("Replay clean decodeur gaps .tex", DEFAULT_TEX_GAP_DECODER_CLEAN_REPLAY),
        ("Queue gaps clean decodeur .tex", DEFAULT_TEX_GAP_DECODER_CLEAN_GAP_QUEUE),
        ("Runs unresolved decodeur .tex", DEFAULT_TEX_GAP_DECODER_UNRESOLVED_RUN_PROBE),
        ("Queue zero unresolved .tex", DEFAULT_TEX_GAP_DECODER_UNRESOLVED_ZERO_QUEUE),
        ("Probe len64 interne .tex", DEFAULT_TEX_GAP_DECODER_LEN64_INTERNAL_PROBE),
        ("Source len64 decodeur .tex", DEFAULT_TEX_GAP_DECODER_LEN64_SOURCE_PROBE),
        ("Selecteurs len64 decodeur .tex", DEFAULT_TEX_GAP_DECODER_LEN64_SELECTOR_PROBE),
        ("Replay len64 promu decodeur .tex", DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_REPLAY),
        ("Queue gaps len64 promu .tex", DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_GAP_QUEUE),
        ("Runs len64 promu .tex", DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_RUN_PROBE),
        ("Queue zero len64 promu .tex", DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_ZERO_QUEUE),
        (
            "Source zero len64 promu .tex",
            DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_ZERO_SOURCE_PROBE,
        ),
        (
            "Selecteurs large32 promu .tex",
            DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_SELECTOR_PROBE,
        ),
        ("Replay large32 promu .tex", DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_REPLAY),
        ("Queue gaps large32 promu .tex", DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_GAP_QUEUE),
        ("Runs large32 promu .tex", DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_RUN_PROBE),
        (
            "Queue zero large32 promu .tex",
            DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_ZERO_QUEUE,
        ),
        (
            "Source zero large32 promu .tex",
            DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_ZERO_SOURCE_PROBE,
        ),
        (
            "Selecteurs medium8 promu .tex",
            DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_SELECTOR_PROBE,
        ),
        ("Replay medium8 promu .tex", DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_REPLAY),
        ("Queue gaps medium8 promu .tex", DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_GAP_QUEUE),
        ("Runs medium8 promu .tex", DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_RUN_PROBE),
        ("Queue zero medium8 promu .tex", DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_ZERO_QUEUE),
        (
            "Source zero medium8 promu .tex",
            DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_ZERO_SOURCE_PROBE,
        ),
        (
            "Selecteurs medium8 restants .tex",
            DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_REMAINING_SELECTOR_PROBE,
        ),
        (
            "Selecteurs large32 restants .tex",
            DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_REMAINING_SELECTOR_PROBE,
        ),
        (
            "Selecteurs trailing large32 .tex",
            DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_TRAILING_LARGE32_SELECTOR_PROBE,
        ),
        (
            "Selecteurs leading len64 .tex",
            DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LEADING_LEN64_SELECTOR_PROBE,
        ),
        (
            "Selecteurs internal small .tex",
            DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_INTERNAL_SMALL_SELECTOR_PROBE,
        ),
        (
            "Selecteurs leading large32 .tex",
            DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LEADING_LARGE32_SELECTOR_PROBE,
        ),
        (
            "Selecteurs trailing medium8 .tex",
            DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_TRAILING_MEDIUM8_SELECTOR_PROBE,
        ),
        ("Replay restants promus .tex", DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_REMAINING_REPLAY),
        ("Queue gaps restants promus .tex", DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_REMAINING_GAP_QUEUE),
        ("Runs restants promus .tex", DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_REMAINING_RUN_PROBE),
        ("Queue zero restants promus .tex", DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_REMAINING_ZERO_QUEUE),
        (
            "Source zero restants promus .tex",
            DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_REMAINING_ZERO_SOURCE_PROBE,
        ),
        (
            "Micro selecteurs internal medium8 .tex",
            DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MICRO_INTERNAL_MEDIUM8_SELECTOR_PROBE,
        ),
        (
            "Micro selecteurs internal large32 .tex",
            DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MICRO_INTERNAL_LARGE32_SELECTOR_PROBE,
        ),
        (
            "Micro selecteurs internal small .tex",
            DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MICRO_INTERNAL_SMALL_SELECTOR_PROBE,
        ),
        (
            "Micro selecteurs leading large32 .tex",
            DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MICRO_LEADING_LARGE32_SELECTOR_PROBE,
        ),
        (
            "Micro selecteurs trailing medium8 .tex",
            DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MICRO_TRAILING_MEDIUM8_SELECTOR_PROBE,
        ),
        (
            "Micro selecteurs trailing large32 .tex",
            DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MICRO_TRAILING_LARGE32_SELECTOR_PROBE,
        ),
        ("Replay micro promu .tex", DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MICRO_REPLAY),
        ("Queue gaps micro promu .tex", DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MICRO_GAP_QUEUE),
        ("Runs micro promu .tex", DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MICRO_RUN_PROBE),
        ("Queue zero micro promu .tex", DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MICRO_ZERO_QUEUE),
        (
            "Source zero micro promu .tex",
            DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MICRO_ZERO_SOURCE_PROBE,
        ),
        (
            "Triple selecteurs internal medium8 .tex",
            Path("output/tex_gap_decoder_len64_promoted_postmicro_internal_medium8_triple_selector_probe/index.html"),
        ),
        (
            "Triple selecteurs internal small .tex",
            Path("output/tex_gap_decoder_len64_promoted_postmicro_internal_small_triple_selector_probe/index.html"),
        ),
        (
            "Triple selecteurs internal large32 .tex",
            Path("output/tex_gap_decoder_len64_promoted_postmicro_internal_large32_triple_selector_probe/index.html"),
        ),
        (
            "Triple selecteurs trailing medium8 .tex",
            Path("output/tex_gap_decoder_len64_promoted_postmicro_trailing_medium8_triple_selector_probe/index.html"),
        ),
        ("Replay triple promu .tex", Path("output/tex_gap_decoder_len64_promoted_triple_replay/index.html")),
        ("Queue gaps triple promu .tex", Path("output/tex_gap_decoder_len64_promoted_triple_gap_queue/index.html")),
        ("Runs triple promu .tex", Path("output/tex_gap_decoder_len64_promoted_triple_run_probe/index.html")),
        ("Queue zero triple promu .tex", Path("output/tex_gap_decoder_len64_promoted_triple_zero_queue/index.html")),
        (
            "Source zero triple promu .tex",
            Path("output/tex_gap_decoder_len64_promoted_triple_zero_source_probe/index.html"),
        ),
        (
            "Post-triple micro selecteurs internal medium8 .tex",
            Path("output/tex_gap_decoder_len64_promoted_posttriple_micro_internal_medium8_triple_selector_probe/index.html"),
        ),
        (
            "Post-triple micro selecteurs internal large32 .tex",
            Path("output/tex_gap_decoder_len64_promoted_posttriple_micro_internal_large32_triple_selector_probe/index.html"),
        ),
        (
            "Post-triple micro selecteurs leading edge large32 .tex",
            Path("output/tex_gap_decoder_len64_promoted_posttriple_micro_leading_edge_large32_triple_selector_probe/index.html"),
        ),
        (
            "Post-triple micro selecteurs internal small .tex",
            Path("output/tex_gap_decoder_len64_promoted_posttriple_micro_internal_small_triple_selector_probe/index.html"),
        ),
        (
            "Post-triple micro selecteurs trailing medium8 .tex",
            Path("output/tex_gap_decoder_len64_promoted_posttriple_micro_trailing_medium8_triple_selector_probe/index.html"),
        ),
        (
            "Replay post-triple micro .tex",
            Path("output/tex_gap_decoder_len64_promoted_posttriple_micro_replay/index.html"),
        ),
        (
            "Queue gaps post-triple micro .tex",
            Path("output/tex_gap_decoder_len64_promoted_posttriple_micro_gap_queue/index.html"),
        ),
        (
            "Runs post-triple micro .tex",
            Path("output/tex_gap_decoder_len64_promoted_posttriple_micro_run_probe/index.html"),
        ),
        (
            "Queue zero post-triple micro .tex",
            Path("output/tex_gap_decoder_len64_promoted_posttriple_micro_zero_queue/index.html"),
        ),
        (
            "Source zero post-triple micro .tex",
            Path("output/tex_gap_decoder_len64_promoted_posttriple_micro_zero_source_probe/index.html"),
        ),
        (
            "Residuel selecteurs trailing large96 edge .tex",
            Path("output/tex_gap_decoder_len64_promoted_residual_trailing_large96_edge_selector_probe/index.html"),
        ),
        (
            "Residuel selecteurs trailing large32 edge .tex",
            Path("output/tex_gap_decoder_len64_promoted_residual_trailing_large32_edge_selector_probe/index.html"),
        ),
        (
            "Residuel selecteurs span large32 edge .tex",
            Path("output/tex_gap_decoder_len64_promoted_residual_span_full_large32_edge_selector_probe/index.html"),
        ),
        (
            "Residuel selecteurs span large32 .tex",
            Path("output/tex_gap_decoder_len64_promoted_residual_span_full_large32_selector_probe/index.html"),
        ),
        (
            "Residuel selecteurs trailing medium8 edge .tex",
            Path("output/tex_gap_decoder_len64_promoted_residual_trailing_medium8_edge_selector_probe/index.html"),
        ),
        (
            "Residuel selecteurs trailing large32 .tex",
            Path("output/tex_gap_decoder_len64_promoted_residual_trailing_large32_selector_probe/index.html"),
        ),
        (
            "Residuel selecteurs trailing small .tex",
            Path("output/tex_gap_decoder_len64_promoted_residual_trailing_small_selector_probe/index.html"),
        ),
        (
            "Residuel selecteurs trailing small edge .tex",
            Path("output/tex_gap_decoder_len64_promoted_residual_trailing_small_edge_selector_probe/index.html"),
        ),
        ("Replay residuel promu .tex", Path("output/tex_gap_decoder_len64_promoted_residual_replay/index.html")),
        ("Queue gaps residuel promu .tex", Path("output/tex_gap_decoder_len64_promoted_residual_gap_queue/index.html")),
        ("Runs residuel promu .tex", Path("output/tex_gap_decoder_len64_promoted_residual_run_probe/index.html")),
        ("Queue zero residuel promu .tex", Path("output/tex_gap_decoder_len64_promoted_residual_zero_queue/index.html")),
        (
            "Source zero residuel promu .tex",
            Path("output/tex_gap_decoder_len64_promoted_residual_zero_source_probe/index.html"),
        ),
        (
            "Tiny selecteurs span small .tex",
            Path("output/tex_gap_decoder_len64_promoted_residual_span_full_small_selector_probe/index.html"),
        ),
        ("Replay tiny promu .tex", Path("output/tex_gap_decoder_len64_promoted_tiny_replay/index.html")),
        (
            "Replay fill nonzero tiny .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_fill_replay/index.html"),
        ),
        (
            "Queue gaps post-fill nonzero tiny .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_fill_gap_queue/index.html"),
        ),
        (
            "Runs post-fill nonzero tiny .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_fill_run_probe/index.html"),
        ),
        (
            "Queue nonzero post-fill tiny .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_fill_nonzero_queue/index.html"),
        ),
        (
            "Source nonzero post-fill tiny .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_fill_nonzero_source_probe/index.html"),
        ),
        (
            "Probe source gaps post-fill nonzero .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_fill_nonzero_gap_source_probe/index.html"),
        ),
        (
            "Probe motifs post-fill nonzero .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_fill_nonzero_gap_pattern_probe/index.html"),
        ),
        (
            "Regles fill post-fill nonzero .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_fill_nonzero_gap_fill_rule_probe/index.html"),
        ),
        (
            "Selecteurs fill post-fill nonzero .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_fill_nonzero_gap_fill_selector_probe/index.html"),
        ),
        ("Queue gaps tiny promu .tex", Path("output/tex_gap_decoder_len64_promoted_tiny_gap_queue/index.html")),
        ("Runs tiny promu .tex", Path("output/tex_gap_decoder_len64_promoted_tiny_run_probe/index.html")),
        ("Queue zero tiny promu .tex", Path("output/tex_gap_decoder_len64_promoted_tiny_zero_queue/index.html")),
        (
            "Source zero tiny promu .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_zero_source_probe/index.html"),
        ),
        (
            "Queue nonzero tiny promu .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_queue/index.html"),
        ),
        (
            "Source nonzero tiny promu .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_source_probe/index.html"),
        ),
        (
            "Probe source gaps nonzero tiny .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_source_probe/index.html"),
        ),
        (
            "Probe motifs gaps nonzero tiny .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_pattern_probe/index.html"),
        ),
        (
            "Controle motifs gaps nonzero tiny .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_control_pattern_probe/index.html"),
        ),
        (
            "Probe valeurs gaps nonzero tiny .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_value_probe/index.html"),
        ),
        (
            "Sequences exactes gaps nonzero tiny .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_exact_sequence_probe/index.html"),
        ),
        (
            "Regles fill gaps nonzero tiny .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_fill_rule_probe/index.html"),
        ),
        (
            "Selecteurs fill gaps nonzero tiny .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_fill_selector_probe/index.html"),
        ),
        (
            "Selecteurs palette gaps nonzero tiny .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_palette_selector_probe/index.html"),
        ),
        (
            "Formes palette gaps nonzero tiny .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_palette_shape_probe/index.html"),
        ),
        (
            "Controle formes palette gaps nonzero tiny .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_palette_shape_control_probe/index.html"),
        ),
        (
            "Valeurs formes palette gaps nonzero tiny .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_palette_shape_value_probe/index.html"),
        ),
        (
            "Paires valeurs palette gaps nonzero tiny .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_palette_pair_value_probe/index.html"),
        ),
        (
            "Dominants gaps nonzero tiny .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_dominant_probe/index.html"),
        ),
        (
            "Formes noisy gaps nonzero tiny .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_noisy_shape_probe/index.html"),
        ),
        (
            "Gradient noisy gaps nonzero tiny .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_probe/index.html"),
        ),
        (
            "Copies verticales post-formule palette flat-walk .tex",
            Path(
                "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_post_formula_vertical_copy_probe/index.html"
            ),
        ),
        (
            "Copies pair meme forme gradient post-formule .tex",
            Path(
                "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_shape_peer_copy_probe/index.html"
            ),
        ),
        (
            "Haut/bas source-profile gradient post-formule .tex",
            Path("output/tex_gradient_source_profile_high_low/index.html"),
        ),
        (
            "Bas apres high-safe source-profile gradient .tex",
            Path("output/tex_gradient_source_profile_high_safe_low/index.html"),
        ),
        (
            "Etat opcode payload gradient .tex",
            Path("output/tex_gradient_payload_state_opcode/index.html"),
        ),
        (
            "Macro opcode payload gradient .tex",
            Path("output/tex_gradient_macro_opcode/index.html"),
        ),
        (
            "Split conflits macro opcode gradient .tex",
            Path("output/tex_gradient_macro_conflict_split/index.html"),
        ),
        (
            "Etat residuel macro opcode gradient .tex",
            Path("output/tex_gradient_macro_residual_state/index.html"),
        ),
        (
            "Phase macro opcode gradient .tex",
            Path("output/tex_gradient_macro_phase/index.html"),
        ),
        (
            "Split conflits phase macro opcode gradient .tex",
            Path("output/tex_gradient_macro_phase_conflict_split/index.html"),
        ),
        (
            "Sequence phase macro opcode gradient .tex",
            Path("output/tex_gradient_macro_phase_sequence/index.html"),
        ),
        (
            "Transition fixture/op macro opcode gradient .tex",
            Path("output/tex_gradient_macro_fixture_transition/index.html"),
        ),
        (
            "Cluster etat macro opcode gradient .tex",
            Path("output/tex_gradient_macro_state_cluster/index.html"),
        ),
        (
            "Etat macro + source-profile gradient .tex",
            Path("output/tex_gradient_macro_source_profile_state/index.html"),
        ),
        (
            "Payload cluster etat macro opcode gradient .tex",
            Path("output/tex_gradient_macro_state_cluster_payload/index.html"),
        ),
        (
            "Source cluster etat macro opcode gradient .tex",
            Path("output/tex_gradient_macro_state_cluster_source/index.html"),
        ),
        (
            "Literal/geometrie cluster etat macro opcode gradient .tex",
            Path("output/tex_gradient_macro_state_cluster_literal/index.html"),
        ),
        (
            "Backrefs cluster etat macro opcode gradient .tex",
            Path("output/tex_gradient_macro_state_cluster_backref/index.html"),
        ),
        (
            "Contexte gradients repetes .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_repeat_context_probe/index.html"),
        ),
        (
            "Seeds gradients repetes .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_unlock_probe/index.html"),
        ),
        (
            "Famille shifts seeds gradients .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_shift_family_probe/index.html"),
        ),
        (
            "Selecteurs delta seeds gradients .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_selector_probe/index.html"),
        ),
        (
            "Contexte delta seeds gradients .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_context_probe/index.html"),
        ),
        (
            "Phase delta seeds gradients .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_phase_probe/index.html"),
        ),
        (
            "Etat delta seeds gradients .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_state_probe/index.html"),
        ),
        (
            "Sequence opcode seeds gradients .tex",
            Path(
                "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_opcode_sequence_probe/index.html"
            ),
        ),
        (
            "Semantique opcode seeds gradients .tex",
            Path(
                "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_semantic_opcode_probe/index.html"
            ),
        ),
        (
            "Payload opcode seeds gradients .tex",
            Path(
                "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_payload_opcode_probe/index.html"
            ),
        ),
        (
            "Profil payload gradient .tex",
            Path("output/tex_gradient_payload_profile/index.html"),
        ),
        (
            "Spatial connu nonlocal gradient .tex",
            Path("output/tex_gradient_nonlocal_known_spatial/index.html"),
        ),
        (
            "Etat sequence connue gradient .tex",
            Path("output/tex_gradient_sequence_known_state/index.html"),
        ),
        (
            "Bas apres high-safe sequence gradient .tex",
            Path("output/tex_gradient_sequence_high_safe_low/index.html"),
        ),
        (
            "Source-profile apres high-safe sequence gradient .tex",
            Path("output/tex_gradient_sequence_high_safe_source_profile_low/index.html"),
        ),
        (
            "Row/corpus apres high-safe sequence gradient .tex",
            Path("output/tex_gradient_sequence_high_safe_row_corpus_low/index.html"),
        ),
        (
            "Transform low apres row/corpus gradient .tex",
            Path("output/tex_gradient_sequence_high_safe_transform_low/index.html"),
        ),
        (
            "Source-window residuel gradient .tex",
            Path("output/tex_gradient_sequence_high_safe_source_window/index.html"),
        ),
        (
            "Controle/opcode residuel high-safe gradient .tex",
            Path("output/tex_gradient_sequence_high_safe_control_opcode/index.html"),
        ),
        (
            "Transition low cross-row high-safe gradient .tex",
            Path("output/tex_gradient_sequence_high_safe_row_transition/index.html"),
        ),
        (
            "Markov low row-local high-safe gradient .tex",
            Path("output/tex_gradient_sequence_high_safe_row_markov/index.html"),
        ),
        (
            "Template low row high-safe gradient .tex",
            Path("output/tex_gradient_sequence_high_safe_row_template/index.html"),
        ),
        (
            "Split bucket low high-safe gradient .tex",
            Path("output/tex_gradient_sequence_high_safe_low_bucket_split/index.html"),
        ),
        (
            "Exceptions low high-safe gradient .tex",
            Path("output/tex_gradient_sequence_high_safe_low_exception/index.html"),
        ),
        (
            "Alignement exceptions low high-safe gradient .tex",
            Path("output/tex_gradient_sequence_high_safe_low_exception_alignment/index.html"),
        ),
        (
            "Revue alignement exceptions low high-safe gradient .tex",
            Path("output/tex_gradient_sequence_high_safe_low_exception_alignment_review/index.html"),
        ),
        (
            "Familles row exceptions low high-safe gradient .tex",
            Path("output/tex_gradient_sequence_high_safe_low_exception_row_family/index.html"),
        ),
        (
            "Etat externe exceptions low high-safe gradient .tex",
            Path("output/tex_gradient_sequence_high_safe_low_exception_external_state/index.html"),
        ),
        (
            "Dependances source exceptions low high-safe gradient .tex",
            Path("output/tex_gradient_sequence_high_safe_low_exception_source_dependency/index.html"),
        ),
        (
            "Chaines source exceptions low high-safe gradient .tex",
            Path("output/tex_gradient_sequence_high_safe_low_exception_source_chain/index.html"),
        ),
        (
            "Terminaux source exceptions low high-safe gradient .tex",
            Path("output/tex_gradient_sequence_high_safe_low_exception_source_terminal/index.html"),
        ),
        (
            "Revue terminaux source exceptions low high-safe gradient .tex",
            Path("output/tex_gradient_sequence_high_safe_low_exception_source_terminal_review/index.html"),
        ),
        (
            "Delta terminaux source exceptions low high-safe gradient .tex",
            Path("output/tex_gradient_sequence_high_safe_low_exception_source_terminal_delta/index.html"),
        ),
        (
            "Contexte chaines terminaux source exceptions low high-safe gradient .tex",
            Path("output/tex_gradient_sequence_high_safe_low_exception_source_terminal_chain_context/index.html"),
        ),
        (
            "Support replay terminaux source exceptions low high-safe gradient .tex",
            Path("output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_support/index.html"),
        ),
        (
            "Union replay terminaux source exceptions low high-safe gradient .tex",
            Path("output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union/index.html"),
        ),
        (
            "Garde union replay terminaux source exceptions low high-safe gradient .tex",
            Path("output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard/index.html"),
        ),
        (
            "Split garde union replay terminaux source exceptions low high-safe gradient .tex",
            Path("output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_split/index.html"),
        ),
        (
            "Couverture garde union replay terminaux source exceptions low high-safe gradient .tex",
            Path("output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover/index.html"),
        ),
        (
            "Promotion couverture garde union replay terminaux source exceptions low high-safe gradient .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_promoted_replay/index.html"
            ),
        ),
        (
            "Dependances source exceptions low high-safe gradient base replay promue .tex",
            Path("output/tex_gradient_sequence_high_safe_low_exception_source_dependency_promoted_replay/index.html"),
        ),
        (
            "Chaines source exceptions low high-safe gradient base replay promue .tex",
            Path("output/tex_gradient_sequence_high_safe_low_exception_source_chain_promoted_replay/index.html"),
        ),
        (
            "Terminaux source exceptions low high-safe gradient base replay promue .tex",
            Path("output/tex_gradient_sequence_high_safe_low_exception_source_terminal_promoted_replay/index.html"),
        ),
        (
            "Revue terminaux source exceptions low high-safe gradient base replay promue .tex",
            Path("output/tex_gradient_sequence_high_safe_low_exception_source_terminal_review_promoted_replay/index.html"),
        ),
        (
            "Contexte chaines terminaux source exceptions low high-safe gradient base replay promue .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_chain_context_promoted_replay/index.html"
            ),
        ),
        (
            "Support replay terminaux source exceptions low high-safe gradient base replay promue .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_support_promoted_replay/index.html"
            ),
        ),
        (
            "Union replay terminaux source exceptions low high-safe gradient base replay promue .tex",
            Path("output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_promoted_replay/index.html"),
        ),
        (
            "Couverture garde union replay terminaux source exceptions low high-safe gradient base replay promue .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_promoted_base/index.html"
            ),
        ),
        (
            "Seconde promotion couverture garde union replay terminaux source exceptions low high-safe gradient .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_second_promoted_replay/index.html"
            ),
        ),
        (
            "Dependances source exceptions low high-safe gradient seconde base replay promue .tex",
            Path("output/tex_gradient_sequence_high_safe_low_exception_source_dependency_second_promoted_replay/index.html"),
        ),
        (
            "Revue noyau residuel dependances source low high-safe gradient .tex",
            Path("output/tex_gradient_sequence_high_safe_low_exception_source_dependency_residual_core/index.html"),
        ),
        (
            "Revue sources terminales externes exceptions low high-safe gradient .tex",
            Path("output/tex_gradient_sequence_high_safe_low_exception_external_terminal_source/index.html"),
        ),
        (
            "Selecteur small nonzero sources terminales externes exceptions low high-safe gradient .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector/index.html"
            ),
        ),
        (
            "Grammaire compact-control sources terminales externes exceptions low high-safe gradient .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_compact_control_grammar/index.html"
            ),
        ),
        (
            "Pont spatial gradient sources terminales externes exceptions low high-safe gradient .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_gradient_bridge/index.html"
            ),
        ),
        (
            "Selecteur pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_selector/index.html"
            ),
        ),
        (
            "Producteur delta pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer/index.html"
            ),
        ),
        (
            "Combinator cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_combinator/index.html"
            ),
        ),
        (
            "Garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_guard/index.html"
            ),
        ),
        (
            "Support garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_support/index.html"
            ),
        ),
        (
            "Revue target-only garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_only_review/index.html"
            ),
        ),
        (
            "Evidence independante garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_independent_evidence/index.html"
            ),
        ),
        (
            "Corpus etendu garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_expanded_corpus/index.html"
            ),
        ),
        (
            "Revue pair-mod garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_pair_mod_review/index.html"
            ),
        ),
        (
            "Support raffine garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_refined_support/index.html"
            ),
        ),
        (
            "Variante formule garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_formula_variant/index.html"
            ),
        ),
        (
            "Gate contexte tail garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_tail_context_gate/index.html"
            ),
        ),
        (
            "Support non-tail garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_non_tail_support/index.html"
            ),
        ),
        (
            "Split familles pair garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_pair_family_split/index.html"
            ),
        ),
        (
            "Pont familles garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_family_bridge/index.html"
            ),
        ),
        (
            "Resolveur atomes garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_atom_resolver/index.html"
            ),
        ),
        (
            "Gating target-overlap garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_overlap_gate/index.html"
            ),
        ),
        (
            "Split carrier target-overlap garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_split/index.html"
            ),
        ),
        (
            "Switch local carrier cible garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_local_switch/index.html"
            ),
        ),
        (
            "Split contexte carrier cible garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_split/index.html"
            ),
        ),
        (
            "Revue contexte carrier cible garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_review/index.html"
            ),
        ),
        (
            "Promotion contexte carrier cible garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_promoted_replay/index.html"
            ),
        ),
        (
            "Dependances source exceptions low high-safe gradient base carrier-context promue .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_carrier_context_promoted_replay/index.html"
            ),
        ),
        (
            "Garde producteur delta pont spatial base carrier-context promue .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer_guard_carrier_context_promoted_replay/index.html"
            ),
        ),
        (
            "Promotion garde producteur delta pont spatial base carrier-context promue .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer_guard_carrier_context_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres promotion delta-guard .tex",
            Path("output/tex_gradient_sequence_high_safe_low_exception_source_dependency_delta_guard_promoted_replay/index.html"),
        ),
        (
            "Coeur residuel dependances source apres promotion delta-guard .tex",
            Path("output/tex_gradient_sequence_high_safe_low_exception_source_dependency_delta_guard_promoted_residual_core/index.html"),
        ),
        (
            "Sources terminales externes apres promotion delta-guard .tex",
            Path("output/tex_gradient_sequence_high_safe_low_exception_external_terminal_source_delta_guard_promoted_replay/index.html"),
        ),
        (
            "Selecteur small nonzero final apres promotion delta-guard .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector_delta_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Revue sources small nonzero finale apres promotion delta-guard .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_source_review_delta_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Preuve elargie small nonzero finale apres promotion delta-guard .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_broader_evidence_delta_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Revue garde relative small nonzero finale apres promotion delta-guard .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_relative_guard_review_delta_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Promotion garde relative small nonzero finale apres promotion delta-guard .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_relative_guard_promoted_replay_delta_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Dependances source apres promotion finale garde relative small nonzero .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_final_relative_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Noyau residuel dependances source apres promotion finale garde relative .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_final_relative_guard_promoted_residual_core/index.html"
            ),
        ),
        (
            "Sources terminales externes apres promotion finale garde relative .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_source_final_relative_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Revue terminaux source apres promotion finale garde relative .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_review_final_relative_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Union replay terminaux source apres promotion finale garde relative .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_final_relative_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Couverture garde union replay terminaux source apres promotion finale garde relative .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_final_relative_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Promotion couverture garde union replay terminaux source apres promotion finale garde relative .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_final_relative_guard_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres promotion finale garde connue .tex",
            Path("output/tex_gradient_sequence_high_safe_low_exception_source_dependency_final_known_guard_promoted_replay/index.html"),
        ),
        (
            "Noyau residuel dependances source apres promotion finale garde connue .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_final_known_guard_promoted_residual_core/index.html"
            ),
        ),
        (
            "Revue garde bucket-split source apres promotion finale garde connue .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_bucket_split_guard_final_known_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Promotion garde bucket-split source apres promotion finale garde connue .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_bucket_split_guard_final_known_guard_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres promotion bucket-split finale .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_bucket_split_guard_final_known_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Noyau residuel dependances source apres promotion bucket-split finale .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_bucket_split_guard_final_known_guard_promoted_residual_core/index.html"
            ),
        ),
        (
            "Union replay terminaux source apres promotion bucket-split finale .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_bucket_split_guard_final_known_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Couverture garde union replay terminaux source apres promotion bucket-split finale .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_bucket_split_guard_final_known_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Promotion couverture garde union replay terminaux source apres promotion bucket-split finale .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_bucket_split_guard_final_known_guard_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Revue garde source-byte apres promotion bucket-split finale .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_bucket_split_guard_final_known_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Promotion garde source-byte apres promotion terminale bucket-split finale .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_bucket_split_terminal_guard_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres promotion source-byte finale .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_source_byte_guard_bucket_split_terminal_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Noyau residuel dependances source apres promotion source-byte finale .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_source_byte_guard_bucket_split_terminal_guard_promoted_residual_core/index.html"
            ),
        ),
        (
            "Promotion deuxieme garde source-byte .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_second_source_byte_guard_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres deuxieme promotion source-byte .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_second_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Promotion troisieme garde source-byte .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_third_source_byte_guard_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres troisieme promotion source-byte .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_third_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Promotion quatrieme garde source-byte .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_fourth_source_byte_guard_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres quatrieme promotion source-byte .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_fourth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Noyau residuel apres quatrieme promotion source-byte .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_fourth_source_byte_guard_promoted_residual_core/index.html"
            ),
        ),
        (
            "Revue cinquieme garde source-byte apres quatrieme promotion .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_fifth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Promotion cinquieme garde source-byte .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_fifth_source_byte_guard_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres cinquieme promotion source-byte .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_fifth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Promotion sixieme garde source-byte .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_sixth_source_byte_guard_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres sixieme promotion source-byte .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_sixth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Promotion septieme garde source-byte .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_seventh_source_byte_guard_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres septieme promotion source-byte .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_seventh_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Promotion huitieme garde source-byte .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_eighth_source_byte_guard_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres huitieme promotion source-byte .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_eighth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Promotion neuvieme garde source-byte .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_ninth_source_byte_guard_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres neuvieme promotion source-byte .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Noyau residuel apres neuvieme promotion source-byte .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_ninth_source_byte_guard_promoted_residual_core/index.html"
            ),
        ),
        (
            "Revue dixieme garde source-byte apres neuvieme promotion .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_tenth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Revue terminale source apres neuvieme promotion source-byte .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_review_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Contexte chaines terminales apres neuvieme promotion source-byte .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_chain_context_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Union replay terminal apres neuvieme promotion source-byte .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Couverture garde union terminale apres neuvieme promotion source-byte .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Promotion couverture garde union terminale apres neuvieme promotion source-byte .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_ninth_source_byte_guard_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres couverture garde terminale neuvieme source-byte .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Noyau residuel apres couverture garde terminale neuvieme source-byte .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_guard_cover_ninth_source_byte_guard_promoted_residual_core/index.html"
            ),
        ),
        (
            "Revue contexte terminal/root apres couverture garde terminale neuvieme source-byte .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Promotion contexte terminal/root apres couverture garde terminale neuvieme source-byte .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres contexte terminal/root neuvieme source-byte .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Noyau residuel apres contexte terminal/root neuvieme source-byte .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_residual_core/index.html"
            ),
        ),
        (
            "Revue transform terminal/root apres contexte terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Promotion transform terminal/root apres contexte terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Noyau residuel apres transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_residual_core/index.html"
            ),
        ),
        (
            "Seconde revue transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_second_terminal_root_transform_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Seconde promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_second_terminal_root_transform_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres seconde promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_second_terminal_root_transform_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Noyau residuel apres seconde promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_second_terminal_root_transform_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_residual_core/index.html"
            ),
        ),
        (
            "Troisieme revue transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_third_terminal_root_transform_second_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Troisieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_third_terminal_root_transform_second_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres troisieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_third_terminal_root_transform_second_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Noyau residuel apres troisieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_third_terminal_root_transform_second_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_residual_core/index.html"
            ),
        ),
        (
            "Quatrieme revue transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_fourth_terminal_root_transform_third_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Quatrieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_fourth_terminal_root_transform_third_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres quatrieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_fourth_terminal_root_transform_third_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Noyau residuel apres quatrieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_fourth_terminal_root_transform_third_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_residual_core/index.html"
            ),
        ),
        (
            "Cinquieme revue transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_fifth_terminal_root_transform_fourth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Cinquieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_fifth_terminal_root_transform_fourth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres cinquieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_fifth_terminal_root_transform_fourth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Noyau residuel apres cinquieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_fifth_terminal_root_transform_fourth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_residual_core/index.html"
            ),
        ),
        (
            "Sixieme revue transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_sixth_terminal_root_transform_fifth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Sixieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_sixth_terminal_root_transform_fifth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres sixieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_sixth_terminal_root_transform_fifth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Noyau residuel apres sixieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_sixth_terminal_root_transform_fifth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_residual_core/index.html"
            ),
        ),
        (
            "Septieme revue transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_seventh_terminal_root_transform_sixth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Septieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_seventh_terminal_root_transform_sixth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres septieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_seventh_terminal_root_transform_sixth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Noyau residuel apres septieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_seventh_terminal_root_transform_sixth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_residual_core/index.html"
            ),
        ),
        (
            "Huitieme revue transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_eighth_terminal_root_transform_seventh_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Huitieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_eighth_terminal_root_transform_seventh_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres huitieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_eighth_terminal_root_transform_seventh_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Noyau residuel apres huitieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_eighth_terminal_root_transform_seventh_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_residual_core/index.html"
            ),
        ),
        (
            "Neuvieme revue transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_ninth_terminal_root_transform_eighth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Neuvieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_ninth_terminal_root_transform_eighth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres neuvieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_ninth_terminal_root_transform_eighth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Noyau residuel apres neuvieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_ninth_terminal_root_transform_eighth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_residual_core/index.html"
            ),
        ),
        (
            "Dixieme revue transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_tenth_terminal_root_transform_ninth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Dixieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_tenth_terminal_root_transform_ninth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres dixieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_tenth_terminal_root_transform_ninth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Noyau residuel apres dixieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_tenth_terminal_root_transform_ninth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_residual_core/index.html"
            ),
        ),
        (
            "Onzieme revue transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_eleventh_terminal_root_transform_tenth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Onzieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_eleventh_terminal_root_transform_tenth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres onzieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_eleventh_terminal_root_transform_tenth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Noyau residuel apres onzieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_eleventh_terminal_root_transform_tenth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_residual_core/index.html"
            ),
        ),
        (
            "Douzieme revue transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_twelfth_terminal_root_transform_eleventh_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Douzieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_twelfth_terminal_root_transform_eleventh_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres douzieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_twelfth_terminal_root_transform_eleventh_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Noyau residuel apres douzieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_twelfth_terminal_root_transform_eleventh_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_residual_core/index.html"
            ),
        ),
        (
            "Treizieme revue transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_thirteenth_terminal_root_transform_twelfth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Treizieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_thirteenth_terminal_root_transform_twelfth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres treizieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_thirteenth_terminal_root_transform_twelfth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Noyau residuel apres treizieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_thirteenth_terminal_root_transform_twelfth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_residual_core/index.html"
            ),
        ),
        (
            "Quatorzieme revue transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_fourteenth_terminal_root_transform_thirteenth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Quatorzieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_fourteenth_terminal_root_transform_thirteenth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres quatorzieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_fourteenth_terminal_root_transform_thirteenth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Noyau residuel apres quatorzieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_fourteenth_terminal_root_transform_thirteenth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_residual_core/index.html"
            ),
        ),
        (
            "Quinzieme revue transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_fifteenth_terminal_root_transform_fourteenth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Quinzieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_fifteenth_terminal_root_transform_fourteenth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres quinzieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_fifteenth_terminal_root_transform_fourteenth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Noyau residuel apres quinzieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_fifteenth_terminal_root_transform_fourteenth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_residual_core/index.html"
            ),
        ),
        (
            "Seizieme revue transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_sixteenth_terminal_root_transform_fifteenth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Seizieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_sixteenth_terminal_root_transform_fifteenth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres seizieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_sixteenth_terminal_root_transform_fifteenth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Noyau residuel apres seizieme promotion transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_terminal_root_transform_sixteenth_terminal_root_transform_fifteenth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_residual_core/index.html"
            ),
        ),
        (
            "Dix-septieme revue transform terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_seventeenth_terminal_root_transform_sixteenth_terminal_root_context_terminal_guard_cover_ninth_source_byte_guard_promoted_replay/index.html"
            ),
        ),
        (
            "Revue garde source-byte apres seizieme promotion terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_terminal_root_transform_sixteenth_promoted_replay/index.html"
            ),
        ),
        (
            "Promotion garde source-byte apres seizieme terminal/root .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_terminal_root_transform_sixteenth_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres promotion source-byte terminal/root seizieme .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_source_byte_guard_terminal_root_transform_sixteenth_promoted_replay/index.html"
            ),
        ),
        (
            "Noyau residuel apres promotion source-byte terminal/root seizieme .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_source_byte_guard_terminal_root_transform_sixteenth_promoted_residual_core/index.html"
            ),
        ),
        (
            "Deuxieme revue garde source-byte apres terminal/root seizieme .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_second_terminal_root_transform_sixteenth_promoted_replay/index.html"
            ),
        ),
        (
            "Deuxieme promotion source-byte apres terminal/root seizieme .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_second_terminal_root_transform_sixteenth_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres deuxieme promotion source-byte terminal/root seizieme .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_second_source_byte_guard_terminal_root_transform_sixteenth_promoted_replay/index.html"
            ),
        ),
        (
            "Noyau residuel apres deuxieme promotion source-byte terminal/root seizieme .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_second_source_byte_guard_terminal_root_transform_sixteenth_promoted_residual_core/index.html"
            ),
        ),
        (
            "Troisieme revue garde source-byte apres terminal/root seizieme .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_third_terminal_root_transform_sixteenth_promoted_replay/index.html"
            ),
        ),
        (
            "Troisieme promotion source-byte apres terminal/root seizieme .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_third_terminal_root_transform_sixteenth_promoted_replay_promoted/index.html"
            ),
        ),
        (
            "Dependances source apres troisieme promotion source-byte terminal/root seizieme .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_third_source_byte_guard_terminal_root_transform_sixteenth_promoted_replay/index.html"
            ),
        ),
        (
            "Noyau residuel apres troisieme promotion source-byte terminal/root seizieme .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_third_source_byte_guard_terminal_root_transform_sixteenth_promoted_residual_core/index.html"
            ),
        ),
        (
            "Quatrieme revue garde source-byte apres terminal/root seizieme .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_fourth_terminal_root_transform_sixteenth_promoted_replay/index.html"
            ),
        ),
        (
            "Revue terminal/root apres troisieme source-byte terminal/root seizieme .tex",
            Path(
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_root_transform_after_third_source_byte_guard_terminal_root_transform_sixteenth_promoted_replay/index.html"
            ),
        ),
        *terminal_source_byte_dashboard_links(),
        (
            "Etat prerequis exceptions low high-safe gradient .tex",
            Path("output/tex_gradient_sequence_high_safe_low_exception_prerequisite_state/index.html"),
        ),
        (
            "Plateaux noisy gaps nonzero tiny .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_probe/index.html"),
        ),
        (
            "Sources plateaux noisy gaps .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_source_probe/index.html"),
        ),
        (
            "Controle formes plateaux noisy .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_shape_control_probe/index.html"),
        ),
        (
            "Valeurs plateaux noisy .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_value_probe/index.html"),
        ),
        (
            "Copies plateaux noisy .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_backref_probe/index.html"),
        ),
        (
            "Seeds palette plateaux .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_seed_probe/index.html"),
        ),
        (
            "Mix palette plateaux .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_mix_probe/index.html"),
        ),
        (
            "Chaines copies plateaux .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_backref_chain_probe/index.html"),
        ),
        (
            "Signatures palette plateaux .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_signature_probe/index.html"),
        ),
        (
            "Contexte palette plateaux .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_context_probe/index.html"),
        ),
        (
            "Normalisation contexte palette plateaux .tex",
            Path(
                "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_normalized_context_probe/index.html"
            ),
        ),
        (
            "Split valeurs palette plateaux .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_value_split_probe/index.html"),
        ),
        (
            "Table valeurs palette plateaux .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_value_table_probe/index.html"),
        ),
        (
            "Selecteurs compresses palette plateaux .tex",
            Path(
                "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_compressed_selector_probe/index.html"
            ),
        ),
        (
            "Combinaisons selecteurs compresses palette plateaux .tex",
            Path(
                "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_compressed_combo_probe/index.html"
            ),
        ),
        (
            "Formules compresses palette plateaux .tex",
            Path(
                "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_compressed_formula_probe/index.html"
            ),
        ),
        (
            "Formules corpus palette plateaux .tex",
            Path(
                "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_corpus_formula_probe/index.html"
            ),
        ),
        (
            "Candidats promotion palette plateaux .tex",
            Path(
                "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_promotion_candidate_probe/index.html"
            ),
        ),
        (
            "Replay formule palette plateaux .tex",
            Path(
                "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_formula_replay/index.html"
            ),
        ),
        (
            "Micro-tokens noisy gaps .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_micro_token_probe/index.html"),
        ),
        (
            "Unicite mixed-token .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_token_uniqueness_probe/index.html"),
        ),
        (
            "Bandes mixed-token .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_token_band_probe/index.html"),
        ),
        (
            "Copies mixed-token .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_token_backref_probe/index.html"),
        ),
        (
            "Controle mixed-token .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_token_control_probe/index.html"),
        ),
        (
            "Contexte controle mixed-token .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_token_control_context_probe/index.html"),
        ),
        (
            "Combinaisons payload mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_combo/index.html"),
        ),
        (
            "Haut/bas payload mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_high_low/index.html"),
        ),
        (
            "Combinaisons sources mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_external_source_combo/index.html"),
        ),
        (
            "Haut/bas sources mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_external_high_low/index.html"),
        ),
        (
            "Combinaisons etat/source mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_state_external_combo/index.html"),
        ),
        (
            "Etat sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_state/index.html"),
        ),
        (
            "Revue candidats sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_candidate_review/index.html"),
        ),
        (
            "Bootstrap prefixes mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_prefix_bootstrap/index.html"),
        ),
        (
            "Replay prefixes/sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_prefix_sequence_replay/index.html"),
        ),
        (
            "Promotion prefixes/sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_prefix_sequence_promoted_replay/index.html"),
        ),
        (
            "Generalisation sequence promue mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_promoted_generalization/index.html"),
        ),
        (
            "Split low sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_low_split/index.html"),
        ),
        (
            "Promotion split low sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_low_split_promoted_replay/index.html"),
        ),
        (
            "Expansion prerequis sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_expansion/index.html"),
        ),
        (
            "Promotion prerequis sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay/index.html"),
        ),
        (
            "Split low apres prerequis sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_low_split/index.html"),
        ),
        (
            "Promotion split low apres prerequis sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay/index.html"),
        ),
        (
            "Generalisation apres split low prerequis sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_low_split_generalization/index.html"),
        ),
        (
            "Split low residuel prerequis sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_second_low_split_max3/index.html"),
        ),
        (
            "Expansion residuelle prerequis sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_second_expansion_max3/index.html"),
        ),
        (
            "Expansion corpus prerequis sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_expansion/index.html"),
        ),
        (
            "Promotion corpus prerequis sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_promoted_replay/index.html"),
        ),
        (
            "Split low corpus sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_low_split/index.html"),
        ),
        (
            "Promotion split low corpus sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_promoted_replay/index.html"),
        ),
        (
            "Second split low corpus sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split/index.html"),
        ),
        (
            "Promotion second split low corpus sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_promoted_replay/index.html"),
        ),
        (
            "Prerequis adjacent-known sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known/index.html"),
        ),
        (
            "Promotion prerequis adjacent-known sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_promoted_replay/index.html"),
        ),
        (
            "Promotion second prerequis adjacent-known sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_second_promoted_replay/index.html"),
        ),
        (
            "Promotion troisieme prerequis adjacent-known sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay/index.html"),
        ),
        (
            "Generalisation apres adjacent-known sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_generalization/index.html"),
        ),
        (
            "Split low residuel adjacent-known sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_low_split/index.html"),
        ),
        (
            "Expansion corpus residuelle adjacent-known sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_corpus_expansion/index.html"),
        ),
        (
            "Quatrieme prerequis adjacent-known sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_fourth/index.html"),
        ),
        (
            "Transform residuel adjacent-known sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform/index.html"),
        ),
        (
            "Promotion transform adjacent-known sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay/index.html"),
        ),
        (
            "Generalisation apres transform sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_generalization/index.html"),
        ),
        (
            "Second transform residuel sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_second/index.html"),
        ),
        (
            "Split low residuel apres transform sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_low_split/index.html"),
        ),
        (
            "Expansion corpus residuelle apres transform sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_expansion/index.html"),
        ),
        (
            "Prerequis adjacent-known residuel apres transform sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_adjacent/index.html"),
        ),
        (
            "Transform corpus residuel sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus/index.html"),
        ),
        (
            "Promotion transform corpus sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_promoted_replay/index.html"),
        ),
        (
            "Second transform corpus residuel sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_second/index.html"),
        ),
        (
            "Promotion second transform corpus sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_second_promoted_replay/index.html"),
        ),
        (
            "Troisieme transform corpus residuel sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third/index.html"),
        ),
        (
            "Promotion troisieme transform corpus sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay/index.html"),
        ),
        (
            "Quatrieme transform corpus residuel sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_fourth/index.html"),
        ),
        (
            "Split low residuel apres transform corpus sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_low_split/index.html"),
        ),
        (
            "Expansion corpus residuelle apres transform corpus sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_corpus_expansion/index.html"),
        ),
        (
            "Prerequis adjacent-known apres transform corpus sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_adjacent/index.html"),
        ),
        (
            "Low-copy residuel sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_low_copy/index.html"),
        ),
        (
            "Promotion low-copy sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_low_copy_promoted_replay/index.html"),
        ),
        (
            "Generalisation apres low-copy sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_low_copy_generalization/index.html"),
        ),
        (
            "Second low-copy sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_low_copy_second/index.html"),
        ),
        (
            "Split low residuel apres low-copy sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_low_copy_low_split/index.html"),
        ),
        (
            "Expansion corpus residuelle apres low-copy sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_low_copy_corpus_expansion/index.html"),
        ),
        (
            "Prerequis adjacent-known apres low-copy sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_low_copy_adjacent/index.html"),
        ),
        (
            "Transform roles prerequis bloques sequence mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_sequence_blocked_prerequisite_role_transform/index.html"),
        ),
        (
            "Etat opcode payload mixed-value .tex",
            Path("output/tex_micro_mixed_value_payload_state_opcode/index.html"),
        ),
        (
            "Jumps noisy gaps .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_jump_token_probe/index.html"),
        ),
        (
            "Etat opcode payload jumps .tex",
            Path("output/tex_jump_token_payload_state_opcode/index.html"),
        ),
        (
            "Copies jumps noisy .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_jump_token_backref_probe/index.html"),
        ),
        (
            "Contexte jumps noisy .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_jump_token_context_probe/index.html"),
        ),
        (
            "Nibbles repetes noisy jumps .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_repeated_nibble_probe/index.html"),
        ),
        (
            "Contexte nibbles repetes .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_repeated_nibble_context_probe/index.html"),
        ),
        (
            "Jumps mixtes noisy gaps .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_jump_probe/index.html"),
        ),
        (
            "Contexte jumps mixtes .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_jump_context_probe/index.html"),
        ),
        (
            "Controle jumps mixtes .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_control_probe/index.html"),
        ),
        (
            "Jumps residuels noisy gaps .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_residual_jump_probe/index.html"),
        ),
        (
            "Controle jumps residuels .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_residual_control_probe/index.html"),
        ),
        (
            "Jumps denses noisy gaps .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_dense_jump_probe/index.html"),
        ),
        (
            "Controle jumps denses noisy .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_dense_control_probe/index.html"),
        ),
        (
            "Gate signaux controle noisy .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_control_signal_gate_probe/index.html"),
        ),
        (
            "Valeurs controle faibles .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_weak_control_value_probe/index.html"),
        ),
        (
            "Valeurs direction noisy .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_probe/index.html"),
        ),
        (
            "Offsets valeurs direction .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_offset_probe/index.html"),
        ),
        (
            "Contexte deltas direction .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_delta_context_probe/index.html"),
        ),
        (
            "Grammaire payload direction .tex",
            Path(
                "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_payload_grammar_probe/index.html"
            ),
        ),
        (
            "Profils source direction .tex",
            Path(
                "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_source_profile_probe/index.html"
            ),
        ),
        (
            "Valeurs source direction .tex",
            Path(
                "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_source_value_probe/index.html"
            ),
        ),
        (
            "Fenetre source direction .tex",
            Path(
                "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_source_window_probe/index.html"
            ),
        ),
        (
            "Contexte controle direction .tex",
            Path(
                "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_control_context_probe/index.html"
            ),
        ),
        (
            "Contexte valeurs exactes direction .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_exact_context_probe/index.html"),
        ),
        (
            "Contexte valeurs partielles direction .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_partial_context_probe/index.html"),
        ),
        (
            "Synthese noisy gaps nonzero .tex",
            Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_noisy_review/index.html"),
        ),
        ("Replay fixtures gaps .tex", DEFAULT_TEX_GAP_FIXTURE_REPLAY),
        ("RUN_HD.sh", DEFAULT_RUN_HD),
        ("Notes Full HD", DEFAULT_DOC),
        ("Mise au point projet", DEFAULT_PROJECT_STATUS),
    ]

    return {
        "auditSummary": audit_summary,
        "auditRows": audit_rows,
        "inventoryRows": inventory_rows,
        "cdcacheSummary": cdcache_summary,
        "cards": cards,
        "links": [
            {"label": label, "href": relative_href(path, base_dir), "exists": Path(path).exists()}
            for label, path in links
        ],
    }


def build_html(payload: dict[str, object], title: str) -> str:
    cards = payload["cards"]
    audit_rows = payload["auditRows"]
    inventory_rows = payload["inventoryRows"]
    links = payload["links"]
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    card_markup = "\n".join(render_card(card) for card in cards)  # type: ignore[arg-type]
    audit_markup = "\n".join(render_audit_row(row) for row in audit_rows)  # type: ignore[arg-type]
    inventory_markup = "\n".join(render_inventory_row(row) for row in inventory_rows)  # type: ignore[arg-type]
    links_markup = "\n".join(render_link(link) for link in links)  # type: ignore[arg-type]
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{
  color-scheme: dark;
  --bg: #101316;
  --panel: #171d22;
  --line: #2f3942;
  --text: #edf3f6;
  --muted: #9caab3;
  --accent: #74d3ae;
  --ok: #78d98f;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.wrap {{ width: min(1600px, calc(100vw - 28px)); margin: 0 auto; }}
header {{
  border-bottom: 1px solid var(--line);
  background: #12171b;
  padding: 20px 0 16px;
}}
h1 {{ margin: 0; font-size: 22px; font-weight: 700; letter-spacing: 0; }}
.sub {{ margin-top: 4px; color: var(--muted); }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.cards {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
  gap: 12px;
}}
.card {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  overflow: hidden;
  min-width: 0;
}}
.preview {{
  aspect-ratio: 16 / 9;
  background: #060708;
  display: grid;
  place-items: center;
  border-bottom: 1px solid var(--line);
}}
.preview img {{ width: 100%; height: 100%; object-fit: cover; }}
.preview .noimg {{ color: var(--muted); }}
.card-body {{ padding: 10px; display: grid; gap: 6px; }}
.card-title {{ font-weight: 700; }}
.metric {{ font-size: 26px; font-weight: 750; line-height: 1; }}
.label, .muted {{ color: var(--muted); }}
a {{ color: var(--accent); text-decoration: none; }}
.panel {{
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  padding: 12px;
  overflow-x: auto;
}}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
table {{ width: 100%; border-collapse: collapse; min-width: 720px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
.pass {{ color: var(--ok); font-weight: 700; }}
.links {{ display: flex; flex-wrap: wrap; gap: 8px; }}
.quick-link {{
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 7px 10px;
}}
@media (max-width: 640px) {{
  .metric {{ font-size: 22px; }}
}}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Point d'entree local pour les exports, galeries, manifests et preuves Full HD.</div>
  </div>
</header>
<main class="wrap">
  <section class="cards">{card_markup}</section>
  <section class="panel">
    <h2>Liens rapides</h2>
    <div class="links">{links_markup}</div>
  </section>
  <section class="panel">
    <h2>Audit</h2>
    <table>
      <thead><tr><th>Gate</th><th>Status</th><th>Actuel</th><th>Evidence</th></tr></thead>
      <tbody>{audit_markup}</tbody>
    </table>
  </section>
  <section class="panel">
    <h2>Inventaire</h2>
    <table>
      <thead><tr><th>Categorie</th><th>Records</th><th>Full HD</th><th>Transparent</th><th>Modes</th></tr></thead>
      <tbody>{inventory_markup}</tbody>
    </table>
  </section>
</main>
<script type="application/json" id="dashboard-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def render_card(card: dict[str, str]) -> str:
    image = html.escape(card.get("image", ""))
    preview = (
        f'<img src="{image}" loading="lazy" decoding="async" alt="">'
        if image
        else '<span class="noimg">CSV</span>'
    )
    return f"""
<article class="card">
  <a class="preview" href="{html.escape(card.get('href', ''))}">{preview}</a>
  <div class="card-body">
    <div class="card-title">{html.escape(card.get('title', ''))}</div>
    <div><span class="metric">{html.escape(card.get('stat', ''))}</span> <span class="label">{html.escape(card.get('label', ''))}</span></div>
    <div class="muted">{html.escape(card.get('description', ''))}</div>
    <a href="{html.escape(card.get('href', ''))}">Ouvrir</a>
  </div>
</article>"""


def render_audit_row(row: dict[str, str]) -> str:
    status = row.get("status", "")
    status_class = "pass" if status == "pass" else ""
    return (
        "<tr>"
        f"<td>{html.escape(row.get('gate', ''))}</td>"
        f"<td class=\"{status_class}\">{html.escape(status)}</td>"
        f"<td>{html.escape(row.get('actual', ''))}</td>"
        f"<td>{html.escape(row.get('evidence', ''))}</td>"
        "</tr>"
    )


def render_inventory_row(row: dict[str, str]) -> str:
    return (
        "<tr>"
        f"<td>{html.escape(row.get('category', ''))}</td>"
        f"<td>{html.escape(row.get('records', ''))}</td>"
        f"<td>{html.escape(row.get('fullhd_files', ''))}</td>"
        f"<td>{html.escape(row.get('transparent_files', ''))}</td>"
        f"<td>{html.escape(row.get('modes', ''))}</td>"
        "</tr>"
    )


def render_link(link: dict[str, object]) -> str:
    exists = "ok" if link.get("exists") else "missing"
    return (
        f"<a class=\"quick-link\" href=\"{html.escape(str(link.get('href', '')))}\">"
        f"{html.escape(str(link.get('label', '')))} <span class=\"muted\">{exists}</span></a>"
    )


def write_dashboard(output: Path, title: str) -> tuple[Path, dict[str, object]]:
    payload = dashboard_payload(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_html(payload, title))
    return output, payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a static Full HD dashboard.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II Full HD Dashboard")
    args = parser.parse_args()

    output, payload = write_dashboard(args.output, args.title)
    audit_summary = payload["auditSummary"]
    cards = payload["cards"]
    print(f"Dashboard cards: {len(cards)}")
    print(
        "Audit status: "
        f"{audit_summary.get('status', '')} "
        f"({audit_summary.get('passed', '')}/{audit_summary.get('gates', '')})"
    )
    print(f"HTML: {output}")


if __name__ == "__main__":
    main()
