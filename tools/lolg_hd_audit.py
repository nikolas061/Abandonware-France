#!/usr/bin/env python3
"""Audit the current Full HD export state from generated verification reports."""

from __future__ import annotations

import argparse
import csv
import html
import json
import os
import re
from collections import Counter
from pathlib import Path


TARGET_SIZE = (1920, 1080)

DEFAULT_OUTPUT = Path("output/fullhd_audit")
DEFAULT_STILL_MANIFEST = Path("output/fullhd_images/manifest.csv")
DEFAULT_STILL_VERIFICATION = Path("output/fullhd_images/verification.csv")
DEFAULT_STILL_GALLERY = Path("output/fullhd_images/index.html")
DEFAULT_STILL_GALLERY_MANIFEST = Path("output/fullhd_images/gallery_manifest.csv")
DEFAULT_VQA_MANIFEST = Path("output/vqa_batch_window_lcw_transparent0_allframes/manifest.csv")
DEFAULT_VQA_VERIFICATION = Path("output/vqa_batch_window_lcw_transparent0_allframes/verification.csv")
DEFAULT_VQA_GALLERY = Path("output/vqa_batch_window_lcw_transparent0_allframes/index.html")
DEFAULT_VQA_GALLERY_MANIFEST = Path(
    "output/vqa_batch_window_lcw_transparent0_allframes/gallery_manifest.csv"
)
DEFAULT_VQA_STATUS_SUMMARY = Path("output/vqa_batch_window_lcw_transparent0_allframes/status_summary.csv")
DEFAULT_VQA_STATUS_BY_ARCHIVE = Path(
    "output/vqa_batch_window_lcw_transparent0_allframes/status_by_archive.csv"
)
DEFAULT_VQA_STATUS_HTML = Path("output/vqa_batch_window_lcw_transparent0_allframes/status.html")
DEFAULT_INVENTORY_SUMMARY = Path("output/fullhd_inventory/summary.csv")
DEFAULT_ARCHIVE_COVERAGE_SUMMARY = Path("output/fullhd_archive_coverage/summary.csv")
DEFAULT_ARCHIVE_COVERAGE_ARCHIVES = Path("output/fullhd_archive_coverage/archives.csv")
DEFAULT_ARCHIVE_COVERAGE_HTML = Path("output/fullhd_archive_coverage/index.html")
DEFAULT_CDCACHE_DESCRIPTOR_MANIFEST = Path("output/cdcache_textures_all_tiled_tiles_rgba/manifest.csv")
DEFAULT_CDCACHE_DESCRIPTOR_VERIFICATION = Path("output/cdcache_textures_all_tiled_tiles_rgba/verification.csv")
DEFAULT_CDCACHE_TILE_MANIFEST = Path("output/cdcache_textures_all_tiled_tiles_rgba/tiles_manifest.csv")
DEFAULT_CDCACHE_TILE_VERIFICATION = Path("output/cdcache_textures_all_tiled_tiles_rgba/tiles_verification.csv")
DEFAULT_PACK_MANIFEST = Path("output/cdcache_hd_asset_pack/manifest.csv")
DEFAULT_PACK_VERIFICATION = Path("output/cdcache_hd_asset_pack/verification.csv")
DEFAULT_PACK_VERIFICATION_SUMMARY = Path("output/cdcache_hd_asset_pack/verification_summary.csv")
DEFAULT_PACK_GALLERY = Path("output/cdcache_hd_asset_pack/index.html")
DEFAULT_TEX_COVERAGE_SUMMARY = Path("output/tex_hd_coverage/summary.csv")
DEFAULT_TEX_COVERAGE_CACHE = Path("output/tex_hd_coverage/cache_assets.csv")
DEFAULT_TEX_COVERAGE_MATERIALS = Path("output/tex_hd_coverage/material_links.csv")
DEFAULT_TEX_COVERAGE_HTML = Path("output/tex_hd_coverage/index.html")
DEFAULT_TEX_REFERENCE_SUMMARY = Path("output/tex_reference_coverage/summary.csv")
DEFAULT_TEX_REFERENCE_REFERENCES = Path("output/tex_reference_coverage/references.csv")
DEFAULT_TEX_REFERENCE_MISSING = Path("output/tex_reference_coverage/missing_references.csv")
DEFAULT_TEX_REFERENCE_ARCHIVES = Path("output/tex_reference_coverage/by_archive.csv")
DEFAULT_TEX_REFERENCE_HTML = Path("output/tex_reference_coverage/index.html")
DEFAULT_TEX_MISSING_EVIDENCE_SUMMARY = Path("output/tex_missing_reference_evidence/summary.csv")
DEFAULT_TEX_MISSING_EVIDENCE_ROWS = Path("output/tex_missing_reference_evidence/evidence.csv")
DEFAULT_TEX_MISSING_EVIDENCE_UNIQUE = Path("output/tex_missing_reference_evidence/unique_missing.csv")
DEFAULT_TEX_MISSING_EVIDENCE_HTML = Path("output/tex_missing_reference_evidence/index.html")
DEFAULT_RAW_REFERENCE_PROBE_SUMMARY = Path("output/cdcache_raw_reference_probe/summary.csv")
DEFAULT_RAW_REFERENCE_PROBE_ROWS = Path("output/cdcache_raw_reference_probe/raw_reference_probe.csv")
DEFAULT_RAW_REFERENCE_PROBE_HTML = Path("output/cdcache_raw_reference_probe/index.html")
DEFAULT_ALIAS_CANDIDATE_SUMMARY = Path("output/cdcache_alias_candidates/summary.csv")
DEFAULT_ALIAS_CANDIDATE_ROWS = Path("output/cdcache_alias_candidates/alias_candidates.csv")
DEFAULT_ALIAS_SYNTHETIC_DESCRIPTORS = Path("output/cdcache_alias_candidates/synthetic_descriptors.csv")
DEFAULT_ALIAS_CANDIDATE_HTML = Path("output/cdcache_alias_candidates/index.html")
DEFAULT_ALIAS_TEXTURE_MANIFEST = Path("output/cdcache_alias_candidate_textures/manifest.csv")
DEFAULT_ALIAS_TEXTURE_VERIFICATION = Path("output/cdcache_alias_candidate_textures/verification.csv")
DEFAULT_ALIAS_TILE_MANIFEST = Path("output/cdcache_alias_candidate_textures/tiles_manifest.csv")
DEFAULT_ALIAS_TILE_VERIFICATION = Path("output/cdcache_alias_candidate_textures/tiles_verification.csv")
DEFAULT_ALIAS_PACK_SUMMARY = Path("output/cdcache_tex_alias_pack/summary.csv")
DEFAULT_ALIAS_PACK_MANIFEST = Path("output/cdcache_tex_alias_pack/manifest.csv")
DEFAULT_ALIAS_PACK_HTML = Path("output/cdcache_tex_alias_pack/index.html")
DEFAULT_TEX_MATERIAL_DECODE_PACK_SUMMARY = Path("output/tex_material_decode_pack/summary.csv")
DEFAULT_TEX_MATERIAL_DECODE_PACK_MANIFEST = Path("output/tex_material_decode_pack/manifest.csv")
DEFAULT_TEX_MATERIAL_DECODE_PACK_HTML = Path("output/tex_material_decode_pack/index.html")
DEFAULT_TEX_RAW_SAME_ARCHIVE_PROMOTED_PACK_SUMMARY = Path("output/tex_raw_same_archive_promoted_pack/summary.csv")
DEFAULT_TEX_RAW_SAME_ARCHIVE_PROMOTED_PACK_MANIFEST = Path("output/tex_raw_same_archive_promoted_pack/manifest.csv")
DEFAULT_TEX_RAW_SAME_ARCHIVE_PROMOTED_PACK_HTML = Path("output/tex_raw_same_archive_promoted_pack/index.html")
DEFAULT_TEX_AUGMENTED_SUMMARY = Path("output/tex_augmented_coverage/summary.csv")
DEFAULT_TEX_AUGMENTED_REFERENCES = Path("output/tex_augmented_coverage/references.csv")
DEFAULT_TEX_AUGMENTED_ALIASES = Path("output/tex_augmented_coverage/aliases.csv")
DEFAULT_TEX_AUGMENTED_MATERIAL_DECODES = Path("output/tex_augmented_coverage/material_decodes.csv")
DEFAULT_TEX_AUGMENTED_RAW_SAME_ARCHIVE = Path("output/tex_augmented_coverage/raw_same_archive_promotions.csv")
DEFAULT_TEX_AUGMENTED_HTML = Path("output/tex_augmented_coverage/index.html")
DEFAULT_TEX_UNRESOLVED_PROBE_SUMMARY = Path("output/tex_unresolved_material_probe_render/summary.csv")
DEFAULT_TEX_UNRESOLVED_PROBE_MANIFEST = Path(
    "output/tex_unresolved_material_probe_render/gallery_manifest.csv"
)
DEFAULT_TEX_UNRESOLVED_PROBE_HTML = Path("output/tex_unresolved_material_probe_render/index.html")
DEFAULT_TEX_PROBE_ANALYSIS_SUMMARY = Path(
    "output/tex_unresolved_material_probe_render/analysis_summary.csv"
)
DEFAULT_TEX_PROBE_ANALYSIS_ROWS = Path("output/tex_unresolved_material_probe_render/analysis.csv")
DEFAULT_TEX_PROBE_ANALYSIS_BEST = Path("output/tex_unresolved_material_probe_render/best_candidates.csv")
DEFAULT_TEX_PROBE_ANALYSIS_HTML = Path("output/tex_unresolved_material_probe_render/analysis.html")
DEFAULT_TEX_MATERIAL_DECODER_QUEUE_SUMMARY = Path("output/tex_material_decoder_queue/summary.csv")
DEFAULT_TEX_MATERIAL_DECODER_QUEUE_ROWS = Path("output/tex_material_decoder_queue/queue.csv")
DEFAULT_TEX_MATERIAL_DECODER_QUEUE_PREFIXES = Path("output/tex_material_decoder_queue/by_prefix.csv")
DEFAULT_TEX_MATERIAL_DECODER_QUEUE_HTML = Path("output/tex_material_decoder_queue/index.html")
DEFAULT_TEX_REMAINING_PROFILE_SUMMARY = Path("output/tex_remaining_reference_profile/summary.csv")
DEFAULT_TEX_REMAINING_PROFILE_ROWS = Path("output/tex_remaining_reference_profile/profile.csv")
DEFAULT_TEX_REMAINING_PROFILE_ARCHIVES = Path("output/tex_remaining_reference_profile/by_archive.csv")
DEFAULT_TEX_REMAINING_PROFILE_PREFIXES = Path("output/tex_remaining_reference_profile/by_prefix.csv")
DEFAULT_TEX_REMAINING_PROFILE_HTML = Path("output/tex_remaining_reference_profile/index.html")
DEFAULT_TEX_EXACT_CDCACHE_COMPARE_SUMMARY = Path("output/tex_exact_cdcache_compare/summary.csv")
DEFAULT_TEX_EXACT_CDCACHE_COMPARE_ROWS = Path("output/tex_exact_cdcache_compare/comparisons.csv")
DEFAULT_TEX_EXACT_CDCACHE_COMPARE_HTML = Path("output/tex_exact_cdcache_compare/index.html")
DEFAULT_TEX_EXACT_CHUNK_EVIDENCE_SUMMARY = Path("output/tex_exact_chunk_evidence/summary.csv")
DEFAULT_TEX_EXACT_CHUNK_EVIDENCE_ROWS = Path("output/tex_exact_chunk_evidence/matches.csv")
DEFAULT_TEX_EXACT_CHUNK_EVIDENCE_HTML = Path("output/tex_exact_chunk_evidence/index.html")
DEFAULT_TEX_EXACT_MATCH_OVERLAY_SUMMARY = Path("output/tex_exact_match_overlays/summary.csv")
DEFAULT_TEX_EXACT_MATCH_OVERLAY_ROWS = Path("output/tex_exact_match_overlays/overlays.csv")
DEFAULT_TEX_EXACT_MATCH_OVERLAY_HTML = Path("output/tex_exact_match_overlays/index.html")
DEFAULT_TEX_DECODER_SEED_SUMMARY = Path("output/tex_decoder_seed_report/summary.csv")
DEFAULT_TEX_DECODER_SEED_ROWS = Path("output/tex_decoder_seed_report/seeds.csv")
DEFAULT_TEX_DECODER_SEED_HTML = Path("output/tex_decoder_seed_report/index.html")
DEFAULT_TEX_EXACT_CHUNK_SCAN_SUMMARY = Path("output/tex_exact_chunk_scan/summary.csv")
DEFAULT_TEX_EXACT_CHUNK_SCAN_ROWS = Path("output/tex_exact_chunk_scan/scan.csv")
DEFAULT_TEX_EXACT_CHUNK_SCAN_HTML = Path("output/tex_exact_chunk_scan/index.html")
DEFAULT_TEX_EXACT_CHUNK_CLUSTER_SUMMARY = Path("output/tex_exact_chunk_clusters/summary.csv")
DEFAULT_TEX_EXACT_CHUNK_CLUSTER_ROWS = Path("output/tex_exact_chunk_clusters/clusters.csv")
DEFAULT_TEX_EXACT_CHUNK_CLUSTER_HTML = Path("output/tex_exact_chunk_clusters/index.html")
DEFAULT_TEX_EXACT_CLUSTER_OVERLAY_SUMMARY = Path("output/tex_exact_cluster_overlays/summary.csv")
DEFAULT_TEX_EXACT_CLUSTER_OVERLAY_ROWS = Path("output/tex_exact_cluster_overlays/overlays.csv")
DEFAULT_TEX_EXACT_CLUSTER_OVERLAY_HTML = Path("output/tex_exact_cluster_overlays/index.html")
DEFAULT_TEX_DECODER_RUN_CORPUS_SUMMARY = Path("output/tex_decoder_run_corpus/summary.csv")
DEFAULT_TEX_DECODER_RUN_CORPUS_ROWS = Path("output/tex_decoder_run_corpus/runs.csv")
DEFAULT_TEX_DECODER_RUN_CORPUS_HTML = Path("output/tex_decoder_run_corpus/index.html")
DEFAULT_TEX_PARTIAL_RAW_DECODER_SUMMARY = Path("output/tex_partial_raw_decoder/summary.csv")
DEFAULT_TEX_PARTIAL_RAW_DECODER_MANIFEST = Path("output/tex_partial_raw_decoder/manifest.csv")
DEFAULT_TEX_PARTIAL_RAW_DECODER_HTML = Path("output/tex_partial_raw_decoder/index.html")
DEFAULT_TEX_PARTIAL_RAW_COVERAGE_SUMMARY = Path("output/tex_partial_raw_coverage/summary.csv")
DEFAULT_TEX_PARTIAL_RAW_COVERAGE_ROWS = Path("output/tex_partial_raw_coverage/coverage.csv")
DEFAULT_TEX_PARTIAL_RAW_COVERAGE_GAPS = Path("output/tex_partial_raw_coverage/gaps.csv")
DEFAULT_TEX_PARTIAL_RAW_COVERAGE_HTML = Path("output/tex_partial_raw_coverage/index.html")
DEFAULT_TEX_GAP_FRONTIER_SUMMARY = Path("output/tex_gap_frontier_report/summary.csv")
DEFAULT_TEX_GAP_FRONTIER_ROWS = Path("output/tex_gap_frontier_report/frontiers.csv")
DEFAULT_TEX_GAP_FRONTIER_HTML = Path("output/tex_gap_frontier_report/index.html")
DEFAULT_TEX_GAP_OPCODE_PROBE_SUMMARY = Path("output/tex_gap_opcode_probe/summary.csv")
DEFAULT_TEX_GAP_OPCODE_PROBE_ROWS = Path("output/tex_gap_opcode_probe/probe.csv")
DEFAULT_TEX_GAP_OPCODE_PROBE_OPCODE_ROWS = Path("output/tex_gap_opcode_probe/opcode_stats.csv")
DEFAULT_TEX_GAP_OPCODE_PROBE_HTML = Path("output/tex_gap_opcode_probe/index.html")
DEFAULT_TEX_GAP_RLE_PROBE_SUMMARY = Path("output/tex_gap_rle_probe/summary.csv")
DEFAULT_TEX_GAP_RLE_PROBE_ROWS = Path("output/tex_gap_rle_probe/hypotheses.csv")
DEFAULT_TEX_GAP_RLE_PROBE_BEST = Path("output/tex_gap_rle_probe/best_by_frontier.csv")
DEFAULT_TEX_GAP_RLE_PROBE_HTML = Path("output/tex_gap_rle_probe/index.html")
DEFAULT_TEX_GAP_RULE_QUEUE_SUMMARY = Path("output/tex_gap_rule_queue/summary.csv")
DEFAULT_TEX_GAP_RULE_QUEUE_ROWS = Path("output/tex_gap_rule_queue/queue.csv")
DEFAULT_TEX_GAP_RULE_QUEUE_RULES = Path("output/tex_gap_rule_queue/by_rule.csv")
DEFAULT_TEX_GAP_RULE_QUEUE_HTML = Path("output/tex_gap_rule_queue/index.html")
DEFAULT_TEX_GAP_RULE_FIXTURE_SUMMARY = Path("output/tex_gap_rule_fixtures/summary.csv")
DEFAULT_TEX_GAP_RULE_FIXTURE_ROWS = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_TEX_GAP_RULE_FIXTURE_HTML = Path("output/tex_gap_rule_fixtures/index.html")
DEFAULT_TEX_GAP_ZERO_RUN_SUMMARY = Path("output/tex_gap_zero_run_probe/summary.csv")
DEFAULT_TEX_GAP_ZERO_RUN_FIXTURES = Path("output/tex_gap_zero_run_probe/fixtures.csv")
DEFAULT_TEX_GAP_ZERO_RUN_RUNS = Path("output/tex_gap_zero_run_probe/runs.csv")
DEFAULT_TEX_GAP_ZERO_RUN_HTML = Path("output/tex_gap_zero_run_probe/index.html")
DEFAULT_TEX_GAP_GEOMETRY_REPLAY_SUMMARY = Path("output/tex_gap_geometry_replay/summary.csv")
DEFAULT_TEX_GAP_GEOMETRY_REPLAY_ROWS = Path("output/tex_gap_geometry_replay/candidates.csv")
DEFAULT_TEX_GAP_GEOMETRY_REPLAY_BEST = Path("output/tex_gap_geometry_replay/best_by_fixture.csv")
DEFAULT_TEX_GAP_GEOMETRY_REPLAY_HTML = Path("output/tex_gap_geometry_replay/index.html")
DEFAULT_TEX_GAP_NONZERO_STREAM_SUMMARY = Path("output/tex_gap_nonzero_stream_probe/summary.csv")
DEFAULT_TEX_GAP_NONZERO_STREAM_ROWS = Path("output/tex_gap_nonzero_stream_probe/candidates.csv")
DEFAULT_TEX_GAP_NONZERO_STREAM_BEST = Path("output/tex_gap_nonzero_stream_probe/best_by_fixture.csv")
DEFAULT_TEX_GAP_NONZERO_STREAM_HTML = Path("output/tex_gap_nonzero_stream_probe/index.html")
DEFAULT_TEX_GAP_CONTROL_WORD_SUMMARY = Path("output/tex_gap_control_word_probe/summary.csv")
DEFAULT_TEX_GAP_CONTROL_WORD_FIXTURES = Path("output/tex_gap_control_word_probe/fixtures.csv")
DEFAULT_TEX_GAP_CONTROL_WORD_HITS = Path("output/tex_gap_control_word_probe/hits.csv")
DEFAULT_TEX_GAP_CONTROL_WORD_METRICS = Path("output/tex_gap_control_word_probe/by_metric.csv")
DEFAULT_TEX_GAP_CONTROL_WORD_HTML = Path("output/tex_gap_control_word_probe/index.html")
DEFAULT_TEX_GAP_HEADER_SCHEMA_SUMMARY = Path("output/tex_gap_header_schema_probe/summary.csv")
DEFAULT_TEX_GAP_HEADER_SCHEMA_FIXTURES = Path("output/tex_gap_header_schema_probe/fixtures.csv")
DEFAULT_TEX_GAP_HEADER_SCHEMA_BLOCKS = Path("output/tex_gap_header_schema_probe/blocks.csv")
DEFAULT_TEX_GAP_HEADER_SCHEMA_PAYLOADS = Path("output/tex_gap_header_schema_probe/payload_candidates.csv")
DEFAULT_TEX_GAP_HEADER_SCHEMA_BEST = Path("output/tex_gap_header_schema_probe/best_by_fixture.csv")
DEFAULT_TEX_GAP_HEADER_SCHEMA_HTML = Path("output/tex_gap_header_schema_probe/index.html")
DEFAULT_TEX_GAP_ROW_STRIDE_SUMMARY = Path("output/tex_gap_row_stride_probe/summary.csv")
DEFAULT_TEX_GAP_ROW_STRIDE_FIXTURES = Path("output/tex_gap_row_stride_probe/fixtures.csv")
DEFAULT_TEX_GAP_ROW_STRIDE_ROWS = Path("output/tex_gap_row_stride_probe/candidates.csv")
DEFAULT_TEX_GAP_ROW_STRIDE_BEST = Path("output/tex_gap_row_stride_probe/best_by_fixture.csv")
DEFAULT_TEX_GAP_ROW_STRIDE_HTML = Path("output/tex_gap_row_stride_probe/index.html")
DEFAULT_TEX_GAP_ROW_STRIDE_MISMATCH_SUMMARY = Path("output/tex_gap_row_stride_mismatch_probe/summary.csv")
DEFAULT_TEX_GAP_ROW_STRIDE_MISMATCH_CANDIDATES = Path("output/tex_gap_row_stride_mismatch_probe/candidates.csv")
DEFAULT_TEX_GAP_ROW_STRIDE_MISMATCH_ROWS = Path("output/tex_gap_row_stride_mismatch_probe/row_scores.csv")
DEFAULT_TEX_GAP_ROW_STRIDE_MISMATCH_HTML = Path("output/tex_gap_row_stride_mismatch_probe/index.html")
DEFAULT_TEX_GAP_ROW_DELTA_SUMMARY = Path("output/tex_gap_row_delta_probe/summary.csv")
DEFAULT_TEX_GAP_ROW_DELTA_CANDIDATES = Path("output/tex_gap_row_delta_probe/candidates.csv")
DEFAULT_TEX_GAP_ROW_DELTA_ROWS = Path("output/tex_gap_row_delta_probe/row_deltas.csv")
DEFAULT_TEX_GAP_ROW_DELTA_HTML = Path("output/tex_gap_row_delta_probe/index.html")
DEFAULT_TEX_GAP_ROW_TRANSFORM_SUMMARY = Path("output/tex_gap_row_transform_probe/summary.csv")
DEFAULT_TEX_GAP_ROW_TRANSFORM_CANDIDATES = Path("output/tex_gap_row_transform_probe/candidates.csv")
DEFAULT_TEX_GAP_ROW_TRANSFORM_ROWS = Path("output/tex_gap_row_transform_probe/row_transforms.csv")
DEFAULT_TEX_GAP_ROW_TRANSFORM_HTML = Path("output/tex_gap_row_transform_probe/index.html")
DEFAULT_TEX_GAP_ROW_CONTROL_SUMMARY = Path("output/tex_gap_row_control_probe/summary.csv")
DEFAULT_TEX_GAP_ROW_CONTROL_CANDIDATES = Path("output/tex_gap_row_control_probe/candidates.csv")
DEFAULT_TEX_GAP_ROW_CONTROL_ROWS = Path("output/tex_gap_row_control_probe/row_controls.csv")
DEFAULT_TEX_GAP_ROW_CONTROL_GROUPS = Path("output/tex_gap_row_control_probe/by_control.csv")
DEFAULT_TEX_GAP_ROW_CONTROL_METRICS = Path("output/tex_gap_row_control_probe/by_metric.csv")
DEFAULT_TEX_GAP_ROW_CONTROL_HTML = Path("output/tex_gap_row_control_probe/index.html")
DEFAULT_TEX_GAP_ROW_SEQUENCE_SUMMARY = Path("output/tex_gap_row_sequence_probe/summary.csv")
DEFAULT_TEX_GAP_ROW_SEQUENCE_CANDIDATES = Path("output/tex_gap_row_sequence_probe/candidates.csv")
DEFAULT_TEX_GAP_ROW_SEQUENCE_ROWS = Path("output/tex_gap_row_sequence_probe/transitions.csv")
DEFAULT_TEX_GAP_ROW_SEQUENCE_STEPS = Path("output/tex_gap_row_sequence_probe/by_step.csv")
DEFAULT_TEX_GAP_ROW_SEQUENCE_HTML = Path("output/tex_gap_row_sequence_probe/index.html")
DEFAULT_TEX_GAP_ROW_LITERAL_SCAN_SUMMARY = Path("output/tex_gap_row_literal_scan_probe/summary.csv")
DEFAULT_TEX_GAP_ROW_LITERAL_SCAN_CANDIDATES = Path("output/tex_gap_row_literal_scan_probe/candidates.csv")
DEFAULT_TEX_GAP_ROW_LITERAL_SCAN_ROWS = Path("output/tex_gap_row_literal_scan_probe/row_scans.csv")
DEFAULT_TEX_GAP_ROW_LITERAL_SCAN_HTML = Path("output/tex_gap_row_literal_scan_probe/index.html")
DEFAULT_TEX_GAP_ROW_FILL_RUN_SUMMARY = Path("output/tex_gap_row_fill_run_probe/summary.csv")
DEFAULT_TEX_GAP_ROW_FILL_RUN_CANDIDATES = Path("output/tex_gap_row_fill_run_probe/candidates.csv")
DEFAULT_TEX_GAP_ROW_FILL_RUN_ROWS = Path("output/tex_gap_row_fill_run_probe/row_fills.csv")
DEFAULT_TEX_GAP_ROW_FILL_RUN_MATCHES = Path("output/tex_gap_row_fill_run_probe/run_matches.csv")
DEFAULT_TEX_GAP_ROW_FILL_RUN_HTML = Path("output/tex_gap_row_fill_run_probe/index.html")
DEFAULT_TEX_GAP_CONTROL_GRAMMAR_SUMMARY = Path("output/tex_gap_control_grammar_probe/summary.csv")
DEFAULT_TEX_GAP_CONTROL_GRAMMAR_CANDIDATES = Path("output/tex_gap_control_grammar_probe/candidates.csv")
DEFAULT_TEX_GAP_CONTROL_GRAMMAR_BEST = Path("output/tex_gap_control_grammar_probe/best_by_fixture.csv")
DEFAULT_TEX_GAP_CONTROL_GRAMMAR_HTML = Path("output/tex_gap_control_grammar_probe/index.html")
DEFAULT_TEX_GAP_MISMATCH_TRACE_SUMMARY = Path("output/tex_gap_mismatch_trace_probe/summary.csv")
DEFAULT_TEX_GAP_MISMATCH_TRACE_ROWS = Path("output/tex_gap_mismatch_trace_probe/mismatches.csv")
DEFAULT_TEX_GAP_MISMATCH_TRACE_OPS = Path("output/tex_gap_mismatch_trace_probe/control_operations.csv")
DEFAULT_TEX_GAP_MISMATCH_TRACE_HTML = Path("output/tex_gap_mismatch_trace_probe/index.html")
DEFAULT_TEX_GAP_ZERO_LITERAL_SWITCH_SUMMARY = Path("output/tex_gap_zero_literal_switch_probe/summary.csv")
DEFAULT_TEX_GAP_ZERO_LITERAL_SWITCH_CANDIDATES = Path("output/tex_gap_zero_literal_switch_probe/candidates.csv")
DEFAULT_TEX_GAP_ZERO_LITERAL_SWITCH_BEST = Path("output/tex_gap_zero_literal_switch_probe/best_by_fixture.csv")
DEFAULT_TEX_GAP_ZERO_LITERAL_SWITCH_HTML = Path("output/tex_gap_zero_literal_switch_probe/index.html")
DEFAULT_TEX_GAP_ZERO_LITERAL_SEGMENTATION_SUMMARY = Path("output/tex_gap_zero_literal_segmentation_probe/summary.csv")
DEFAULT_TEX_GAP_ZERO_LITERAL_SEGMENTATION_STRATEGIES = Path("output/tex_gap_zero_literal_segmentation_probe/strategies.csv")
DEFAULT_TEX_GAP_ZERO_LITERAL_SEGMENTATION_OPS = Path("output/tex_gap_zero_literal_segmentation_probe/operations.csv")
DEFAULT_TEX_GAP_ZERO_LITERAL_SEGMENTATION_BEST = Path("output/tex_gap_zero_literal_segmentation_probe/best_by_fixture.csv")
DEFAULT_TEX_GAP_ZERO_LITERAL_SEGMENTATION_HTML = Path("output/tex_gap_zero_literal_segmentation_probe/index.html")
DEFAULT_TEX_GAP_SEGMENTATION_CONTROL_CORRELATION_SUMMARY = Path(
    "output/tex_gap_segmentation_control_correlation_probe/summary.csv"
)
DEFAULT_TEX_GAP_SEGMENTATION_CONTROL_CORRELATION_OPS = Path(
    "output/tex_gap_segmentation_control_correlation_probe/operations.csv"
)
DEFAULT_TEX_GAP_SEGMENTATION_CONTROL_CORRELATION_CONTEXTS = Path(
    "output/tex_gap_segmentation_control_correlation_probe/by_pre_context.csv"
)
DEFAULT_TEX_GAP_SEGMENTATION_CONTROL_CORRELATION_DELTAS = Path(
    "output/tex_gap_segmentation_control_correlation_probe/by_source_delta.csv"
)
DEFAULT_TEX_GAP_SEGMENTATION_CONTROL_CORRELATION_HTML = Path(
    "output/tex_gap_segmentation_control_correlation_probe/index.html"
)
DEFAULT_TEX_GAP_LITERAL_TOKEN_SUMMARY = Path("output/tex_gap_literal_token_probe/summary.csv")
DEFAULT_TEX_GAP_LITERAL_TOKEN_RULES = Path("output/tex_gap_literal_token_probe/rules.csv")
DEFAULT_TEX_GAP_LITERAL_TOKEN_LITERALS = Path("output/tex_gap_literal_token_probe/literals.csv")
DEFAULT_TEX_GAP_LITERAL_TOKEN_TOKENS = Path("output/tex_gap_literal_token_probe/by_token.csv")
DEFAULT_TEX_GAP_LITERAL_TOKEN_FIXTURES = Path("output/tex_gap_literal_token_probe/by_fixture.csv")
DEFAULT_TEX_GAP_LITERAL_TOKEN_HTML = Path("output/tex_gap_literal_token_probe/index.html")
DEFAULT_TEX_GAP_LITERAL_TOKEN_CLASSIFIER_SUMMARY = Path(
    "output/tex_gap_literal_token_classifier_probe/summary.csv"
)
DEFAULT_TEX_GAP_LITERAL_TOKEN_CLASSIFIER_ROWS = Path(
    "output/tex_gap_literal_token_classifier_probe/classifiers.csv"
)
DEFAULT_TEX_GAP_LITERAL_TOKEN_CLASSIFIER_ERRORS = Path(
    "output/tex_gap_literal_token_classifier_probe/classifier_errors.csv"
)
DEFAULT_TEX_GAP_LITERAL_TOKEN_CLASSIFIER_FIXTURES = Path(
    "output/tex_gap_literal_token_classifier_probe/by_fixture.csv"
)
DEFAULT_TEX_GAP_LITERAL_TOKEN_CLASSIFIER_HTML = Path(
    "output/tex_gap_literal_token_classifier_probe/index.html"
)
DEFAULT_TEX_GAP_LITERAL_FP_REJECTION_SUMMARY = Path(
    "output/tex_gap_literal_fp_rejection_probe/summary.csv"
)
DEFAULT_TEX_GAP_LITERAL_FP_REJECTION_ROWS = Path(
    "output/tex_gap_literal_fp_rejection_probe/classifiers.csv"
)
DEFAULT_TEX_GAP_LITERAL_FP_REJECTION_REJECTIONS = Path(
    "output/tex_gap_literal_fp_rejection_probe/rejections.csv"
)
DEFAULT_TEX_GAP_LITERAL_FP_REJECTION_FIXTURES = Path(
    "output/tex_gap_literal_fp_rejection_probe/by_fixture.csv"
)
DEFAULT_TEX_GAP_LITERAL_FP_REJECTION_HTML = Path(
    "output/tex_gap_literal_fp_rejection_probe/index.html"
)
DEFAULT_TEX_GAP_ZERO_RUN_ALIGNMENT_SUMMARY = Path("output/tex_gap_zero_run_alignment_probe/summary.csv")
DEFAULT_TEX_GAP_ZERO_RUN_ALIGNMENT_ZERO_ROWS = Path("output/tex_gap_zero_run_alignment_probe/zero_runs.csv")
DEFAULT_TEX_GAP_ZERO_RUN_ALIGNMENT_LENGTHS = Path("output/tex_gap_zero_run_alignment_probe/by_length.csv")
DEFAULT_TEX_GAP_ZERO_RUN_ALIGNMENT_TRANSITIONS = Path("output/tex_gap_zero_run_alignment_probe/by_transition.csv")
DEFAULT_TEX_GAP_ZERO_RUN_ALIGNMENT_FIXTURES = Path("output/tex_gap_zero_run_alignment_probe/by_fixture.csv")
DEFAULT_TEX_GAP_ZERO_RUN_ALIGNMENT_HTML = Path("output/tex_gap_zero_run_alignment_probe/index.html")
DEFAULT_TEX_GAP_ZERO_CONTROL_RISK_SUMMARY = Path("output/tex_gap_zero_control_risk_probe/summary.csv")
DEFAULT_TEX_GAP_ZERO_CONTROL_RISK_ROWS = Path("output/tex_gap_zero_control_risk_probe/classifiers.csv")
DEFAULT_TEX_GAP_ZERO_CONTROL_RISK_FALSE_POSITIVES = Path(
    "output/tex_gap_zero_control_risk_probe/false_positives.csv"
)
DEFAULT_TEX_GAP_ZERO_CONTROL_RISK_KINDS = Path("output/tex_gap_zero_control_risk_probe/by_kind.csv")
DEFAULT_TEX_GAP_ZERO_CONTROL_RISK_FIXTURES = Path("output/tex_gap_zero_control_risk_probe/by_fixture.csv")
DEFAULT_TEX_GAP_ZERO_CONTROL_RISK_HTML = Path("output/tex_gap_zero_control_risk_probe/index.html")
DEFAULT_TEX_GAP_DECODER_SKELETON_CANDIDATE_SUMMARY = Path(
    "output/tex_gap_decoder_skeleton_candidate_probe/summary.csv"
)
DEFAULT_TEX_GAP_DECODER_SKELETON_CANDIDATE_ROWS = Path(
    "output/tex_gap_decoder_skeleton_candidate_probe/candidates.csv"
)
DEFAULT_TEX_GAP_DECODER_SKELETON_CANDIDATE_FIXTURES = Path(
    "output/tex_gap_decoder_skeleton_candidate_probe/by_fixture.csv"
)
DEFAULT_TEX_GAP_DECODER_SKELETON_CANDIDATE_HTML = Path(
    "output/tex_gap_decoder_skeleton_candidate_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_RISK_ADJUSTED_SUMMARY = Path(
    "output/tex_gap_decoder_risk_adjusted_probe/summary.csv"
)
DEFAULT_TEX_GAP_DECODER_RISK_ADJUSTED_ROWS = Path(
    "output/tex_gap_decoder_risk_adjusted_probe/candidates.csv"
)
DEFAULT_TEX_GAP_DECODER_RISK_ADJUSTED_FIXTURES = Path(
    "output/tex_gap_decoder_risk_adjusted_probe/by_fixture.csv"
)
DEFAULT_TEX_GAP_DECODER_RISK_ADJUSTED_HTML = Path(
    "output/tex_gap_decoder_risk_adjusted_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_SEED_REPLAY_SUMMARY = Path("output/tex_gap_decoder_seed_replay/summary.csv")
DEFAULT_TEX_GAP_DECODER_SEED_REPLAY_FIXTURES = Path("output/tex_gap_decoder_seed_replay/fixtures.csv")
DEFAULT_TEX_GAP_DECODER_SEED_REPLAY_DECISIONS = Path("output/tex_gap_decoder_seed_replay/decisions.csv")
DEFAULT_TEX_GAP_DECODER_SEED_REPLAY_HTML = Path("output/tex_gap_decoder_seed_replay/index.html")
DEFAULT_TEX_GAP_DECODER_CONTROL_PROMOTION_SUMMARY = Path(
    "output/tex_gap_decoder_control_promotion_probe/summary.csv"
)
DEFAULT_TEX_GAP_DECODER_CONTROL_PROMOTION_SELECTORS = Path(
    "output/tex_gap_decoder_control_promotion_probe/selectors.csv"
)
DEFAULT_TEX_GAP_DECODER_CONTROL_PROMOTION_SIGNATURES = Path(
    "output/tex_gap_decoder_control_promotion_probe/signatures.csv"
)
DEFAULT_TEX_GAP_DECODER_CONTROL_PROMOTION_FIXTURES = Path(
    "output/tex_gap_decoder_control_promotion_probe/by_fixture.csv"
)
DEFAULT_TEX_GAP_DECODER_CONTROL_PROMOTION_HTML = Path(
    "output/tex_gap_decoder_control_promotion_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_FALSE_RISK_QUEUE_SUMMARY = Path(
    "output/tex_gap_decoder_false_risk_queue/summary.csv"
)
DEFAULT_TEX_GAP_DECODER_FALSE_RISK_QUEUE_ROWS = Path(
    "output/tex_gap_decoder_false_risk_queue/queue.csv"
)
DEFAULT_TEX_GAP_DECODER_FALSE_RISK_QUEUE_REJECTORS = Path(
    "output/tex_gap_decoder_false_risk_queue/rejectors.csv"
)
DEFAULT_TEX_GAP_DECODER_FALSE_RISK_QUEUE_FIXTURES = Path(
    "output/tex_gap_decoder_false_risk_queue/by_fixture.csv"
)
DEFAULT_TEX_GAP_DECODER_FALSE_RISK_QUEUE_HTML = Path(
    "output/tex_gap_decoder_false_risk_queue/index.html"
)
DEFAULT_TEX_GAP_DECODER_CLEAN_REPLAY_SUMMARY = Path(
    "output/tex_gap_decoder_clean_replay/summary.csv"
)
DEFAULT_TEX_GAP_DECODER_CLEAN_REPLAY_FIXTURES = Path(
    "output/tex_gap_decoder_clean_replay/fixtures.csv"
)
DEFAULT_TEX_GAP_DECODER_CLEAN_REPLAY_DECISIONS = Path(
    "output/tex_gap_decoder_clean_replay/decisions.csv"
)
DEFAULT_TEX_GAP_DECODER_CLEAN_REPLAY_HTML = Path(
    "output/tex_gap_decoder_clean_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_CLEAN_GAP_QUEUE_SUMMARY = Path(
    "output/tex_gap_decoder_clean_gap_queue/summary.csv"
)
DEFAULT_TEX_GAP_DECODER_CLEAN_GAP_QUEUE_SPANS = Path(
    "output/tex_gap_decoder_clean_gap_queue/spans.csv"
)
DEFAULT_TEX_GAP_DECODER_CLEAN_GAP_QUEUE_FIXTURES = Path(
    "output/tex_gap_decoder_clean_gap_queue/by_fixture.csv"
)
DEFAULT_TEX_GAP_DECODER_CLEAN_GAP_QUEUE_HTML = Path(
    "output/tex_gap_decoder_clean_gap_queue/index.html"
)
DEFAULT_TEX_GAP_DECODER_UNRESOLVED_RUN_SUMMARY = Path(
    "output/tex_gap_decoder_unresolved_run_probe/summary.csv"
)
DEFAULT_TEX_GAP_DECODER_UNRESOLVED_RUN_SPANS = Path(
    "output/tex_gap_decoder_unresolved_run_probe/by_span.csv"
)
DEFAULT_TEX_GAP_DECODER_UNRESOLVED_RUN_RUNS = Path(
    "output/tex_gap_decoder_unresolved_run_probe/runs.csv"
)
DEFAULT_TEX_GAP_DECODER_UNRESOLVED_RUN_FIXTURES = Path(
    "output/tex_gap_decoder_unresolved_run_probe/by_fixture.csv"
)
DEFAULT_TEX_GAP_DECODER_UNRESOLVED_RUN_HTML = Path(
    "output/tex_gap_decoder_unresolved_run_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_UNRESOLVED_ZERO_QUEUE_SUMMARY = Path(
    "output/tex_gap_decoder_unresolved_zero_queue/summary.csv"
)
DEFAULT_TEX_GAP_DECODER_UNRESOLVED_ZERO_QUEUE_ROWS = Path(
    "output/tex_gap_decoder_unresolved_zero_queue/queue.csv"
)
DEFAULT_TEX_GAP_DECODER_UNRESOLVED_ZERO_QUEUE_SIGNATURES = Path(
    "output/tex_gap_decoder_unresolved_zero_queue/by_signature.csv"
)
DEFAULT_TEX_GAP_DECODER_UNRESOLVED_ZERO_QUEUE_FIXTURES = Path(
    "output/tex_gap_decoder_unresolved_zero_queue/by_fixture.csv"
)
DEFAULT_TEX_GAP_DECODER_UNRESOLVED_ZERO_QUEUE_HTML = Path(
    "output/tex_gap_decoder_unresolved_zero_queue/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_INTERNAL_SUMMARY = Path(
    "output/tex_gap_decoder_len64_internal_probe/summary.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_INTERNAL_TARGETS = Path(
    "output/tex_gap_decoder_len64_internal_probe/targets.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_INTERNAL_NEIGHBORS = Path(
    "output/tex_gap_decoder_len64_internal_probe/by_neighbor_signature.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_INTERNAL_FIXTURES = Path(
    "output/tex_gap_decoder_len64_internal_probe/by_fixture.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_INTERNAL_HTML = Path(
    "output/tex_gap_decoder_len64_internal_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_SOURCE_SUMMARY = Path(
    "output/tex_gap_decoder_len64_source_probe/summary.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_SOURCE_TARGETS = Path(
    "output/tex_gap_decoder_len64_source_probe/targets.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_SOURCE_CONTROLS = Path(
    "output/tex_gap_decoder_len64_source_probe/by_control_window.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_SOURCE_REFS = Path(
    "output/tex_gap_decoder_len64_source_probe/by_control_ref.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_SOURCE_HTML = Path(
    "output/tex_gap_decoder_len64_source_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_SELECTOR_SUMMARY = Path(
    "output/tex_gap_decoder_len64_selector_probe/summary.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_SELECTOR_CANDIDATES = Path(
    "output/tex_gap_decoder_len64_selector_probe/candidates.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_SELECTOR_GREEDY = Path(
    "output/tex_gap_decoder_len64_selector_probe/greedy.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_SELECTOR_TARGETS = Path(
    "output/tex_gap_decoder_len64_selector_probe/targets.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_SELECTOR_HTML = Path(
    "output/tex_gap_decoder_len64_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_replay/summary.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_FIXTURES = Path(
    "output/tex_gap_decoder_len64_promoted_replay/fixtures.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_PROMOTIONS = Path(
    "output/tex_gap_decoder_len64_promoted_replay/promotions.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_HTML = Path(
    "output/tex_gap_decoder_len64_promoted_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_GAP_QUEUE_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_gap_queue/summary.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_GAP_QUEUE_SPANS = Path(
    "output/tex_gap_decoder_len64_promoted_gap_queue/spans.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_GAP_QUEUE_FIXTURES = Path(
    "output/tex_gap_decoder_len64_promoted_gap_queue/by_fixture.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_GAP_QUEUE_HTML = Path(
    "output/tex_gap_decoder_len64_promoted_gap_queue/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_RUN_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_run_probe/summary.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_RUN_SPANS = Path(
    "output/tex_gap_decoder_len64_promoted_run_probe/by_span.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_RUN_RUNS = Path(
    "output/tex_gap_decoder_len64_promoted_run_probe/runs.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_RUN_FIXTURES = Path(
    "output/tex_gap_decoder_len64_promoted_run_probe/by_fixture.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_RUN_HTML = Path(
    "output/tex_gap_decoder_len64_promoted_run_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_ZERO_QUEUE_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_zero_queue/summary.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_ZERO_QUEUE_ROWS = Path(
    "output/tex_gap_decoder_len64_promoted_zero_queue/queue.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_ZERO_QUEUE_SIGNATURES = Path(
    "output/tex_gap_decoder_len64_promoted_zero_queue/by_signature.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_ZERO_QUEUE_FIXTURES = Path(
    "output/tex_gap_decoder_len64_promoted_zero_queue/by_fixture.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_ZERO_QUEUE_HTML = Path(
    "output/tex_gap_decoder_len64_promoted_zero_queue/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_ZERO_SOURCE_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_zero_source_probe/summary.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_ZERO_SOURCE_TARGETS = Path(
    "output/tex_gap_decoder_len64_promoted_zero_source_probe/targets.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_ZERO_SOURCE_CONTROLS = Path(
    "output/tex_gap_decoder_len64_promoted_zero_source_probe/by_control_window.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_ZERO_SOURCE_REFS = Path(
    "output/tex_gap_decoder_len64_promoted_zero_source_probe/by_control_ref.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_ZERO_SOURCE_HTML = Path(
    "output/tex_gap_decoder_len64_promoted_zero_source_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_SELECTOR_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_large32_selector_probe/summary.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_SELECTOR_CANDIDATES = Path(
    "output/tex_gap_decoder_len64_promoted_large32_selector_probe/candidates.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_SELECTOR_GREEDY = Path(
    "output/tex_gap_decoder_len64_promoted_large32_selector_probe/greedy.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_SELECTOR_TARGETS = Path(
    "output/tex_gap_decoder_len64_promoted_large32_selector_probe/targets.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_SELECTOR_HTML = Path(
    "output/tex_gap_decoder_len64_promoted_large32_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_REPLAY_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_large32_replay/summary.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_REPLAY_FIXTURES = Path(
    "output/tex_gap_decoder_len64_promoted_large32_replay/fixtures.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_REPLAY_PROMOTIONS = Path(
    "output/tex_gap_decoder_len64_promoted_large32_replay/promotions.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_REPLAY_HTML = Path(
    "output/tex_gap_decoder_len64_promoted_large32_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_GAP_QUEUE_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_large32_gap_queue/summary.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_GAP_QUEUE_SPANS = Path(
    "output/tex_gap_decoder_len64_promoted_large32_gap_queue/spans.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_GAP_QUEUE_FIXTURES = Path(
    "output/tex_gap_decoder_len64_promoted_large32_gap_queue/by_fixture.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_GAP_QUEUE_HTML = Path(
    "output/tex_gap_decoder_len64_promoted_large32_gap_queue/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_RUN_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_large32_run_probe/summary.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_RUN_SPANS = Path(
    "output/tex_gap_decoder_len64_promoted_large32_run_probe/by_span.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_RUN_RUNS = Path(
    "output/tex_gap_decoder_len64_promoted_large32_run_probe/runs.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_RUN_FIXTURES = Path(
    "output/tex_gap_decoder_len64_promoted_large32_run_probe/by_fixture.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_RUN_HTML = Path(
    "output/tex_gap_decoder_len64_promoted_large32_run_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_ZERO_QUEUE_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_large32_zero_queue/summary.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_ZERO_QUEUE_ROWS = Path(
    "output/tex_gap_decoder_len64_promoted_large32_zero_queue/queue.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_ZERO_QUEUE_SIGNATURES = Path(
    "output/tex_gap_decoder_len64_promoted_large32_zero_queue/by_signature.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_ZERO_QUEUE_FIXTURES = Path(
    "output/tex_gap_decoder_len64_promoted_large32_zero_queue/by_fixture.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_ZERO_QUEUE_HTML = Path(
    "output/tex_gap_decoder_len64_promoted_large32_zero_queue/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_ZERO_SOURCE_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_large32_zero_source_probe/summary.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_ZERO_SOURCE_TARGETS = Path(
    "output/tex_gap_decoder_len64_promoted_large32_zero_source_probe/targets.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_ZERO_SOURCE_CONTROLS = Path(
    "output/tex_gap_decoder_len64_promoted_large32_zero_source_probe/by_control_window.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_ZERO_SOURCE_REFS = Path(
    "output/tex_gap_decoder_len64_promoted_large32_zero_source_probe/by_control_ref.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_ZERO_SOURCE_HTML = Path(
    "output/tex_gap_decoder_len64_promoted_large32_zero_source_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_SELECTOR_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_selector_probe/summary.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_SELECTOR_CANDIDATES = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_selector_probe/candidates.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_SELECTOR_GREEDY = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_selector_probe/greedy.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_SELECTOR_TARGETS = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_selector_probe/targets.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_SELECTOR_HTML = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_REPLAY_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_replay/summary.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_REPLAY_FIXTURES = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_replay/fixtures.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_REPLAY_PROMOTIONS = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_replay/promotions.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_REPLAY_HTML = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_replay/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_GAP_QUEUE_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_gap_queue/summary.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_GAP_QUEUE_SPANS = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_gap_queue/spans.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_GAP_QUEUE_FIXTURES = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_gap_queue/by_fixture.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_GAP_QUEUE_HTML = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_gap_queue/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_RUN_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_run_probe/summary.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_RUN_SPANS = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_run_probe/by_span.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_RUN_RUNS = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_run_probe/runs.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_RUN_FIXTURES = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_run_probe/by_fixture.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_RUN_HTML = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_run_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_ZERO_QUEUE_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_zero_queue/summary.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_ZERO_QUEUE_ROWS = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_zero_queue/queue.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_ZERO_QUEUE_SIGNATURES = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_zero_queue/by_signature.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_ZERO_QUEUE_FIXTURES = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_zero_queue/by_fixture.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_ZERO_QUEUE_HTML = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_zero_queue/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_ZERO_SOURCE_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_zero_source_probe/summary.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_ZERO_SOURCE_TARGETS = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_zero_source_probe/targets.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_ZERO_SOURCE_CONTROLS = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_zero_source_probe/by_control_window.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_ZERO_SOURCE_REFS = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_zero_source_probe/by_control_ref.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_ZERO_SOURCE_HTML = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_zero_source_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_REMAINING_SELECTOR_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_remaining_selector_probe/summary.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_REMAINING_SELECTOR_CANDIDATES = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_remaining_selector_probe/candidates.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_REMAINING_SELECTOR_GREEDY = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_remaining_selector_probe/greedy.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_REMAINING_SELECTOR_TARGETS = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_remaining_selector_probe/targets.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_REMAINING_SELECTOR_HTML = Path(
    "output/tex_gap_decoder_len64_promoted_medium8_remaining_selector_probe/index.html"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_REMAINING_SELECTOR_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_large32_remaining_selector_probe/summary.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_REMAINING_SELECTOR_CANDIDATES = Path(
    "output/tex_gap_decoder_len64_promoted_large32_remaining_selector_probe/candidates.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_REMAINING_SELECTOR_GREEDY = Path(
    "output/tex_gap_decoder_len64_promoted_large32_remaining_selector_probe/greedy.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_REMAINING_SELECTOR_TARGETS = Path(
    "output/tex_gap_decoder_len64_promoted_large32_remaining_selector_probe/targets.csv"
)
DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_REMAINING_SELECTOR_HTML = Path(
    "output/tex_gap_decoder_len64_promoted_large32_remaining_selector_probe/index.html"
)
DEFAULT_TEX_GAP_FIXTURE_REPLAY_SUMMARY = Path("output/tex_gap_fixture_replay/summary.csv")
DEFAULT_TEX_GAP_FIXTURE_REPLAY_ROWS = Path("output/tex_gap_fixture_replay/replay.csv")
DEFAULT_TEX_GAP_FIXTURE_REPLAY_BEST = Path("output/tex_gap_fixture_replay/best_by_fixture.csv")
DEFAULT_TEX_GAP_FIXTURE_REPLAY_HTML = Path("output/tex_gap_fixture_replay/index.html")
DEFAULT_TEX_MATERIAL_LINKS = Path("output/texture_report/cdcache_material_texture_links.csv")
DEFAULT_DASHBOARD = Path("output/fullhd_dashboard/index.html")
DEFAULT_RUN_HD = Path("RUN_HD.sh")
DEFAULT_DOSBOX_CONF = Path("lol2dos.conf")

AUDIT_FIELDNAMES = [
    "gate",
    "status",
    "expected",
    "actual",
    "evidence",
    "issues",
]

SUMMARY_FIELDNAMES = [
    "status",
    "gates",
    "passed",
    "failed",
    "total_fullhd_pngs",
    "vqa_fullhd_frames",
    "vqa_gallery_entries",
    "vqa_status_archives",
    "archive_coverage_visual_entries",
    "still_fullhd_images",
    "still_gallery_entries",
    "cdcache_fullhd_outputs",
    "cdcache_pack_assets",
    "cdcache_pack_linked_assets",
    "tex_hd_linked_assets",
    "tex_hd_material_links",
    "tex_reference_unique_pcx",
    "tex_reference_covered_unique_pcx",
    "tex_reference_missing_unique_pcx",
    "tex_missing_reference_raw_unique_pcx",
    "tex_missing_reference_material_unique_pcx",
    "cdcache_raw_probe_candidate_rows",
    "cdcache_alias_candidate_assets",
    "cdcache_alias_synthetic_descriptors",
    "cdcache_alias_fullhd_outputs",
    "cdcache_tex_alias_pack_assets",
    "tex_material_decode_pack_assets",
    "tex_raw_same_archive_promoted_pack_eligible",
    "tex_augmented_exact_or_alias_unique_pcx",
    "tex_augmented_exact_alias_or_decoded_unique_pcx",
    "tex_augmented_exact_alias_decoded_or_raw_unique_pcx",
    "tex_augmented_unresolved_unique_pcx",
    "tex_unresolved_material_probe_fullhd_previews",
    "tex_unresolved_material_probe_unique_pcx",
    "tex_probe_analysis_best_candidates",
    "tex_probe_analysis_segments",
    "tex_material_decoder_queue_rows",
    "tex_material_decoder_queue_segments",
    "tex_remaining_reference_profile_unique",
    "tex_exact_cdcache_compare_segments",
    "tex_exact_cdcache_compare_32b_matches",
    "tex_exact_cdcache_compare_16b_matches",
    "tex_exact_chunk_evidence_matches",
    "tex_exact_chunk_evidence_matched_segments",
    "tex_exact_match_overlays_fullhd",
    "tex_exact_match_overlays_pixels",
    "tex_decoder_seed_strong",
    "tex_decoder_seed_medium",
    "tex_exact_chunk_scan_rows",
    "tex_exact_chunk_scan_capped_groups",
    "tex_exact_chunk_clusters",
    "tex_exact_chunk_cluster_strong",
    "tex_exact_chunk_cluster_longest_span",
    "tex_exact_cluster_overlays_fullhd",
    "tex_exact_cluster_overlays_pixels",
    "tex_decoder_run_corpus_runs",
    "tex_decoder_run_corpus_bytes",
    "tex_partial_raw_decoder_fullhd",
    "tex_partial_raw_decoder_bytes",
    "tex_partial_raw_coverage_pixels",
    "tex_partial_raw_coverage_gaps",
    "tex_gap_frontier_gaps",
    "tex_gap_frontier_segment_windows",
    "tex_gap_opcode_probe_rows",
    "tex_gap_opcode_probe_best_prefix",
    "tex_gap_opcode_probe_exact_replays",
    "tex_gap_rle_probe_pairs",
    "tex_gap_rle_probe_full_matches",
    "tex_gap_rle_probe_best_prefix",
    "tex_gap_rule_queue_rows",
    "tex_gap_rule_queue_rule_types",
    "tex_gap_rule_queue_top_priority",
    "tex_gap_rule_fixture_rows",
    "tex_gap_rule_fixture_files",
    "tex_gap_rule_fixture_fragment_bytes",
    "tex_gap_zero_run_fixtures",
    "tex_gap_zero_run_rows",
    "tex_gap_zero_run_max_zero",
    "tex_gap_geometry_replay_rows",
    "tex_gap_geometry_replay_best_prefix",
    "tex_gap_geometry_replay_best_exact",
    "tex_gap_nonzero_stream_rows",
    "tex_gap_nonzero_stream_best_prefix",
    "tex_gap_nonzero_stream_best_exact",
    "tex_gap_control_word_hits",
    "tex_gap_control_word_u16le_hits",
    "tex_gap_control_word_metrics",
    "tex_gap_header_schema_blocks",
    "tex_gap_header_schema_candidates",
    "tex_gap_header_schema_dimension_blocks",
    "tex_gap_header_schema_best_prefix",
    "tex_gap_header_schema_best_exact",
    "tex_gap_row_stride_rows",
    "tex_gap_row_stride_best_prefix",
    "tex_gap_row_stride_best_exact",
    "tex_gap_row_stride_mismatch_candidates",
    "tex_gap_row_stride_mismatch_rows",
    "tex_gap_row_stride_mismatch_full_rows",
    "tex_gap_row_delta_rows",
    "tex_gap_row_delta_best_adjusted",
    "tex_gap_row_delta_best_gain",
    "tex_gap_row_transform_rows",
    "tex_gap_row_transform_best",
    "tex_gap_row_transform_gain",
    "tex_gap_row_control_rows",
    "tex_gap_row_control_groups",
    "tex_gap_row_control_best_metric_hits",
    "tex_gap_row_sequence_rows",
    "tex_gap_row_sequence_step_groups",
    "tex_gap_row_sequence_rewinds",
    "tex_gap_row_literal_scan_rows",
    "tex_gap_row_literal_scan_best",
    "tex_gap_row_literal_scan_gain",
    "tex_gap_row_fill_run_rows",
    "tex_gap_row_fill_run_best",
    "tex_gap_row_fill_run_full_rows",
    "tex_gap_control_grammar_rows",
    "tex_gap_control_grammar_best_prefix",
    "tex_gap_control_grammar_best_exact",
    "tex_gap_mismatch_trace_rows",
    "tex_gap_mismatch_trace_ops",
    "tex_gap_mismatch_trace_control_prefix",
    "tex_gap_mismatch_trace_replay_prefix",
    "tex_gap_zero_literal_switch_rows",
    "tex_gap_zero_literal_switch_best_prefix",
    "tex_gap_zero_literal_switch_best_exact",
    "tex_gap_zero_literal_segmentation_covered",
    "tex_gap_zero_literal_segmentation_gap",
    "tex_gap_zero_literal_segmentation_literal",
    "tex_gap_zero_literal_segmentation_full_fixtures",
    "tex_gap_segmentation_control_correlation_ops",
    "tex_gap_segmentation_control_correlation_literal_ops",
    "tex_gap_segmentation_control_correlation_forward_steps",
    "tex_gap_segmentation_control_correlation_len_hits",
    "tex_gap_literal_token_match_ops",
    "tex_gap_literal_token_match_bytes",
    "tex_gap_literal_token_full_fixtures",
    "tex_gap_literal_token_small_matches",
    "tex_gap_literal_token_classifier_small_fp",
    "tex_gap_literal_token_classifier_high_recall_fp",
    "tex_gap_literal_token_classifier_high_precision_fp",
    "tex_gap_literal_token_classifier_rows",
    "tex_gap_literal_fp_rejection_full_recall_fp",
    "tex_gap_literal_fp_rejection_full_recall_false_bytes",
    "tex_gap_literal_fp_rejection_low_false_fp",
    "tex_gap_literal_fp_rejection_candidate_rows",
    "tex_gap_zero_run_alignment_zero_ops",
    "tex_gap_zero_run_alignment_zero_bytes",
    "tex_gap_zero_run_alignment_len64_ops",
    "tex_gap_zero_run_alignment_fill_mod64_ops",
    "tex_gap_zero_control_risk_current_false_bytes",
    "tex_gap_zero_control_risk_false_free_bytes",
    "tex_gap_zero_control_risk_low_false_bytes",
    "tex_gap_zero_control_risk_classifier_rows",
    "tex_gap_decoder_skeleton_best_nonoracle_bytes",
    "tex_gap_decoder_skeleton_best_nonoracle_false",
    "tex_gap_decoder_skeleton_best_oracle_bytes",
    "tex_gap_decoder_skeleton_candidate_rows",
    "tex_gap_decoder_risk_adjusted_best_correct_bytes",
    "tex_gap_decoder_risk_adjusted_best_false_bytes",
    "tex_gap_decoder_risk_adjusted_best_net_bytes",
    "tex_gap_decoder_risk_adjusted_best_low_false_bytes",
    "tex_gap_decoder_risk_adjusted_candidate_rows",
    "tex_gap_decoder_seed_replay_selected_bytes",
    "tex_gap_decoder_seed_replay_trusted_bytes",
    "tex_gap_decoder_seed_replay_false_bytes",
    "tex_gap_decoder_seed_replay_fixture_rows",
    "tex_gap_decoder_seed_replay_fullhd_previews",
    "tex_gap_decoder_control_promotion_bytes",
    "tex_gap_decoder_control_promotion_literal_bytes",
    "tex_gap_decoder_control_promotion_zero_bytes",
    "tex_gap_decoder_control_promotion_ambiguous_groups",
    "tex_gap_decoder_false_risk_promoted_bytes",
    "tex_gap_decoder_false_risk_rejected_bytes",
    "tex_gap_decoder_false_risk_review_bytes",
    "tex_gap_decoder_false_risk_safe_rejectors",
    "tex_gap_decoder_clean_replay_bytes",
    "tex_gap_decoder_clean_replay_rejected_bytes",
    "tex_gap_decoder_clean_replay_fullhd_previews",
    "tex_gap_decoder_clean_gap_unresolved_bytes",
    "tex_gap_decoder_clean_gap_span_rows",
    "tex_gap_decoder_clean_gap_largest_span",
    "tex_gap_decoder_unresolved_run_zero_bytes",
    "tex_gap_decoder_unresolved_run_rows",
    "tex_gap_decoder_unresolved_run_max_zero",
    "tex_gap_decoder_unresolved_zero_queue_bytes",
    "tex_gap_decoder_unresolved_zero_queue_internal_bytes",
    "tex_gap_decoder_unresolved_zero_queue_signatures",
    "tex_gap_decoder_len64_internal_rows",
    "tex_gap_decoder_len64_internal_bytes",
    "tex_gap_decoder_len64_internal_top_neighbor_rows",
    "tex_gap_decoder_len64_source_joined_rows",
    "tex_gap_decoder_len64_source_control_refs",
    "tex_gap_decoder_len64_source_top_ref_rows",
    "tex_gap_decoder_len64_selector_best_bytes",
    "tex_gap_decoder_len64_selector_greedy_bytes",
    "tex_gap_decoder_len64_selector_greedy_selectors",
    "tex_gap_decoder_len64_promoted_added_bytes",
    "tex_gap_decoder_len64_promoted_total_clean_bytes",
    "tex_gap_decoder_len64_promoted_remaining_unresolved_bytes",
    "tex_gap_decoder_len64_promoted_gap_unresolved_bytes",
    "tex_gap_decoder_len64_promoted_gap_span_rows",
    "tex_gap_decoder_len64_promoted_gap_largest_span",
    "tex_gap_decoder_len64_promoted_run_zero_bytes",
    "tex_gap_decoder_len64_promoted_run_rows",
    "tex_gap_decoder_len64_promoted_run_max_zero",
    "tex_gap_decoder_len64_promoted_zero_queue_bytes",
    "tex_gap_decoder_len64_promoted_zero_queue_internal_bytes",
    "tex_gap_decoder_len64_promoted_zero_queue_signatures",
    "tex_gap_decoder_len64_promoted_zero_source_joined_rows",
    "tex_gap_decoder_len64_promoted_zero_source_joined_bytes",
    "tex_gap_decoder_len64_promoted_zero_source_control_refs",
    "tex_gap_decoder_len64_promoted_large32_selector_best_bytes",
    "tex_gap_decoder_len64_promoted_large32_selector_greedy_bytes",
    "tex_gap_decoder_len64_promoted_large32_selector_greedy_selectors",
    "tex_gap_decoder_len64_promoted_large32_replay_added_bytes",
    "tex_gap_decoder_len64_promoted_large32_replay_total_clean_bytes",
    "tex_gap_decoder_len64_promoted_large32_replay_remaining_unresolved_bytes",
    "tex_gap_decoder_len64_promoted_large32_gap_unresolved_bytes",
    "tex_gap_decoder_len64_promoted_large32_gap_span_rows",
    "tex_gap_decoder_len64_promoted_large32_gap_largest_span",
    "tex_gap_decoder_len64_promoted_large32_run_zero_bytes",
    "tex_gap_decoder_len64_promoted_large32_run_rows",
    "tex_gap_decoder_len64_promoted_large32_run_max_zero",
    "tex_gap_decoder_len64_promoted_large32_zero_queue_bytes",
    "tex_gap_decoder_len64_promoted_large32_zero_queue_internal_bytes",
    "tex_gap_decoder_len64_promoted_large32_zero_queue_signatures",
    "tex_gap_decoder_len64_promoted_large32_zero_source_joined_rows",
    "tex_gap_decoder_len64_promoted_large32_zero_source_joined_bytes",
    "tex_gap_decoder_len64_promoted_large32_zero_source_control_refs",
    "tex_gap_decoder_len64_promoted_medium8_selector_best_bytes",
    "tex_gap_decoder_len64_promoted_medium8_selector_greedy_bytes",
    "tex_gap_decoder_len64_promoted_medium8_selector_greedy_selectors",
    "tex_gap_decoder_len64_promoted_medium8_replay_added_bytes",
    "tex_gap_decoder_len64_promoted_medium8_replay_total_clean_bytes",
    "tex_gap_decoder_len64_promoted_medium8_replay_remaining_unresolved_bytes",
    "tex_gap_decoder_len64_promoted_medium8_gap_unresolved_bytes",
    "tex_gap_decoder_len64_promoted_medium8_gap_span_rows",
    "tex_gap_decoder_len64_promoted_medium8_gap_largest_span",
    "tex_gap_decoder_len64_promoted_medium8_run_zero_bytes",
    "tex_gap_decoder_len64_promoted_medium8_run_rows",
    "tex_gap_decoder_len64_promoted_medium8_run_max_zero",
    "tex_gap_decoder_len64_promoted_medium8_zero_queue_bytes",
    "tex_gap_decoder_len64_promoted_medium8_zero_queue_internal_bytes",
    "tex_gap_decoder_len64_promoted_medium8_zero_queue_signatures",
    "tex_gap_decoder_len64_promoted_medium8_zero_source_joined_rows",
    "tex_gap_decoder_len64_promoted_medium8_zero_source_joined_bytes",
    "tex_gap_decoder_len64_promoted_medium8_zero_source_control_refs",
    "tex_gap_decoder_len64_promoted_medium8_remaining_selector_best_bytes",
    "tex_gap_decoder_len64_promoted_medium8_remaining_selector_greedy_bytes",
    "tex_gap_decoder_len64_promoted_medium8_remaining_selector_greedy_selectors",
    "tex_gap_decoder_len64_promoted_large32_remaining_selector_best_bytes",
    "tex_gap_decoder_len64_promoted_large32_remaining_selector_greedy_bytes",
    "tex_gap_decoder_len64_promoted_large32_remaining_selector_greedy_selectors",
    "tex_gap_fixture_replay_rows",
    "tex_gap_fixture_replay_exact_matches",
    "tex_gap_fixture_replay_best_prefix",
    "cdcache_gallery_assets",
    "dashboard_cards",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def int_value(row: dict[str, str], field: str) -> int:
    raw = row.get(field, "")
    return int(raw) if raw else 0


def split_values(value: str) -> list[str]:
    return [part for part in value.split(";") if part]


def gate(
    name: str,
    ok: bool,
    *,
    expected: str,
    actual: str,
    evidence: Path | str,
    issues: list[str] | None = None,
) -> dict[str, str]:
    return {
        "gate": name,
        "status": "pass" if ok else "fail",
        "expected": expected,
        "actual": actual,
        "evidence": str(evidence),
        "issues": ";".join(issues or []),
    }


def missing_gate(name: str, path: Path) -> dict[str, str]:
    return gate(
        name,
        False,
        expected="required evidence file exists",
        actual="missing",
        evidence=path,
        issues=["missing_evidence_file"],
    )


def audit_generated_report(
    name: str,
    *,
    summary_path: Path,
    required_paths: list[Path],
    html_report: Path,
    expected_fields: list[str],
    html_marker: str,
    zero_issue_rows: bool = True,
    zero_false_fields: list[str] | None = None,
    positive_fields: list[str] | None = None,
    fullhd_previews_match_fixtures: bool = False,
) -> dict[str, str]:
    for path in [summary_path, *required_paths, html_report]:
        if not path.exists():
            return missing_gate(name, path)

    issues: list[str] = []
    rows = read_csv(summary_path)
    summary = rows[0] if rows else {}
    if not summary:
        issues.append("empty_summary")
    for field in expected_fields:
        if field not in summary:
            issues.append(f"missing_summary_field:{field}")
    if zero_issue_rows and "issue_rows" in summary and int_value(summary, "issue_rows"):
        issues.append(f"issue_rows:{summary.get('issue_rows', '')}")
    for field in zero_false_fields or []:
        if int_value(summary, field):
            issues.append(f"{field}:{summary.get(field, '')}")
    for field in positive_fields or []:
        if int_value(summary, field) <= 0:
            issues.append(f"non_positive:{field}")
    if fullhd_previews_match_fixtures and summary:
        if summary.get("fullhd_previews") != summary.get("fixture_rows"):
            issues.append("fullhd_preview_count_mismatch")
    text = html_report.read_text(errors="ignore")
    if html_marker not in text:
        issues.append("missing_report_json")

    actual = ",".join(
        f"{field}={summary.get(field, '')}"
        for field in expected_fields
        if field in summary
    )
    return gate(
        name,
        not issues,
        expected="report files, summary invariants, and HTML JSON payload",
        actual=actual,
        evidence=summary_path,
        issues=issues,
    )


def audit_still(manifest: Path, verification: Path) -> tuple[dict[str, str], int]:
    if not manifest.exists():
        return missing_gate("still_fullhd_exports", manifest), 0
    if not verification.exists():
        return missing_gate("still_fullhd_exports", verification), 0
    manifest_rows = read_csv(manifest)
    rows = read_csv(verification)
    issues: list[str] = []
    if len(rows) != len(manifest_rows):
        issues.append("manifest_verification_count_mismatch")
    issue_rows = sum(1 for row in rows if row.get("issues"))
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    bad_dimensions = [
        row
        for row in rows
        if (row.get("actual_width"), row.get("actual_height"))
        != (str(TARGET_SIZE[0]), str(TARGET_SIZE[1]))
    ]
    if bad_dimensions:
        issues.append(f"not_fullhd:{len(bad_dimensions)}")
    ok = not issues
    return (
        gate(
            "still_fullhd_exports",
            ok,
            expected=f"{len(manifest_rows)} verified 1920x1080 still PNGs, 0 issues",
            actual=f"{len(rows)} rows, {issue_rows} issue rows, {len(bad_dimensions)} non-Full-HD rows",
            evidence=verification,
            issues=issues,
        ),
        len(rows) if ok else 0,
    )


def audit_still_gallery(
    gallery: Path,
    gallery_manifest: Path,
    still_manifest: Path,
) -> tuple[dict[str, str], int]:
    if not gallery.exists():
        return missing_gate("still_hd_gallery", gallery), 0
    if not gallery_manifest.exists():
        return missing_gate("still_hd_gallery", gallery_manifest), 0
    if not still_manifest.exists():
        return missing_gate("still_hd_gallery", still_manifest), 0
    still_rows = read_csv(still_manifest)
    manifest_rows = read_csv(gallery_manifest)
    text = gallery.read_text(errors="replace")
    issues: list[str] = []
    match = re.search(r"const ASSETS = (.*?);\nconst grid", text)
    if not match:
        return (
            gate(
                "still_hd_gallery",
                False,
                expected="embedded ASSETS JSON in still-image gallery HTML",
                actual="missing",
                evidence=gallery,
                issues=["missing_assets_json"],
            ),
            0,
        )
    try:
        assets = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        return (
            gate(
                "still_hd_gallery",
                False,
                expected="valid embedded ASSETS JSON",
                actual=f"JSON error at {exc.pos}",
                evidence=gallery,
                issues=[f"invalid_assets_json:{exc}"],
            ),
            0,
        )
    if len(manifest_rows) != len(still_rows):
        issues.append("still_manifest_gallery_manifest_count_mismatch")
    if len(assets) != len(manifest_rows):
        issues.append("gallery_json_manifest_count_mismatch")
    issue_rows = sum(1 for row in manifest_rows if row.get("issues"))
    if issue_rows:
        issues.append(f"gallery_manifest_issue_rows:{issue_rows}")
    missing_paths = 0
    for asset in assets:
        value = asset.get("image", "")
        if value and not (gallery.parent / value).exists():
            missing_paths += 1
    if missing_paths:
        issues.append(f"missing_gallery_paths:{missing_paths}")
    if "function escapeHtml" not in text:
        issues.append("missing_html_escape_function")
    ok = not issues
    return (
        gate(
            "still_hd_gallery",
            ok,
            expected=f"{len(still_rows)} still-image gallery entries with valid Full HD paths",
            actual=(
                f"assets={len(assets)}, issue_rows={issue_rows}, "
                f"missing_paths={missing_paths}"
            ),
            evidence=gallery,
            issues=issues,
        ),
        len(assets) if ok else 0,
    )


def audit_vqa(manifest: Path, verification: Path) -> tuple[dict[str, str], int]:
    if not manifest.exists():
        return missing_gate("vqa_frame_fullhd_exports", manifest), 0
    if not verification.exists():
        return missing_gate("vqa_frame_fullhd_exports", verification), 0
    manifest_rows = read_csv(manifest)
    rows = read_csv(verification)
    issues: list[str] = []
    if len(rows) != len(manifest_rows):
        issues.append("manifest_verification_count_mismatch")
    issue_rows = sum(1 for row in rows if row.get("issues"))
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    expected_frames = sum(int_value(row, "expected_frames") for row in rows)
    native_frames = sum(int_value(row, "native_frames") for row in rows)
    fullhd_frames = sum(int_value(row, "fullhd_frames") for row in rows)
    missing_fullhd = sum(int_value(row, "missing_fullhd_output_files") for row in rows)
    if native_frames != expected_frames:
        issues.append("native_frame_total_mismatch")
    if fullhd_frames != expected_frames:
        issues.append("fullhd_frame_total_mismatch")
    if missing_fullhd:
        issues.append(f"missing_fullhd_files:{missing_fullhd}")
    ok = not issues
    return (
        gate(
            "vqa_frame_fullhd_exports",
            ok,
            expected=f"{expected_frames} native and Full HD frame PNGs, 0 issues",
            actual=(
                f"{len(rows)} entries, native={native_frames}, "
                f"fullhd={fullhd_frames}, issues={issue_rows}"
            ),
            evidence=verification,
            issues=issues,
        ),
        fullhd_frames if ok else 0,
    )


def audit_vqa_gallery(gallery: Path, gallery_manifest: Path, vqa_manifest: Path) -> tuple[dict[str, str], int]:
    if not gallery.exists():
        return missing_gate("vqa_hd_gallery", gallery), 0
    if not gallery_manifest.exists():
        return missing_gate("vqa_hd_gallery", gallery_manifest), 0
    if not vqa_manifest.exists():
        return missing_gate("vqa_hd_gallery", vqa_manifest), 0
    vqa_rows = read_csv(vqa_manifest)
    manifest_rows = read_csv(gallery_manifest)
    text = gallery.read_text(errors="replace")
    issues: list[str] = []
    match = re.search(r"const ASSETS = (.*?);\nconst grid", text)
    if not match:
        return (
            gate(
                "vqa_hd_gallery",
                False,
                expected="embedded ASSETS JSON in VQA gallery HTML",
                actual="missing",
                evidence=gallery,
                issues=["missing_assets_json"],
            ),
            0,
        )
    try:
        assets = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        return (
            gate(
                "vqa_hd_gallery",
                False,
                expected="valid embedded ASSETS JSON",
                actual=f"JSON error at {exc.pos}",
                evidence=gallery,
                issues=[f"invalid_assets_json:{exc}"],
            ),
            0,
        )
    if len(manifest_rows) != len(vqa_rows):
        issues.append("vqa_manifest_gallery_manifest_count_mismatch")
    if len(assets) != len(manifest_rows):
        issues.append("gallery_json_manifest_count_mismatch")
    issue_rows = sum(1 for row in manifest_rows if row.get("issues"))
    if issue_rows:
        issues.append(f"gallery_manifest_issue_rows:{issue_rows}")
    missing_paths = 0
    for asset in assets:
        for field in ("image", "framesDir", "outputDir"):
            value = asset.get(field, "")
            if value and not (gallery.parent / value).exists():
                missing_paths += 1
    if missing_paths:
        issues.append(f"missing_gallery_paths:{missing_paths}")
    if "function escapeHtml" not in text:
        issues.append("missing_html_escape_function")
    frame_total = sum(int(asset.get("fullhdFrames") or 0) for asset in assets)
    ok = not issues
    return (
        gate(
            "vqa_hd_gallery",
            ok,
            expected=f"{len(vqa_rows)} VQA gallery entries with valid representative Full HD paths",
            actual=(
                f"assets={len(assets)}, frames={frame_total}, "
                f"issue_rows={issue_rows}, missing_paths={missing_paths}"
            ),
            evidence=gallery,
            issues=issues,
        ),
        len(assets) if ok else 0,
    )


def audit_vqa_status_report(
    summary: Path,
    by_archive: Path,
    html_report: Path,
    vqa_manifest: Path,
) -> tuple[dict[str, str], int]:
    if not summary.exists():
        return missing_gate("vqa_status_report", summary), 0
    if not by_archive.exists():
        return missing_gate("vqa_status_report", by_archive), 0
    if not html_report.exists():
        return missing_gate("vqa_status_report", html_report), 0
    if not vqa_manifest.exists():
        return missing_gate("vqa_status_report", vqa_manifest), 0

    summary_rows = read_csv(summary)
    archive_rows = read_csv(by_archive)
    vqa_rows = read_csv(vqa_manifest)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    entries = int_value(total, "entries")
    archives = int_value(total, "archives")
    expected_frames = int_value(total, "expected_frames")
    native_frames = int_value(total, "native_frames")
    fullhd_frames = int_value(total, "fullhd_frames")
    issue_rows = int_value(total, "issue_rows")
    non_output_rows = int_value(total, "non_output_rows")
    missing_fullhd = int_value(total, "missing_fullhd_output_files")
    missing_frames = int_value(total, "missing_frame_rows")
    duplicate_frames = int_value(total, "duplicate_frame_rows")

    if entries != len(vqa_rows):
        issues.append("vqa_status_entry_count_mismatch")
    if archives != len(archive_rows):
        issues.append("vqa_status_archive_count_mismatch")
    if expected_frames != native_frames or expected_frames != fullhd_frames:
        issues.append("vqa_status_frame_total_mismatch")
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    if non_output_rows:
        issues.append(f"non_output_rows:{non_output_rows}")
    if missing_fullhd:
        issues.append(f"missing_fullhd_files:{missing_fullhd}")
    if missing_frames:
        issues.append(f"missing_frame_rows:{missing_frames}")
    if duplicate_frames:
        issues.append(f"duplicate_frame_rows:{duplicate_frames}")
    if "const REPORT = " not in text or "const byArchive" not in text:
        issues.append("missing_status_report_json")

    ok = not issues
    return (
        gate(
            "vqa_status_report",
            ok,
            expected="VQA status summary matches manifest and has no missing Full HD frames",
            actual=(
                f"entries={entries}, archives={archives}, fullhd={fullhd_frames}, "
                f"held={int_value(total, 'held_frame_rows')}, issues={issue_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        archives if ok else 0,
    )


def audit_inventory(summary: Path) -> tuple[dict[str, str], int]:
    if not summary.exists():
        return missing_gate("global_fullhd_inventory", summary), 0
    rows = read_csv(summary)
    total = next((row for row in rows if row.get("category") == "total"), None)
    if total is None:
        return (
            gate(
                "global_fullhd_inventory",
                False,
                expected="total row in inventory summary",
                actual="missing",
                evidence=summary,
                issues=["missing_total_row"],
            ),
            0,
        )
    records = int_value(total, "records")
    existing = int_value(total, "existing_files")
    fullhd = int_value(total, "fullhd_files")
    issue_rows = int_value(total, "issue_rows")
    issues: list[str] = []
    if records != existing:
        issues.append("missing_inventory_files")
    if records != fullhd:
        issues.append("inventory_non_fullhd_files")
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    ok = not issues
    return (
        gate(
            "global_fullhd_inventory",
            ok,
            expected="all inventoried outputs exist and are 1920x1080, 0 issues",
            actual=f"records={records}, existing={existing}, fullhd={fullhd}, issues={issue_rows}",
            evidence=summary,
            issues=issues,
        ),
        fullhd if ok else 0,
    )


def audit_archive_coverage(
    summary: Path,
    archives: Path,
    html_report: Path,
    vqa_manifest: Path,
    still_manifest: Path,
) -> tuple[dict[str, str], int]:
    if not summary.exists():
        return missing_gate("fullhd_archive_coverage", summary), 0
    if not archives.exists():
        return missing_gate("fullhd_archive_coverage", archives), 0
    if not html_report.exists():
        return missing_gate("fullhd_archive_coverage", html_report), 0
    if not vqa_manifest.exists():
        return missing_gate("fullhd_archive_coverage", vqa_manifest), 0
    if not still_manifest.exists():
        return missing_gate("fullhd_archive_coverage", still_manifest), 0

    summary_rows = read_csv(summary)
    archive_rows = read_csv(archives)
    vqa_rows = read_csv(vqa_manifest)
    still_rows = read_csv(still_manifest)
    mix_pcx_rows = [row for row in still_rows if row.get("source_type") == "mix_pcx"]
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    archive_count = int_value(total, "archives")
    visual_entries = int_value(total, "visual_entries")
    vqa_entries = int_value(total, "vqa_entries")
    vqa_fullhd_entries = int_value(total, "vqa_fullhd_entries")
    pcx_entries = int_value(total, "pcx_entries")
    pcx_fullhd_entries = int_value(total, "pcx_fullhd_entries")
    missing_vqa = int_value(total, "missing_vqa_fullhd_entries")
    missing_pcx = int_value(total, "missing_pcx_fullhd_entries")
    issue_rows = int_value(total, "issue_rows")

    if archive_count != len(archive_rows):
        issues.append("archive_count_mismatch")
    if visual_entries != vqa_entries + pcx_entries:
        issues.append("visual_entry_total_mismatch")
    if vqa_entries != len(vqa_rows) or vqa_fullhd_entries != len(vqa_rows):
        issues.append("vqa_coverage_count_mismatch")
    if pcx_entries != len(mix_pcx_rows) or pcx_fullhd_entries != len(mix_pcx_rows):
        issues.append("pcx_coverage_count_mismatch")
    if missing_vqa:
        issues.append(f"missing_vqa_fullhd_entries:{missing_vqa}")
    if missing_pcx:
        issues.append(f"missing_pcx_fullhd_entries:{missing_pcx}")
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    if "const COVERAGE = " not in text:
        issues.append("missing_archive_coverage_json")

    ok = not issues
    return (
        gate(
            "fullhd_archive_coverage",
            ok,
            expected="all detected VQA/PCX MIX visual entries have Full HD outputs",
            actual=(
                f"archives={archive_count}, visual={visual_entries}, "
                f"vqa={vqa_fullhd_entries}/{vqa_entries}, pcx={pcx_fullhd_entries}/{pcx_entries}, "
                f"issues={issue_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        visual_entries if ok else 0,
    )


def audit_cdcache_export(
    gate_name: str,
    manifest: Path,
    verification: Path,
) -> tuple[dict[str, str], int]:
    if not manifest.exists():
        return missing_gate(gate_name, manifest), 0
    if not verification.exists():
        return missing_gate(gate_name, verification), 0
    manifest_rows = read_csv(manifest)
    rows = read_csv(verification)
    issues: list[str] = []
    if len(rows) != len(manifest_rows):
        issues.append("manifest_verification_count_mismatch")
    issue_rows = sum(1 for row in rows if row.get("issues"))
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    bad_fullhd = [
        row
        for row in rows
        if (row.get("fullhd_actual_width"), row.get("fullhd_actual_height"))
        != (str(TARGET_SIZE[0]), str(TARGET_SIZE[1]))
    ]
    if bad_fullhd:
        issues.append(f"non_fullhd:{len(bad_fullhd)}")
    non_rgba = [row for row in rows if row.get("expected_image_mode") != "RGBA"]
    if non_rgba:
        issues.append(f"non_rgba:{len(non_rgba)}")
    ok = not issues
    return (
        gate(
            gate_name,
            ok,
            expected=f"{len(manifest_rows)} RGBA Full HD CDCACHE rows, 0 issues",
            actual=(
                f"{len(rows)} rows, {len(bad_fullhd)} non-Full-HD rows, "
                f"{len(non_rgba)} non-RGBA rows, issues={issue_rows}"
            ),
            evidence=verification,
            issues=issues,
        ),
        len(rows) if ok else 0,
    )


def audit_pack(manifest: Path, verification: Path, summary: Path) -> tuple[dict[str, str], int, int]:
    if not manifest.exists():
        return missing_gate("cdcache_hd_asset_pack", manifest), 0, 0
    if not verification.exists():
        return missing_gate("cdcache_hd_asset_pack", verification), 0, 0
    if not summary.exists():
        return missing_gate("cdcache_hd_asset_pack", summary), 0, 0
    manifest_rows = read_csv(manifest)
    rows = read_csv(verification)
    summary_rows = read_csv(summary)
    total = next((row for row in summary_rows if row.get("group") == "total"), {})
    issues: list[str] = []
    if len(rows) != len(manifest_rows):
        issues.append("manifest_verification_count_mismatch")
    issue_rows = sum(1 for row in rows if row.get("issues"))
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    all_matches = sum(1 for row in rows if row.get("all_pack_target_matches_source") == "True")
    linked_rows = [row for row in rows if row.get("linked_to_tex") == "yes"]
    linked_matches = sum(
        1 for row in linked_rows if row.get("linked_pack_target_matches_source") == "True"
    )
    if all_matches != len(rows):
        issues.append("all_pack_target_mismatch")
    if linked_matches != len(linked_rows):
        issues.append("linked_pack_target_mismatch")
    if int_value(total, "issue_rows") != 0:
        issues.append("summary_issue_rows_nonzero")
    if int_value(total, "rows") and int_value(total, "rows") != len(rows):
        issues.append("summary_row_count_mismatch")
    ok = not issues
    return (
        gate(
            "cdcache_hd_asset_pack",
            ok,
            expected="all pack links target selected source PNGs, 0 issues",
            actual=(
                f"assets={len(rows)}, all_matches={all_matches}, "
                f"linked={len(linked_rows)}, linked_matches={linked_matches}, issues={issue_rows}"
            ),
            evidence=verification,
            issues=issues,
        ),
        len(rows) if ok else 0,
        len(linked_rows) if ok else 0,
    )


def audit_tex_coverage(
    summary: Path,
    cache_assets: Path,
    material_report: Path,
    html_report: Path,
    pack_manifest: Path,
    material_links: Path,
) -> tuple[dict[str, str], int, int]:
    if not summary.exists():
        return missing_gate("tex_hd_coverage", summary), 0, 0
    if not cache_assets.exists():
        return missing_gate("tex_hd_coverage", cache_assets), 0, 0
    if not material_report.exists():
        return missing_gate("tex_hd_coverage", material_report), 0, 0
    if not html_report.exists():
        return missing_gate("tex_hd_coverage", html_report), 0, 0
    if not pack_manifest.exists():
        return missing_gate("tex_hd_coverage", pack_manifest), 0, 0
    if not material_links.exists():
        return missing_gate("tex_hd_coverage", material_links), 0, 0

    summary_rows = read_csv(summary)
    cache_rows = read_csv(cache_assets)
    material_rows = read_csv(material_report)
    pack_rows = read_csv(pack_manifest)
    source_material_rows = read_csv(material_links)
    linked_pack_rows = [row for row in pack_rows if row.get("linked_to_tex") == "yes"]
    linked_descriptors = [
        row for row in linked_pack_rows if row.get("asset_kind") == "descriptor"
    ]
    linked_tiles = [row for row in linked_pack_rows if row.get("asset_kind") == "tile"]
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    tex_assets = int_value(total, "tex_linked_pack_assets")
    tex_descriptors = int_value(total, "tex_linked_descriptors")
    tex_tiles = int_value(total, "tex_linked_tiles")
    material_link_rows = int_value(total, "material_link_rows")
    issue_rows = int_value(total, "issue_rows")
    missing_all = int_value(total, "missing_all_pack_paths")
    missing_linked = int_value(total, "missing_linked_pack_paths")
    missing_source = int_value(total, "missing_source_paths")

    if tex_assets != len(linked_pack_rows):
        issues.append("tex_linked_asset_count_mismatch")
    if tex_descriptors != len(linked_descriptors) or tex_descriptors != len(cache_rows):
        issues.append("tex_descriptor_count_mismatch")
    if tex_tiles != len(linked_tiles):
        issues.append("tex_tile_count_mismatch")
    if material_link_rows != len(source_material_rows) or material_link_rows != len(material_rows):
        issues.append("tex_material_link_count_mismatch")
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    if missing_all:
        issues.append(f"missing_all_pack_paths:{missing_all}")
    if missing_linked:
        issues.append(f"missing_linked_pack_paths:{missing_linked}")
    if missing_source:
        issues.append(f"missing_source_paths:{missing_source}")
    if "const TEX_COVERAGE = " not in text:
        issues.append("missing_tex_coverage_json")

    ok = not issues
    return (
        gate(
            "tex_hd_coverage",
            ok,
            expected=".tex-linked CDCACHE pack assets and material links have valid Full HD paths",
            actual=(
                f"assets={tex_assets}, descriptors={tex_descriptors}, tiles={tex_tiles}, "
                f"material_links={material_link_rows}, issues={issue_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        tex_assets if ok else 0,
        material_link_rows if ok else 0,
    )


def audit_tex_reference_coverage(
    summary: Path,
    references: Path,
    missing_references: Path,
    archives: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_reference_coverage", summary), 0, 0, 0
    if not references.exists():
        return missing_gate("tex_reference_coverage", references), 0, 0, 0
    if not missing_references.exists():
        return missing_gate("tex_reference_coverage", missing_references), 0, 0, 0
    if not archives.exists():
        return missing_gate("tex_reference_coverage", archives), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_reference_coverage", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    reference_rows = read_csv(references)
    missing_rows = read_csv(missing_references)
    archive_rows = read_csv(archives)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    texture_archives = int_value(total, "texture_archives")
    likely_references = int_value(total, "likely_references")
    unique_likely = int_value(total, "unique_likely_pcx")
    covered_references = int_value(total, "covered_references")
    missing_reference_count = int_value(total, "missing_references")
    covered_unique = int_value(total, "covered_unique_pcx")
    missing_unique = int_value(total, "missing_unique_pcx")
    issue_rows = int_value(total, "issue_rows")
    missing_covered_paths = int_value(total, "missing_covered_fullhd_paths")

    covered_rows = [row for row in reference_rows if row.get("covered") == "yes"]
    uncovered_rows = [row for row in reference_rows if row.get("covered") != "yes"]
    unique_names = {row.get("normalized_pcx_name", "") for row in reference_rows if row.get("normalized_pcx_name")}
    covered_names = {row.get("normalized_pcx_name", "") for row in covered_rows if row.get("normalized_pcx_name")}
    missing_names = {row.get("normalized_pcx_name", "") for row in uncovered_rows if row.get("normalized_pcx_name")}

    if texture_archives != len(archive_rows):
        issues.append("tex_reference_archive_count_mismatch")
    if likely_references != len(reference_rows):
        issues.append("tex_reference_row_count_mismatch")
    if covered_references != len(covered_rows):
        issues.append("tex_reference_covered_count_mismatch")
    if missing_reference_count != len(missing_rows) or missing_reference_count != len(uncovered_rows):
        issues.append("tex_reference_missing_count_mismatch")
    if unique_likely != len(unique_names):
        issues.append("tex_reference_unique_count_mismatch")
    if covered_unique != len(covered_names):
        issues.append("tex_reference_covered_unique_count_mismatch")
    if missing_unique != len(missing_names):
        issues.append("tex_reference_missing_unique_count_mismatch")
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    if missing_covered_paths:
        issues.append(f"missing_covered_fullhd_paths:{missing_covered_paths}")
    if "const TEX_REFERENCE_COVERAGE = " not in text:
        issues.append("missing_tex_reference_coverage_json")

    missing_paths = 0
    for row in covered_rows:
        for field in ("descriptor_fullhd_paths", "descriptor_pack_paths"):
            for value in split_values(row.get(field, "")):
                if not Path(value).exists():
                    missing_paths += 1
    if missing_paths:
        issues.append(f"missing_tex_reference_paths:{missing_paths}")

    ok = not issues
    return (
        gate(
            "tex_reference_coverage",
            ok,
            expected=".tex PCX reference report is internally consistent and covered rows have valid paths",
            actual=(
                f"unique={unique_likely}, covered={covered_unique}, "
                f"missing={missing_unique}, row_missing={missing_reference_count}, issues={issue_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        unique_likely if ok else 0,
        covered_unique if ok else 0,
        missing_unique if ok else 0,
    )


def audit_tex_missing_reference_evidence(
    summary: Path,
    evidence: Path,
    unique: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int]:
    if not summary.exists():
        return missing_gate("tex_missing_reference_evidence", summary), 0, 0
    if not evidence.exists():
        return missing_gate("tex_missing_reference_evidence", evidence), 0, 0
    if not unique.exists():
        return missing_gate("tex_missing_reference_evidence", unique), 0, 0
    if not html_report.exists():
        return missing_gate("tex_missing_reference_evidence", html_report), 0, 0

    summary_rows = read_csv(summary)
    evidence_rows = read_csv(evidence)
    unique_rows = read_csv(unique)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    missing_reference_rows = int_value(total, "missing_reference_rows")
    unique_missing = int_value(total, "unique_missing_pcx")
    rows_with_raw = int_value(total, "rows_with_raw_cdcache")
    unique_with_raw = int_value(total, "unique_with_raw_cdcache")
    rows_with_raw_same = int_value(total, "rows_with_raw_same_archive")
    unique_with_raw_same = int_value(total, "unique_with_raw_same_archive")
    rows_with_material = int_value(total, "rows_with_material_match")
    unique_with_material = int_value(total, "unique_with_material_match")
    rows_with_segment = int_value(total, "rows_with_texture_segment")
    unique_with_segment = int_value(total, "unique_with_texture_segment")
    unexpected_descriptors = int_value(total, "unexpected_descriptor_rows")
    issue_rows = int_value(total, "issue_rows")

    evidence_names = {
        row.get("normalized_pcx_name", "")
        for row in evidence_rows
        if row.get("normalized_pcx_name", "")
    }
    unique_names = {
        row.get("normalized_pcx_name", "")
        for row in unique_rows
        if row.get("normalized_pcx_name", "")
    }
    if missing_reference_rows != len(evidence_rows):
        issues.append("tex_missing_evidence_row_count_mismatch")
    if unique_missing != len(unique_rows) or unique_missing != len(evidence_names):
        issues.append("tex_missing_evidence_unique_count_mismatch")
    if evidence_names != unique_names:
        issues.append("tex_missing_evidence_unique_names_mismatch")
    if rows_with_raw != sum(1 for row in evidence_rows if int_value(row, "raw_cache_refs") > 0):
        issues.append("tex_missing_evidence_raw_row_count_mismatch")
    if unique_with_raw != sum(1 for row in unique_rows if int_value(row, "raw_cache_refs") > 0):
        issues.append("tex_missing_evidence_raw_unique_count_mismatch")
    if rows_with_raw_same != sum(1 for row in evidence_rows if int_value(row, "raw_cache_same_archive_refs") > 0):
        issues.append("tex_missing_evidence_raw_same_row_count_mismatch")
    if unique_with_raw_same != sum(1 for row in unique_rows if int_value(row, "raw_cache_same_archive_refs") > 0):
        issues.append("tex_missing_evidence_raw_same_unique_count_mismatch")
    if rows_with_material != sum(1 for row in evidence_rows if int_value(row, "material_name_matches") > 0):
        issues.append("tex_missing_evidence_material_row_count_mismatch")
    if unique_with_material != sum(1 for row in unique_rows if int_value(row, "material_name_matches") > 0):
        issues.append("tex_missing_evidence_material_unique_count_mismatch")
    if rows_with_segment != len(evidence_rows) or unique_with_segment != len(unique_rows):
        issues.append("tex_missing_evidence_segment_count_mismatch")
    if unexpected_descriptors:
        issues.append(f"unexpected_descriptor_rows:{unexpected_descriptors}")
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    if "const TEX_MISSING_REFERENCE_EVIDENCE = " not in text:
        issues.append("missing_tex_missing_reference_evidence_json")

    ok = not issues
    return (
        gate(
            "tex_missing_reference_evidence",
            ok,
            expected="missing .tex reference evidence report is internally consistent",
            actual=(
                f"missing_unique={unique_missing}, raw_unique={unique_with_raw}, "
                f"raw_same_unique={unique_with_raw_same}, material_unique={unique_with_material}, "
                f"issues={issue_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        unique_with_raw if ok else 0,
        unique_with_material if ok else 0,
    )


def audit_raw_reference_probe(
    summary: Path,
    probe_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int]:
    if not summary.exists():
        return missing_gate("cdcache_raw_reference_probe", summary), 0
    if not probe_rows_path.exists():
        return missing_gate("cdcache_raw_reference_probe", probe_rows_path), 0
    if not html_report.exists():
        return missing_gate("cdcache_raw_reference_probe", html_report), 0

    summary_rows = read_csv(summary)
    probe_rows = read_csv(probe_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    probe_count = int_value(total, "probe_rows")
    unique_pcx = int_value(total, "unique_pcx")
    candidate_rows = int_value(total, "rows_with_descriptor_candidates")
    issue_rows = int_value(total, "issue_rows")
    if probe_count != len(probe_rows):
        issues.append("raw_probe_row_count_mismatch")
    if unique_pcx != len({row.get("normalized_pcx_name", "") for row in probe_rows}):
        issues.append("raw_probe_unique_count_mismatch")
    if candidate_rows != sum(1 for row in probe_rows if int_value(row, "descriptor_candidate_count") > 0):
        issues.append("raw_probe_candidate_count_mismatch")
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    if "const CDCACHE_RAW_REFERENCE_PROBE = " not in text:
        issues.append("missing_raw_reference_probe_json")

    ok = not issues
    return (
        gate(
            "cdcache_raw_reference_probe",
            ok,
            expected="raw CDCACHE probe report is internally consistent",
            actual=f"probes={probe_count}, unique={unique_pcx}, candidates={candidate_rows}, issues={issue_rows}",
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        candidate_rows if ok else 0,
    )


def audit_alias_candidates(
    summary: Path,
    aliases: Path,
    synthetic_descriptors: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int]:
    if not summary.exists():
        return missing_gate("cdcache_alias_candidates", summary), 0, 0
    if not aliases.exists():
        return missing_gate("cdcache_alias_candidates", aliases), 0, 0
    if not synthetic_descriptors.exists():
        return missing_gate("cdcache_alias_candidates", synthetic_descriptors), 0, 0
    if not html_report.exists():
        return missing_gate("cdcache_alias_candidates", html_report), 0, 0

    summary_rows = read_csv(summary)
    alias_rows = read_csv(aliases)
    synthetic_rows = read_csv(synthetic_descriptors)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    alias_count = int_value(total, "alias_rows")
    unique_missing = int_value(total, "unique_missing_pcx")
    existing_aliases = int_value(total, "existing_descriptor_aliases")
    synthetic_aliases = int_value(total, "synthetic_descriptor_aliases")
    synthetic_descriptor_rows = int_value(total, "synthetic_descriptor_rows")
    issue_rows = int_value(total, "issue_rows")
    if alias_count != len(alias_rows):
        issues.append("alias_candidate_row_count_mismatch")
    if unique_missing != len({row.get("missing_pcx_name", "") for row in alias_rows}):
        issues.append("alias_candidate_unique_count_mismatch")
    if existing_aliases + synthetic_aliases != alias_count:
        issues.append("alias_candidate_kind_total_mismatch")
    if synthetic_descriptor_rows != len(synthetic_rows):
        issues.append("alias_candidate_synthetic_descriptor_count_mismatch")
    if synthetic_aliases != len(synthetic_rows):
        issues.append("alias_candidate_synthetic_alias_count_mismatch")
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    if "const CDCACHE_ALIAS_CANDIDATES = " not in text:
        issues.append("missing_alias_candidates_json")

    ok = not issues
    return (
        gate(
            "cdcache_alias_candidates",
            ok,
            expected="CDCACHE alias-candidate report and synthetic descriptors are consistent",
            actual=(
                f"aliases={alias_count}, existing={existing_aliases}, "
                f"synthetic={synthetic_aliases}, issues={issue_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        alias_count if ok else 0,
        synthetic_descriptor_rows if ok else 0,
    )


def audit_alias_pack(
    summary: Path,
    manifest: Path,
    html_report: Path,
) -> tuple[dict[str, str], int]:
    if not summary.exists():
        return missing_gate("cdcache_tex_alias_pack", summary), 0
    if not manifest.exists():
        return missing_gate("cdcache_tex_alias_pack", manifest), 0
    if not html_report.exists():
        return missing_gate("cdcache_tex_alias_pack", html_report), 0

    summary_rows = read_csv(summary)
    manifest_rows = read_csv(manifest)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    alias_assets = int_value(total, "alias_assets")
    existing_aliases = int_value(total, "existing_descriptor_aliases")
    synthetic_aliases = int_value(total, "synthetic_descriptor_aliases")
    missing_source = int_value(total, "missing_source_paths")
    missing_alias = int_value(total, "missing_alias_paths")
    target_mismatch = int_value(total, "target_mismatch_rows")
    issue_rows = int_value(total, "issue_rows")
    if alias_assets != len(manifest_rows):
        issues.append("alias_pack_asset_count_mismatch")
    if existing_aliases + synthetic_aliases != alias_assets:
        issues.append("alias_pack_kind_total_mismatch")
    if missing_source:
        issues.append(f"missing_source_paths:{missing_source}")
    if missing_alias:
        issues.append(f"missing_alias_paths:{missing_alias}")
    if target_mismatch:
        issues.append(f"target_mismatch_rows:{target_mismatch}")
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    missing_paths = 0
    for row in manifest_rows:
        for field in ("source_fullhd_path", "alias_pack_path"):
            value = row.get(field, "")
            if value and not Path(value).exists():
                missing_paths += 1
    if missing_paths:
        issues.append(f"missing_manifest_paths:{missing_paths}")
    if "const CDCACHE_TEX_ALIAS_PACK = " not in text:
        issues.append("missing_alias_pack_json")

    ok = not issues
    return (
        gate(
            "cdcache_tex_alias_pack",
            ok,
            expected=".tex CDCACHE alias pack symlinks target existing Full HD assets",
            actual=(
                f"assets={alias_assets}, existing={existing_aliases}, "
                f"synthetic={synthetic_aliases}, issues={issue_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        alias_assets if ok else 0,
    )


def audit_tex_material_decode_pack(
    summary: Path,
    manifest: Path,
    html_report: Path,
) -> tuple[dict[str, str], int]:
    if not summary.exists():
        return missing_gate("tex_material_decode_pack", summary), 0
    if not manifest.exists():
        return missing_gate("tex_material_decode_pack", manifest), 0
    if not html_report.exists():
        return missing_gate("tex_material_decode_pack", html_report), 0

    summary_rows = read_csv(summary)
    manifest_rows = read_csv(manifest)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    decoded_assets = int_value(total, "decoded_assets")
    unique_pcx = int_value(total, "unique_pcx")
    segments = int_value(total, "segments")
    fullhd_assets = int_value(total, "fullhd_assets")
    native_assets = int_value(total, "native_assets")
    issue_rows = int_value(total, "issue_rows")

    unique_names = {
        row.get("normalized_pcx_name", "")
        for row in manifest_rows
        if row.get("normalized_pcx_name")
    }
    segment_keys = {
        (row.get("archive", ""), row.get("normalized_pcx_name", ""), row.get("segment_index", ""), row.get("body_offset", ""))
        for row in manifest_rows
    }
    if decoded_assets != len(manifest_rows):
        issues.append("material_decode_asset_count_mismatch")
    if unique_pcx != len(unique_names):
        issues.append("material_decode_unique_pcx_mismatch")
    if segments != len(segment_keys):
        issues.append("material_decode_segment_count_mismatch")
    if fullhd_assets != sum(1 for row in manifest_rows if row.get("decoded_fullhd_exists") == "yes"):
        issues.append("material_decode_fullhd_asset_count_mismatch")
    if native_assets != sum(1 for row in manifest_rows if row.get("decoded_native_exists") == "yes"):
        issues.append("material_decode_native_asset_count_mismatch")
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    missing_paths = 0
    for row in manifest_rows:
        for field in ("source_fullhd_path", "source_native_path", "decoded_fullhd_path", "decoded_native_path"):
            value = row.get(field, "")
            if value and not Path(value).exists():
                missing_paths += 1
    if missing_paths:
        issues.append(f"missing_material_decode_paths:{missing_paths}")
    if "const TEX_MATERIAL_DECODE_PACK = " not in text:
        issues.append("missing_tex_material_decode_pack_json")

    ok = not issues
    return (
        gate(
            "tex_material_decode_pack",
            ok,
            expected=".tex material decode pack has valid source and output paths",
            actual=(
                f"assets={decoded_assets}, unique={unique_pcx}, segments={segments}, "
                f"issues={issue_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        decoded_assets if ok else 0,
    )


def audit_tex_raw_same_archive_promoted_pack(
    summary: Path,
    manifest: Path,
    html_report: Path,
) -> tuple[dict[str, str], int]:
    if not summary.exists():
        return missing_gate("tex_raw_same_archive_promoted_pack", summary), 0
    if not manifest.exists():
        return missing_gate("tex_raw_same_archive_promoted_pack", manifest), 0
    if not html_report.exists():
        return missing_gate("tex_raw_same_archive_promoted_pack", html_report), 0

    summary_rows = read_csv(summary)
    manifest_rows = read_csv(manifest)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    candidate_rows = int_value(total, "candidate_rows")
    unique_pcx = int_value(total, "unique_pcx")
    accepted_rows = int_value(total, "accepted_rows")
    pending_rows = int_value(total, "pending_rows")
    coverage_eligible_rows = int_value(total, "coverage_eligible_rows")
    native_assets = int_value(total, "native_assets")
    fullhd_assets = int_value(total, "fullhd_assets")
    accepted_fullhd_assets = int_value(total, "accepted_fullhd_assets")
    missing_source_paths = int_value(total, "missing_source_paths")
    missing_fullhd_paths = int_value(total, "missing_fullhd_paths")
    issue_rows = int_value(total, "issue_rows")

    unique_names = {
        row.get("normalized_pcx_name", "")
        for row in manifest_rows
        if row.get("normalized_pcx_name")
    }
    accepted = [row for row in manifest_rows if row.get("review_status") == "accepted"]
    pending = [row for row in manifest_rows if row.get("review_status") != "accepted"]
    eligible = [row for row in manifest_rows if row.get("coverage_eligible") == "yes"]

    if candidate_rows != len(manifest_rows):
        issues.append("raw_same_archive_candidate_count_mismatch")
    if unique_pcx != len(unique_names):
        issues.append("raw_same_archive_unique_pcx_mismatch")
    if accepted_rows != len(accepted):
        issues.append("raw_same_archive_accepted_count_mismatch")
    if pending_rows != len(pending):
        issues.append("raw_same_archive_pending_count_mismatch")
    if coverage_eligible_rows != len(eligible):
        issues.append("raw_same_archive_eligible_count_mismatch")
    if native_assets != sum(1 for row in manifest_rows if row.get("promoted_native_exists") == "yes"):
        issues.append("raw_same_archive_native_count_mismatch")
    if fullhd_assets != sum(1 for row in manifest_rows if row.get("promoted_fullhd_exists") == "yes"):
        issues.append("raw_same_archive_fullhd_count_mismatch")
    if accepted_fullhd_assets != sum(1 for row in accepted if row.get("promoted_fullhd_exists") == "yes"):
        issues.append("raw_same_archive_accepted_fullhd_count_mismatch")
    if missing_source_paths != sum(1 for row in manifest_rows if row.get("source_native_exists") != "yes"):
        issues.append("raw_same_archive_missing_source_count_mismatch")
    if missing_fullhd_paths != sum(1 for row in manifest_rows if row.get("promoted_fullhd_exists") != "yes"):
        issues.append("raw_same_archive_missing_fullhd_count_mismatch")
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")

    missing_paths = 0
    bad_dimensions = 0
    accepted_with_issues = 0
    for row in manifest_rows:
        if row.get("coverage_eligible") == "yes" and row.get("review_status") != "accepted":
            issues.append("raw_same_archive_eligible_not_accepted")
        if row.get("review_status") == "accepted" and row.get("issues"):
            accepted_with_issues += 1
        value = row.get("promoted_fullhd_path", "")
        if row.get("promoted_fullhd_exists") == "yes":
            if not value or not Path(value).exists():
                missing_paths += 1
            if (row.get("promoted_fullhd_width"), row.get("promoted_fullhd_height")) != (
                str(TARGET_SIZE[0]),
                str(TARGET_SIZE[1]),
            ):
                bad_dimensions += 1
    if missing_paths:
        issues.append(f"missing_raw_same_archive_paths:{missing_paths}")
    if bad_dimensions:
        issues.append(f"raw_same_archive_bad_dimensions:{bad_dimensions}")
    if accepted_with_issues:
        issues.append(f"accepted_raw_same_archive_rows_have_issues:{accepted_with_issues}")
    if "const TEX_RAW_SAME_ARCHIVE_PROMOTED_PACK = " not in text:
        issues.append("missing_tex_raw_same_archive_promoted_pack_json")

    ok = not issues
    return (
        gate(
            "tex_raw_same_archive_promoted_pack",
            ok,
            expected="raw same-archive .tex promotion pack has valid reviewed Full HD outputs",
            actual=(
                f"candidates={candidate_rows}, accepted={accepted_rows}, "
                f"eligible={coverage_eligible_rows}, pending={pending_rows}, issues={issue_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        coverage_eligible_rows if ok else 0,
    )


def audit_tex_augmented_coverage(
    summary: Path,
    references: Path,
    aliases: Path,
    material_decodes: Path,
    raw_same_archive_promotions: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int, int]:
    if not summary.exists():
        return missing_gate("tex_augmented_coverage", summary), 0, 0, 0, 0
    if not references.exists():
        return missing_gate("tex_augmented_coverage", references), 0, 0, 0, 0
    if not aliases.exists():
        return missing_gate("tex_augmented_coverage", aliases), 0, 0, 0, 0
    if not material_decodes.exists():
        return missing_gate("tex_augmented_coverage", material_decodes), 0, 0, 0, 0
    if not raw_same_archive_promotions.exists():
        return missing_gate("tex_augmented_coverage", raw_same_archive_promotions), 0, 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_augmented_coverage", html_report), 0, 0, 0, 0

    summary_rows = read_csv(summary)
    reference_rows = read_csv(references)
    alias_rows = read_csv(aliases)
    material_decode_rows = read_csv(material_decodes)
    raw_same_archive_rows = read_csv(raw_same_archive_promotions)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    reference_count = int_value(total, "reference_rows")
    unique_likely = int_value(total, "unique_likely_pcx")
    exact_unique = int_value(total, "exact_covered_unique_pcx")
    alias_reference_rows = int_value(total, "alias_reference_rows")
    alias_unique = int_value(total, "alias_unique_pcx")
    alias_assets = int_value(total, "alias_assets")
    decoded_reference_rows = int_value(total, "decoded_material_reference_rows")
    decoded_unique = int_value(total, "decoded_material_unique_pcx")
    decoded_assets = int_value(total, "decoded_material_assets")
    raw_reference_rows = int_value(total, "raw_same_archive_reference_rows")
    raw_unique = int_value(total, "raw_same_archive_unique_pcx")
    raw_assets = int_value(total, "raw_same_archive_assets")
    exact_or_alias = int_value(total, "exact_or_alias_unique_pcx")
    exact_alias_or_decoded = int_value(total, "exact_alias_or_decoded_unique_pcx")
    exact_alias_decoded_or_raw = int_value(total, "exact_alias_decoded_or_raw_unique_pcx")
    unresolved_unique = int_value(total, "unresolved_unique_pcx")
    issue_rows = int_value(total, "issue_rows")

    reference_names = {row.get("normalized_pcx_name", "") for row in reference_rows}
    exact_names = {
        row.get("normalized_pcx_name", "")
        for row in reference_rows
        if row.get("coverage_status") == "exact"
    }
    alias_names = {
        row.get("normalized_pcx_name", "")
        for row in reference_rows
        if row.get("coverage_status") == "alias"
    }
    decoded_names = {
        row.get("normalized_pcx_name", "")
        for row in reference_rows
        if row.get("coverage_status") == "decoded_material"
    }
    raw_names = {
        row.get("normalized_pcx_name", "")
        for row in reference_rows
        if row.get("coverage_status") == "raw_same_archive"
    }
    unresolved_names = {
        row.get("normalized_pcx_name", "")
        for row in reference_rows
        if row.get("coverage_status") == "unresolved"
    }
    eligible_raw = [row for row in raw_same_archive_rows if row.get("coverage_eligible") == "yes"]
    if reference_count != len(reference_rows):
        issues.append("tex_augmented_reference_count_mismatch")
    if unique_likely != len(reference_names):
        issues.append("tex_augmented_unique_count_mismatch")
    if exact_unique != len(exact_names):
        issues.append("tex_augmented_exact_unique_count_mismatch")
    if alias_reference_rows != sum(1 for row in reference_rows if row.get("coverage_status") == "alias"):
        issues.append("tex_augmented_alias_reference_count_mismatch")
    if alias_unique != len(alias_names):
        issues.append("tex_augmented_alias_unique_count_mismatch")
    if alias_assets != len(alias_rows):
        issues.append("tex_augmented_alias_asset_count_mismatch")
    if decoded_reference_rows != sum(1 for row in reference_rows if row.get("coverage_status") == "decoded_material"):
        issues.append("tex_augmented_decoded_reference_count_mismatch")
    if decoded_unique != len(decoded_names):
        issues.append("tex_augmented_decoded_unique_count_mismatch")
    if decoded_assets != len(material_decode_rows):
        issues.append("tex_augmented_decoded_asset_count_mismatch")
    if raw_reference_rows != sum(1 for row in reference_rows if row.get("coverage_status") == "raw_same_archive"):
        issues.append("tex_augmented_raw_reference_count_mismatch")
    if raw_unique != len(raw_names):
        issues.append("tex_augmented_raw_unique_count_mismatch")
    if raw_assets != len(eligible_raw):
        issues.append("tex_augmented_raw_asset_count_mismatch")
    if exact_or_alias != len(exact_names | alias_names):
        issues.append("tex_augmented_exact_or_alias_count_mismatch")
    if exact_alias_or_decoded != len(exact_names | alias_names | decoded_names):
        issues.append("tex_augmented_exact_alias_or_decoded_count_mismatch")
    if exact_alias_decoded_or_raw != len(exact_names | alias_names | decoded_names | raw_names):
        issues.append("tex_augmented_exact_alias_decoded_or_raw_count_mismatch")
    if unresolved_unique != len(unresolved_names):
        issues.append("tex_augmented_unresolved_unique_count_mismatch")
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    missing_alias_paths = 0
    for row in alias_rows:
        value = row.get("alias_pack_path", "")
        if value and not Path(value).exists():
            missing_alias_paths += 1
    if missing_alias_paths:
        issues.append(f"missing_alias_paths:{missing_alias_paths}")
    missing_decoded_paths = 0
    for row in material_decode_rows:
        value = row.get("decoded_fullhd_path", "")
        if value and not Path(value).exists():
            missing_decoded_paths += 1
        if row.get("issues"):
            issues.append("material_decode_row_has_issues")
    if missing_decoded_paths:
        issues.append(f"missing_material_decode_paths:{missing_decoded_paths}")
    missing_raw_paths = 0
    for row in eligible_raw:
        value = row.get("promoted_fullhd_path", "")
        if not value or not Path(value).exists():
            missing_raw_paths += 1
        if row.get("issues"):
            issues.append("raw_same_archive_row_has_issues")
    if missing_raw_paths:
        issues.append(f"missing_raw_same_archive_paths:{missing_raw_paths}")
    if "const TEX_AUGMENTED_COVERAGE = " not in text:
        issues.append("missing_tex_augmented_coverage_json")

    ok = not issues
    return (
        gate(
            "tex_augmented_coverage",
            ok,
            expected=".tex exact, alias and material decode coverage report is internally consistent",
            actual=(
                f"unique={unique_likely}, exact={exact_unique}, alias={alias_unique}, "
                f"decoded={decoded_unique}, raw={raw_unique}, "
                f"exact_alias_decoded_raw={exact_alias_decoded_or_raw}, "
                f"unresolved={unresolved_unique}, issues={issue_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        exact_or_alias if ok else 0,
        exact_alias_or_decoded if ok else 0,
        exact_alias_decoded_or_raw if ok else 0,
        unresolved_unique if ok else 0,
    )


def audit_tex_unresolved_material_probe(
    summary: Path,
    manifest: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int]:
    if not summary.exists():
        return missing_gate("tex_unresolved_material_probe", summary), 0, 0
    if not manifest.exists():
        return missing_gate("tex_unresolved_material_probe", manifest), 0, 0
    if not html_report.exists():
        return missing_gate("tex_unresolved_material_probe", html_report), 0, 0

    summary_rows = read_csv(summary)
    manifest_rows = read_csv(manifest)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    preview_rows = int_value(total, "preview_rows")
    fullhd_previews = int_value(total, "fullhd_previews")
    unique_pcx = int_value(total, "unique_pcx")
    archives = int_value(total, "archives")
    segments = int_value(total, "segments")
    issue_rows = int_value(total, "issue_rows")
    missing_native = int_value(total, "missing_native_paths")
    missing_fullhd = int_value(total, "missing_fullhd_paths")
    native_mismatch = int_value(total, "native_dimension_mismatch_rows")
    non_fullhd = int_value(total, "non_fullhd_rows")

    unique_segments = {
        (row.get("archive", ""), row.get("pcx_name", ""), row.get("segment_index", ""), row.get("body_offset", ""))
        for row in manifest_rows
    }
    if preview_rows != len(manifest_rows):
        issues.append("tex_probe_preview_count_mismatch")
    if fullhd_previews != sum(1 for row in manifest_rows if row.get("fullhd_exists") == "yes"):
        issues.append("tex_probe_fullhd_count_mismatch")
    if unique_pcx != len({row.get("pcx_name", "").lower() for row in manifest_rows if row.get("pcx_name")}):
        issues.append("tex_probe_unique_pcx_count_mismatch")
    if archives != len({row.get("archive", "") for row in manifest_rows if row.get("archive")}):
        issues.append("tex_probe_archive_count_mismatch")
    if segments != len(unique_segments):
        issues.append("tex_probe_segment_count_mismatch")
    if issue_rows != sum(1 for row in manifest_rows if row.get("issues")):
        issues.append("tex_probe_issue_count_mismatch")
    if missing_native:
        issues.append(f"missing_native_paths:{missing_native}")
    if missing_fullhd:
        issues.append(f"missing_fullhd_paths:{missing_fullhd}")
    if native_mismatch:
        issues.append(f"native_dimension_mismatch_rows:{native_mismatch}")
    if non_fullhd:
        issues.append(f"non_fullhd_rows:{non_fullhd}")

    missing_paths = 0
    bad_dimensions = 0
    for row in manifest_rows:
        for field in ("native_path", "fullhd_path"):
            value = row.get(field, "")
            if value and not Path(value).exists():
                missing_paths += 1
        if (row.get("fullhd_actual_width"), row.get("fullhd_actual_height")) != (
            str(TARGET_SIZE[0]),
            str(TARGET_SIZE[1]),
        ):
            bad_dimensions += 1
    if missing_paths:
        issues.append(f"missing_manifest_paths:{missing_paths}")
    if bad_dimensions:
        issues.append(f"bad_manifest_fullhd_dimensions:{bad_dimensions}")
    if "const TEX_UNRESOLVED_MATERIAL_PROBES = " not in text:
        issues.append("missing_tex_unresolved_probe_json")

    ok = not issues
    return (
        gate(
            "tex_unresolved_material_probe",
            ok,
            expected="unresolved .tex material probes have valid 1920x1080 diagnostic previews",
            actual=(
                f"previews={preview_rows}, fullhd={fullhd_previews}, "
                f"unique={unique_pcx}, segments={segments}, issues={issue_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        fullhd_previews if ok else 0,
        unique_pcx if ok else 0,
    )


def audit_tex_probe_analysis(
    summary: Path,
    analysis_rows_path: Path,
    best_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int]:
    if not summary.exists():
        return missing_gate("tex_probe_analysis", summary), 0, 0
    if not analysis_rows_path.exists():
        return missing_gate("tex_probe_analysis", analysis_rows_path), 0, 0
    if not best_rows_path.exists():
        return missing_gate("tex_probe_analysis", best_rows_path), 0, 0
    if not html_report.exists():
        return missing_gate("tex_probe_analysis", html_report), 0, 0

    summary_rows = read_csv(summary)
    analysis_rows = read_csv(analysis_rows_path)
    best_rows = read_csv(best_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    preview_rows = int_value(total, "preview_rows")
    analyzed_rows = int_value(total, "analyzed_rows")
    best_candidate_rows = int_value(total, "best_candidate_rows")
    unique_pcx = int_value(total, "unique_pcx")
    segments = int_value(total, "segments")
    issue_rows = int_value(total, "issue_rows")

    unique_segments = {
        (row.get("archive", ""), row.get("pcx_name", ""), row.get("segment_index", ""), row.get("body_offset", ""))
        for row in analysis_rows
    }
    if preview_rows != len(analysis_rows):
        issues.append("tex_probe_analysis_row_count_mismatch")
    if analyzed_rows != sum(1 for row in analysis_rows if not row.get("issues")):
        issues.append("tex_probe_analysis_analyzed_count_mismatch")
    if best_candidate_rows != len(best_rows):
        issues.append("tex_probe_analysis_best_count_mismatch")
    if unique_pcx != len({row.get("pcx_name", "").lower() for row in analysis_rows if row.get("pcx_name")}):
        issues.append("tex_probe_analysis_unique_pcx_count_mismatch")
    if segments != len(unique_segments):
        issues.append("tex_probe_analysis_segment_count_mismatch")
    if issue_rows != sum(1 for row in analysis_rows if row.get("issues")):
        issues.append("tex_probe_analysis_issue_count_mismatch")
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    missing_paths = 0
    for row in best_rows:
        for field in ("native_path", "fullhd_path"):
            value = row.get(field, "")
            if value and not Path(value).exists():
                missing_paths += 1
    if missing_paths:
        issues.append(f"missing_best_candidate_paths:{missing_paths}")
    if "const TEX_PROBE_ANALYSIS = " not in text:
        issues.append("missing_tex_probe_analysis_json")

    ok = not issues
    return (
        gate(
            "tex_probe_analysis",
            ok,
            expected=".tex probe ranking report is internally consistent and links to existing previews",
            actual=(
                f"analyzed={analyzed_rows}/{preview_rows}, segments={segments}, "
                f"best={best_candidate_rows}, issues={issue_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        best_candidate_rows if ok else 0,
        segments if ok else 0,
    )


def audit_tex_material_decoder_queue(
    summary: Path,
    queue_rows_path: Path,
    prefix_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int]:
    if not summary.exists():
        return missing_gate("tex_material_decoder_queue", summary), 0, 0
    if not queue_rows_path.exists():
        return missing_gate("tex_material_decoder_queue", queue_rows_path), 0, 0
    if not prefix_rows_path.exists():
        return missing_gate("tex_material_decoder_queue", prefix_rows_path), 0, 0
    if not html_report.exists():
        return missing_gate("tex_material_decoder_queue", html_report), 0, 0

    summary_rows = read_csv(summary)
    queue_rows = read_csv(queue_rows_path)
    prefix_rows = read_csv(prefix_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    material_rows = int_value(total, "material_link_rows")
    unique_pcx = int_value(total, "unique_pcx")
    exact_rows = int_value(total, "exact_rows")
    alias_rows = int_value(total, "alias_rows")
    decoded_material_rows = int_value(total, "decoded_material_rows")
    decoded_material_segments = int_value(total, "decoded_material_segments")
    unresolved_rows = int_value(total, "unresolved_rows")
    unresolved_unique = int_value(total, "unresolved_unique_pcx")
    unresolved_segments = int_value(total, "unresolved_segments")
    queued_probe_rows = int_value(total, "queued_probe_rows")
    queued_probe_segments = int_value(total, "queued_probe_segments")
    coverage_missing = int_value(total, "coverage_missing_rows")
    issue_rows = int_value(total, "issue_rows")

    status_counts = Counter(row.get("coverage_status", "") for row in queue_rows)
    unique_names = {row.get("normalized_pcx_name", "") for row in queue_rows if row.get("normalized_pcx_name")}
    unresolved_names = {
        row.get("normalized_pcx_name", "")
        for row in queue_rows
        if row.get("coverage_status") == "unresolved"
    }
    decoded_material_segment_keys = {
        (row.get("archive", ""), row.get("normalized_pcx_name", ""), row.get("texture_segment_index", ""), row.get("texture_body_offset", ""))
        for row in queue_rows
        if row.get("coverage_status") == "decoded_material"
    }
    unresolved_segment_keys = {
        (row.get("archive", ""), row.get("normalized_pcx_name", ""), row.get("texture_segment_index", ""), row.get("texture_body_offset", ""))
        for row in queue_rows
        if row.get("coverage_status") == "unresolved"
    }
    queued_segment_keys = {
        (row.get("archive", ""), row.get("normalized_pcx_name", ""), row.get("texture_segment_index", ""), row.get("texture_body_offset", ""))
        for row in queue_rows
        if row.get("priority") == "decode_probe"
    }
    prefix_keys = {
        (row.get("texture_body_first_word", ""), row.get("coverage_status", ""))
        for row in queue_rows
    }

    if material_rows != len(queue_rows):
        issues.append("decoder_queue_row_count_mismatch")
    if unique_pcx != len(unique_names):
        issues.append("decoder_queue_unique_pcx_count_mismatch")
    if exact_rows != status_counts.get("exact", 0):
        issues.append("decoder_queue_exact_count_mismatch")
    if alias_rows != status_counts.get("alias", 0):
        issues.append("decoder_queue_alias_count_mismatch")
    if decoded_material_rows != status_counts.get("decoded_material", 0):
        issues.append("decoder_queue_decoded_material_count_mismatch")
    if decoded_material_segments != len(decoded_material_segment_keys):
        issues.append("decoder_queue_decoded_material_segment_count_mismatch")
    if unresolved_rows != status_counts.get("unresolved", 0):
        issues.append("decoder_queue_unresolved_count_mismatch")
    if unresolved_unique != len(unresolved_names):
        issues.append("decoder_queue_unresolved_unique_count_mismatch")
    if unresolved_segments != len(unresolved_segment_keys):
        issues.append("decoder_queue_unresolved_segment_count_mismatch")
    if queued_probe_rows != sum(1 for row in queue_rows if row.get("priority") == "decode_probe"):
        issues.append("decoder_queue_probe_row_count_mismatch")
    if queued_probe_segments != len(queued_segment_keys):
        issues.append("decoder_queue_probe_segment_count_mismatch")
    if coverage_missing:
        issues.append(f"coverage_missing_rows:{coverage_missing}")
    if issue_rows or issue_rows != sum(1 for row in queue_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if len(prefix_rows) != len(prefix_keys):
        issues.append("decoder_queue_prefix_count_mismatch")

    missing_paths = 0
    for row in queue_rows:
        value = row.get("best_probe_fullhd_path", "")
        if value and not Path(value).exists():
            missing_paths += 1
    if missing_paths:
        issues.append(f"missing_probe_paths:{missing_paths}")
    if "const TEX_MATERIAL_DECODER_QUEUE = " not in text:
        issues.append("missing_tex_material_decoder_queue_json")

    ok = not issues
    return (
        gate(
            "tex_material_decoder_queue",
            ok,
            expected="material-linked .tex decoder queue is internally consistent",
            actual=(
                f"rows={material_rows}, exact={exact_rows}, alias={alias_rows}, "
                f"unresolved={unresolved_rows}, queued_segments={queued_probe_segments}, issues={issue_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        material_rows if ok else 0,
        queued_probe_segments if ok else 0,
    )


def audit_tex_remaining_reference_profile(
    summary: Path,
    profile_rows_path: Path,
    archive_rows_path: Path,
    prefix_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int]:
    if not summary.exists():
        return missing_gate("tex_remaining_reference_profile", summary), 0
    if not profile_rows_path.exists():
        return missing_gate("tex_remaining_reference_profile", profile_rows_path), 0
    if not archive_rows_path.exists():
        return missing_gate("tex_remaining_reference_profile", archive_rows_path), 0
    if not prefix_rows_path.exists():
        return missing_gate("tex_remaining_reference_profile", prefix_rows_path), 0
    if not html_report.exists():
        return missing_gate("tex_remaining_reference_profile", html_report), 0

    summary_rows = read_csv(summary)
    profile_rows = read_csv(profile_rows_path)
    archive_rows = read_csv(archive_rows_path)
    prefix_rows = read_csv(prefix_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    unresolved_rows = int_value(total, "unresolved_reference_rows")
    unresolved_unique = int_value(total, "unresolved_unique_pcx")
    archives = int_value(total, "archives")
    raw_same_archive_unique = int_value(total, "raw_same_archive_unique")
    tex_segment_only_unique = int_value(total, "tex_segment_only_unique")
    large_segment_unique = int_value(total, "large_segment_unique")
    issue_rows = int_value(total, "issue_rows")

    unique_names = {
        row.get("normalized_pcx_name", "")
        for row in profile_rows
        if row.get("normalized_pcx_name")
    }
    archive_keys = {row.get("archive", "") for row in profile_rows if row.get("archive")}
    raw_same_names = {
        row.get("normalized_pcx_name", "")
        for row in profile_rows
        if row.get("normalized_pcx_name") and int_value(row, "raw_cache_same_archive_refs") > 0
    }
    segment_only_names = {
        row.get("normalized_pcx_name", "")
        for row in profile_rows
        if row.get("normalized_pcx_name") and row.get("evidence_class") == "tex_segment_only"
    }
    large_segment_names = {
        row.get("normalized_pcx_name", "")
        for row in profile_rows
        if row.get("normalized_pcx_name") and int_value(row, "texture_segment_size_total") >= 1_000_000
    }

    if unresolved_rows != len(profile_rows):
        issues.append("remaining_profile_row_count_mismatch")
    if unresolved_unique != len(unique_names):
        issues.append("remaining_profile_unique_pcx_mismatch")
    if archives != len(archive_keys):
        issues.append("remaining_profile_archive_count_mismatch")
    if raw_same_archive_unique != len(raw_same_names):
        issues.append("remaining_profile_raw_same_archive_mismatch")
    if tex_segment_only_unique != len(segment_only_names):
        issues.append("remaining_profile_segment_only_mismatch")
    if large_segment_unique != len(large_segment_names):
        issues.append("remaining_profile_large_segment_mismatch")
    if issue_rows or issue_rows != sum(1 for row in profile_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if len(archive_rows) != len(archive_keys):
        issues.append("remaining_profile_archive_rows_mismatch")
    if profile_rows and not prefix_rows:
        issues.append("remaining_profile_missing_prefix_rows")
    if "const TEX_REMAINING_REFERENCE_PROFILE = " not in text:
        issues.append("missing_tex_remaining_reference_profile_json")

    ok = not issues
    return (
        gate(
            "tex_remaining_reference_profile",
            ok,
            expected="remaining unresolved .tex references are profiled consistently",
            actual=(
                f"rows={unresolved_rows}, unique={unresolved_unique}, "
                f"raw_same_archive={raw_same_archive_unique}, issues={issue_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        unresolved_unique if ok else 0,
    )


def audit_tex_exact_cdcache_compare(
    summary: Path,
    comparison_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_exact_cdcache_compare", summary), 0, 0, 0
    if not comparison_rows_path.exists():
        return missing_gate("tex_exact_cdcache_compare", comparison_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_exact_cdcache_compare", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    comparison_rows = read_csv(comparison_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    exact_segments = int_value(total, "exact_segments")
    segments_with_32 = int_value(total, "segments_with_32_byte_match")
    segments_with_16 = int_value(total, "segments_with_16_byte_match")
    issue_rows = int_value(total, "issue_rows")
    rows_with_32 = sum(1 for row in comparison_rows if int_value(row, "chunks_32_found") > 0)
    rows_with_16 = sum(1 for row in comparison_rows if int_value(row, "chunks_16_found") > 0)

    if exact_segments != len(comparison_rows):
        issues.append("exact_cdcache_compare_row_count_mismatch")
    if segments_with_32 != rows_with_32:
        issues.append("exact_cdcache_compare_32b_count_mismatch")
    if segments_with_16 != rows_with_16:
        issues.append("exact_cdcache_compare_16b_count_mismatch")
    if issue_rows or issue_rows != sum(1 for row in comparison_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")

    missing_paths = 0
    for row in comparison_rows:
        native_path = row.get("cdcache_native_path", "")
        if native_path and not Path(native_path).exists():
            missing_paths += 1
    if missing_paths:
        issues.append(f"missing_cdcache_native_paths:{missing_paths}")
    if "const TEX_EXACT_CDCACHE_COMPARE = " not in text:
        issues.append("missing_tex_exact_cdcache_compare_json")

    ok = not issues
    return (
        gate(
            "tex_exact_cdcache_compare",
            ok,
            expected="exact material .tex segments are compared against decoded CDCACHE pixel exports",
            actual=(
                f"segments={exact_segments}, 32b_matches={segments_with_32}, "
                f"16b_matches={segments_with_16}, issues={issue_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        exact_segments if ok else 0,
        segments_with_32 if ok else 0,
        segments_with_16 if ok else 0,
    )


def audit_tex_exact_chunk_evidence(
    summary: Path,
    match_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int]:
    if not summary.exists():
        return missing_gate("tex_exact_chunk_evidence", summary), 0, 0
    if not match_rows_path.exists():
        return missing_gate("tex_exact_chunk_evidence", match_rows_path), 0, 0
    if not html_report.exists():
        return missing_gate("tex_exact_chunk_evidence", html_report), 0, 0

    summary_rows = read_csv(summary)
    match_rows = read_csv(match_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    segments = int_value(total, "segments")
    matched_segments = int_value(total, "matched_segments")
    match_count = int_value(total, "match_rows")
    chunks_32 = int_value(total, "chunks_32_rows")
    chunks_16 = int_value(total, "chunks_16_rows")
    chunks_8 = int_value(total, "chunks_8_rows")
    issue_rows = int_value(total, "issue_rows")
    rows_with_matches = [row for row in match_rows if row.get("segment_offset")]
    matched_segment_keys = {
        (row.get("archive", ""), row.get("pcx_name", ""))
        for row in rows_with_matches
        if not row.get("issues")
    }

    if segments < matched_segments:
        issues.append("chunk_evidence_segment_count_invalid")
    if matched_segments != len(matched_segment_keys):
        issues.append("chunk_evidence_matched_segment_count_mismatch")
    if match_count != len(rows_with_matches):
        issues.append("chunk_evidence_match_count_mismatch")
    if chunks_32 != sum(1 for row in match_rows if row.get("chunk_size") == "32"):
        issues.append("chunk_evidence_32b_count_mismatch")
    if chunks_16 != sum(1 for row in match_rows if row.get("chunk_size") == "16"):
        issues.append("chunk_evidence_16b_count_mismatch")
    if chunks_8 != sum(1 for row in match_rows if row.get("chunk_size") == "8"):
        issues.append("chunk_evidence_8b_count_mismatch")
    if issue_rows or issue_rows != sum(1 for row in match_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if "const TEX_EXACT_CHUNK_EVIDENCE = " not in text:
        issues.append("missing_tex_exact_chunk_evidence_json")

    ok = not issues
    return (
        gate(
            "tex_exact_chunk_evidence",
            ok,
            expected="direct .tex/CDCACHE chunk evidence is internally consistent",
            actual=(
                f"segments={segments}, matched_segments={matched_segments}, "
                f"matches={match_count}, 32/16/8={chunks_32}/{chunks_16}/{chunks_8}, "
                f"issues={issue_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        match_count if ok else 0,
        matched_segments if ok else 0,
    )


def audit_tex_exact_match_overlays(
    summary: Path,
    overlay_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int]:
    if not summary.exists():
        return missing_gate("tex_exact_match_overlays", summary), 0, 0
    if not overlay_rows_path.exists():
        return missing_gate("tex_exact_match_overlays", overlay_rows_path), 0, 0
    if not html_report.exists():
        return missing_gate("tex_exact_match_overlays", html_report), 0, 0

    summary_rows = read_csv(summary)
    overlay_rows = read_csv(overlay_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    overlays = int_value(total, "overlays")
    fullhd_overlays = int_value(total, "fullhd_overlays")
    matched_segments = int_value(total, "matched_segments")
    covered_pixels = int_value(total, "covered_pixels")
    issue_rows = int_value(total, "issue_rows")
    fullhd_rows = [
        row
        for row in overlay_rows
        if (row.get("fullhd_width"), row.get("fullhd_height")) == (str(TARGET_SIZE[0]), str(TARGET_SIZE[1]))
    ]
    matched_segment_keys = {
        (row.get("archive", ""), row.get("pcx_name", ""))
        for row in overlay_rows
        if row.get("archive") and row.get("pcx_name")
    }

    if overlays != len(overlay_rows):
        issues.append("match_overlay_row_count_mismatch")
    if fullhd_overlays != len(fullhd_rows):
        issues.append("match_overlay_fullhd_count_mismatch")
    if matched_segments != len(matched_segment_keys):
        issues.append("match_overlay_segment_count_mismatch")
    if covered_pixels != sum(int_value(row, "covered_pixels") for row in overlay_rows):
        issues.append("match_overlay_covered_pixel_count_mismatch")
    if issue_rows or issue_rows != sum(1 for row in overlay_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")

    missing_paths = 0
    for row in overlay_rows:
        for field in ("native_overlay_path", "fullhd_overlay_path"):
            value = row.get(field, "")
            if value and not Path(value).exists():
                missing_paths += 1
    if missing_paths:
        issues.append(f"missing_overlay_paths:{missing_paths}")
    if "const TEX_EXACT_MATCH_OVERLAYS = " not in text:
        issues.append("missing_tex_exact_match_overlays_json")

    ok = not issues
    return (
        gate(
            "tex_exact_match_overlays",
            ok,
            expected="direct .tex chunk overlays are valid 1920x1080 PNG artifacts",
            actual=(
                f"overlays={overlays}, fullhd={fullhd_overlays}, "
                f"segments={matched_segments}, covered_pixels={covered_pixels}, issues={issue_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        fullhd_overlays if ok else 0,
        covered_pixels if ok else 0,
    )


def audit_tex_decoder_seed_report(
    summary: Path,
    seed_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int]:
    if not summary.exists():
        return missing_gate("tex_decoder_seed_report", summary), 0, 0
    if not seed_rows_path.exists():
        return missing_gate("tex_decoder_seed_report", seed_rows_path), 0, 0
    if not html_report.exists():
        return missing_gate("tex_decoder_seed_report", html_report), 0, 0

    summary_rows = read_csv(summary)
    seed_rows = read_csv(seed_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    match_rows = int_value(total, "match_rows")
    seed_count = int_value(total, "seed_rows")
    strong_count = int_value(total, "strong_seed_rows")
    medium_count = int_value(total, "medium_seed_rows")
    weak_count = int_value(total, "weak_seed_rows")
    unique_pcx = int_value(total, "unique_pcx")
    issue_rows = int_value(total, "issue_rows")
    valid_rows = [row for row in seed_rows if not row.get("issues")]
    class_counts = Counter(row.get("seed_class", "") for row in valid_rows)

    if match_rows != len(seed_rows):
        issues.append("seed_report_match_row_count_mismatch")
    if seed_count != len(valid_rows):
        issues.append("seed_report_seed_row_count_mismatch")
    if strong_count != class_counts.get("strong", 0):
        issues.append("seed_report_strong_count_mismatch")
    if medium_count != class_counts.get("medium", 0):
        issues.append("seed_report_medium_count_mismatch")
    if weak_count != class_counts.get("weak", 0):
        issues.append("seed_report_weak_count_mismatch")
    if unique_pcx != len({row.get("pcx_name", "") for row in valid_rows if row.get("pcx_name")}):
        issues.append("seed_report_unique_pcx_count_mismatch")
    if issue_rows or issue_rows != sum(1 for row in seed_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if strong_count < 1:
        issues.append("missing_strong_decoder_seeds")
    if "const TEX_DECODER_SEED_REPORT = " not in text:
        issues.append("missing_tex_decoder_seed_report_json")

    ok = not issues
    return (
        gate(
            "tex_decoder_seed_report",
            ok,
            expected="direct chunk matches are ranked into decoder seed candidates",
            actual=(
                f"matches={match_rows}, seeds={seed_count}, strong={strong_count}, "
                f"medium={medium_count}, weak={weak_count}, issues={issue_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        strong_count if ok else 0,
        medium_count if ok else 0,
    )


def audit_tex_exact_chunk_scan(
    summary: Path,
    scan_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int]:
    if not summary.exists():
        return missing_gate("tex_exact_chunk_scan", summary), 0, 0
    if not scan_rows_path.exists():
        return missing_gate("tex_exact_chunk_scan", scan_rows_path), 0, 0
    if not html_report.exists():
        return missing_gate("tex_exact_chunk_scan", html_report), 0, 0

    summary_rows = read_csv(summary)
    scan_rows = read_csv(scan_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    segments = int_value(total, "segments")
    matched_segments = int_value(total, "matched_segments")
    scan_count = int_value(total, "scan_rows")
    capped_groups = int_value(total, "capped_segment_size_groups")
    issue_rows = int_value(total, "issue_rows")
    rows_with_matches = [row for row in scan_rows if row.get("segment_offset")]
    matched_segment_keys = {
        (row.get("archive", ""), row.get("pcx_name", ""))
        for row in rows_with_matches
        if not row.get("issues")
    }

    if segments < matched_segments:
        issues.append("chunk_scan_segment_count_invalid")
    if matched_segments != len(matched_segment_keys):
        issues.append("chunk_scan_matched_segment_count_mismatch")
    if scan_count != len(rows_with_matches):
        issues.append("chunk_scan_row_count_mismatch")
    if not total.get("chunk_sizes"):
        issues.append("missing_chunk_scan_sizes")
    if not total.get("max_rows_per_segment_size"):
        issues.append("missing_chunk_scan_cap")
    if issue_rows or issue_rows != sum(1 for row in scan_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if scan_count < 1:
        issues.append("missing_chunk_scan_rows")
    if "const TEX_EXACT_CHUNK_SCAN = " not in text:
        issues.append("missing_tex_exact_chunk_scan_json")

    ok = not issues
    return (
        gate(
            "tex_exact_chunk_scan",
            ok,
            expected="high-signal exact .tex/CDCACHE chunk scan is internally consistent",
            actual=(
                f"segments={segments}, matched_segments={matched_segments}, "
                f"scan_rows={scan_count}, capped_groups={capped_groups}, issues={issue_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        scan_count if ok else 0,
        capped_groups if ok else 0,
    )


def audit_tex_exact_chunk_clusters(
    summary: Path,
    cluster_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_exact_chunk_clusters", summary), 0, 0, 0
    if not cluster_rows_path.exists():
        return missing_gate("tex_exact_chunk_clusters", cluster_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_exact_chunk_clusters", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    cluster_rows = read_csv(cluster_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    scan_count = int_value(total, "scan_rows")
    cluster_count = int_value(total, "clusters")
    matched_segments = int_value(total, "matched_segments")
    strong_count = int_value(total, "strong_clusters")
    medium_count = int_value(total, "medium_clusters")
    weak_count = int_value(total, "weak_clusters")
    longest_span = int_value(total, "longest_pixel_span")
    issue_rows = int_value(total, "issue_rows")
    valid_rows = [row for row in cluster_rows if not row.get("issues")]
    class_counts = Counter(row.get("cluster_class", "") for row in valid_rows)
    matched_segment_keys = {
        (row.get("archive", ""), row.get("pcx_name", ""))
        for row in valid_rows
        if row.get("archive") and row.get("pcx_name")
    }

    if scan_count < cluster_count:
        issues.append("chunk_cluster_scan_count_invalid")
    if cluster_count != len(valid_rows):
        issues.append("chunk_cluster_row_count_mismatch")
    if matched_segments != len(matched_segment_keys):
        issues.append("chunk_cluster_matched_segment_count_mismatch")
    if strong_count != class_counts.get("strong", 0):
        issues.append("chunk_cluster_strong_count_mismatch")
    if medium_count != class_counts.get("medium", 0):
        issues.append("chunk_cluster_medium_count_mismatch")
    if weak_count != class_counts.get("weak", 0):
        issues.append("chunk_cluster_weak_count_mismatch")
    if longest_span != max((int_value(row, "pixel_span_bytes") for row in valid_rows), default=0):
        issues.append("chunk_cluster_longest_span_mismatch")
    if issue_rows or issue_rows != sum(1 for row in cluster_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if cluster_count < 1:
        issues.append("missing_chunk_clusters")
    if strong_count < 1:
        issues.append("missing_strong_chunk_clusters")
    if "const TEX_EXACT_CHUNK_CLUSTERS = " not in text:
        issues.append("missing_tex_exact_chunk_clusters_json")

    ok = not issues
    return (
        gate(
            "tex_exact_chunk_clusters",
            ok,
            expected="exact .tex/CDCACHE chunk matches are clustered into decoder runs",
            actual=(
                f"scan_rows={scan_count}, clusters={cluster_count}, strong={strong_count}, "
                f"medium={medium_count}, weak={weak_count}, longest_span={longest_span}, issues={issue_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        cluster_count if ok else 0,
        strong_count if ok else 0,
        longest_span if ok else 0,
    )


def audit_tex_exact_cluster_overlays(
    summary: Path,
    overlay_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int]:
    if not summary.exists():
        return missing_gate("tex_exact_cluster_overlays", summary), 0, 0
    if not overlay_rows_path.exists():
        return missing_gate("tex_exact_cluster_overlays", overlay_rows_path), 0, 0
    if not html_report.exists():
        return missing_gate("tex_exact_cluster_overlays", html_report), 0, 0

    summary_rows = read_csv(summary)
    overlay_rows = read_csv(overlay_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    overlays = int_value(total, "overlays")
    fullhd_overlays = int_value(total, "fullhd_overlays")
    matched_segments = int_value(total, "matched_segments")
    clusters = int_value(total, "clusters")
    strong_clusters = int_value(total, "strong_clusters")
    covered_pixels = int_value(total, "covered_pixels")
    longest_span = int_value(total, "longest_span")
    issue_rows = int_value(total, "issue_rows")
    valid_rows = [row for row in overlay_rows if not row.get("issues")]
    fullhd_rows = [
        row
        for row in valid_rows
        if (row.get("fullhd_width"), row.get("fullhd_height"))
        == (str(TARGET_SIZE[0]), str(TARGET_SIZE[1]))
    ]

    if overlays != len(overlay_rows):
        issues.append("cluster_overlay_row_count_mismatch")
    if fullhd_overlays != len(fullhd_rows):
        issues.append("cluster_overlay_fullhd_count_mismatch")
    if matched_segments != len({(row.get("archive", ""), row.get("pcx_name", "")) for row in valid_rows}):
        issues.append("cluster_overlay_segment_count_mismatch")
    if clusters != sum(int_value(row, "clusters") for row in valid_rows):
        issues.append("cluster_overlay_cluster_count_mismatch")
    if strong_clusters != sum(int_value(row, "strong_clusters") for row in valid_rows):
        issues.append("cluster_overlay_strong_count_mismatch")
    if covered_pixels != sum(int_value(row, "covered_pixels") for row in valid_rows):
        issues.append("cluster_overlay_covered_pixel_mismatch")
    if longest_span != max((int_value(row, "longest_span") for row in valid_rows), default=0):
        issues.append("cluster_overlay_longest_span_mismatch")
    if issue_rows or issue_rows != sum(1 for row in overlay_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    missing_paths = 0
    for row in valid_rows:
        for field in ("native_overlay_path", "fullhd_overlay_path"):
            value = row.get(field, "")
            if value and not Path(value).exists():
                missing_paths += 1
    if missing_paths:
        issues.append(f"missing_overlay_paths:{missing_paths}")
    if fullhd_overlays < 1:
        issues.append("missing_cluster_fullhd_overlays")
    if covered_pixels < 1:
        issues.append("missing_cluster_overlay_pixels")
    if "const TEX_EXACT_CLUSTER_OVERLAYS = " not in text:
        issues.append("missing_tex_exact_cluster_overlays_json")

    ok = not issues
    return (
        gate(
            "tex_exact_cluster_overlays",
            ok,
            expected="clustered .tex decoder runs render as valid 1920x1080 PNG overlays",
            actual=(
                f"overlays={overlays}, fullhd={fullhd_overlays}, clusters={clusters}, "
                f"strong={strong_clusters}, covered_pixels={covered_pixels}, "
                f"longest_span={longest_span}, issues={issue_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        fullhd_overlays if ok else 0,
        covered_pixels if ok else 0,
    )


def audit_tex_decoder_run_corpus(
    summary: Path,
    run_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int]:
    if not summary.exists():
        return missing_gate("tex_decoder_run_corpus", summary), 0, 0
    if not run_rows_path.exists():
        return missing_gate("tex_decoder_run_corpus", run_rows_path), 0, 0
    if not html_report.exists():
        return missing_gate("tex_decoder_run_corpus", html_report), 0, 0

    summary_rows = read_csv(summary)
    run_rows = read_csv(run_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    clusters = int_value(total, "clusters")
    extracted_runs = int_value(total, "extracted_runs")
    exact_runs = int_value(total, "byte_exact_runs")
    mismatch_runs = int_value(total, "byte_mismatch_runs")
    total_exact_bytes = int_value(total, "total_exact_bytes")
    longest_exact_bytes = int_value(total, "longest_exact_bytes")
    unique_pcx = int_value(total, "unique_pcx")
    issue_rows = int_value(total, "issue_rows")
    valid_rows = [row for row in run_rows if not row.get("issues")]
    exact_rows = [row for row in valid_rows if row.get("byte_equal") == "1"]

    if clusters != len(run_rows):
        issues.append("run_corpus_cluster_count_mismatch")
    if extracted_runs != len(run_rows):
        issues.append("run_corpus_row_count_mismatch")
    if exact_runs != len(exact_rows):
        issues.append("run_corpus_exact_count_mismatch")
    if mismatch_runs != sum(1 for row in run_rows if "run_bytes_mismatch" in row.get("issues", "")):
        issues.append("run_corpus_mismatch_count_mismatch")
    if total_exact_bytes != sum(int_value(row, "run_bytes") for row in exact_rows):
        issues.append("run_corpus_total_exact_bytes_mismatch")
    if longest_exact_bytes != max((int_value(row, "run_bytes") for row in exact_rows), default=0):
        issues.append("run_corpus_longest_exact_bytes_mismatch")
    if unique_pcx != len({row.get("pcx_name", "") for row in run_rows if row.get("pcx_name")}):
        issues.append("run_corpus_unique_pcx_mismatch")
    if issue_rows or issue_rows != sum(1 for row in run_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    missing_paths = 0
    for row in exact_rows:
        for field in ("segment_bin_path", "pixel_bin_path"):
            value = row.get(field, "")
            if value and not Path(value).exists():
                missing_paths += 1
    if missing_paths:
        issues.append(f"missing_run_bins:{missing_paths}")
    if exact_runs < 1:
        issues.append("missing_byte_exact_runs")
    if total_exact_bytes < 1:
        issues.append("missing_byte_exact_payload")
    if mismatch_runs:
        issues.append(f"byte_mismatch_runs:{mismatch_runs}")
    if "const TEX_DECODER_RUN_CORPUS = " not in text:
        issues.append("missing_tex_decoder_run_corpus_json")

    ok = not issues
    return (
        gate(
            "tex_decoder_run_corpus",
            ok,
            expected="clustered .tex/CDCACHE runs extract into byte-identical decoder fixtures",
            actual=(
                f"runs={extracted_runs}, byte_exact={exact_runs}, mismatches={mismatch_runs}, "
                f"bytes={total_exact_bytes}, longest={longest_exact_bytes}, issues={issue_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        exact_runs if ok else 0,
        total_exact_bytes if ok else 0,
    )


def audit_tex_partial_raw_decoder(
    summary: Path,
    manifest_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int]:
    if not summary.exists():
        return missing_gate("tex_partial_raw_decoder", summary), 0, 0
    if not manifest_path.exists():
        return missing_gate("tex_partial_raw_decoder", manifest_path), 0, 0
    if not html_report.exists():
        return missing_gate("tex_partial_raw_decoder", html_report), 0, 0

    summary_rows = read_csv(summary)
    manifest_rows = read_csv(manifest_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    decoded_textures = int_value(total, "decoded_textures")
    fullhd_outputs = int_value(total, "fullhd_outputs")
    raw_runs = int_value(total, "raw_runs")
    raw_bytes = int_value(total, "raw_bytes")
    covered_pixels = int_value(total, "covered_pixels")
    verified_pixels = int_value(total, "verified_pixels")
    mismatched_pixels = int_value(total, "mismatched_pixels")
    issue_rows = int_value(total, "issue_rows")
    valid_rows = [row for row in manifest_rows if not row.get("issues")]
    fullhd_rows = [
        row
        for row in valid_rows
        if (row.get("fullhd_width"), row.get("fullhd_height"))
        == (str(TARGET_SIZE[0]), str(TARGET_SIZE[1]))
    ]

    if decoded_textures != len(manifest_rows):
        issues.append("partial_decoder_row_count_mismatch")
    if fullhd_outputs != len(fullhd_rows):
        issues.append("partial_decoder_fullhd_count_mismatch")
    if raw_runs != sum(int_value(row, "raw_runs") for row in valid_rows):
        issues.append("partial_decoder_run_count_mismatch")
    if raw_bytes != sum(int_value(row, "raw_bytes") for row in valid_rows):
        issues.append("partial_decoder_raw_byte_count_mismatch")
    if covered_pixels != sum(int_value(row, "covered_pixels") for row in valid_rows):
        issues.append("partial_decoder_covered_pixel_mismatch")
    if verified_pixels != sum(int_value(row, "verified_pixels") for row in valid_rows):
        issues.append("partial_decoder_verified_pixel_mismatch")
    if mismatched_pixels != sum(int_value(row, "mismatched_pixels") for row in valid_rows):
        issues.append("partial_decoder_mismatch_count_mismatch")
    if issue_rows or issue_rows != sum(1 for row in manifest_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    missing_paths = 0
    for row in valid_rows:
        for field in ("native_output_path", "fullhd_output_path"):
            value = row.get(field, "")
            if value and not Path(value).exists():
                missing_paths += 1
    if missing_paths:
        issues.append(f"missing_partial_decode_paths:{missing_paths}")
    if fullhd_outputs < 1:
        issues.append("missing_partial_fullhd_outputs")
    if raw_bytes < 1:
        issues.append("missing_partial_raw_bytes")
    if mismatched_pixels:
        issues.append(f"partial_decoder_mismatched_pixels:{mismatched_pixels}")
    if "const TEX_PARTIAL_RAW_DECODER = " not in text:
        issues.append("missing_tex_partial_raw_decoder_json")

    ok = not issues
    return (
        gate(
            "tex_partial_raw_decoder",
            ok,
            expected="byte-exact .tex raw-copy runs decode into verified partial Full HD textures",
            actual=(
                f"textures={decoded_textures}, fullhd={fullhd_outputs}, runs={raw_runs}, "
                f"bytes={raw_bytes}, covered={covered_pixels}, verified={verified_pixels}, "
                f"mismatches={mismatched_pixels}, issues={issue_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        fullhd_outputs if ok else 0,
        raw_bytes if ok else 0,
    )


def audit_tex_partial_raw_coverage(
    summary: Path,
    coverage_rows_path: Path,
    gap_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int]:
    if not summary.exists():
        return missing_gate("tex_partial_raw_coverage", summary), 0, 0
    if not coverage_rows_path.exists():
        return missing_gate("tex_partial_raw_coverage", coverage_rows_path), 0, 0
    if not gap_rows_path.exists():
        return missing_gate("tex_partial_raw_coverage", gap_rows_path), 0, 0
    if not html_report.exists():
        return missing_gate("tex_partial_raw_coverage", html_report), 0, 0

    summary_rows = read_csv(summary)
    coverage_rows = read_csv(coverage_rows_path)
    gap_rows = read_csv(gap_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    textures = int_value(total, "textures")
    raw_runs = int_value(total, "raw_runs")
    total_pixels = int_value(total, "total_pixels")
    covered_pixels = int_value(total, "covered_pixels")
    gaps = int_value(total, "gaps")
    largest_gap = int_value(total, "largest_gap")
    issue_rows = int_value(total, "issue_rows")
    valid_rows = [row for row in coverage_rows if not row.get("issues")]

    if textures != len(coverage_rows):
        issues.append("partial_coverage_texture_count_mismatch")
    if raw_runs != sum(int_value(row, "raw_runs") for row in valid_rows):
        issues.append("partial_coverage_run_count_mismatch")
    if total_pixels != sum(int_value(row, "total_pixels") for row in valid_rows):
        issues.append("partial_coverage_total_pixel_mismatch")
    if covered_pixels != sum(int_value(row, "covered_pixels") for row in valid_rows):
        issues.append("partial_coverage_covered_pixel_mismatch")
    if gaps != sum(int_value(row, "gaps") for row in valid_rows):
        issues.append("partial_coverage_gap_count_mismatch")
    if largest_gap != max((int_value(row, "largest_gap") for row in valid_rows), default=0):
        issues.append("partial_coverage_largest_gap_mismatch")
    if issue_rows or issue_rows != sum(1 for row in coverage_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if covered_pixels < 1:
        issues.append("missing_partial_coverage_pixels")
    if gaps < 1:
        issues.append("missing_partial_coverage_gaps")
    if not gap_rows:
        issues.append("missing_partial_gap_rows")
    if "const TEX_PARTIAL_RAW_COVERAGE = " not in text:
        issues.append("missing_tex_partial_raw_coverage_json")

    ok = not issues
    return (
        gate(
            "tex_partial_raw_coverage",
            ok,
            expected="partial .tex raw decoder coverage and remaining gaps are internally consistent",
            actual=(
                f"textures={textures}, runs={raw_runs}, covered={covered_pixels}/{total_pixels}, "
                f"gaps={gaps}, largest_gap={largest_gap}, issues={issue_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        covered_pixels if ok else 0,
        gaps if ok else 0,
    )


def audit_tex_gap_frontier_report(
    summary: Path,
    frontier_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_frontier_report", summary), 0, 0
    if not frontier_rows_path.exists():
        return missing_gate("tex_gap_frontier_report", frontier_rows_path), 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_frontier_report", html_report), 0, 0

    summary_rows = read_csv(summary)
    frontier_rows = read_csv(frontier_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    textures = int_value(total, "textures")
    gaps = int_value(total, "gaps")
    internal_gaps = int_value(total, "internal_gaps")
    leading_gaps = int_value(total, "leading_gaps")
    trailing_gaps = int_value(total, "trailing_gaps")
    segment_windows = int_value(total, "gaps_with_segment_window")
    largest_pixel_gap = int_value(total, "largest_pixel_gap")
    largest_segment_gap = int_value(total, "largest_segment_gap")
    issue_rows = int_value(total, "issue_rows")
    valid_rows = [row for row in frontier_rows if not row.get("issues")]

    if textures != len({(row.get("archive", ""), row.get("pcx_name", "")) for row in frontier_rows}):
        issues.append("gap_frontier_texture_count_mismatch")
    if gaps != len(frontier_rows):
        issues.append("gap_frontier_row_count_mismatch")
    if internal_gaps != sum(1 for row in frontier_rows if row.get("frontier_type") == "internal"):
        issues.append("gap_frontier_internal_count_mismatch")
    if leading_gaps != sum(1 for row in frontier_rows if row.get("frontier_type") == "leading"):
        issues.append("gap_frontier_leading_count_mismatch")
    if trailing_gaps != sum(1 for row in frontier_rows if row.get("frontier_type") == "trailing"):
        issues.append("gap_frontier_trailing_count_mismatch")
    if segment_windows != sum(1 for row in valid_rows if int_value(row, "segment_gap_bytes") > 0):
        issues.append("gap_frontier_segment_window_count_mismatch")
    if largest_pixel_gap != max((int_value(row, "pixel_gap") for row in frontier_rows), default=0):
        issues.append("gap_frontier_largest_pixel_gap_mismatch")
    if largest_segment_gap != max((int_value(row, "segment_gap_bytes") for row in valid_rows), default=0):
        issues.append("gap_frontier_largest_segment_gap_mismatch")
    if issue_rows or issue_rows != sum(1 for row in frontier_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if gaps < 1:
        issues.append("missing_gap_frontiers")
    if segment_windows < 1:
        issues.append("missing_gap_frontier_segment_windows")
    if "const TEX_GAP_FRONTIER_REPORT = " not in text:
        issues.append("missing_tex_gap_frontier_report_json")

    ok = not issues
    return (
        gate(
            "tex_gap_frontier_report",
            ok,
            expected=".tex gap frontier report maps partial decoder gaps to neighboring runs and segment windows",
            actual=(
                f"textures={textures}, gaps={gaps}, internal={internal_gaps}, "
                f"segment_windows={segment_windows}, largest_pixel_gap={largest_pixel_gap}, "
                f"largest_segment_gap={largest_segment_gap}, issues={issue_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        gaps if ok else 0,
        segment_windows if ok else 0,
    )


def audit_tex_gap_opcode_probe(
    summary: Path,
    probe_rows_path: Path,
    opcode_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_opcode_probe", summary), 0, 0, 0
    if not probe_rows_path.exists():
        return missing_gate("tex_gap_opcode_probe", probe_rows_path), 0, 0, 0
    if not opcode_rows_path.exists():
        return missing_gate("tex_gap_opcode_probe", opcode_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_opcode_probe", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    probe_rows = read_csv(probe_rows_path)
    opcode_rows = read_csv(opcode_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    textures = int_value(total, "textures")
    frontiers = int_value(total, "frontiers")
    probe_count = int_value(total, "probe_rows")
    forward_windows = int_value(total, "forward_windows")
    exact_rows = int_value(total, "exact_raw_replay_rows")
    prefix_rows = int_value(total, "raw_prefix_probe_rows")
    best_prefix = int_value(total, "best_prefix_bytes")
    compressed = int_value(total, "compressed_windows")
    expanded = int_value(total, "expanded_windows")
    opcode_groups = int_value(total, "opcode_groups")
    issue_rows = int_value(total, "issue_rows")
    valid_rows = [row for row in probe_rows if not row.get("issues")]

    if textures != len({(row.get("archive", ""), row.get("pcx_name", "")) for row in probe_rows}):
        issues.append("gap_opcode_texture_count_mismatch")
    if frontiers != len({row.get("frontier_id", "") for row in probe_rows if row.get("frontier_id")}):
        issues.append("gap_opcode_frontier_count_mismatch")
    if probe_count != len(probe_rows):
        issues.append("gap_opcode_probe_row_count_mismatch")
    if forward_windows != len(probe_rows):
        issues.append("gap_opcode_forward_window_count_mismatch")
    if exact_rows != sum(1 for row in valid_rows if int_value(row, "raw_exact_pixels") > 0):
        issues.append("gap_opcode_exact_replay_count_mismatch")
    if prefix_rows != sum(1 for row in valid_rows if int_value(row, "best_raw_prefix_bytes") > 0):
        issues.append("gap_opcode_prefix_count_mismatch")
    if best_prefix != max((int_value(row, "best_raw_prefix_bytes") for row in valid_rows), default=0):
        issues.append("gap_opcode_best_prefix_mismatch")
    if compressed != sum(
        1 for row in valid_rows if int_value(row, "segment_gap_bytes") < int_value(row, "pixel_gap")
    ):
        issues.append("gap_opcode_compressed_count_mismatch")
    if expanded != sum(
        1
        for row in valid_rows
        if int_value(row, "segment_gap_bytes") > int_value(row, "pixel_gap") * 4
    ):
        issues.append("gap_opcode_expanded_count_mismatch")
    if opcode_groups != len(opcode_rows):
        issues.append("gap_opcode_group_count_mismatch")
    if sum(int_value(row, "rows") for row in opcode_rows) != len(probe_rows):
        issues.append("gap_opcode_group_row_sum_mismatch")
    if sum(int_value(row, "exact_raw_replay_rows") for row in opcode_rows) != exact_rows:
        issues.append("gap_opcode_group_exact_sum_mismatch")
    if issue_rows or issue_rows != sum(1 for row in probe_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if probe_count < 1:
        issues.append("missing_gap_opcode_probe_rows")
    if opcode_groups < 1:
        issues.append("missing_gap_opcode_groups")
    if "const TEX_GAP_OPCODE_PROBE = " not in text:
        issues.append("missing_tex_gap_opcode_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_opcode_probe",
            ok,
            expected=".tex gap opcode probe is internally consistent and byte-checked against CDCACHE gaps",
            actual=(
                f"rows={probe_count}, exact_replays={exact_rows}, prefixes={prefix_rows}, "
                f"best_prefix={best_prefix}, opcodes={opcode_groups}, issues={issue_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        probe_count if ok else 0,
        best_prefix if ok else 0,
        exact_rows if ok else 0,
    )


def audit_tex_gap_rle_probe(
    summary: Path,
    hypothesis_rows_path: Path,
    best_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_rle_probe", summary), 0, 0, 0
    if not hypothesis_rows_path.exists():
        return missing_gate("tex_gap_rle_probe", hypothesis_rows_path), 0, 0, 0
    if not best_rows_path.exists():
        return missing_gate("tex_gap_rle_probe", best_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_rle_probe", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    hypothesis_rows = read_csv(hypothesis_rows_path)
    best_rows = read_csv(best_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    textures = int_value(total, "textures")
    frontiers = int_value(total, "frontiers")
    variants = int_value(total, "variants")
    tested_pairs = int_value(total, "tested_pairs")
    full_matches = int_value(total, "full_match_rows")
    frontiers_with_full = int_value(total, "frontiers_with_full_match")
    frontiers_with_prefix = int_value(total, "frontiers_with_prefix")
    best_prefix = int_value(total, "best_prefix_bytes")
    issue_rows = int_value(total, "issue_rows")
    valid_rows = [row for row in hypothesis_rows if not row.get("issues")]

    if textures != len({(row.get("archive", ""), row.get("pcx_name", "")) for row in best_rows}):
        issues.append("gap_rle_texture_count_mismatch")
    if frontiers != len(best_rows):
        issues.append("gap_rle_frontier_count_mismatch")
    if variants != len({row.get("variant", "") for row in hypothesis_rows if row.get("variant")}):
        issues.append("gap_rle_variant_count_mismatch")
    if tested_pairs != len(hypothesis_rows):
        issues.append("gap_rle_tested_pair_count_mismatch")
    if tested_pairs != frontiers * variants:
        issues.append("gap_rle_frontier_variant_product_mismatch")
    if full_matches != sum(1 for row in valid_rows if row.get("full_match") == "yes"):
        issues.append("gap_rle_full_match_count_mismatch")
    if frontiers_with_full != len(
        {
            (row.get("archive", ""), row.get("pcx_name", ""), row.get("frontier_id", ""))
            for row in valid_rows
            if row.get("full_match") == "yes"
        }
    ):
        issues.append("gap_rle_full_match_frontier_count_mismatch")
    if frontiers_with_prefix != sum(1 for row in best_rows if int_value(row, "best_prefix_bytes") > 0):
        issues.append("gap_rle_prefix_frontier_count_mismatch")
    if best_prefix != max((int_value(row, "prefix_bytes") for row in valid_rows), default=0):
        issues.append("gap_rle_best_prefix_mismatch")
    if issue_rows or issue_rows != sum(1 for row in hypothesis_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if tested_pairs < 1:
        issues.append("missing_gap_rle_probe_rows")
    if "const TEX_GAP_RLE_PROBE = " not in text:
        issues.append("missing_tex_gap_rle_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_rle_probe",
            ok,
            expected="common .tex gap RLE hypotheses are tested and internally consistent",
            actual=(
                f"pairs={tested_pairs}, variants={variants}, full_matches={full_matches}, "
                f"frontiers_with_prefix={frontiers_with_prefix}, best_prefix={best_prefix}, "
                f"issues={issue_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        tested_pairs if ok else 0,
        full_matches if ok else 0,
        best_prefix if ok else 0,
    )


def audit_tex_gap_rule_queue(
    summary: Path,
    queue_rows_path: Path,
    rule_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_rule_queue", summary), 0, 0, 0
    if not queue_rows_path.exists():
        return missing_gate("tex_gap_rule_queue", queue_rows_path), 0, 0, 0
    if not rule_rows_path.exists():
        return missing_gate("tex_gap_rule_queue", rule_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_rule_queue", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    queue_rows = read_csv(queue_rows_path)
    rule_rows = read_csv(rule_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    queue_count = int_value(total, "queue_rows")
    rule_types = int_value(total, "rule_types")
    top_priority = int_value(total, "top_priority")
    top_rule_type = total.get("top_rule_type", "")
    compact_rows = int_value(total, "compact_rows")
    expanded_rows = int_value(total, "expanded_rows")
    literal_rows = int_value(total, "literal_rows")
    short_echo_rows = int_value(total, "short_echo_rows")
    balanced_rows = int_value(total, "balanced_rows")
    issue_rows = int_value(total, "issue_rows")
    counts = Counter(row.get("rule_type", "") for row in queue_rows)
    valid_rows = [row for row in queue_rows if not row.get("issues")]
    top = max(queue_rows, key=lambda row: int_value(row, "priority_score")) if queue_rows else {}

    if queue_count != len(queue_rows):
        issues.append("gap_rule_queue_row_count_mismatch")
    if rule_types != len(rule_rows):
        issues.append("gap_rule_type_count_mismatch")
    if rule_types != len({row.get("rule_type", "") for row in queue_rows if row.get("rule_type")}):
        issues.append("gap_rule_unique_type_count_mismatch")
    if sum(int_value(row, "rows") for row in rule_rows) != len(queue_rows):
        issues.append("gap_rule_group_row_sum_mismatch")
    for rule_row in rule_rows:
        if int_value(rule_row, "rows") != counts.get(rule_row.get("rule_type", ""), 0):
            issues.append(f"gap_rule_group_count_mismatch:{rule_row.get('rule_type', '')}")
    if top_priority != int_value(top, "priority_score"):
        issues.append("gap_rule_top_priority_mismatch")
    if top_rule_type != top.get("rule_type", ""):
        issues.append("gap_rule_top_type_mismatch")
    if compact_rows != counts.get("compact_control_stream", 0):
        issues.append("gap_rule_compact_count_mismatch")
    if expanded_rows != counts.get("expanded_control_stream", 0):
        issues.append("gap_rule_expanded_count_mismatch")
    if literal_rows != counts.get("literal_fragment_probe", 0):
        issues.append("gap_rule_literal_count_mismatch")
    if short_echo_rows != counts.get("short_echo_probe", 0):
        issues.append("gap_rule_short_echo_count_mismatch")
    if balanced_rows != counts.get("balanced_transform_stream", 0):
        issues.append("gap_rule_balanced_count_mismatch")
    if issue_rows or issue_rows != sum(1 for row in queue_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if len(valid_rows) != len(queue_rows):
        issues.append("gap_rule_queue_invalid_rows")
    if queue_count < 1:
        issues.append("missing_gap_rule_queue_rows")
    if "const TEX_GAP_RULE_QUEUE = " not in text:
        issues.append("missing_tex_gap_rule_queue_json")

    ok = not issues
    return (
        gate(
            "tex_gap_rule_queue",
            ok,
            expected=".tex gap decoder-rule queue is ranked and internally consistent",
            actual=(
                f"rows={queue_count}, rule_types={rule_types}, top={top_rule_type}:{top_priority}, "
                f"compact={compact_rows}, expanded={expanded_rows}, issues={issue_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        queue_count if ok else 0,
        rule_types if ok else 0,
        top_priority if ok else 0,
    )


def audit_tex_gap_rule_fixtures(
    summary: Path,
    fixture_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_rule_fixtures", summary), 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate("tex_gap_rule_fixtures", fixture_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_rule_fixtures", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    fixture_rows = read_csv(fixture_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    binary_files = int_value(total, "binary_files")
    rule_types = int_value(total, "rule_types")
    total_expected = int_value(total, "total_expected_pixels")
    total_segment = int_value(total, "total_segment_bytes")
    total_prefix = int_value(total, "total_control_prefix_bytes")
    total_fragment = int_value(total, "total_fragment_bytes")
    issue_rows = int_value(total, "issue_rows")

    if fixture_count != len(fixture_rows):
        issues.append("gap_fixture_row_count_mismatch")
    if binary_files != len(fixture_rows) * 4:
        issues.append("gap_fixture_binary_count_mismatch")
    if rule_types != len({row.get("rule_type", "") for row in fixture_rows if row.get("rule_type")}):
        issues.append("gap_fixture_rule_type_count_mismatch")
    if total_expected != sum(int_value(row, "pixel_gap") for row in fixture_rows):
        issues.append("gap_fixture_expected_pixel_sum_mismatch")
    if total_segment != sum(int_value(row, "segment_gap_bytes") for row in fixture_rows):
        issues.append("gap_fixture_segment_byte_sum_mismatch")
    if total_prefix != sum(int_value(row, "control_prefix_bytes") for row in fixture_rows):
        issues.append("gap_fixture_prefix_byte_sum_mismatch")
    if total_fragment != sum(int_value(row, "fragment_bytes") for row in fixture_rows):
        issues.append("gap_fixture_fragment_byte_sum_mismatch")
    if issue_rows or issue_rows != sum(1 for row in fixture_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")

    missing_paths = 0
    size_mismatches = 0
    for row in fixture_rows:
        expected_sizes = {
            "segment_gap_path": int_value(row, "segment_gap_bytes"),
            "expected_gap_path": int_value(row, "pixel_gap"),
            "control_prefix_path": int_value(row, "control_prefix_bytes"),
            "fragment_path": int_value(row, "fragment_bytes"),
        }
        for field, expected_size in expected_sizes.items():
            value = row.get(field, "")
            path = Path(value)
            if not value or not path.exists():
                missing_paths += 1
            elif path.stat().st_size != expected_size:
                size_mismatches += 1
    if missing_paths:
        issues.append(f"missing_fixture_paths:{missing_paths}")
    if size_mismatches:
        issues.append(f"fixture_size_mismatches:{size_mismatches}")
    if fixture_count < 1:
        issues.append("missing_gap_rule_fixtures")
    if "const TEX_GAP_RULE_FIXTURES = " not in text:
        issues.append("missing_tex_gap_rule_fixtures_json")

    ok = not issues
    return (
        gate(
            "tex_gap_rule_fixtures",
            ok,
            expected=".tex gap rule fixtures exist and match manifest byte sizes",
            actual=(
                f"fixtures={fixture_count}, files={binary_files}, rule_types={rule_types}, "
                f"segment_bytes={total_segment}, fragment_bytes={total_fragment}, issues={issue_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        fixture_count if ok else 0,
        binary_files if ok else 0,
        total_fragment if ok else 0,
    )


def audit_tex_gap_zero_run_probe(
    summary: Path,
    fixture_rows_path: Path,
    run_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_zero_run_probe", summary), 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate("tex_gap_zero_run_probe", fixture_rows_path), 0, 0, 0
    if not run_rows_path.exists():
        return missing_gate("tex_gap_zero_run_probe", run_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_zero_run_probe", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    fixture_rows = read_csv(fixture_rows_path)
    run_rows = read_csv(run_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    run_count = int_value(total, "run_rows")
    zero_run_count = int_value(total, "zero_run_rows")
    nonzero_run_count = int_value(total, "nonzero_run_rows")
    leading_zero_fixtures = int_value(total, "fixtures_with_leading_zero")
    row_prefix_fixtures = int_value(total, "fixtures_with_row_prefix_zero_runs")
    total_zero_bytes = int_value(total, "total_zero_bytes")
    max_leading_zero = int_value(total, "max_leading_zero_bytes")
    max_zero = int_value(total, "max_zero_run_bytes")
    issue_rows = int_value(total, "issue_rows")

    if fixture_count != len(fixture_rows):
        issues.append("zero_run_fixture_count_mismatch")
    if run_count != len(run_rows):
        issues.append("zero_run_row_count_mismatch")
    if zero_run_count != sum(1 for row in run_rows if row.get("run_class") == "zero"):
        issues.append("zero_run_zero_count_mismatch")
    if nonzero_run_count != sum(1 for row in run_rows if row.get("run_class") == "nonzero"):
        issues.append("zero_run_nonzero_count_mismatch")
    if leading_zero_fixtures != sum(1 for row in fixture_rows if int_value(row, "leading_zero_bytes")):
        issues.append("zero_run_leading_fixture_count_mismatch")
    if row_prefix_fixtures != sum(1 for row in fixture_rows if int_value(row, "row_prefix_zero_runs")):
        issues.append("zero_run_row_prefix_fixture_count_mismatch")
    if total_zero_bytes != sum(int_value(row, "zero_bytes") for row in fixture_rows):
        issues.append("zero_run_total_zero_bytes_mismatch")
    if max_leading_zero != max([int_value(row, "leading_zero_bytes") for row in fixture_rows] or [0]):
        issues.append("zero_run_max_leading_mismatch")
    if max_zero != max([int_value(row, "max_zero_run_bytes") for row in fixture_rows] or [0]):
        issues.append("zero_run_max_zero_mismatch")
    if issue_rows or issue_rows != sum(1 for row in fixture_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if fixture_count < 1 or run_count < fixture_count:
        issues.append("missing_zero_run_probe_rows")
    if "const TEX_GAP_ZERO_RUN_PROBE = " not in text:
        issues.append("missing_tex_gap_zero_run_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_zero_run_probe",
            ok,
            expected=".tex gap zero-run probe is internally consistent",
            actual=(
                f"fixtures={fixture_count}, runs={run_count}, zero_runs={zero_run_count}, "
                f"zero_bytes={total_zero_bytes}, max_zero={max_zero}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        fixture_count if ok else 0,
        run_count if ok else 0,
        max_zero if ok else 0,
    )


def audit_tex_gap_geometry_replay(
    summary: Path,
    candidate_rows_path: Path,
    best_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_geometry_replay", summary), 0, 0, 0
    if not candidate_rows_path.exists():
        return missing_gate("tex_gap_geometry_replay", candidate_rows_path), 0, 0, 0
    if not best_rows_path.exists():
        return missing_gate("tex_gap_geometry_replay", best_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_geometry_replay", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    candidate_rows = read_csv(candidate_rows_path)
    best_rows = read_csv(best_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    candidate_count = int_value(total, "candidate_rows")
    stream_modes = int_value(total, "stream_modes")
    exact_matches = int_value(total, "exact_match_rows")
    exact_match_fixtures = int_value(total, "exact_match_fixtures")
    best_prefix = int_value(total, "best_prefix_bytes")
    best_exact = int_value(total, "best_exact_bytes")
    issue_rows = int_value(total, "issue_rows")

    if fixture_count != len(best_rows):
        issues.append("geometry_replay_fixture_count_mismatch")
    if candidate_count != len(candidate_rows):
        issues.append("geometry_replay_candidate_count_mismatch")
    if stream_modes != len({row.get("stream_mode", "") for row in candidate_rows if row.get("stream_mode")}):
        issues.append("geometry_replay_stream_mode_count_mismatch")
    if exact_matches != sum(1 for row in candidate_rows if row.get("full_match") == "1"):
        issues.append("geometry_replay_exact_match_count_mismatch")
    if exact_match_fixtures != sum(1 for row in best_rows if row.get("full_match") == "1"):
        issues.append("geometry_replay_exact_fixture_count_mismatch")
    if best_prefix != max([int_value(row, "prefix_bytes") for row in candidate_rows] or [0]):
        issues.append("geometry_replay_best_prefix_mismatch")
    if best_exact != max([int_value(row, "exact_bytes") for row in candidate_rows] or [0]):
        issues.append("geometry_replay_best_exact_mismatch")
    if issue_rows or issue_rows != sum(1 for row in candidate_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if fixture_count < 1 or candidate_count < fixture_count:
        issues.append("missing_geometry_replay_rows")
    if "const TEX_GAP_GEOMETRY_REPLAY = " not in text:
        issues.append("missing_tex_gap_geometry_replay_json")

    ok = not issues
    return (
        gate(
            "tex_gap_geometry_replay",
            ok,
            expected=".tex geometry-aware gap replay report is internally consistent",
            actual=(
                f"fixtures={fixture_count}, candidates={candidate_count}, modes={stream_modes}, "
                f"exact={exact_matches}, best_prefix={best_prefix}, best_exact={best_exact}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        candidate_count if ok else 0,
        best_prefix if ok else 0,
        best_exact if ok else 0,
    )


def audit_tex_gap_nonzero_stream_probe(
    summary: Path,
    candidate_rows_path: Path,
    best_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_nonzero_stream_probe", summary), 0, 0, 0
    if not candidate_rows_path.exists():
        return missing_gate("tex_gap_nonzero_stream_probe", candidate_rows_path), 0, 0, 0
    if not best_rows_path.exists():
        return missing_gate("tex_gap_nonzero_stream_probe", best_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_nonzero_stream_probe", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    candidate_rows = read_csv(candidate_rows_path)
    best_rows = read_csv(best_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    candidate_count = int_value(total, "candidate_rows")
    stream_modes = int_value(total, "stream_modes")
    transform_modes = int_value(total, "transform_modes")
    exact_matches = int_value(total, "exact_match_rows")
    exact_match_fixtures = int_value(total, "exact_match_fixtures")
    best_prefix = int_value(total, "best_prefix_bytes")
    best_exact = int_value(total, "best_exact_bytes")
    issue_rows = int_value(total, "issue_rows")

    if fixture_count != len(best_rows):
        issues.append("nonzero_stream_fixture_count_mismatch")
    if candidate_count != len(candidate_rows):
        issues.append("nonzero_stream_candidate_count_mismatch")
    if stream_modes != len({row.get("stream_mode", "") for row in candidate_rows if row.get("stream_mode")}):
        issues.append("nonzero_stream_mode_count_mismatch")
    if transform_modes != len({row.get("transform", "") for row in candidate_rows if row.get("transform")}):
        issues.append("nonzero_transform_count_mismatch")
    if exact_matches != sum(1 for row in candidate_rows if row.get("full_match") == "1"):
        issues.append("nonzero_stream_exact_match_count_mismatch")
    if exact_match_fixtures != sum(1 for row in best_rows if row.get("full_match") == "1"):
        issues.append("nonzero_stream_exact_fixture_count_mismatch")
    if best_prefix != max([int_value(row, "prefix_bytes") for row in candidate_rows] or [0]):
        issues.append("nonzero_stream_best_prefix_mismatch")
    if best_exact != max([int_value(row, "exact_bytes") for row in candidate_rows] or [0]):
        issues.append("nonzero_stream_best_exact_mismatch")
    if issue_rows or issue_rows != sum(1 for row in candidate_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if fixture_count < 1 or candidate_count < fixture_count:
        issues.append("missing_nonzero_stream_rows")
    if "const TEX_GAP_NONZERO_STREAM_PROBE = " not in text:
        issues.append("missing_tex_gap_nonzero_stream_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_nonzero_stream_probe",
            ok,
            expected=".tex nonzero stream transform probe is internally consistent",
            actual=(
                f"fixtures={fixture_count}, candidates={candidate_count}, streams={stream_modes}, "
                f"transforms={transform_modes}, exact={exact_matches}, "
                f"best_prefix={best_prefix}, best_exact={best_exact}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        candidate_count if ok else 0,
        best_prefix if ok else 0,
        best_exact if ok else 0,
    )


def audit_tex_gap_control_word_probe(
    summary: Path,
    fixture_rows_path: Path,
    hit_rows_path: Path,
    metric_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_control_word_probe", summary), 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate("tex_gap_control_word_probe", fixture_rows_path), 0, 0, 0
    if not hit_rows_path.exists():
        return missing_gate("tex_gap_control_word_probe", hit_rows_path), 0, 0, 0
    if not metric_rows_path.exists():
        return missing_gate("tex_gap_control_word_probe", metric_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_control_word_probe", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    fixture_rows = read_csv(fixture_rows_path)
    hit_rows = read_csv(hit_rows_path)
    metric_rows = read_csv(metric_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    hit_count = int_value(total, "hit_rows")
    fixtures_with_hits = int_value(total, "fixtures_with_hits")
    metric_names = int_value(total, "metric_names")
    u16le_hits = int_value(total, "u16le_hits")
    u16be_hits = int_value(total, "u16be_hits")
    byte_hits = int_value(total, "byte_hits")
    top_metric_hits = int_value(total, "top_metric_hits")
    top_fixture_hits = int_value(total, "top_fixture_hits")
    issue_rows = int_value(total, "issue_rows")

    if fixture_count != len(fixture_rows):
        issues.append("control_word_fixture_count_mismatch")
    if hit_count != len(hit_rows):
        issues.append("control_word_hit_count_mismatch")
    if fixtures_with_hits != sum(1 for row in fixture_rows if int_value(row, "hit_count")):
        issues.append("control_word_fixtures_with_hits_mismatch")
    if metric_names != len({row.get("metric", "") for row in hit_rows if row.get("metric")}):
        issues.append("control_word_metric_name_count_mismatch")
    if u16le_hits != sum(1 for row in hit_rows if row.get("encoding") == "u16le"):
        issues.append("control_word_u16le_count_mismatch")
    if u16be_hits != sum(1 for row in hit_rows if row.get("encoding") == "u16be"):
        issues.append("control_word_u16be_count_mismatch")
    if byte_hits != sum(1 for row in hit_rows if row.get("encoding") == "byte"):
        issues.append("control_word_byte_count_mismatch")
    if top_metric_hits != max([int_value(row, "hits") for row in metric_rows] or [0]):
        issues.append("control_word_top_metric_mismatch")
    if top_fixture_hits != max([int_value(row, "hit_count") for row in fixture_rows] or [0]):
        issues.append("control_word_top_fixture_mismatch")
    if issue_rows or issue_rows != sum(1 for row in fixture_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if fixture_count < 1 or hit_count < 1 or not metric_rows:
        issues.append("missing_control_word_probe_rows")
    if "const TEX_GAP_CONTROL_WORD_PROBE = " not in text:
        issues.append("missing_tex_gap_control_word_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_control_word_probe",
            ok,
            expected=".tex control word probe is internally consistent",
            actual=(
                f"fixtures={fixture_count}, hits={hit_count}, metrics={metric_names}, "
                f"u16le={u16le_hits}, u16be={u16be_hits}, byte={byte_hits}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        hit_count if ok else 0,
        u16le_hits if ok else 0,
        metric_names if ok else 0,
    )


def audit_tex_gap_header_schema_probe(
    summary: Path,
    fixture_rows_path: Path,
    block_rows_path: Path,
    payload_rows_path: Path,
    best_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_header_schema_probe", summary), 0, 0, 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate("tex_gap_header_schema_probe", fixture_rows_path), 0, 0, 0, 0, 0
    if not block_rows_path.exists():
        return missing_gate("tex_gap_header_schema_probe", block_rows_path), 0, 0, 0, 0, 0
    if not payload_rows_path.exists():
        return missing_gate("tex_gap_header_schema_probe", payload_rows_path), 0, 0, 0, 0, 0
    if not best_rows_path.exists():
        return missing_gate("tex_gap_header_schema_probe", best_rows_path), 0, 0, 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_header_schema_probe", html_report), 0, 0, 0, 0, 0

    summary_rows = read_csv(summary)
    fixture_rows = read_csv(fixture_rows_path)
    block_rows = read_csv(block_rows_path)
    payload_rows = read_csv(payload_rows_path)
    best_rows = read_csv(best_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    block_count = int_value(total, "block_rows")
    payload_count = int_value(total, "payload_candidate_rows")
    source_modes = int_value(total, "source_modes")
    dimension_blocks = int_value(total, "dimension_pair_blocks")
    fixtures_with_dimensions = int_value(total, "fixtures_with_dimension_pair")
    row_mask_blocks = int_value(total, "row_mask_blocks")
    fixtures_with_row_mask = int_value(total, "fixtures_with_row_mask_block")
    exact_matches = int_value(total, "exact_match_rows")
    exact_match_fixtures = int_value(total, "exact_match_fixtures")
    best_prefix = int_value(total, "best_prefix_bytes")
    best_exact = int_value(total, "best_exact_bytes")
    issue_rows = int_value(total, "issue_rows")

    dimension_fixture_keys = {
        (row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", ""))
        for row in block_rows
        if row.get("dimension_pair") == "1"
    }
    row_mask_fixture_keys = {
        (row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", ""))
        for row in block_rows
        if row.get("row_mask_block") == "1"
    }

    if fixture_count != len(fixture_rows) or fixture_count != len(best_rows):
        issues.append("header_schema_fixture_count_mismatch")
    if block_count != len(block_rows):
        issues.append("header_schema_block_count_mismatch")
    if payload_count != len(payload_rows):
        issues.append("header_schema_payload_count_mismatch")
    if source_modes != len({row.get("source_mode", "") for row in payload_rows if row.get("source_mode")}):
        issues.append("header_schema_source_mode_count_mismatch")
    if dimension_blocks != sum(1 for row in block_rows if row.get("dimension_pair") == "1"):
        issues.append("header_schema_dimension_block_count_mismatch")
    if fixtures_with_dimensions != len(dimension_fixture_keys):
        issues.append("header_schema_dimension_fixture_count_mismatch")
    if row_mask_blocks != sum(1 for row in block_rows if row.get("row_mask_block") == "1"):
        issues.append("header_schema_row_mask_block_count_mismatch")
    if fixtures_with_row_mask != len(row_mask_fixture_keys):
        issues.append("header_schema_row_mask_fixture_count_mismatch")
    if exact_matches != sum(1 for row in payload_rows if row.get("full_match") == "1"):
        issues.append("header_schema_exact_match_count_mismatch")
    if exact_match_fixtures != sum(1 for row in best_rows if row.get("full_match") == "1"):
        issues.append("header_schema_exact_fixture_count_mismatch")
    if best_prefix != max([int_value(row, "prefix_bytes") for row in payload_rows] or [0]):
        issues.append("header_schema_best_prefix_mismatch")
    if best_exact != max([int_value(row, "exact_bytes") for row in payload_rows] or [0]):
        issues.append("header_schema_best_exact_mismatch")
    if issue_rows or issue_rows != sum(1 for row in fixture_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if fixture_count < 1 or block_count < 1 or payload_count < fixture_count:
        issues.append("missing_header_schema_probe_rows")
    if dimension_blocks < 1:
        issues.append("missing_header_schema_dimension_blocks")
    if "const TEX_GAP_HEADER_SCHEMA_PROBE = " not in text:
        issues.append("missing_tex_gap_header_schema_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_header_schema_probe",
            ok,
            expected=".tex header schema probe is internally consistent",
            actual=(
                f"fixtures={fixture_count}, blocks={block_count}, payloads={payload_count}, "
                f"dimension_blocks={dimension_blocks}, row_masks={row_mask_blocks}, "
                f"best_prefix={best_prefix}, best_exact={best_exact}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        block_count if ok else 0,
        payload_count if ok else 0,
        dimension_blocks if ok else 0,
        best_prefix if ok else 0,
        best_exact if ok else 0,
    )


def audit_tex_gap_row_stride_probe(
    summary: Path,
    fixture_rows_path: Path,
    candidate_rows_path: Path,
    best_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_row_stride_probe", summary), 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate("tex_gap_row_stride_probe", fixture_rows_path), 0, 0, 0
    if not candidate_rows_path.exists():
        return missing_gate("tex_gap_row_stride_probe", candidate_rows_path), 0, 0, 0
    if not best_rows_path.exists():
        return missing_gate("tex_gap_row_stride_probe", best_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_row_stride_probe", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    fixture_rows = read_csv(fixture_rows_path)
    candidate_rows = read_csv(candidate_rows_path)
    best_rows = read_csv(best_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    candidate_count = int_value(total, "candidate_rows")
    source_modes = int_value(total, "source_modes")
    payload_offsets = int_value(total, "payload_offsets")
    stride_values = int_value(total, "stride_values")
    exact_matches = int_value(total, "exact_match_rows")
    exact_match_fixtures = int_value(total, "exact_match_fixtures")
    best_prefix = int_value(total, "best_prefix_bytes")
    best_exact = int_value(total, "best_exact_bytes")
    issue_rows = int_value(total, "issue_rows")

    offset_keys = {
        (row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", ""), row.get("payload_offset", ""))
        for row in candidate_rows
    }
    if fixture_count != len(fixture_rows) or fixture_count != len(best_rows):
        issues.append("row_stride_fixture_count_mismatch")
    if candidate_count != len(candidate_rows):
        issues.append("row_stride_candidate_count_mismatch")
    if source_modes != len({row.get("source_mode", "") for row in candidate_rows if row.get("source_mode")}):
        issues.append("row_stride_source_mode_count_mismatch")
    if payload_offsets != len(offset_keys):
        issues.append("row_stride_payload_offset_count_mismatch")
    if stride_values != len({row.get("row_stride", "") for row in candidate_rows if row.get("row_stride")}):
        issues.append("row_stride_value_count_mismatch")
    if exact_matches != sum(1 for row in candidate_rows if row.get("full_match") == "1"):
        issues.append("row_stride_exact_match_count_mismatch")
    if exact_match_fixtures != sum(1 for row in best_rows if row.get("full_match") == "1"):
        issues.append("row_stride_exact_fixture_count_mismatch")
    if best_prefix != max([int_value(row, "prefix_bytes") for row in candidate_rows] or [0]):
        issues.append("row_stride_best_prefix_mismatch")
    if best_exact != max([int_value(row, "exact_bytes") for row in candidate_rows] or [0]):
        issues.append("row_stride_best_exact_mismatch")
    if issue_rows or issue_rows != sum(1 for row in fixture_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if fixture_count < 1 or candidate_count < fixture_count:
        issues.append("missing_row_stride_probe_rows")
    if "const TEX_GAP_ROW_STRIDE_PROBE = " not in text:
        issues.append("missing_tex_gap_row_stride_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_row_stride_probe",
            ok,
            expected=".tex row-stride gap probe is internally consistent",
            actual=(
                f"fixtures={fixture_count}, candidates={candidate_count}, offsets={payload_offsets}, "
                f"strides={stride_values}, exact={exact_matches}, "
                f"best_prefix={best_prefix}, best_exact={best_exact}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        candidate_count if ok else 0,
        best_prefix if ok else 0,
        best_exact if ok else 0,
    )


def audit_tex_gap_row_stride_mismatch_probe(
    summary: Path,
    candidate_rows_path: Path,
    row_scores_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_row_stride_mismatch_probe", summary), 0, 0, 0
    if not candidate_rows_path.exists():
        return missing_gate("tex_gap_row_stride_mismatch_probe", candidate_rows_path), 0, 0, 0
    if not row_scores_path.exists():
        return missing_gate("tex_gap_row_stride_mismatch_probe", row_scores_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_row_stride_mismatch_probe", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    candidate_rows = read_csv(candidate_rows_path)
    row_scores = read_csv(row_scores_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    selected_candidates = int_value(total, "selected_candidates")
    row_score_rows = int_value(total, "row_score_rows")
    fixture_count = int_value(total, "fixtures")
    full_nonzero_rows = int_value(total, "full_nonzero_rows")
    best_nonzero = int_value(total, "best_nonzero_exact_slots")
    issue_rows = int_value(total, "issue_rows")

    candidate_fixtures = {
        (row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", ""))
        for row in candidate_rows
    }
    if selected_candidates != len(candidate_rows):
        issues.append("row_stride_mismatch_candidate_count_mismatch")
    if row_score_rows != len(row_scores):
        issues.append("row_stride_mismatch_row_count_mismatch")
    if fixture_count != len(candidate_fixtures):
        issues.append("row_stride_mismatch_fixture_count_mismatch")
    if full_nonzero_rows != sum(int_value(row, "full_nonzero_rows") for row in candidate_rows):
        issues.append("row_stride_mismatch_full_row_count_mismatch")
    if best_nonzero != max([int_value(row, "nonzero_exact_slots") for row in candidate_rows] or [0]):
        issues.append("row_stride_mismatch_best_nonzero_mismatch")
    if issue_rows or issue_rows != sum(1 for row in candidate_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if selected_candidates < 1 or row_score_rows < selected_candidates:
        issues.append("missing_row_stride_mismatch_rows")
    if "const TEX_GAP_ROW_STRIDE_MISMATCH_PROBE = " not in text:
        issues.append("missing_tex_gap_row_stride_mismatch_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_row_stride_mismatch_probe",
            ok,
            expected=".tex row-stride mismatch probe is internally consistent",
            actual=(
                f"candidates={selected_candidates}, row_scores={row_score_rows}, "
                f"fixtures={fixture_count}, full_nonzero_rows={full_nonzero_rows}, "
                f"best_nonzero={best_nonzero}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        selected_candidates if ok else 0,
        row_score_rows if ok else 0,
        full_nonzero_rows if ok else 0,
    )


def audit_tex_gap_row_delta_probe(
    summary: Path,
    candidate_rows_path: Path,
    row_delta_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_row_delta_probe", summary), 0, 0, 0
    if not candidate_rows_path.exists():
        return missing_gate("tex_gap_row_delta_probe", candidate_rows_path), 0, 0, 0
    if not row_delta_rows_path.exists():
        return missing_gate("tex_gap_row_delta_probe", row_delta_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_row_delta_probe", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    candidate_rows = read_csv(candidate_rows_path)
    row_delta_rows = read_csv(row_delta_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    selected_candidates = int_value(total, "selected_candidates")
    row_delta_count = int_value(total, "row_delta_rows")
    fixture_count = int_value(total, "fixtures")
    unique_deltas = int_value(total, "unique_delta_values")
    full_nonzero_rows = int_value(total, "full_nonzero_rows")
    best_adjusted = int_value(total, "best_adjusted_nonzero_slots")
    best_gain = int_value(total, "best_gain_nonzero_slots")
    issue_rows = int_value(total, "issue_rows")

    candidate_fixtures = {
        (row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", ""))
        for row in candidate_rows
    }
    delta_values = {
        row.get("best_delta", "")
        for row in row_delta_rows
        if row.get("best_delta", "")
    }
    if selected_candidates != len(candidate_rows):
        issues.append("row_delta_candidate_count_mismatch")
    if row_delta_count != len(row_delta_rows):
        issues.append("row_delta_row_count_mismatch")
    if fixture_count != len(candidate_fixtures):
        issues.append("row_delta_fixture_count_mismatch")
    if unique_deltas != len(delta_values):
        issues.append("row_delta_unique_delta_count_mismatch")
    if full_nonzero_rows != sum(int_value(row, "full_nonzero_rows") for row in candidate_rows):
        issues.append("row_delta_full_row_count_mismatch")
    if best_adjusted != max([int_value(row, "adjusted_nonzero_exact_slots") for row in candidate_rows] or [0]):
        issues.append("row_delta_best_adjusted_mismatch")
    if best_gain != max([int_value(row, "adjusted_gain_nonzero_slots") for row in candidate_rows] or [0]):
        issues.append("row_delta_best_gain_mismatch")
    if issue_rows or issue_rows != sum(1 for row in candidate_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if selected_candidates < 1 or row_delta_count < selected_candidates:
        issues.append("missing_row_delta_probe_rows")
    if "const TEX_GAP_ROW_DELTA_PROBE = " not in text:
        issues.append("missing_tex_gap_row_delta_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_row_delta_probe",
            ok,
            expected=".tex row-delta gap probe is internally consistent",
            actual=(
                f"candidates={selected_candidates}, row_deltas={row_delta_count}, "
                f"fixtures={fixture_count}, unique_deltas={unique_deltas}, "
                f"best_adjusted={best_adjusted}, best_gain={best_gain}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        row_delta_count if ok else 0,
        best_adjusted if ok else 0,
        best_gain if ok else 0,
    )


def audit_tex_gap_row_transform_probe(
    summary: Path,
    candidate_rows_path: Path,
    row_transform_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_row_transform_probe", summary), 0, 0, 0
    if not candidate_rows_path.exists():
        return missing_gate("tex_gap_row_transform_probe", candidate_rows_path), 0, 0, 0
    if not row_transform_rows_path.exists():
        return missing_gate("tex_gap_row_transform_probe", row_transform_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_row_transform_probe", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    candidate_rows = read_csv(candidate_rows_path)
    row_transform_rows = read_csv(row_transform_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    selected_candidates = int_value(total, "selected_candidates")
    row_transform_count = int_value(total, "row_transform_rows")
    fixture_count = int_value(total, "fixtures")
    transform_modes = int_value(total, "transform_modes")
    full_nonzero_rows = int_value(total, "full_nonzero_rows")
    best_transformed = int_value(total, "best_transformed_nonzero_slots")
    best_gain = int_value(total, "best_gain_over_delta")
    issue_rows = int_value(total, "issue_rows")

    candidate_fixtures = {
        (row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", ""))
        for row in candidate_rows
    }
    row_transforms = {
        row.get("transform", "")
        for row in row_transform_rows
        if row.get("transform", "")
    }
    if selected_candidates != len(candidate_rows):
        issues.append("row_transform_candidate_count_mismatch")
    if row_transform_count != len(row_transform_rows):
        issues.append("row_transform_row_count_mismatch")
    if fixture_count != len(candidate_fixtures):
        issues.append("row_transform_fixture_count_mismatch")
    if transform_modes != len(row_transforms):
        issues.append("row_transform_mode_count_mismatch")
    if full_nonzero_rows != sum(int_value(row, "full_nonzero_rows") for row in candidate_rows):
        issues.append("row_transform_full_row_count_mismatch")
    if best_transformed != max([int_value(row, "transformed_nonzero_exact_slots") for row in candidate_rows] or [0]):
        issues.append("row_transform_best_transformed_mismatch")
    if best_gain != max([int_value(row, "gain_over_delta") for row in candidate_rows] or [0]):
        issues.append("row_transform_best_gain_mismatch")
    if issue_rows or issue_rows != sum(1 for row in candidate_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if selected_candidates < 1 or row_transform_count < selected_candidates:
        issues.append("missing_row_transform_probe_rows")
    if "const TEX_GAP_ROW_TRANSFORM_PROBE = " not in text:
        issues.append("missing_tex_gap_row_transform_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_row_transform_probe",
            ok,
            expected=".tex row-transform gap probe is internally consistent",
            actual=(
                f"candidates={selected_candidates}, row_transforms={row_transform_count}, "
                f"fixtures={fixture_count}, transform_modes={transform_modes}, "
                f"best_transformed={best_transformed}, best_gain={best_gain}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        row_transform_count if ok else 0,
        best_transformed if ok else 0,
        best_gain if ok else 0,
    )


def audit_tex_gap_row_control_probe(
    summary: Path,
    candidate_rows_path: Path,
    row_control_rows_path: Path,
    control_group_rows_path: Path,
    metric_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_row_control_probe", summary), 0, 0, 0
    if not candidate_rows_path.exists():
        return missing_gate("tex_gap_row_control_probe", candidate_rows_path), 0, 0, 0
    if not row_control_rows_path.exists():
        return missing_gate("tex_gap_row_control_probe", row_control_rows_path), 0, 0, 0
    if not control_group_rows_path.exists():
        return missing_gate("tex_gap_row_control_probe", control_group_rows_path), 0, 0, 0
    if not metric_rows_path.exists():
        return missing_gate("tex_gap_row_control_probe", metric_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_row_control_probe", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    candidate_rows = read_csv(candidate_rows_path)
    row_control_rows = read_csv(row_control_rows_path)
    control_group_rows = read_csv(control_group_rows_path)
    metric_rows = read_csv(metric_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    selected_candidates = int_value(total, "selected_candidates")
    row_control_count = int_value(total, "row_control_rows")
    fixture_count = int_value(total, "fixtures")
    control_group_count = int_value(total, "control_groups")
    repeated_control_groups = int_value(total, "repeated_control_groups")
    unique_before2 = int_value(total, "unique_before2")
    unique_at2 = int_value(total, "unique_at2")
    unique_deltas = int_value(total, "unique_delta_values")
    metric_count = int_value(total, "metric_rows")
    best_metric_hits = int_value(total, "best_metric_hits")
    best_group_rows = int_value(total, "best_group_rows")
    negative_start_rows = int_value(total, "negative_start_rows")
    out_of_range_start_rows = int_value(total, "out_of_range_start_rows")
    full_nonzero_rows = int_value(total, "full_nonzero_rows")
    issue_rows = int_value(total, "issue_rows")

    candidate_fixtures = {
        (row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", ""))
        for row in candidate_rows
    }
    before2_values = {
        row.get("source_before2_hex", "")
        for row in row_control_rows
        if row.get("source_before2_hex", "")
    }
    at2_values = {
        row.get("source_at2_hex", "")
        for row in row_control_rows
        if row.get("source_at2_hex", "")
    }
    delta_values = {
        row.get("best_delta", "")
        for row in row_control_rows
        if row.get("best_delta", "")
    }
    non_na_groups = [row for row in control_group_rows if row.get("control_key", "") != "NA|NA"]
    best_group_candidates = non_na_groups or control_group_rows
    max_group_rows = max([int_value(row, "rows") for row in best_group_candidates] or [0])

    if selected_candidates != len(candidate_rows):
        issues.append("row_control_candidate_count_mismatch")
    if row_control_count != len(row_control_rows):
        issues.append("row_control_row_count_mismatch")
    if fixture_count != len(candidate_fixtures):
        issues.append("row_control_fixture_count_mismatch")
    if control_group_count != len(control_group_rows):
        issues.append("row_control_group_count_mismatch")
    if repeated_control_groups != sum(1 for row in control_group_rows if int_value(row, "rows") > 1):
        issues.append("row_control_repeated_group_count_mismatch")
    if unique_before2 != len(before2_values):
        issues.append("row_control_unique_before2_mismatch")
    if unique_at2 != len(at2_values):
        issues.append("row_control_unique_at2_mismatch")
    if unique_deltas != len(delta_values):
        issues.append("row_control_unique_delta_count_mismatch")
    if metric_count != len(metric_rows):
        issues.append("row_control_metric_count_mismatch")
    if best_metric_hits != max([int_value(row, "hits") for row in metric_rows] or [0]):
        issues.append("row_control_best_metric_hits_mismatch")
    if best_group_rows != max_group_rows:
        issues.append("row_control_best_group_rows_mismatch")
    if negative_start_rows != sum(
        1 for row in row_control_rows if "negative_best_source_start" in split_values(row.get("issues", ""))
    ):
        issues.append("row_control_negative_start_count_mismatch")
    if out_of_range_start_rows != sum(
        1 for row in row_control_rows if "best_source_start_out_of_range" in split_values(row.get("issues", ""))
    ):
        issues.append("row_control_out_of_range_count_mismatch")
    if full_nonzero_rows != sum(int_value(row, "full_nonzero_rows") for row in candidate_rows):
        issues.append("row_control_full_row_count_mismatch")
    if issue_rows or issue_rows != sum(1 for row in candidate_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if selected_candidates < 1 or row_control_count < selected_candidates or control_group_count < 1:
        issues.append("missing_row_control_probe_rows")
    if "const TEX_GAP_ROW_CONTROL_PROBE = " not in text:
        issues.append("missing_tex_gap_row_control_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_row_control_probe",
            ok,
            expected=".tex row-control context probe is internally consistent",
            actual=(
                f"candidates={selected_candidates}, row_controls={row_control_count}, "
                f"control_groups={control_group_count}, metrics={metric_count}, "
                f"best_metric_hits={best_metric_hits}, out_of_range={out_of_range_start_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        row_control_count if ok else 0,
        control_group_count if ok else 0,
        best_metric_hits if ok else 0,
    )


def audit_tex_gap_row_sequence_probe(
    summary: Path,
    candidate_rows_path: Path,
    transition_rows_path: Path,
    step_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_row_sequence_probe", summary), 0, 0, 0
    if not candidate_rows_path.exists():
        return missing_gate("tex_gap_row_sequence_probe", candidate_rows_path), 0, 0, 0
    if not transition_rows_path.exists():
        return missing_gate("tex_gap_row_sequence_probe", transition_rows_path), 0, 0, 0
    if not step_rows_path.exists():
        return missing_gate("tex_gap_row_sequence_probe", step_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_row_sequence_probe", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    candidate_rows = read_csv(candidate_rows_path)
    transition_rows = read_csv(transition_rows_path)
    step_rows = read_csv(step_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    selected_candidates = int_value(total, "selected_candidates")
    row_sequence_count = int_value(total, "row_sequence_rows")
    fixture_count = int_value(total, "fixtures")
    valid_sequence_count = int_value(total, "valid_sequence_rows")
    source_step_groups = int_value(total, "source_step_groups")
    valid_source_step_groups = int_value(total, "valid_source_step_groups")
    dominant_source_step_rows = int_value(total, "dominant_source_step_rows")
    dominant_valid_source_step_rows = int_value(total, "dominant_valid_source_step_rows")
    stride_step_rows = int_value(total, "stride_step_rows")
    prev_nonzero_step_rows = int_value(total, "prev_nonzero_step_rows")
    current_nonzero_step_rows = int_value(total, "current_nonzero_step_rows")
    repeat_start_rows = int_value(total, "repeat_start_rows")
    rewind_rows = int_value(total, "rewind_rows")
    monotonic_candidates = int_value(total, "monotonic_candidates")
    strict_monotonic_candidates = int_value(total, "strict_monotonic_candidates")
    issue_rows = int_value(total, "issue_rows")

    candidate_fixtures = {
        (row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", ""))
        for row in candidate_rows
    }
    valid_step_counts = Counter(
        row.get("source_step", "")
        for row in transition_rows
        if row.get("valid_transition") == "1" and row.get("source_step", "")
    )

    if selected_candidates != len(candidate_rows):
        issues.append("row_sequence_candidate_count_mismatch")
    if row_sequence_count != len(transition_rows):
        issues.append("row_sequence_row_count_mismatch")
    if fixture_count != len(candidate_fixtures):
        issues.append("row_sequence_fixture_count_mismatch")
    if valid_sequence_count != sum(int_value(row, "valid_transition") for row in transition_rows):
        issues.append("row_sequence_valid_count_mismatch")
    if source_step_groups != len(step_rows):
        issues.append("row_sequence_step_group_count_mismatch")
    if valid_source_step_groups != len(valid_step_counts):
        issues.append("row_sequence_valid_step_group_count_mismatch")
    if dominant_source_step_rows != max([int_value(row, "rows") for row in step_rows] or [0]):
        issues.append("row_sequence_dominant_step_rows_mismatch")
    if dominant_valid_source_step_rows != max(valid_step_counts.values() or [0]):
        issues.append("row_sequence_dominant_valid_step_rows_mismatch")
    if stride_step_rows != sum(int_value(row, "stride_step_rows") for row in candidate_rows):
        issues.append("row_sequence_stride_step_count_mismatch")
    if prev_nonzero_step_rows != sum(int_value(row, "prev_nonzero_step_rows") for row in candidate_rows):
        issues.append("row_sequence_prev_nonzero_step_count_mismatch")
    if current_nonzero_step_rows != sum(int_value(row, "current_nonzero_step_rows") for row in candidate_rows):
        issues.append("row_sequence_current_nonzero_step_count_mismatch")
    if repeat_start_rows != sum(int_value(row, "repeat_start_rows") for row in candidate_rows):
        issues.append("row_sequence_repeat_start_count_mismatch")
    if rewind_rows != sum(int_value(row, "rewind_rows") for row in candidate_rows):
        issues.append("row_sequence_rewind_count_mismatch")
    if monotonic_candidates != sum(int_value(row, "monotonic") for row in candidate_rows):
        issues.append("row_sequence_monotonic_count_mismatch")
    if strict_monotonic_candidates != sum(int_value(row, "strict_monotonic") for row in candidate_rows):
        issues.append("row_sequence_strict_monotonic_count_mismatch")
    if issue_rows or issue_rows != sum(1 for row in candidate_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if selected_candidates < 1 or row_sequence_count < 1 or source_step_groups < 1:
        issues.append("missing_row_sequence_probe_rows")
    if "const TEX_GAP_ROW_SEQUENCE_PROBE = " not in text:
        issues.append("missing_tex_gap_row_sequence_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_row_sequence_probe",
            ok,
            expected=".tex row sequence probe is internally consistent",
            actual=(
                f"candidates={selected_candidates}, transitions={row_sequence_count}, "
                f"valid={valid_sequence_count}, source_steps={source_step_groups}, "
                f"dominant_step_rows={dominant_source_step_rows}, rewinds={rewind_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        row_sequence_count if ok else 0,
        source_step_groups if ok else 0,
        rewind_rows if ok else 0,
    )


def audit_tex_gap_row_literal_scan_probe(
    summary: Path,
    candidate_rows_path: Path,
    row_scan_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_row_literal_scan_probe", summary), 0, 0, 0
    if not candidate_rows_path.exists():
        return missing_gate("tex_gap_row_literal_scan_probe", candidate_rows_path), 0, 0, 0
    if not row_scan_rows_path.exists():
        return missing_gate("tex_gap_row_literal_scan_probe", row_scan_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_row_literal_scan_probe", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    candidate_rows = read_csv(candidate_rows_path)
    row_scan_rows = read_csv(row_scan_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    selected_candidates = int_value(total, "selected_candidates")
    literal_scan_count = int_value(total, "literal_scan_rows")
    fixture_count = int_value(total, "fixtures")
    full_nonzero_rows = int_value(total, "full_nonzero_rows")
    rows_with_literal_gain = int_value(total, "rows_with_literal_gain")
    unique_best_source_starts = int_value(total, "unique_best_source_starts")
    best_literal = int_value(total, "best_literal_nonzero_slots")
    best_gain = int_value(total, "best_gain_over_delta")
    issue_rows = int_value(total, "issue_rows")

    candidate_fixtures = {
        (row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", ""))
        for row in candidate_rows
    }
    best_starts = {
        row.get("literal_best_source_start", "")
        for row in row_scan_rows
        if row.get("literal_best_source_start", "")
    }
    if selected_candidates != len(candidate_rows):
        issues.append("row_literal_scan_candidate_count_mismatch")
    if literal_scan_count != len(row_scan_rows):
        issues.append("row_literal_scan_row_count_mismatch")
    if fixture_count != len(candidate_fixtures):
        issues.append("row_literal_scan_fixture_count_mismatch")
    if full_nonzero_rows != sum(int_value(row, "full_nonzero_rows") for row in candidate_rows):
        issues.append("row_literal_scan_full_row_count_mismatch")
    if rows_with_literal_gain != sum(int_value(row, "rows_with_literal_gain") for row in candidate_rows):
        issues.append("row_literal_scan_gain_row_count_mismatch")
    if unique_best_source_starts != len(best_starts):
        issues.append("row_literal_scan_unique_start_count_mismatch")
    if best_literal != max([int_value(row, "literal_nonzero_exact_slots") for row in candidate_rows] or [0]):
        issues.append("row_literal_scan_best_literal_mismatch")
    if best_gain != max([int_value(row, "gain_over_delta") for row in candidate_rows] or [0]):
        issues.append("row_literal_scan_best_gain_mismatch")
    if issue_rows or issue_rows != sum(1 for row in candidate_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if selected_candidates < 1 or literal_scan_count < selected_candidates:
        issues.append("missing_row_literal_scan_probe_rows")
    if "const TEX_GAP_ROW_LITERAL_SCAN_PROBE = " not in text:
        issues.append("missing_tex_gap_row_literal_scan_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_row_literal_scan_probe",
            ok,
            expected=".tex row literal scan probe is internally consistent",
            actual=(
                f"candidates={selected_candidates}, row_scans={literal_scan_count}, "
                f"fixtures={fixture_count}, full_rows={full_nonzero_rows}, "
                f"gain_rows={rows_with_literal_gain}, best_literal={best_literal}, best_gain={best_gain}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        literal_scan_count if ok else 0,
        best_literal if ok else 0,
        best_gain if ok else 0,
    )


def audit_tex_gap_row_fill_run_probe(
    summary: Path,
    candidate_rows_path: Path,
    row_fill_rows_path: Path,
    run_match_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_row_fill_run_probe", summary), 0, 0, 0
    if not candidate_rows_path.exists():
        return missing_gate("tex_gap_row_fill_run_probe", candidate_rows_path), 0, 0, 0
    if not row_fill_rows_path.exists():
        return missing_gate("tex_gap_row_fill_run_probe", row_fill_rows_path), 0, 0, 0
    if not run_match_rows_path.exists():
        return missing_gate("tex_gap_row_fill_run_probe", run_match_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_row_fill_run_probe", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    candidate_rows = read_csv(candidate_rows_path)
    row_fill_rows = read_csv(row_fill_rows_path)
    run_match_rows = read_csv(run_match_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    selected_candidates = int_value(total, "selected_candidates")
    row_fill_count = int_value(total, "row_fill_rows")
    fixture_count = int_value(total, "fixtures")
    literal_runs = int_value(total, "literal_runs")
    literal_bytes = int_value(total, "literal_bytes")
    eligible_literal_runs = int_value(total, "eligible_literal_runs")
    eligible_literal_bytes = int_value(total, "eligible_literal_bytes")
    sequential_literal_runs = int_value(total, "sequential_literal_runs")
    sequential_literal_bytes = int_value(total, "sequential_literal_bytes")
    unordered_literal_runs = int_value(total, "unordered_literal_runs")
    unordered_literal_bytes = int_value(total, "unordered_literal_bytes")
    full_rows = int_value(total, "full_sequential_literal_rows")
    best_sequential = int_value(total, "best_sequential_literal_bytes")
    issue_rows = int_value(total, "issue_rows")

    candidate_fixtures = {
        (row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", ""))
        for row in candidate_rows
    }
    if selected_candidates != len(candidate_rows):
        issues.append("row_fill_run_candidate_count_mismatch")
    if row_fill_count != len(row_fill_rows):
        issues.append("row_fill_run_row_count_mismatch")
    if fixture_count != len(candidate_fixtures):
        issues.append("row_fill_run_fixture_count_mismatch")
    if literal_runs != sum(int_value(row, "literal_runs") for row in candidate_rows):
        issues.append("row_fill_run_literal_run_count_mismatch")
    if literal_bytes != sum(int_value(row, "literal_bytes") for row in candidate_rows):
        issues.append("row_fill_run_literal_byte_count_mismatch")
    if eligible_literal_runs != sum(int_value(row, "eligible_literal_runs") for row in candidate_rows):
        issues.append("row_fill_run_eligible_run_count_mismatch")
    if eligible_literal_bytes != sum(int_value(row, "eligible_literal_bytes") for row in candidate_rows):
        issues.append("row_fill_run_eligible_byte_count_mismatch")
    if sequential_literal_runs != sum(int_value(row, "sequential_literal_runs") for row in candidate_rows):
        issues.append("row_fill_run_sequential_run_count_mismatch")
    if sequential_literal_bytes != sum(int_value(row, "sequential_literal_bytes") for row in candidate_rows):
        issues.append("row_fill_run_sequential_byte_count_mismatch")
    if unordered_literal_runs != sum(int_value(row, "unordered_literal_runs") for row in candidate_rows):
        issues.append("row_fill_run_unordered_run_count_mismatch")
    if unordered_literal_bytes != sum(int_value(row, "unordered_literal_bytes") for row in candidate_rows):
        issues.append("row_fill_run_unordered_byte_count_mismatch")
    if full_rows != sum(int_value(row, "full_sequential_literal_rows") for row in candidate_rows):
        issues.append("row_fill_run_full_row_count_mismatch")
    if best_sequential != max([int_value(row, "sequential_literal_bytes") for row in candidate_rows] or [0]):
        issues.append("row_fill_run_best_sequential_mismatch")
    if len(run_match_rows) != eligible_literal_runs:
        issues.append("row_fill_run_match_row_count_mismatch")
    if issue_rows or issue_rows != sum(1 for row in candidate_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if selected_candidates < 1 or row_fill_count < selected_candidates or eligible_literal_runs < 1:
        issues.append("missing_row_fill_run_probe_rows")
    if "const TEX_GAP_ROW_FILL_RUN_PROBE = " not in text:
        issues.append("missing_tex_gap_row_fill_run_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_row_fill_run_probe",
            ok,
            expected=".tex row zero-fill/literal-run probe is internally consistent",
            actual=(
                f"candidates={selected_candidates}, row_fills={row_fill_count}, "
                f"eligible_runs={eligible_literal_runs}, seq_bytes={sequential_literal_bytes}, "
                f"best_seq={best_sequential}, full_rows={full_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        row_fill_count if ok else 0,
        best_sequential if ok else 0,
        full_rows if ok else 0,
    )


def audit_tex_gap_control_grammar_probe(
    summary: Path,
    candidate_rows_path: Path,
    best_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_control_grammar_probe", summary), 0, 0, 0
    if not candidate_rows_path.exists():
        return missing_gate("tex_gap_control_grammar_probe", candidate_rows_path), 0, 0, 0
    if not best_rows_path.exists():
        return missing_gate("tex_gap_control_grammar_probe", best_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_control_grammar_probe", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    candidate_rows = read_csv(candidate_rows_path)
    best_rows = read_csv(best_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    candidate_count = int_value(total, "candidate_rows")
    grammar_variants = int_value(total, "grammar_variants")
    payload_offsets = int_value(total, "payload_offsets")
    exact_match_rows = int_value(total, "exact_match_rows")
    exact_match_fixtures = int_value(total, "exact_match_fixtures")
    best_prefix = int_value(total, "best_prefix_bytes")
    best_exact = int_value(total, "best_exact_bytes")
    issue_rows = int_value(total, "issue_rows")

    variants = {f"{row.get('variant', '')}:{row.get('parameter', '')}" for row in candidate_rows}
    offsets = {row.get("payload_offset", "") for row in candidate_rows if row.get("payload_offset", "")}
    full_rows = [row for row in candidate_rows if row.get("full_match") == "1"]
    full_fixtures = {fixture_key(row) for row in full_rows}

    if fixture_count != len(best_rows):
        issues.append("control_grammar_fixture_count_mismatch")
    if candidate_count != len(candidate_rows):
        issues.append("control_grammar_candidate_count_mismatch")
    if grammar_variants != len(variants):
        issues.append("control_grammar_variant_count_mismatch")
    if payload_offsets != len(offsets):
        issues.append("control_grammar_payload_offset_count_mismatch")
    if exact_match_rows != len(full_rows):
        issues.append("control_grammar_exact_row_count_mismatch")
    if exact_match_fixtures != len(full_fixtures):
        issues.append("control_grammar_exact_fixture_count_mismatch")
    if best_prefix != max([int_value(row, "prefix_bytes") for row in candidate_rows] or [0]):
        issues.append("control_grammar_best_prefix_mismatch")
    if best_exact != max([int_value(row, "exact_bytes") for row in candidate_rows] or [0]):
        issues.append("control_grammar_best_exact_mismatch")
    if issue_rows or issue_rows != sum(1 for row in best_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if fixture_count < 1 or candidate_count < fixture_count or grammar_variants < 1:
        issues.append("missing_control_grammar_probe_rows")
    if "const TEX_GAP_CONTROL_GRAMMAR_PROBE = " not in text:
        issues.append("missing_tex_gap_control_grammar_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_control_grammar_probe",
            ok,
            expected=".tex skip/copy control grammar probe is internally consistent",
            actual=(
                f"fixtures={fixture_count}, candidates={candidate_count}, variants={grammar_variants}, "
                f"offsets={payload_offsets}, exact={exact_match_rows}, "
                f"best_prefix={best_prefix}, best_exact={best_exact}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        candidate_count if ok else 0,
        best_prefix if ok else 0,
        best_exact if ok else 0,
    )


def audit_tex_gap_mismatch_trace_probe(
    summary: Path,
    trace_rows_path: Path,
    operation_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_mismatch_trace_probe", summary), 0, 0, 0, 0
    if not trace_rows_path.exists():
        return missing_gate("tex_gap_mismatch_trace_probe", trace_rows_path), 0, 0, 0, 0
    if not operation_rows_path.exists():
        return missing_gate("tex_gap_mismatch_trace_probe", operation_rows_path), 0, 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_mismatch_trace_probe", html_report), 0, 0, 0, 0

    summary_rows = read_csv(summary)
    trace_rows = read_csv(trace_rows_path)
    operation_rows = read_csv(operation_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    trace_count = int_value(total, "trace_rows")
    control_trace_rows = int_value(total, "control_trace_rows")
    replay_trace_rows = int_value(total, "replay_trace_rows")
    operation_count = int_value(total, "operation_rows")
    full_match_rows = int_value(total, "full_match_rows")
    first_mismatch_rows = int_value(total, "first_mismatch_rows")
    output_short_rows = int_value(total, "output_short_rows")
    expected_zero_rows = int_value(total, "expected_zero_mismatch_rows")
    output_zero_rows = int_value(total, "output_zero_mismatch_rows")
    best_control_prefix = int_value(total, "best_control_prefix")
    best_control_exact = int_value(total, "best_control_exact")
    best_replay_prefix = int_value(total, "best_replay_prefix")
    best_replay_exact = int_value(total, "best_replay_exact")
    issue_rows = int_value(total, "issue_rows")

    control_rows = [row for row in trace_rows if row.get("source") == "control_grammar"]
    replay_rows = [row for row in trace_rows if row.get("source") == "fixture_replay"]
    mismatch_rows = [row for row in trace_rows if row.get("first_mismatch_at")]

    if trace_count != len(trace_rows):
        issues.append("mismatch_trace_row_count_mismatch")
    if control_trace_rows != len(control_rows):
        issues.append("mismatch_trace_control_count_mismatch")
    if replay_trace_rows != len(replay_rows):
        issues.append("mismatch_trace_replay_count_mismatch")
    if fixture_count and trace_count != fixture_count * 2:
        issues.append("mismatch_trace_fixture_pair_count_mismatch")
    if operation_count != len(operation_rows):
        issues.append("mismatch_trace_operation_count_mismatch")
    if full_match_rows != sum(1 for row in trace_rows if row.get("full_match") == "1"):
        issues.append("mismatch_trace_full_match_count_mismatch")
    if first_mismatch_rows != len(mismatch_rows):
        issues.append("mismatch_trace_first_mismatch_count_mismatch")
    if output_short_rows != sum(1 for row in trace_rows if row.get("mismatch_kind") == "output_short"):
        issues.append("mismatch_trace_output_short_count_mismatch")
    if expected_zero_rows != sum(1 for row in mismatch_rows if row.get("expected_byte_hex") == "00"):
        issues.append("mismatch_trace_expected_zero_count_mismatch")
    if output_zero_rows != sum(1 for row in mismatch_rows if row.get("output_byte_hex") == "00"):
        issues.append("mismatch_trace_output_zero_count_mismatch")
    if best_control_prefix != max([int_value(row, "prefix_bytes") for row in control_rows] or [0]):
        issues.append("mismatch_trace_control_prefix_mismatch")
    if best_control_exact != max([int_value(row, "exact_bytes") for row in control_rows] or [0]):
        issues.append("mismatch_trace_control_exact_mismatch")
    if best_replay_prefix != max([int_value(row, "prefix_bytes") for row in replay_rows] or [0]):
        issues.append("mismatch_trace_replay_prefix_mismatch")
    if best_replay_exact != max([int_value(row, "exact_bytes") for row in replay_rows] or [0]):
        issues.append("mismatch_trace_replay_exact_mismatch")
    if issue_rows or issue_rows != sum(1 for row in trace_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if fixture_count < 1 or trace_count < 1 or operation_count < 1:
        issues.append("missing_mismatch_trace_rows")
    if "const TEX_GAP_MISMATCH_TRACE_PROBE = " not in text:
        issues.append("missing_tex_gap_mismatch_trace_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_mismatch_trace_probe",
            ok,
            expected=".tex gap mismatch trace probe is internally consistent",
            actual=(
                f"fixtures={fixture_count}, traces={trace_count}, ops={operation_count}, "
                f"mismatches={first_mismatch_rows}, control_prefix={best_control_prefix}, "
                f"replay_prefix={best_replay_prefix}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        trace_count if ok else 0,
        operation_count if ok else 0,
        best_control_prefix if ok else 0,
        best_replay_prefix if ok else 0,
    )


def audit_tex_gap_zero_literal_switch_probe(
    summary: Path,
    candidate_rows_path: Path,
    best_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_zero_literal_switch_probe", summary), 0, 0, 0
    if not candidate_rows_path.exists():
        return missing_gate("tex_gap_zero_literal_switch_probe", candidate_rows_path), 0, 0, 0
    if not best_rows_path.exists():
        return missing_gate("tex_gap_zero_literal_switch_probe", best_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_zero_literal_switch_probe", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    candidate_rows = read_csv(candidate_rows_path)
    best_rows = read_csv(best_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    candidate_count = int_value(total, "candidate_rows")
    zero_prefix_values = int_value(total, "zero_prefix_values")
    source_offsets = int_value(total, "source_offsets")
    stream_modes = int_value(total, "stream_modes")
    exact_match_rows = int_value(total, "exact_match_rows")
    exact_match_fixtures = int_value(total, "exact_match_fixtures")
    best_prefix = int_value(total, "best_prefix_bytes")
    best_exact = int_value(total, "best_exact_bytes")
    issue_rows = int_value(total, "issue_rows")

    full_rows = [row for row in candidate_rows if row.get("full_match") == "1"]
    if fixture_count != len(best_rows):
        issues.append("zero_literal_switch_fixture_count_mismatch")
    if candidate_count != len(candidate_rows):
        issues.append("zero_literal_switch_candidate_count_mismatch")
    if zero_prefix_values != len({row.get("zero_prefix", "") for row in candidate_rows}):
        issues.append("zero_literal_switch_zero_prefix_count_mismatch")
    if source_offsets != len({row.get("source_offset", "") for row in candidate_rows}):
        issues.append("zero_literal_switch_source_offset_count_mismatch")
    if stream_modes != len({row.get("stream_mode", "") for row in candidate_rows}):
        issues.append("zero_literal_switch_stream_mode_count_mismatch")
    if exact_match_rows != len(full_rows):
        issues.append("zero_literal_switch_exact_row_count_mismatch")
    if exact_match_fixtures != len({fixture_key(row) for row in full_rows}):
        issues.append("zero_literal_switch_exact_fixture_count_mismatch")
    if best_prefix != max([int_value(row, "prefix_bytes") for row in candidate_rows] or [0]):
        issues.append("zero_literal_switch_best_prefix_mismatch")
    if best_exact != max([int_value(row, "exact_bytes") for row in candidate_rows] or [0]):
        issues.append("zero_literal_switch_best_exact_mismatch")
    if issue_rows or issue_rows != sum(1 for row in best_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if fixture_count < 1 or candidate_count < fixture_count or stream_modes < 1:
        issues.append("missing_zero_literal_switch_rows")
    if "const TEX_GAP_ZERO_LITERAL_SWITCH_PROBE = " not in text:
        issues.append("missing_tex_gap_zero_literal_switch_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_zero_literal_switch_probe",
            ok,
            expected=".tex zero-prefix/literal-switch probe is internally consistent",
            actual=(
                f"fixtures={fixture_count}, candidates={candidate_count}, zero_prefixes={zero_prefix_values}, "
                f"offsets={source_offsets}, modes={stream_modes}, exact={exact_match_rows}, "
                f"best_prefix={best_prefix}, best_exact={best_exact}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        candidate_count if ok else 0,
        best_prefix if ok else 0,
        best_exact if ok else 0,
    )


def audit_tex_gap_zero_literal_segmentation_probe(
    summary: Path,
    strategy_rows_path: Path,
    operation_rows_path: Path,
    best_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_zero_literal_segmentation_probe", summary), 0, 0, 0, 0
    if not strategy_rows_path.exists():
        return missing_gate("tex_gap_zero_literal_segmentation_probe", strategy_rows_path), 0, 0, 0, 0
    if not operation_rows_path.exists():
        return missing_gate("tex_gap_zero_literal_segmentation_probe", operation_rows_path), 0, 0, 0, 0
    if not best_rows_path.exists():
        return missing_gate("tex_gap_zero_literal_segmentation_probe", best_rows_path), 0, 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_zero_literal_segmentation_probe", html_report), 0, 0, 0, 0

    summary_rows = read_csv(summary)
    strategy_rows = read_csv(strategy_rows_path)
    operation_rows = read_csv(operation_rows_path)
    best_rows = read_csv(best_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    strategy_count = int_value(total, "strategy_rows")
    operation_count = int_value(total, "operation_rows")
    strategies = int_value(total, "strategies")
    total_expected = int_value(total, "total_expected_bytes")
    best_total_covered = int_value(total, "best_total_covered_bytes")
    best_total_gap = int_value(total, "best_total_gap_bytes")
    best_total_literal = int_value(total, "best_total_literal_bytes")
    best_total_zero = int_value(total, "best_total_zero_bytes")
    best_total_ops = int_value(total, "best_total_ops")
    full_cover_fixtures = int_value(total, "full_cover_fixtures")
    issue_rows = int_value(total, "issue_rows")

    if fixture_count != len(best_rows):
        issues.append("zero_literal_segmentation_fixture_count_mismatch")
    if strategy_count != len(strategy_rows):
        issues.append("zero_literal_segmentation_strategy_count_mismatch")
    if operation_count != len(operation_rows):
        issues.append("zero_literal_segmentation_operation_count_mismatch")
    if strategies != len({row.get("strategy", "") for row in strategy_rows}):
        issues.append("zero_literal_segmentation_strategy_name_count_mismatch")
    if total_expected != sum(int_value(row, "pixel_gap") for row in best_rows):
        issues.append("zero_literal_segmentation_expected_sum_mismatch")
    if best_total_covered != sum(int_value(row, "best_covered_bytes") for row in best_rows):
        issues.append("zero_literal_segmentation_covered_sum_mismatch")
    if best_total_gap != sum(int_value(row, "best_gap_bytes") for row in best_rows):
        issues.append("zero_literal_segmentation_gap_sum_mismatch")
    if best_total_literal != sum(int_value(row, "best_literal_bytes") for row in best_rows):
        issues.append("zero_literal_segmentation_literal_sum_mismatch")
    if best_total_zero != sum(int_value(row, "best_zero_bytes") for row in best_rows):
        issues.append("zero_literal_segmentation_zero_sum_mismatch")
    if best_total_ops != sum(int_value(row, "best_total_ops") for row in best_rows):
        issues.append("zero_literal_segmentation_ops_sum_mismatch")
    if full_cover_fixtures != sum(1 for row in best_rows if int_value(row, "best_gap_bytes") == 0):
        issues.append("zero_literal_segmentation_full_cover_count_mismatch")
    if issue_rows or issue_rows != sum(1 for row in best_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if fixture_count < 1 or strategy_count < fixture_count or operation_count < 1:
        issues.append("missing_zero_literal_segmentation_rows")
    if "const TEX_GAP_ZERO_LITERAL_SEGMENTATION_PROBE = " not in text:
        issues.append("missing_tex_gap_zero_literal_segmentation_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_zero_literal_segmentation_probe",
            ok,
            expected=".tex zero/literal segmentation probe is internally consistent",
            actual=(
                f"fixtures={fixture_count}, strategies={strategy_count}, ops={operation_count}, "
                f"covered={best_total_covered}/{total_expected}, gaps={best_total_gap}, "
                f"literal={best_total_literal}, full={full_cover_fixtures}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        best_total_covered if ok else 0,
        best_total_gap if ok else 0,
        best_total_literal if ok else 0,
        full_cover_fixtures if ok else 0,
    )


def audit_tex_gap_segmentation_control_correlation_probe(
    summary: Path,
    operation_rows_path: Path,
    context_rows_path: Path,
    delta_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_segmentation_control_correlation_probe", summary), 0, 0, 0, 0
    if not operation_rows_path.exists():
        return missing_gate("tex_gap_segmentation_control_correlation_probe", operation_rows_path), 0, 0, 0, 0
    if not context_rows_path.exists():
        return missing_gate("tex_gap_segmentation_control_correlation_probe", context_rows_path), 0, 0, 0, 0
    if not delta_rows_path.exists():
        return missing_gate("tex_gap_segmentation_control_correlation_probe", delta_rows_path), 0, 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_segmentation_control_correlation_probe", html_report), 0, 0, 0, 0

    summary_rows = read_csv(summary)
    operation_rows = read_csv(operation_rows_path)
    context_rows = read_csv(context_rows_path)
    delta_rows = read_csv(delta_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    operation_count = int_value(total, "operation_rows")
    literal_ops = int_value(total, "literal_ops")
    zero_ops = int_value(total, "zero_ops")
    gap_ops = int_value(total, "gap_ops")
    literal_with_prev = int_value(total, "literal_ops_with_prev_literal")
    literal_forward_steps = int_value(total, "literal_forward_steps")
    literal_backward_steps = int_value(total, "literal_backward_steps")
    literal_reuse_steps = int_value(total, "literal_reuse_steps")
    length_u8_hits = int_value(total, "length_u8_hit_rows")
    length_u16_hits = int_value(total, "length_u16le_hit_rows")
    delta_u8_hits = int_value(total, "source_delta_u8_hit_rows")
    delta_u16_hits = int_value(total, "source_delta_u16le_hit_rows")
    zero_len64_ops = int_value(total, "zero_len64_ops")
    zero_len93_ops = int_value(total, "zero_len93_ops")
    top_literal_pre2 = total.get("top_literal_pre2", "")
    top_literal_delta = total.get("top_literal_delta", "")
    issue_rows = int_value(total, "issue_rows")

    literal_rows = [row for row in operation_rows if row.get("op_kind") == "literal"]
    zero_rows = [row for row in operation_rows if row.get("op_kind") == "zero"]
    gap_rows = [row for row in operation_rows if row.get("op_kind") == "gap"]
    literal_prev_rows = [row for row in literal_rows if row.get("source_delta_from_prev_literal_end")]
    pre2_counter = Counter(row.get("pre2_hex", "") for row in literal_rows if row.get("pre2_hex"))
    delta_counter = Counter(row.get("source_delta_from_prev_literal_end", "") for row in literal_prev_rows)
    actual_top_pre2 = pre2_counter.most_common(1)[0][0] if pre2_counter else ""
    actual_top_delta = delta_counter.most_common(1)[0][0] if delta_counter else ""

    if operation_count != len(operation_rows):
        issues.append("segmentation_control_correlation_operation_count_mismatch")
    if literal_ops != len(literal_rows):
        issues.append("segmentation_control_correlation_literal_count_mismatch")
    if zero_ops != len(zero_rows):
        issues.append("segmentation_control_correlation_zero_count_mismatch")
    if gap_ops != len(gap_rows):
        issues.append("segmentation_control_correlation_gap_count_mismatch")
    if operation_count != literal_ops + zero_ops + gap_ops:
        issues.append("segmentation_control_correlation_kind_sum_mismatch")
    if literal_with_prev != len(literal_prev_rows):
        issues.append("segmentation_control_correlation_prev_literal_count_mismatch")
    if literal_forward_steps != sum(1 for row in literal_prev_rows if row.get("source_direction") == "forward"):
        issues.append("segmentation_control_correlation_forward_count_mismatch")
    if literal_backward_steps != sum(1 for row in literal_prev_rows if row.get("source_direction") == "backward"):
        issues.append("segmentation_control_correlation_backward_count_mismatch")
    if literal_reuse_steps != sum(1 for row in literal_prev_rows if row.get("source_direction") == "reuse"):
        issues.append("segmentation_control_correlation_reuse_count_mismatch")
    if length_u8_hits != sum(1 for row in operation_rows if row.get("length_u8_hit_offsets")):
        issues.append("segmentation_control_correlation_length_u8_count_mismatch")
    if length_u16_hits != sum(1 for row in operation_rows if row.get("length_u16le_hit_offsets")):
        issues.append("segmentation_control_correlation_length_u16_count_mismatch")
    if delta_u8_hits != sum(1 for row in literal_rows if row.get("source_delta_u8_hit_offsets")):
        issues.append("segmentation_control_correlation_delta_u8_count_mismatch")
    if delta_u16_hits != sum(1 for row in literal_rows if row.get("source_delta_u16le_hit_offsets")):
        issues.append("segmentation_control_correlation_delta_u16_count_mismatch")
    if zero_len64_ops != sum(1 for row in zero_rows if int_value(row, "length") == 64):
        issues.append("segmentation_control_correlation_zero64_count_mismatch")
    if zero_len93_ops != sum(1 for row in zero_rows if int_value(row, "length") == 93):
        issues.append("segmentation_control_correlation_zero93_count_mismatch")
    if top_literal_pre2 != actual_top_pre2:
        issues.append("segmentation_control_correlation_top_pre2_mismatch")
    if top_literal_delta != actual_top_delta:
        issues.append("segmentation_control_correlation_top_delta_mismatch")
    if actual_top_pre2 and not any(
        row.get("context_type") == "pre2_hex" and row.get("value") == actual_top_pre2 for row in context_rows
    ):
        issues.append("segmentation_control_correlation_missing_top_pre2_context")
    if actual_top_delta and not any(
        row.get("delta_type") == "source_delta_from_prev_literal_end" and row.get("value") == actual_top_delta
        for row in delta_rows
    ):
        issues.append("segmentation_control_correlation_missing_top_delta_row")
    if issue_rows or issue_rows != sum(1 for row in operation_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if fixture_count < 1 or operation_count < 1 or literal_ops < 1 or zero_ops < 1:
        issues.append("missing_segmentation_control_correlation_rows")
    if not context_rows:
        issues.append("missing_segmentation_control_correlation_context_rows")
    if not delta_rows:
        issues.append("missing_segmentation_control_correlation_delta_rows")
    if "const TEX_GAP_SEGMENTATION_CONTROL_CORRELATION_PROBE = " not in text:
        issues.append("missing_tex_gap_segmentation_control_correlation_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_segmentation_control_correlation_probe",
            ok,
            expected=".tex segmentation/control correlation probe is internally consistent",
            actual=(
                f"fixtures={fixture_count}, ops={operation_count}, literal={literal_ops}, "
                f"forward={literal_forward_steps}, len_u8_hits={length_u8_hits}, "
                f"top_pre2={top_literal_pre2}, top_delta={top_literal_delta}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        operation_count if ok else 0,
        literal_ops if ok else 0,
        literal_forward_steps if ok else 0,
        length_u8_hits if ok else 0,
    )


def audit_tex_gap_literal_token_probe(
    summary: Path,
    rule_rows_path: Path,
    literal_rows_path: Path,
    token_rows_path: Path,
    fixture_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_literal_token_probe", summary), 0, 0, 0, 0
    if not rule_rows_path.exists():
        return missing_gate("tex_gap_literal_token_probe", rule_rows_path), 0, 0, 0, 0
    if not literal_rows_path.exists():
        return missing_gate("tex_gap_literal_token_probe", literal_rows_path), 0, 0, 0, 0
    if not token_rows_path.exists():
        return missing_gate("tex_gap_literal_token_probe", token_rows_path), 0, 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate("tex_gap_literal_token_probe", fixture_rows_path), 0, 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_literal_token_probe", html_report), 0, 0, 0, 0

    summary_rows = read_csv(summary)
    rule_rows = read_csv(rule_rows_path)
    literal_rows = read_csv(literal_rows_path)
    token_rows = read_csv(token_rows_path)
    fixture_rows = read_csv(fixture_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    fixtures_with_literal_ops = int_value(total, "fixtures_with_literal_ops")
    literal_ops = int_value(total, "literal_ops")
    literal_bytes = int_value(total, "literal_bytes")
    plus3_ops = int_value(total, "token_plus3_match_ops")
    plus3_bytes = int_value(total, "token_plus3_match_bytes")
    plus3_full_fixtures = int_value(total, "token_plus3_full_fixtures")
    first_plus3 = int_value(total, "first_literal_token_plus3_matches")
    with_prev_plus3 = int_value(total, "with_prev_token_plus3_matches")
    small_token_ops = int_value(total, "small_token_ops")
    small_token_plus3 = int_value(total, "small_token_plus3_matches")
    missing_pre1 = int_value(total, "literal_ops_missing_pre1")
    token_rule_rows = int_value(total, "token_rule_rows")
    issue_rows = int_value(total, "issue_rows")

    plus3_rows = [row for row in literal_rows if row.get("token_plus3_match") == "1"]
    first_literal_rows = [row for row in literal_rows if not row.get("source_delta_from_prev_literal_end")]
    with_prev_rows = [row for row in literal_rows if row.get("source_delta_from_prev_literal_end")]
    small_token_rows = [
        row for row in literal_rows if row.get("token_value") and int_value(row, "token_value") <= 13
    ]
    plus3_rule = next((row for row in rule_rows if row.get("rule") == "token_plus_3"), {})

    if fixture_count != len(fixture_rows):
        issues.append("literal_token_fixture_count_mismatch")
    if fixtures_with_literal_ops != sum(1 for row in fixture_rows if int_value(row, "literal_ops") > 0):
        issues.append("literal_token_nonempty_fixture_count_mismatch")
    if literal_ops != len(literal_rows):
        issues.append("literal_token_literal_count_mismatch")
    if literal_bytes != sum(int_value(row, "length") for row in literal_rows):
        issues.append("literal_token_literal_byte_sum_mismatch")
    if plus3_ops != len(plus3_rows):
        issues.append("literal_token_plus3_count_mismatch")
    if plus3_bytes != sum(int_value(row, "length") for row in plus3_rows):
        issues.append("literal_token_plus3_byte_sum_mismatch")
    if plus3_full_fixtures != sum(1 for row in fixture_rows if row.get("token_plus3_full") == "1"):
        issues.append("literal_token_plus3_full_fixture_count_mismatch")
    if first_plus3 != sum(1 for row in first_literal_rows if row.get("token_plus3_match") == "1"):
        issues.append("literal_token_first_plus3_count_mismatch")
    if with_prev_plus3 != sum(1 for row in with_prev_rows if row.get("token_plus3_match") == "1"):
        issues.append("literal_token_with_prev_plus3_count_mismatch")
    if small_token_ops != len(small_token_rows):
        issues.append("literal_token_small_token_count_mismatch")
    if small_token_plus3 != sum(1 for row in small_token_rows if row.get("token_plus3_match") == "1"):
        issues.append("literal_token_small_token_plus3_count_mismatch")
    if missing_pre1 != sum(1 for row in literal_rows if not row.get("token_hex")):
        issues.append("literal_token_missing_pre1_count_mismatch")
    if token_rule_rows != len(rule_rows):
        issues.append("literal_token_rule_count_mismatch")
    if not plus3_rule:
        issues.append("literal_token_missing_plus3_rule")
    else:
        if int_value(plus3_rule, "match_ops") != plus3_ops:
            issues.append("literal_token_plus3_rule_ops_mismatch")
        if int_value(plus3_rule, "match_bytes") != plus3_bytes:
            issues.append("literal_token_plus3_rule_bytes_mismatch")
        if int_value(plus3_rule, "full_fixture_count") != plus3_full_fixtures:
            issues.append("literal_token_plus3_rule_full_fixture_mismatch")
    if issue_rows or issue_rows != sum(1 for row in literal_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if literal_ops < 1 or plus3_ops < 1 or not token_rows:
        issues.append("missing_literal_token_rows")
    if "const TEX_GAP_LITERAL_TOKEN_PROBE = " not in text:
        issues.append("missing_tex_gap_literal_token_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_literal_token_probe",
            ok,
            expected=".tex literal token length probe is internally consistent",
            actual=(
                f"fixtures={fixture_count}, literal_ops={literal_ops}, literal_bytes={literal_bytes}, "
                f"token_plus3={plus3_ops}/{plus3_bytes}, full_fixtures={plus3_full_fixtures}, "
                f"small_tokens={small_token_plus3}/{small_token_ops}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        plus3_ops if ok else 0,
        plus3_bytes if ok else 0,
        plus3_full_fixtures if ok else 0,
        small_token_plus3 if ok else 0,
    )


def literal_token_classifier_value(row: dict[str, str]) -> int:
    return int_value(row, "token_value") if row.get("token_value") else -1


def literal_token_classifier_delta(row: dict[str, str]) -> int:
    return int_value(row, "source_delta_from_prev_literal_end") if row.get("source_delta_from_prev_literal_end") else 0


def literal_token_classifier_predicate(name: str, row: dict[str, str]) -> bool:
    token = literal_token_classifier_value(row)
    direction = row.get("source_direction", "")
    delta = abs(literal_token_classifier_delta(row))
    if name == "small_token":
        return 0 <= token <= 13
    if name == "small_nonzero_token":
        return 1 <= token <= 13
    if name == "small_not_backward":
        return 0 <= token <= 13 and direction != "backward"
    if name == "small_forward":
        return 0 <= token <= 13 and direction == "forward"
    if name == "small_abs_delta_le16":
        return 0 <= token <= 13 and delta <= 16
    if name == "small_not_backward_abs_delta_le128":
        return 0 <= token <= 13 and direction != "backward" and delta <= 128
    if name == "small_not_backward_abs_delta_le512":
        return 0 <= token <= 13 and direction != "backward" and delta <= 512
    if name == "oracle_token_plus3":
        return row.get("token_plus3_match") == "1"
    return False


def literal_token_classifier_metrics(
    name: str,
    literal_rows: list[dict[str, str]],
) -> tuple[int, int, int, int, int, int]:
    selected = [row for row in literal_rows if literal_token_classifier_predicate(name, row)]
    actual_rows = [row for row in literal_rows if row.get("token_plus3_match") == "1"]
    true_positive = [row for row in selected if row.get("token_plus3_match") == "1"]
    false_positive = [row for row in selected if row.get("token_plus3_match") != "1"]
    selected_ids = {id(row) for row in true_positive}
    false_negative = [row for row in actual_rows if id(row) not in selected_ids]
    return (
        len(selected),
        len(true_positive),
        len(false_positive),
        len(false_negative),
        sum(int_value(row, "length") for row in true_positive),
        sum(int_value(row, "length") for row in false_positive),
    )


def audit_tex_gap_literal_token_classifier_probe(
    summary: Path,
    classifier_rows_path: Path,
    error_rows_path: Path,
    fixture_rows_path: Path,
    literal_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_literal_token_classifier_probe", summary), 0, 0, 0, 0
    if not classifier_rows_path.exists():
        return missing_gate("tex_gap_literal_token_classifier_probe", classifier_rows_path), 0, 0, 0, 0
    if not error_rows_path.exists():
        return missing_gate("tex_gap_literal_token_classifier_probe", error_rows_path), 0, 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate("tex_gap_literal_token_classifier_probe", fixture_rows_path), 0, 0, 0, 0
    if not literal_rows_path.exists():
        return missing_gate("tex_gap_literal_token_classifier_probe", literal_rows_path), 0, 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_literal_token_classifier_probe", html_report), 0, 0, 0, 0

    summary_rows = read_csv(summary)
    classifier_rows = read_csv(classifier_rows_path)
    error_rows = read_csv(error_rows_path)
    fixture_rows = read_csv(fixture_rows_path)
    literal_rows = read_csv(literal_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    literal_ops = int_value(total, "literal_ops")
    actual_ops = int_value(total, "actual_token_plus3_ops")
    actual_bytes = int_value(total, "actual_token_plus3_bytes")
    small_selected = int_value(total, "small_token_selected_ops")
    small_fp = int_value(total, "small_token_false_positive_ops")
    high_recall_name = total.get("high_recall_classifier", "")
    high_recall_fp = int_value(total, "high_recall_false_positive_ops")
    high_precision_name = total.get("high_precision_classifier", "")
    high_precision_fp = int_value(total, "high_precision_false_positive_ops")
    classifier_count = int_value(total, "classifier_rows")
    issue_rows = int_value(total, "issue_rows")

    actual_rows = [row for row in literal_rows if row.get("token_plus3_match") == "1"]
    if literal_ops != len(literal_rows):
        issues.append("literal_token_classifier_literal_count_mismatch")
    if actual_ops != len(actual_rows):
        issues.append("literal_token_classifier_actual_count_mismatch")
    if actual_bytes != sum(int_value(row, "length") for row in actual_rows):
        issues.append("literal_token_classifier_actual_byte_sum_mismatch")
    if classifier_count != len(classifier_rows):
        issues.append("literal_token_classifier_row_count_mismatch")
    small_metrics = literal_token_classifier_metrics("small_token", literal_rows)
    if small_selected != small_metrics[0]:
        issues.append("literal_token_classifier_small_selected_mismatch")
    if small_fp != small_metrics[2]:
        issues.append("literal_token_classifier_small_fp_mismatch")

    classifier_names = {row.get("classifier", "") for row in classifier_rows}
    expected_classifiers = {
        "small_token",
        "small_nonzero_token",
        "small_not_backward",
        "small_forward",
        "small_abs_delta_le16",
        "small_not_backward_abs_delta_le128",
        "small_not_backward_abs_delta_le512",
        "oracle_token_plus3",
    }
    if classifier_names != expected_classifiers:
        issues.append("literal_token_classifier_name_set_mismatch")
    for row in classifier_rows:
        name = row.get("classifier", "")
        selected, tp, fp, fn, tp_bytes, fp_bytes = literal_token_classifier_metrics(name, literal_rows)
        if int_value(row, "selected_ops") != selected:
            issues.append(f"{name}:selected_ops_mismatch")
        if int_value(row, "true_positive_ops") != tp:
            issues.append(f"{name}:true_positive_ops_mismatch")
        if int_value(row, "false_positive_ops") != fp:
            issues.append(f"{name}:false_positive_ops_mismatch")
        if int_value(row, "false_negative_ops") != fn:
            issues.append(f"{name}:false_negative_ops_mismatch")
        if int_value(row, "true_positive_bytes") != tp_bytes:
            issues.append(f"{name}:true_positive_bytes_mismatch")
        if int_value(row, "false_positive_bytes") != fp_bytes:
            issues.append(f"{name}:false_positive_bytes_mismatch")

    if high_recall_name not in classifier_names:
        issues.append("literal_token_classifier_high_recall_missing")
    elif high_recall_fp != literal_token_classifier_metrics(high_recall_name, literal_rows)[2]:
        issues.append("literal_token_classifier_high_recall_fp_mismatch")
    if high_precision_name not in classifier_names:
        issues.append("literal_token_classifier_high_precision_missing")
    elif high_precision_fp != literal_token_classifier_metrics(high_precision_name, literal_rows)[2]:
        issues.append("literal_token_classifier_high_precision_fp_mismatch")
    if len(fixture_rows) != len({(row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")) for row in literal_rows}):
        issues.append("literal_token_classifier_fixture_count_mismatch")
    expected_error_rows = []
    for name in ("small_token", "small_not_backward", "small_not_backward_abs_delta_le512"):
        for row in literal_rows:
            selected = literal_token_classifier_predicate(name, row)
            actual = row.get("token_plus3_match") == "1"
            if (selected and not actual) or (actual and not selected):
                expected_error_rows.append((name, row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", ""), row.get("op_index", "")))
    actual_error_rows = [
        (row.get("classifier", ""), row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", ""), row.get("op_index", ""))
        for row in error_rows
    ]
    if sorted(actual_error_rows) != sorted(expected_error_rows):
        issues.append("literal_token_classifier_error_rows_mismatch")
    if issue_rows or issue_rows != sum(1 for row in literal_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if literal_ops < 1 or actual_ops < 1 or not classifier_rows:
        issues.append("missing_literal_token_classifier_rows")
    if "const TEX_GAP_LITERAL_TOKEN_CLASSIFIER_PROBE = " not in text:
        issues.append("missing_tex_gap_literal_token_classifier_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_literal_token_classifier_probe",
            ok,
            expected=".tex literal token classifier probe is internally consistent",
            actual=(
                f"literal_ops={literal_ops}, actual={actual_ops}/{actual_bytes}, "
                f"small_fp={small_fp}, high_recall={high_recall_name}:{high_recall_fp}, "
                f"high_precision={high_precision_name}:{high_precision_fp}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        small_fp if ok else 0,
        high_recall_fp if ok else 0,
        high_precision_fp if ok else 0,
        classifier_count if ok else 0,
    )


LITERAL_FP_REJECTION_REPEATED_FALSE_PRE2 = {"020a", "0703", "0704", "0002", "2f08"}
LITERAL_FP_REJECTION_REPEATED_FALSE_PRE4 = {"6edc020a", "5d5c0703", "6bfc0704", "17542f08"}
LITERAL_FP_REJECTION_REPEATED_FALSE_NEXT2 = {"5a5c", "5d6d", "aa6c", "7b6a"}
LITERAL_FP_REJECTION_REPEATED_FALSE_MOD64 = {5, 28, 34}


def literal_fp_rejection_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", ""), row.get("op_index", "")


def literal_fp_rejection_fixture_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def literal_fp_rejection_enrich(
    literal_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    operations = {literal_fp_rejection_key(row): row for row in operation_rows}
    enriched_rows: list[dict[str, str]] = []
    for row in literal_rows:
        operation = operations.get(literal_fp_rejection_key(row), {})
        enriched = dict(row)
        enriched["pre2_hex"] = operation.get("pre2_hex", "")
        enriched["pre4_hex"] = operation.get("pre4_hex", "")
        enriched["next2_hex"] = operation.get("next2_hex", "")
        enriched["expected_mod64"] = operation.get("expected_mod64", "")
        enriched["join_missing"] = "0" if operation else "1"
        enriched_rows.append(enriched)
    return enriched_rows


def literal_fp_rejection_token(row: dict[str, str]) -> int:
    return int_value(row, "token_value") if row.get("token_value") else -1


def literal_fp_rejection_mod64(row: dict[str, str]) -> int:
    return int_value(row, "expected_mod64") if row.get("expected_mod64") else -1


def literal_fp_rejection_is_actual(row: dict[str, str]) -> bool:
    return row.get("token_plus3_match") == "1"


def literal_fp_rejection_is_small(row: dict[str, str]) -> bool:
    return 0 <= literal_fp_rejection_token(row) <= 13


def literal_fp_rejection_is_nonzero_small(row: dict[str, str]) -> bool:
    return 1 <= literal_fp_rejection_token(row) <= 13


def literal_fp_rejection_predicate(name: str, row: dict[str, str]) -> bool:
    if name == "small_token":
        return literal_fp_rejection_is_small(row)
    if name == "small_nonzero_token":
        return literal_fp_rejection_is_nonzero_small(row)
    if name == "small_nonzero_next2_clean":
        return (
            literal_fp_rejection_is_nonzero_small(row)
            and row.get("next2_hex") not in LITERAL_FP_REJECTION_REPEATED_FALSE_NEXT2
        )
    if name == "small_nonzero_pre4_clean":
        return (
            literal_fp_rejection_is_nonzero_small(row)
            and row.get("pre4_hex") not in LITERAL_FP_REJECTION_REPEATED_FALSE_PRE4
        )
    if name == "small_nonzero_pre2_clean":
        return (
            literal_fp_rejection_is_nonzero_small(row)
            and row.get("pre2_hex") not in LITERAL_FP_REJECTION_REPEATED_FALSE_PRE2
        )
    if name == "small_not_backward_nonzero_pre2_clean":
        return (
            literal_fp_rejection_is_nonzero_small(row)
            and row.get("source_direction") != "backward"
            and row.get("pre2_hex") not in LITERAL_FP_REJECTION_REPEATED_FALSE_PRE2
        )
    if name == "small_not_backward_nonzero_pre4_mod_clean":
        return (
            literal_fp_rejection_is_nonzero_small(row)
            and row.get("source_direction") != "backward"
            and row.get("pre4_hex") not in LITERAL_FP_REJECTION_REPEATED_FALSE_PRE4
            and literal_fp_rejection_mod64(row) not in LITERAL_FP_REJECTION_REPEATED_FALSE_MOD64
        )
    if name == "oracle_token_plus3":
        return literal_fp_rejection_is_actual(row)
    return False


def literal_fp_rejection_metrics(
    name: str,
    literal_rows: list[dict[str, str]],
) -> tuple[int, int, int, int, int, int, int, int]:
    selected = [row for row in literal_rows if literal_fp_rejection_predicate(name, row)]
    actual_rows = [row for row in literal_rows if literal_fp_rejection_is_actual(row)]
    true_positive = [row for row in selected if literal_fp_rejection_is_actual(row)]
    false_positive = [row for row in selected if not literal_fp_rejection_is_actual(row)]
    true_ids = {id(row) for row in true_positive}
    false_negative = [row for row in actual_rows if id(row) not in true_ids]
    selected_ids = {id(row) for row in selected}
    baseline_false = [
        row for row in literal_rows if literal_fp_rejection_is_small(row) and not literal_fp_rejection_is_actual(row)
    ]
    rejected_baseline = [row for row in baseline_false if id(row) not in selected_ids]
    return (
        len(selected),
        len(true_positive),
        len(false_positive),
        len(false_negative),
        sum(int_value(row, "length") for row in true_positive),
        sum(int_value(row, "length") for row in false_positive),
        len(rejected_baseline),
        sum(int_value(row, "length") for row in rejected_baseline),
    )


def literal_fp_rejection_best_full_recall(
    classifier_rows: list[dict[str, str]],
    actual_ops: int,
) -> dict[str, str]:
    candidates = [
        row
        for row in classifier_rows
        if row.get("uses_oracle_filter") != "1" and int_value(row, "true_positive_ops") == actual_ops
    ]
    return min(
        candidates,
        key=lambda row: (
            int_value(row, "false_positive_bytes"),
            int_value(row, "false_positive_ops"),
            row.get("classifier", ""),
        ),
    )


def literal_fp_rejection_best_low_false(
    classifier_rows: list[dict[str, str]],
    actual_ops: int,
) -> dict[str, str]:
    candidates = [
        row
        for row in classifier_rows
        if row.get("uses_oracle_filter") != "1"
        and actual_ops
        and int_value(row, "true_positive_ops") / actual_ops >= 0.90
    ]
    return min(
        candidates,
        key=lambda row: (
            int_value(row, "false_positive_bytes"),
            int_value(row, "false_positive_ops"),
            -int_value(row, "true_positive_bytes"),
            row.get("classifier", ""),
        ),
    )


def audit_tex_gap_literal_fp_rejection_probe(
    summary: Path,
    classifier_rows_path: Path,
    rejection_rows_path: Path,
    fixture_rows_path: Path,
    literal_rows_path: Path,
    operation_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_literal_fp_rejection_probe", summary), 0, 0, 0, 0
    if not classifier_rows_path.exists():
        return missing_gate("tex_gap_literal_fp_rejection_probe", classifier_rows_path), 0, 0, 0, 0
    if not rejection_rows_path.exists():
        return missing_gate("tex_gap_literal_fp_rejection_probe", rejection_rows_path), 0, 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate("tex_gap_literal_fp_rejection_probe", fixture_rows_path), 0, 0, 0, 0
    if not literal_rows_path.exists():
        return missing_gate("tex_gap_literal_fp_rejection_probe", literal_rows_path), 0, 0, 0, 0
    if not operation_rows_path.exists():
        return missing_gate("tex_gap_literal_fp_rejection_probe", operation_rows_path), 0, 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_literal_fp_rejection_probe", html_report), 0, 0, 0, 0

    summary_rows = read_csv(summary)
    classifier_rows = read_csv(classifier_rows_path)
    rejection_rows = read_csv(rejection_rows_path)
    fixture_rows = read_csv(fixture_rows_path)
    raw_literal_rows = read_csv(literal_rows_path)
    operation_rows = read_csv(operation_rows_path)
    literal_rows = literal_fp_rejection_enrich(raw_literal_rows, operation_rows)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    literal_count = int_value(total, "literal_rows")
    operation_count = int_value(total, "operation_rows")
    actual_ops = int_value(total, "actual_token_plus3_ops")
    actual_bytes = int_value(total, "actual_token_plus3_bytes")
    baseline_fp = int_value(total, "baseline_false_positive_ops")
    baseline_fp_bytes = int_value(total, "baseline_false_positive_bytes")
    full_recall_name = total.get("full_recall_candidate", "")
    full_recall_tp = int_value(total, "full_recall_true_positive_ops")
    full_recall_fp = int_value(total, "full_recall_false_positive_ops")
    full_recall_fp_bytes = int_value(total, "full_recall_false_positive_bytes")
    low_false_name = total.get("low_false_candidate", "")
    low_false_tp = int_value(total, "low_false_true_positive_ops")
    low_false_fp = int_value(total, "low_false_false_positive_ops")
    low_false_fp_bytes = int_value(total, "low_false_false_positive_bytes")
    candidate_count = int_value(total, "candidate_rows")
    rejection_count = int_value(total, "rejection_rows")
    fixture_count = int_value(total, "fixture_rows")
    issue_rows = int_value(total, "issue_rows")

    actual_rows = [row for row in literal_rows if literal_fp_rejection_is_actual(row)]
    baseline_false_rows = [
        row for row in literal_rows if literal_fp_rejection_is_small(row) and not literal_fp_rejection_is_actual(row)
    ]
    expected_issue_rows = (
        sum(1 for row in literal_rows if row.get("issues"))
        + sum(1 for row in literal_rows if row.get("join_missing") == "1")
    )
    if literal_count != len(literal_rows):
        issues.append("literal_fp_rejection_literal_count_mismatch")
    if operation_count != len(operation_rows):
        issues.append("literal_fp_rejection_operation_count_mismatch")
    if actual_ops != len(actual_rows):
        issues.append("literal_fp_rejection_actual_count_mismatch")
    if actual_bytes != sum(int_value(row, "length") for row in actual_rows):
        issues.append("literal_fp_rejection_actual_byte_sum_mismatch")
    if baseline_fp != len(baseline_false_rows):
        issues.append("literal_fp_rejection_baseline_fp_mismatch")
    if baseline_fp_bytes != sum(int_value(row, "length") for row in baseline_false_rows):
        issues.append("literal_fp_rejection_baseline_fp_bytes_mismatch")
    if candidate_count != len(classifier_rows):
        issues.append("literal_fp_rejection_candidate_count_mismatch")
    if rejection_count != len(rejection_rows):
        issues.append("literal_fp_rejection_rejection_count_mismatch")
    if fixture_count != len(fixture_rows):
        issues.append("literal_fp_rejection_fixture_count_mismatch")

    expected_names = {
        "small_token",
        "small_nonzero_token",
        "small_nonzero_next2_clean",
        "small_nonzero_pre4_clean",
        "small_nonzero_pre2_clean",
        "small_not_backward_nonzero_pre2_clean",
        "small_not_backward_nonzero_pre4_mod_clean",
        "oracle_token_plus3",
    }
    classifier_names = {row.get("classifier", "") for row in classifier_rows}
    if classifier_names != expected_names:
        issues.append("literal_fp_rejection_classifier_name_set_mismatch")
    for row in classifier_rows:
        name = row.get("classifier", "")
        selected, tp, fp, fn, tp_bytes, fp_bytes, rejected_ops, rejected_bytes = literal_fp_rejection_metrics(
            name,
            literal_rows,
        )
        if int_value(row, "selected_ops") != selected:
            issues.append(f"{name}:selected_ops_mismatch")
        if int_value(row, "true_positive_ops") != tp:
            issues.append(f"{name}:true_positive_ops_mismatch")
        if int_value(row, "false_positive_ops") != fp:
            issues.append(f"{name}:false_positive_ops_mismatch")
        if int_value(row, "false_negative_ops") != fn:
            issues.append(f"{name}:false_negative_ops_mismatch")
        if int_value(row, "true_positive_bytes") != tp_bytes:
            issues.append(f"{name}:true_positive_bytes_mismatch")
        if int_value(row, "false_positive_bytes") != fp_bytes:
            issues.append(f"{name}:false_positive_bytes_mismatch")
        if int_value(row, "rejected_baseline_false_positive_ops") != rejected_ops:
            issues.append(f"{name}:rejected_ops_mismatch")
        if int_value(row, "rejected_baseline_false_positive_bytes") != rejected_bytes:
            issues.append(f"{name}:rejected_bytes_mismatch")

    if classifier_rows:
        actual_full_recall = literal_fp_rejection_best_full_recall(classifier_rows, len(actual_rows))
        actual_low_false = literal_fp_rejection_best_low_false(classifier_rows, len(actual_rows))
        if full_recall_name != actual_full_recall.get("classifier", ""):
            issues.append("literal_fp_rejection_full_recall_name_mismatch")
        if full_recall_tp != int_value(actual_full_recall, "true_positive_ops"):
            issues.append("literal_fp_rejection_full_recall_tp_mismatch")
        if full_recall_fp != int_value(actual_full_recall, "false_positive_ops"):
            issues.append("literal_fp_rejection_full_recall_fp_mismatch")
        if full_recall_fp_bytes != int_value(actual_full_recall, "false_positive_bytes"):
            issues.append("literal_fp_rejection_full_recall_fp_bytes_mismatch")
        if low_false_name != actual_low_false.get("classifier", ""):
            issues.append("literal_fp_rejection_low_false_name_mismatch")
        if low_false_tp != int_value(actual_low_false, "true_positive_ops"):
            issues.append("literal_fp_rejection_low_false_tp_mismatch")
        if low_false_fp != int_value(actual_low_false, "false_positive_ops"):
            issues.append("literal_fp_rejection_low_false_fp_mismatch")
        if low_false_fp_bytes != int_value(actual_low_false, "false_positive_bytes"):
            issues.append("literal_fp_rejection_low_false_fp_bytes_mismatch")

    expected_rejection_keys = sorted(literal_fp_rejection_key(row) for row in baseline_false_rows)
    actual_rejection_keys = sorted(literal_fp_rejection_key(row) for row in rejection_rows)
    if actual_rejection_keys != expected_rejection_keys:
        issues.append("literal_fp_rejection_rejection_keys_mismatch")
    if fixture_count != len({literal_fp_rejection_fixture_key(row) for row in literal_rows}):
        issues.append("literal_fp_rejection_fixture_key_count_mismatch")
    if issue_rows or issue_rows != expected_issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    if literal_count < 1 or not classifier_rows or not rejection_rows:
        issues.append("missing_literal_fp_rejection_rows")
    if "const TEX_GAP_LITERAL_FP_REJECTION_PROBE = " not in text:
        issues.append("missing_tex_gap_literal_fp_rejection_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_literal_fp_rejection_probe",
            ok,
            expected=".tex literal false-positive rejection probe is internally consistent",
            actual=(
                f"baseline_fp={baseline_fp}/{baseline_fp_bytes}, "
                f"full_recall={full_recall_name}:{full_recall_fp}/{full_recall_fp_bytes}, "
                f"low_false={low_false_name}:{low_false_fp}/{low_false_fp_bytes}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        full_recall_fp if ok else 0,
        full_recall_fp_bytes if ok else 0,
        low_false_fp if ok else 0,
        candidate_count if ok else 0,
    )


def audit_tex_gap_zero_run_alignment_probe(
    summary: Path,
    zero_rows_path: Path,
    length_rows_path: Path,
    transition_rows_path: Path,
    fixture_rows_path: Path,
    operation_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_zero_run_alignment_probe", summary), 0, 0, 0, 0
    if not zero_rows_path.exists():
        return missing_gate("tex_gap_zero_run_alignment_probe", zero_rows_path), 0, 0, 0, 0
    if not length_rows_path.exists():
        return missing_gate("tex_gap_zero_run_alignment_probe", length_rows_path), 0, 0, 0, 0
    if not transition_rows_path.exists():
        return missing_gate("tex_gap_zero_run_alignment_probe", transition_rows_path), 0, 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate("tex_gap_zero_run_alignment_probe", fixture_rows_path), 0, 0, 0, 0
    if not operation_rows_path.exists():
        return missing_gate("tex_gap_zero_run_alignment_probe", operation_rows_path), 0, 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_zero_run_alignment_probe", html_report), 0, 0, 0, 0

    summary_rows = read_csv(summary)
    zero_rows = read_csv(zero_rows_path)
    length_rows = read_csv(length_rows_path)
    transition_rows = read_csv(transition_rows_path)
    fixture_rows = read_csv(fixture_rows_path)
    operation_rows = read_csv(operation_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    operation_count = int_value(total, "operation_rows")
    zero_ops = int_value(total, "zero_ops")
    zero_bytes = int_value(total, "zero_bytes")
    length64_ops = int_value(total, "length64_ops")
    fill_to_mod64_ops = int_value(total, "fill_to_mod64_ops")
    full_aligned64_ops = int_value(total, "full_aligned64_ops")
    length_u8_hits = int_value(total, "length_u8_hit_ops")
    length_u16_hits = int_value(total, "length_u16le_hit_ops")
    gap_to_gap_zero_ops = int_value(total, "gap_to_gap_zero_ops")
    transition_count = int_value(total, "transition_rows")
    length_count = int_value(total, "length_rows")
    fixture_count = int_value(total, "fixture_rows")
    issue_rows = int_value(total, "issue_rows")

    if operation_count != len(operation_rows):
        issues.append("zero_run_alignment_operation_count_mismatch")
    if zero_ops != len(zero_rows):
        issues.append("zero_run_alignment_zero_count_mismatch")
    if zero_ops != sum(1 for row in operation_rows if row.get("op_kind") == "zero"):
        issues.append("zero_run_alignment_source_zero_count_mismatch")
    if zero_bytes != sum(int_value(row, "length") for row in zero_rows):
        issues.append("zero_run_alignment_zero_byte_sum_mismatch")
    if length64_ops != sum(1 for row in zero_rows if int_value(row, "length") == 64):
        issues.append("zero_run_alignment_len64_count_mismatch")
    if fill_to_mod64_ops != sum(1 for row in zero_rows if row.get("fill_to_mod64") == "1"):
        issues.append("zero_run_alignment_fill_mod64_count_mismatch")
    if full_aligned64_ops != sum(1 for row in zero_rows if row.get("full_aligned64") == "1"):
        issues.append("zero_run_alignment_full_aligned64_count_mismatch")
    if length_u8_hits != sum(1 for row in zero_rows if row.get("length_u8_hit_offsets")):
        issues.append("zero_run_alignment_length_u8_count_mismatch")
    if length_u16_hits != sum(1 for row in zero_rows if row.get("length_u16le_hit_offsets")):
        issues.append("zero_run_alignment_length_u16_count_mismatch")
    if gap_to_gap_zero_ops != sum(
        1 for row in zero_rows if row.get("prev_kind") == "gap" and row.get("next_kind") == "gap"
    ):
        issues.append("zero_run_alignment_gap_to_gap_count_mismatch")
    if transition_count != len(transition_rows):
        issues.append("zero_run_alignment_transition_count_mismatch")
    if length_count != len(length_rows):
        issues.append("zero_run_alignment_length_row_count_mismatch")
    if fixture_count != len(fixture_rows):
        issues.append("zero_run_alignment_fixture_count_mismatch")
    if issue_rows or issue_rows != sum(1 for row in zero_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if zero_ops < 1 or zero_bytes < 1 or not length_rows or not transition_rows:
        issues.append("missing_zero_run_alignment_rows")
    if "const TEX_GAP_ZERO_RUN_ALIGNMENT_PROBE = " not in text:
        issues.append("missing_tex_gap_zero_run_alignment_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_zero_run_alignment_probe",
            ok,
            expected=".tex zero-run alignment probe is internally consistent",
            actual=(
                f"zero_ops={zero_ops}, zero_bytes={zero_bytes}, len64={length64_ops}, "
                f"fill_mod64={fill_to_mod64_ops}, u8_hits={length_u8_hits}, gap_gap={gap_to_gap_zero_ops}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        zero_ops if ok else 0,
        zero_bytes if ok else 0,
        length64_ops if ok else 0,
        fill_to_mod64_ops if ok else 0,
    )


def zero_control_risk_length(row: dict[str, str]) -> int:
    return int_value(row, "length")


def zero_control_risk_mod64(row: dict[str, str]) -> int:
    return int_value(row, "expected_mod64") if row.get("expected_mod64") else -1


def zero_control_risk_has_u8(row: dict[str, str]) -> bool:
    return bool(row.get("length_u8_hit_offsets"))


def zero_control_risk_has_u16(row: dict[str, str]) -> bool:
    return bool(row.get("length_u16le_hit_offsets"))


def zero_control_risk_is_zero(row: dict[str, str]) -> bool:
    return row.get("op_kind") == "zero"


def zero_control_risk_predicate(name: str, row: dict[str, str]) -> bool:
    row_length = zero_control_risk_length(row)
    mod64 = zero_control_risk_mod64(row)
    if name == "len64":
        return row_length == 64
    if name == "length_u8":
        return zero_control_risk_has_u8(row)
    if name == "length_u16":
        return zero_control_risk_has_u16(row)
    if name == "len64_or_u8":
        return row_length == 64 or zero_control_risk_has_u8(row)
    if name == "len64_or_u8_or_u16":
        return row_length == 64 or zero_control_risk_has_u8(row) or zero_control_risk_has_u16(row)
    if name == "len64_and_u8":
        return row_length == 64 and zero_control_risk_has_u8(row)
    if name == "u8_len32_64":
        return zero_control_risk_has_u8(row) and 32 <= row_length <= 64
    if name == "len_ge64":
        return row_length >= 64
    if name == "len_ge64_unaligned":
        return row_length >= 64 and mod64 != 0 and (mod64 + row_length) % 64 != 0
    if name == "oracle_zero":
        return zero_control_risk_is_zero(row)
    return False


def zero_control_risk_metrics(
    name: str,
    operation_rows: list[dict[str, str]],
) -> tuple[int, int, int, int, int, int]:
    selected = [row for row in operation_rows if zero_control_risk_predicate(name, row)]
    zero_rows = [row for row in operation_rows if zero_control_risk_is_zero(row)]
    true_zero = [row for row in selected if zero_control_risk_is_zero(row)]
    false_nonzero = [row for row in selected if not zero_control_risk_is_zero(row)]
    true_ids = {id(row) for row in true_zero}
    false_negative = [row for row in zero_rows if id(row) not in true_ids]
    return (
        len(selected),
        len(true_zero),
        len(false_nonzero),
        len(false_negative),
        sum(zero_control_risk_length(row) for row in true_zero),
        sum(zero_control_risk_length(row) for row in false_nonzero),
    )


def zero_control_risk_best_false_free(classifier_rows: list[dict[str, str]]) -> dict[str, str]:
    candidates = [
        row
        for row in classifier_rows
        if row.get("uses_oracle_filter") != "1" and int_value(row, "false_nonzero_bytes") == 0
    ]
    return max(
        candidates,
        key=lambda row: (
            int_value(row, "true_zero_bytes"),
            int_value(row, "true_zero_ops"),
            row.get("classifier", ""),
        ),
    )


def zero_control_risk_best_low_false(classifier_rows: list[dict[str, str]]) -> dict[str, str]:
    candidates = [
        row
        for row in classifier_rows
        if row.get("uses_oracle_filter") != "1" and int_value(row, "false_nonzero_bytes") <= 64
    ]
    return max(
        candidates,
        key=lambda row: (
            int_value(row, "true_zero_bytes"),
            -int_value(row, "false_nonzero_bytes"),
            row.get("classifier", ""),
        ),
    )


def zero_control_risk_false_positive_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        row.get("classifier", ""),
        row.get("rank", ""),
        row.get("pcx_name", ""),
        row.get("frontier_id", ""),
        row.get("op_index", ""),
    )


def audit_tex_gap_zero_control_risk_probe(
    summary: Path,
    classifier_rows_path: Path,
    false_positive_rows_path: Path,
    by_kind_rows_path: Path,
    fixture_rows_path: Path,
    operation_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_zero_control_risk_probe", summary), 0, 0, 0, 0
    if not classifier_rows_path.exists():
        return missing_gate("tex_gap_zero_control_risk_probe", classifier_rows_path), 0, 0, 0, 0
    if not false_positive_rows_path.exists():
        return missing_gate("tex_gap_zero_control_risk_probe", false_positive_rows_path), 0, 0, 0, 0
    if not by_kind_rows_path.exists():
        return missing_gate("tex_gap_zero_control_risk_probe", by_kind_rows_path), 0, 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate("tex_gap_zero_control_risk_probe", fixture_rows_path), 0, 0, 0, 0
    if not operation_rows_path.exists():
        return missing_gate("tex_gap_zero_control_risk_probe", operation_rows_path), 0, 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_zero_control_risk_probe", html_report), 0, 0, 0, 0

    summary_rows = read_csv(summary)
    classifier_rows = read_csv(classifier_rows_path)
    false_positive_rows = read_csv(false_positive_rows_path)
    by_kind_rows = read_csv(by_kind_rows_path)
    fixture_rows = read_csv(fixture_rows_path)
    operation_rows = read_csv(operation_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    operation_count = int_value(total, "operation_rows")
    zero_ops = int_value(total, "zero_ops")
    zero_bytes = int_value(total, "zero_bytes")
    nonzero_ops = int_value(total, "nonzero_ops")
    nonzero_bytes = int_value(total, "nonzero_bytes")
    current_selector = total.get("current_selector", "")
    current_true_bytes = int_value(total, "current_true_zero_bytes")
    current_false_ops = int_value(total, "current_false_nonzero_ops")
    current_false_bytes = int_value(total, "current_false_nonzero_bytes")
    false_free_name = total.get("false_free_candidate", "")
    false_free_bytes = int_value(total, "false_free_true_zero_bytes")
    low_false_name = total.get("low_false_candidate", "")
    low_false_bytes = int_value(total, "low_false_true_zero_bytes")
    low_false_false_bytes = int_value(total, "low_false_false_nonzero_bytes")
    classifier_count = int_value(total, "classifier_rows")
    false_positive_count = int_value(total, "false_positive_rows")
    issue_rows = int_value(total, "issue_rows")

    zero_rows = [row for row in operation_rows if zero_control_risk_is_zero(row)]
    nonzero_rows = [row for row in operation_rows if not zero_control_risk_is_zero(row)]
    if operation_count != len(operation_rows):
        issues.append("zero_control_risk_operation_count_mismatch")
    if zero_ops != len(zero_rows):
        issues.append("zero_control_risk_zero_count_mismatch")
    if zero_bytes != sum(zero_control_risk_length(row) for row in zero_rows):
        issues.append("zero_control_risk_zero_bytes_mismatch")
    if nonzero_ops != len(nonzero_rows):
        issues.append("zero_control_risk_nonzero_count_mismatch")
    if nonzero_bytes != sum(zero_control_risk_length(row) for row in nonzero_rows):
        issues.append("zero_control_risk_nonzero_bytes_mismatch")
    if classifier_count != len(classifier_rows):
        issues.append("zero_control_risk_classifier_count_mismatch")
    if false_positive_count != len(false_positive_rows):
        issues.append("zero_control_risk_false_positive_count_mismatch")

    expected_names = {
        "len64",
        "length_u8",
        "length_u16",
        "len64_or_u8",
        "len64_or_u8_or_u16",
        "len64_and_u8",
        "u8_len32_64",
        "len_ge64",
        "len_ge64_unaligned",
        "oracle_zero",
    }
    classifier_names = {row.get("classifier", "") for row in classifier_rows}
    if classifier_names != expected_names:
        issues.append("zero_control_risk_classifier_name_set_mismatch")
    for row in classifier_rows:
        name = row.get("classifier", "")
        selected, tp, fp, fn, tp_bytes, fp_bytes = zero_control_risk_metrics(name, operation_rows)
        if int_value(row, "selected_ops") != selected:
            issues.append(f"{name}:selected_ops_mismatch")
        if int_value(row, "true_zero_ops") != tp:
            issues.append(f"{name}:true_zero_ops_mismatch")
        if int_value(row, "false_nonzero_ops") != fp:
            issues.append(f"{name}:false_nonzero_ops_mismatch")
        if int_value(row, "false_negative_zero_ops") != fn:
            issues.append(f"{name}:false_negative_zero_ops_mismatch")
        if int_value(row, "true_zero_bytes") != tp_bytes:
            issues.append(f"{name}:true_zero_bytes_mismatch")
        if int_value(row, "false_nonzero_bytes") != fp_bytes:
            issues.append(f"{name}:false_nonzero_bytes_mismatch")

    classifier_by_name = {row.get("classifier", ""): row for row in classifier_rows}
    current_row = classifier_by_name.get("len64_or_u8", {})
    if current_selector != "len64_or_u8":
        issues.append("zero_control_risk_current_selector_mismatch")
    if current_true_bytes != int_value(current_row, "true_zero_bytes"):
        issues.append("zero_control_risk_current_true_bytes_mismatch")
    if current_false_ops != int_value(current_row, "false_nonzero_ops"):
        issues.append("zero_control_risk_current_false_ops_mismatch")
    if current_false_bytes != int_value(current_row, "false_nonzero_bytes"):
        issues.append("zero_control_risk_current_false_bytes_mismatch")
    if classifier_rows:
        false_free = zero_control_risk_best_false_free(classifier_rows)
        low_false = zero_control_risk_best_low_false(classifier_rows)
        if false_free_name != false_free.get("classifier", ""):
            issues.append("zero_control_risk_false_free_name_mismatch")
        if false_free_bytes != int_value(false_free, "true_zero_bytes"):
            issues.append("zero_control_risk_false_free_bytes_mismatch")
        if low_false_name != low_false.get("classifier", ""):
            issues.append("zero_control_risk_low_false_name_mismatch")
        if low_false_bytes != int_value(low_false, "true_zero_bytes"):
            issues.append("zero_control_risk_low_false_bytes_mismatch")
        if low_false_false_bytes != int_value(low_false, "false_nonzero_bytes"):
            issues.append("zero_control_risk_low_false_false_bytes_mismatch")

    expected_false_positive_keys = []
    for name in expected_names - {"oracle_zero"}:
        for row in operation_rows:
            if not zero_control_risk_is_zero(row) and zero_control_risk_predicate(name, row):
                expected_false_positive_keys.append(
                    (name, row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", ""), row.get("op_index", ""))
                )
    actual_false_positive_keys = [zero_control_risk_false_positive_key(row) for row in false_positive_rows]
    if sorted(actual_false_positive_keys) != sorted(expected_false_positive_keys):
        issues.append("zero_control_risk_false_positive_keys_mismatch")
    if not by_kind_rows or not fixture_rows:
        issues.append("missing_zero_control_risk_breakdown_rows")
    if issue_rows or issue_rows != sum(1 for row in operation_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if operation_count < 1 or not classifier_rows:
        issues.append("missing_zero_control_risk_rows")
    if "const TEX_GAP_ZERO_CONTROL_RISK_PROBE = " not in text:
        issues.append("missing_tex_gap_zero_control_risk_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_zero_control_risk_probe",
            ok,
            expected=".tex zero-control false-positive risk probe is internally consistent",
            actual=(
                f"current={current_true_bytes}/{current_false_bytes}, "
                f"false_free={false_free_name}:{false_free_bytes}, "
                f"low_false={low_false_name}:{low_false_bytes}/{low_false_false_bytes}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        current_false_bytes if ok else 0,
        false_free_bytes if ok else 0,
        low_false_bytes if ok else 0,
        classifier_count if ok else 0,
    )


def audit_tex_gap_decoder_skeleton_candidate_probe(
    summary: Path,
    candidate_rows_path: Path,
    fixture_rows_path: Path,
    operation_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_decoder_skeleton_candidate_probe", summary), 0, 0, 0, 0
    if not candidate_rows_path.exists():
        return missing_gate("tex_gap_decoder_skeleton_candidate_probe", candidate_rows_path), 0, 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate("tex_gap_decoder_skeleton_candidate_probe", fixture_rows_path), 0, 0, 0, 0
    if not operation_rows_path.exists():
        return missing_gate("tex_gap_decoder_skeleton_candidate_probe", operation_rows_path), 0, 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_decoder_skeleton_candidate_probe", html_report), 0, 0, 0, 0

    summary_rows = read_csv(summary)
    candidate_rows = read_csv(candidate_rows_path)
    fixture_rows = read_csv(fixture_rows_path)
    operation_rows = read_csv(operation_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    operation_count = int_value(total, "operation_rows")
    fixture_count = int_value(total, "fixture_rows")
    total_expected = int_value(total, "total_expected_bytes")
    skeleton_covered = int_value(total, "skeleton_covered_bytes")
    skeleton_gap = int_value(total, "skeleton_gap_bytes")
    candidate_count = int_value(total, "candidate_rows")
    best_nonoracle = total.get("best_nonoracle_candidate", "")
    best_nonoracle_bytes = int_value(total, "best_nonoracle_correct_bytes")
    best_nonoracle_false = int_value(total, "best_nonoracle_false_bytes")
    best_oracle = total.get("best_oracle_candidate", "")
    best_oracle_bytes = int_value(total, "best_oracle_correct_bytes")
    best_oracle_false = int_value(total, "best_oracle_false_bytes")
    issue_rows = int_value(total, "issue_rows")

    actual_total_expected = sum(int_value(row, "length") for row in operation_rows)
    actual_fixture_count = len(
        {(row.get("rank", ""), row.get("pcx_name", ""), row.get("frontier_id", "")) for row in operation_rows}
    )
    actual_skeleton_covered = sum(
        int_value(row, "length") for row in operation_rows if row.get("op_kind") in {"zero", "literal"}
    )
    if operation_count != len(operation_rows):
        issues.append("decoder_skeleton_operation_count_mismatch")
    if fixture_count != actual_fixture_count:
        issues.append("decoder_skeleton_fixture_count_mismatch")
    if total_expected != actual_total_expected:
        issues.append("decoder_skeleton_total_expected_mismatch")
    if skeleton_covered != actual_skeleton_covered:
        issues.append("decoder_skeleton_covered_sum_mismatch")
    if skeleton_gap != total_expected - skeleton_covered:
        issues.append("decoder_skeleton_gap_sum_mismatch")
    if candidate_count != len(candidate_rows):
        issues.append("decoder_skeleton_candidate_count_mismatch")
    if len(fixture_rows) != candidate_count * fixture_count:
        issues.append("decoder_skeleton_fixture_row_count_mismatch")
    nonoracle_rows = [row for row in candidate_rows if row.get("uses_oracle_filter") != "1"]
    oracle_rows = [row for row in candidate_rows if row.get("uses_oracle_filter") == "1"]
    if not nonoracle_rows or not oracle_rows:
        issues.append("decoder_skeleton_missing_candidate_family")
        actual_best_nonoracle = {}
        actual_best_oracle = {}
    else:
        actual_best_nonoracle = max(
            nonoracle_rows,
            key=lambda row: (int_value(row, "correct_bytes"), -int_value(row, "false_bytes")),
        )
        actual_best_oracle = max(
            oracle_rows,
            key=lambda row: (int_value(row, "correct_bytes"), -int_value(row, "false_bytes")),
        )
    if actual_best_nonoracle and best_nonoracle != actual_best_nonoracle.get("candidate", ""):
        issues.append("decoder_skeleton_best_nonoracle_name_mismatch")
    if actual_best_nonoracle and best_nonoracle_bytes != int_value(actual_best_nonoracle, "correct_bytes"):
        issues.append("decoder_skeleton_best_nonoracle_bytes_mismatch")
    if actual_best_nonoracle and best_nonoracle_false != int_value(actual_best_nonoracle, "false_bytes"):
        issues.append("decoder_skeleton_best_nonoracle_false_mismatch")
    if actual_best_oracle and best_oracle != actual_best_oracle.get("candidate", ""):
        issues.append("decoder_skeleton_best_oracle_name_mismatch")
    if actual_best_oracle and best_oracle_bytes != int_value(actual_best_oracle, "correct_bytes"):
        issues.append("decoder_skeleton_best_oracle_bytes_mismatch")
    if actual_best_oracle and best_oracle_false != int_value(actual_best_oracle, "false_bytes"):
        issues.append("decoder_skeleton_best_oracle_false_mismatch")
    for row in candidate_rows:
        if int_value(row, "correct_bytes") != int_value(row, "selected_zero_bytes") + int_value(row, "true_literal_bytes"):
            issues.append(f"{row.get('candidate', '')}:correct_byte_sum_mismatch")
        if int_value(row, "false_bytes") != int_value(row, "false_literal_bytes"):
            issues.append(f"{row.get('candidate', '')}:false_byte_sum_mismatch")
    if issue_rows or issue_rows != sum(1 for row in operation_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if candidate_count < 1 or total_expected < 1 or skeleton_covered < 1:
        issues.append("missing_decoder_skeleton_candidate_rows")
    if "const TEX_GAP_DECODER_SKELETON_CANDIDATE_PROBE = " not in text:
        issues.append("missing_tex_gap_decoder_skeleton_candidate_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_decoder_skeleton_candidate_probe",
            ok,
            expected=".tex decoder skeleton candidate probe is internally consistent",
            actual=(
                f"total={total_expected}, skeleton={skeleton_covered}, candidates={candidate_count}, "
                f"best_nonoracle={best_nonoracle_bytes}/{best_nonoracle_false}, "
                f"best_oracle={best_oracle_bytes}/{best_oracle_false}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        best_nonoracle_bytes if ok else 0,
        best_nonoracle_false if ok else 0,
        best_oracle_bytes if ok else 0,
        candidate_count if ok else 0,
    )


DECODER_RISK_REPEATED_FALSE_PRE4 = {"6edc020a", "5d5c0703", "6bfc0704", "17542f08"}
DECODER_RISK_REPEATED_FALSE_NEXT2 = {"5a5c", "5d6d", "aa6c", "7b6a"}
DECODER_RISK_REPEATED_FALSE_MOD64 = {5, 28, 34}


def decoder_risk_literal_predicate(name: str, row: dict[str, str] | None) -> bool:
    if row is None:
        return False
    token = literal_fp_rejection_token(row)
    direction = row.get("source_direction", "")
    delta = abs(literal_token_classifier_delta(row))
    mod64 = literal_fp_rejection_mod64(row)
    if name == "none":
        return False
    if name == "oracle_token_plus3":
        return row.get("token_plus3_match") == "1"
    if name == "small_token":
        return 0 <= token <= 13
    if name == "small_nonzero_next2_clean":
        return 1 <= token <= 13 and row.get("next2_hex") not in DECODER_RISK_REPEATED_FALSE_NEXT2
    if name == "small_not_backward":
        return 0 <= token <= 13 and direction != "backward"
    if name == "small_not_backward_abs_delta_le512":
        return 0 <= token <= 13 and direction != "backward" and delta <= 512
    if name == "small_not_backward_nonzero_pre4_mod_clean":
        return (
            1 <= token <= 13
            and direction != "backward"
            and row.get("pre4_hex") not in DECODER_RISK_REPEATED_FALSE_PRE4
            and mod64 not in DECODER_RISK_REPEATED_FALSE_MOD64
        )
    return False


def decoder_risk_zero_predicate(name: str, row: dict[str, str]) -> bool:
    if name == "none":
        return False
    if name == "oracle_zero":
        return row.get("op_kind") == "zero"
    return zero_control_risk_predicate(name, row)


def decoder_risk_metrics(
    priority: str,
    zero_rule: str,
    literal_rule: str,
    operation_rows: list[dict[str, str]],
    literal_rows: list[dict[str, str]],
) -> dict[str, int]:
    literals = {literal_fp_rejection_key(row): row for row in literal_rows}
    metrics = {
        "selected_zero_ops": 0,
        "true_zero_ops": 0,
        "false_zero_ops": 0,
        "selected_literal_ops": 0,
        "true_literal_ops": 0,
        "false_literal_ops": 0,
        "conflict_ops": 0,
        "true_zero_bytes": 0,
        "false_zero_bytes": 0,
        "true_literal_bytes": 0,
        "false_literal_bytes": 0,
    }
    for operation in operation_rows:
        literal = literals.get(literal_fp_rejection_key(operation))
        zero_selected = decoder_risk_zero_predicate(zero_rule, operation)
        literal_selected = decoder_risk_literal_predicate(literal_rule, literal)
        if zero_selected and literal_selected:
            metrics["conflict_ops"] += 1
        decision = ""
        if priority == "zero_first":
            if zero_selected:
                decision = "zero"
            elif literal_selected:
                decision = "literal"
        elif priority == "literal_first":
            if literal_selected:
                decision = "literal"
            elif zero_selected:
                decision = "zero"
        row_length = int_value(operation, "length")
        if decision == "zero":
            metrics["selected_zero_ops"] += 1
            if operation.get("op_kind") == "zero":
                metrics["true_zero_ops"] += 1
                metrics["true_zero_bytes"] += row_length
            else:
                metrics["false_zero_ops"] += 1
                metrics["false_zero_bytes"] += row_length
        elif decision == "literal":
            metrics["selected_literal_ops"] += 1
            if literal and literal.get("token_plus3_match") == "1":
                metrics["true_literal_ops"] += 1
                metrics["true_literal_bytes"] += row_length
            else:
                metrics["false_literal_ops"] += 1
                metrics["false_literal_bytes"] += row_length
    metrics["correct_bytes"] = metrics["true_zero_bytes"] + metrics["true_literal_bytes"]
    metrics["false_bytes"] = metrics["false_zero_bytes"] + metrics["false_literal_bytes"]
    metrics["net_bytes"] = metrics["correct_bytes"] - metrics["false_bytes"]
    return metrics


def audit_tex_gap_decoder_risk_adjusted_probe(
    summary: Path,
    candidate_rows_path: Path,
    fixture_rows_path: Path,
    operation_rows_path: Path,
    literal_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_decoder_risk_adjusted_probe", summary), 0, 0, 0, 0, 0
    if not candidate_rows_path.exists():
        return missing_gate("tex_gap_decoder_risk_adjusted_probe", candidate_rows_path), 0, 0, 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate("tex_gap_decoder_risk_adjusted_probe", fixture_rows_path), 0, 0, 0, 0, 0
    if not operation_rows_path.exists():
        return missing_gate("tex_gap_decoder_risk_adjusted_probe", operation_rows_path), 0, 0, 0, 0, 0
    if not literal_rows_path.exists():
        return missing_gate("tex_gap_decoder_risk_adjusted_probe", literal_rows_path), 0, 0, 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_decoder_risk_adjusted_probe", html_report), 0, 0, 0, 0, 0

    summary_rows = read_csv(summary)
    candidate_rows = read_csv(candidate_rows_path)
    fixture_rows = read_csv(fixture_rows_path)
    operation_rows = read_csv(operation_rows_path)
    literal_rows = literal_fp_rejection_enrich(read_csv(literal_rows_path), operation_rows)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    operation_count = int_value(total, "operation_rows")
    fixture_count = int_value(total, "fixture_rows")
    total_expected = int_value(total, "total_expected_bytes")
    candidate_count = int_value(total, "candidate_rows")
    best_correct_name = total.get("best_nonoracle_by_correct", "")
    best_correct_bytes = int_value(total, "best_nonoracle_correct_bytes")
    best_correct_false = int_value(total, "best_nonoracle_false_bytes")
    best_correct_net = int_value(total, "best_nonoracle_net_bytes")
    best_net_name = total.get("best_nonoracle_by_net", "")
    best_net_correct = int_value(total, "best_net_correct_bytes")
    best_net_false = int_value(total, "best_net_false_bytes")
    best_net_bytes = int_value(total, "best_net_bytes")
    best_low_false_name = total.get("best_low_false_candidate", "")
    best_low_false_correct = int_value(total, "best_low_false_correct_bytes")
    best_low_false_false = int_value(total, "best_low_false_false_bytes")
    best_oracle_name = total.get("best_oracle_candidate", "")
    best_oracle_correct = int_value(total, "best_oracle_correct_bytes")
    best_oracle_false = int_value(total, "best_oracle_false_bytes")
    issue_rows = int_value(total, "issue_rows")

    actual_total_expected = sum(int_value(row, "length") for row in operation_rows)
    actual_fixture_count = len({literal_fp_rejection_fixture_key(row) for row in operation_rows})
    if operation_count != len(operation_rows):
        issues.append("decoder_risk_operation_count_mismatch")
    if fixture_count != actual_fixture_count:
        issues.append("decoder_risk_fixture_count_mismatch")
    if total_expected != actual_total_expected:
        issues.append("decoder_risk_total_expected_mismatch")
    if candidate_count != len(candidate_rows):
        issues.append("decoder_risk_candidate_count_mismatch")
    if len(fixture_rows) != candidate_count * fixture_count:
        issues.append("decoder_risk_fixture_row_count_mismatch")

    expected_priorities = {"zero_first", "literal_first"}
    expected_zero_rules = {"none", "len64", "length_u8", "len64_or_u8", "len64_and_u8", "u8_len32_64", "oracle_zero"}
    expected_literal_rules = {
        "none",
        "oracle_token_plus3",
        "small_token",
        "small_nonzero_next2_clean",
        "small_not_backward",
        "small_not_backward_abs_delta_le512",
        "small_not_backward_nonzero_pre4_mod_clean",
    }
    expected_count = len(expected_priorities) * len(expected_zero_rules) * len(expected_literal_rules)
    if candidate_count != expected_count:
        issues.append("decoder_risk_expected_candidate_count_mismatch")
    for row in candidate_rows:
        priority = row.get("priority", "")
        zero_rule = row.get("zero_rule", "")
        literal_rule = row.get("literal_rule", "")
        if priority not in expected_priorities or zero_rule not in expected_zero_rules or literal_rule not in expected_literal_rules:
            issues.append(f"{row.get('candidate', '')}:unknown_rule")
            continue
        metrics = decoder_risk_metrics(priority, zero_rule, literal_rule, operation_rows, literal_rows)
        for field in (
            "selected_zero_ops",
            "true_zero_ops",
            "false_zero_ops",
            "selected_literal_ops",
            "true_literal_ops",
            "false_literal_ops",
            "conflict_ops",
            "true_zero_bytes",
            "false_zero_bytes",
            "true_literal_bytes",
            "false_literal_bytes",
            "correct_bytes",
            "false_bytes",
            "net_bytes",
        ):
            if int_value(row, field) != metrics[field]:
                issues.append(f"{row.get('candidate', '')}:{field}_mismatch")
        if int_value(row, "uses_oracle_filter") != int(
            zero_rule == "oracle_zero" or literal_rule == "oracle_token_plus3"
        ):
            issues.append(f"{row.get('candidate', '')}:oracle_flag_mismatch")

    nonoracle = [row for row in candidate_rows if row.get("uses_oracle_filter") != "1"]
    oracle = [row for row in candidate_rows if row.get("uses_oracle_filter") == "1"]
    if not nonoracle or not oracle:
        issues.append("decoder_risk_missing_candidate_family")
    else:
        actual_best_correct = max(
            nonoracle,
            key=lambda row: (int_value(row, "correct_bytes"), -int_value(row, "false_bytes")),
        )
        actual_best_net = max(
            nonoracle,
            key=lambda row: (int_value(row, "net_bytes"), int_value(row, "correct_bytes"), -int_value(row, "false_bytes")),
        )
        low_false_rows = [
            row for row in nonoracle if int_value(row, "false_bytes") <= 64 and int_value(row, "correct_bytes") > 0
        ]
        actual_best_low_false = max(
            low_false_rows,
            key=lambda row: (int_value(row, "correct_bytes"), -int_value(row, "false_bytes"), row.get("candidate", "")),
        )
        actual_best_oracle = max(
            oracle,
            key=lambda row: (int_value(row, "correct_bytes"), -int_value(row, "false_bytes")),
        )
        if best_correct_name != actual_best_correct.get("candidate", ""):
            issues.append("decoder_risk_best_correct_name_mismatch")
        if best_correct_bytes != int_value(actual_best_correct, "correct_bytes"):
            issues.append("decoder_risk_best_correct_bytes_mismatch")
        if best_correct_false != int_value(actual_best_correct, "false_bytes"):
            issues.append("decoder_risk_best_correct_false_mismatch")
        if best_correct_net != int_value(actual_best_correct, "net_bytes"):
            issues.append("decoder_risk_best_correct_net_mismatch")
        if best_net_name != actual_best_net.get("candidate", ""):
            issues.append("decoder_risk_best_net_name_mismatch")
        if best_net_correct != int_value(actual_best_net, "correct_bytes"):
            issues.append("decoder_risk_best_net_correct_mismatch")
        if best_net_false != int_value(actual_best_net, "false_bytes"):
            issues.append("decoder_risk_best_net_false_mismatch")
        if best_net_bytes != int_value(actual_best_net, "net_bytes"):
            issues.append("decoder_risk_best_net_bytes_mismatch")
        if best_low_false_name != actual_best_low_false.get("candidate", ""):
            issues.append("decoder_risk_best_low_false_name_mismatch")
        if best_low_false_correct != int_value(actual_best_low_false, "correct_bytes"):
            issues.append("decoder_risk_best_low_false_correct_mismatch")
        if best_low_false_false != int_value(actual_best_low_false, "false_bytes"):
            issues.append("decoder_risk_best_low_false_false_mismatch")
        if best_oracle_name != actual_best_oracle.get("candidate", ""):
            issues.append("decoder_risk_best_oracle_name_mismatch")
        if best_oracle_correct != int_value(actual_best_oracle, "correct_bytes"):
            issues.append("decoder_risk_best_oracle_correct_mismatch")
        if best_oracle_false != int_value(actual_best_oracle, "false_bytes"):
            issues.append("decoder_risk_best_oracle_false_mismatch")

    if issue_rows or issue_rows != sum(1 for row in operation_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if candidate_count < 1 or total_expected < 1:
        issues.append("missing_decoder_risk_rows")
    if "const TEX_GAP_DECODER_RISK_ADJUSTED_PROBE = " not in text:
        issues.append("missing_tex_gap_decoder_risk_adjusted_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_decoder_risk_adjusted_probe",
            ok,
            expected=".tex decoder risk-adjusted probe is internally consistent",
            actual=(
                f"best_correct={best_correct_bytes}/{best_correct_false}, "
                f"best_net={best_net_correct}/{best_net_false}:{best_net_bytes}, "
                f"low_false={best_low_false_correct}/{best_low_false_false}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        best_correct_bytes if ok else 0,
        best_correct_false if ok else 0,
        best_net_bytes if ok else 0,
        best_low_false_correct if ok else 0,
        candidate_count if ok else 0,
    )


def audit_tex_gap_decoder_seed_replay(
    summary: Path,
    fixture_rows_path: Path,
    decision_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_decoder_seed_replay", summary), 0, 0, 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate("tex_gap_decoder_seed_replay", fixture_rows_path), 0, 0, 0, 0, 0
    if not decision_rows_path.exists():
        return missing_gate("tex_gap_decoder_seed_replay", decision_rows_path), 0, 0, 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_decoder_seed_replay", html_report), 0, 0, 0, 0, 0

    summary_rows = read_csv(summary)
    fixture_rows = read_csv(fixture_rows_path)
    decision_rows = read_csv(decision_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    operation_count = int_value(total, "operation_rows")
    selected_ops = int_value(total, "selected_ops")
    trusted_ops = int_value(total, "trusted_ops")
    false_ops = int_value(total, "false_ops")
    selected_bytes = int_value(total, "selected_bytes")
    trusted_bytes = int_value(total, "trusted_bytes")
    false_bytes = int_value(total, "false_bytes")
    unselected_bytes = int_value(total, "unselected_bytes")
    output_exact_bytes = int_value(total, "output_exact_bytes")
    native_previews = int_value(total, "native_previews")
    fullhd_previews = int_value(total, "fullhd_previews")
    issue_rows = int_value(total, "issue_rows")

    decision_selected_ops = sum(1 for row in decision_rows if row.get("decision"))
    decision_trusted_ops = sum(1 for row in decision_rows if row.get("risk_class", "").startswith("true_"))
    decision_false_ops = sum(1 for row in decision_rows if row.get("risk_class", "").startswith("false_"))
    decision_selected_bytes = sum(int_value(row, "selected_bytes") for row in decision_rows)
    decision_trusted_bytes = sum(int_value(row, "trusted_bytes") for row in decision_rows)
    decision_false_bytes = sum(int_value(row, "false_bytes") for row in decision_rows)
    decision_exact_bytes = sum(int_value(row, "output_exact_bytes") for row in decision_rows)
    counted_issue_rows = sum(1 for row in fixture_rows if row.get("issues")) + sum(
        1 for row in decision_rows if row.get("issues")
    )

    if fixture_count != len(fixture_rows):
        issues.append("decoder_seed_fixture_count_mismatch")
    if operation_count != len(decision_rows):
        issues.append("decoder_seed_decision_count_mismatch")
    if selected_ops != decision_selected_ops:
        issues.append("decoder_seed_selected_op_count_mismatch")
    if trusted_ops != decision_trusted_ops:
        issues.append("decoder_seed_trusted_op_count_mismatch")
    if false_ops != decision_false_ops:
        issues.append("decoder_seed_false_op_count_mismatch")
    if selected_bytes != decision_selected_bytes:
        issues.append("decoder_seed_selected_byte_mismatch")
    if trusted_bytes != decision_trusted_bytes:
        issues.append("decoder_seed_trusted_byte_mismatch")
    if false_bytes != decision_false_bytes:
        issues.append("decoder_seed_false_byte_mismatch")
    if output_exact_bytes != decision_exact_bytes:
        issues.append("decoder_seed_exact_byte_mismatch")
    if selected_bytes != trusted_bytes + false_bytes:
        issues.append("decoder_seed_selected_bytes_not_partitioned")
    if output_exact_bytes != selected_bytes:
        issues.append("decoder_seed_selected_output_not_exact")
    if unselected_bytes != sum(int_value(row, "unselected_bytes") for row in fixture_rows):
        issues.append("decoder_seed_unselected_byte_mismatch")
    if issue_rows or issue_rows != counted_issue_rows:
        issues.append(f"issue_rows:{issue_rows}")

    missing_paths = 0
    wrong_size_paths = 0
    fullhd_preview_rows = 0
    for row in fixture_rows:
        fixture_bytes = int_value(row, "fixture_bytes")
        for field in ("decoded_path", "known_mask_path", "risk_mask_path"):
            value = row.get(field, "")
            if not value or not Path(value).exists():
                missing_paths += 1
                continue
            if Path(value).stat().st_size != fixture_bytes:
                wrong_size_paths += 1
        for field in ("native_preview_path", "fullhd_preview_path"):
            value = row.get(field, "")
            if not value or not Path(value).exists():
                missing_paths += 1
        if (row.get("fullhd_width"), row.get("fullhd_height")) == (
            str(TARGET_SIZE[0]),
            str(TARGET_SIZE[1]),
        ):
            fullhd_preview_rows += 1
    if missing_paths:
        issues.append(f"missing_decoder_seed_paths:{missing_paths}")
    if wrong_size_paths:
        issues.append(f"decoder_seed_path_size_mismatch:{wrong_size_paths}")
    if fixture_count != 32:
        issues.append("decoder_seed_fixture_total_changed")
    if operation_count != 984:
        issues.append("decoder_seed_operation_total_changed")
    if native_previews != len(fixture_rows):
        issues.append("decoder_seed_native_preview_count_mismatch")
    if fullhd_previews != fullhd_preview_rows:
        issues.append("decoder_seed_fullhd_preview_count_mismatch")
    if fullhd_previews != 32:
        issues.append("decoder_seed_fullhd_preview_total_changed")
    if trusted_bytes < 1600:
        issues.append("decoder_seed_trusted_bytes_too_low")
    if false_bytes > 64:
        issues.append("decoder_seed_false_bytes_too_high")
    if "const TEX_GAP_DECODER_SEED_REPLAY = " not in text:
        issues.append("missing_tex_gap_decoder_seed_replay_json")

    ok = not issues
    return (
        gate(
            "tex_gap_decoder_seed_replay",
            ok,
            expected=".tex low-false decoder seed replays into consistent fixture buffers",
            actual=(
                f"fixtures={fixture_count}, ops={operation_count}, selected={selected_bytes}, "
                f"trusted={trusted_bytes}, false={false_bytes}, exact={output_exact_bytes}, "
                f"fullhd={fullhd_previews}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        selected_bytes if ok else 0,
        trusted_bytes if ok else 0,
        false_bytes if ok else 0,
        fixture_count if ok else 0,
        fullhd_previews if ok else 0,
    )


def audit_tex_gap_decoder_control_promotion_probe(
    summary: Path,
    selector_rows_path: Path,
    signature_rows_path: Path,
    fixture_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_decoder_control_promotion_probe", summary), 0, 0, 0, 0
    if not selector_rows_path.exists():
        return missing_gate("tex_gap_decoder_control_promotion_probe", selector_rows_path), 0, 0, 0, 0
    if not signature_rows_path.exists():
        return missing_gate("tex_gap_decoder_control_promotion_probe", signature_rows_path), 0, 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate("tex_gap_decoder_control_promotion_probe", fixture_rows_path), 0, 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_decoder_control_promotion_probe", html_report), 0, 0, 0, 0

    summary_rows = read_csv(summary)
    selector_rows = read_csv(selector_rows_path)
    signature_rows = read_csv(signature_rows_path)
    fixture_rows = read_csv(fixture_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    operation_rows = int_value(total, "operation_rows")
    decision_rows = int_value(total, "decision_rows")
    fixture_count = int_value(total, "fixture_rows")
    seed_selected = int_value(total, "seed_selected_bytes")
    seed_trusted = int_value(total, "seed_trusted_bytes")
    seed_false = int_value(total, "seed_false_bytes")
    literal_promoted = int_value(total, "literal_pre4_next2_pure_bytes")
    zero_promoted = int_value(total, "zero_len64_and_u8_pure_bytes")
    combined_promoted = int_value(total, "combined_promoted_bytes")
    ambiguous_groups = int_value(total, "ambiguous_signature_groups")
    issue_rows = int_value(total, "issue_rows")

    selectors = {row.get("selector", ""): row for row in selector_rows}
    pre4_next2 = selectors.get("pre4_next2", {})
    zero_len64 = selectors.get("zero_len64_and_u8", {})
    signature_ambiguous = sum(1 for row in signature_rows if row.get("promotion_class") == "ambiguous")
    fixture_combined = sum(int_value(row, "combined_promoted_bytes") for row in fixture_rows)
    fixture_seed_selected = sum(int_value(row, "seed_selected_bytes") for row in fixture_rows)
    fixture_seed_trusted = sum(int_value(row, "seed_trusted_bytes") for row in fixture_rows)
    fixture_seed_false = sum(int_value(row, "seed_false_bytes") for row in fixture_rows)

    if operation_rows != 984 or decision_rows != 984:
        issues.append("control_promotion_operation_count_changed")
    if fixture_count != len(fixture_rows) or fixture_count != 32:
        issues.append("control_promotion_fixture_count_mismatch")
    if seed_selected != fixture_seed_selected or seed_selected != 1667:
        issues.append("control_promotion_seed_selected_mismatch")
    if seed_trusted != fixture_seed_trusted or seed_trusted != 1610:
        issues.append("control_promotion_seed_trusted_mismatch")
    if seed_false != fixture_seed_false or seed_false != 57:
        issues.append("control_promotion_seed_false_mismatch")
    if literal_promoted != int_value(pre4_next2, "pure_bytes") or literal_promoted != 1034:
        issues.append("control_promotion_literal_promoted_mismatch")
    if zero_promoted != int_value(zero_len64, "pure_bytes") or zero_promoted != 576:
        issues.append("control_promotion_zero_promoted_mismatch")
    if combined_promoted != literal_promoted + zero_promoted:
        issues.append("control_promotion_combined_not_partitioned")
    if combined_promoted != fixture_combined:
        issues.append("control_promotion_fixture_sum_mismatch")
    if combined_promoted != seed_trusted:
        issues.append("control_promotion_does_not_cover_seed_trusted")
    if ambiguous_groups != signature_ambiguous:
        issues.append("control_promotion_ambiguous_count_mismatch")
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    if "const TEX_GAP_DECODER_CONTROL_PROMOTION_PROBE = " not in text:
        issues.append("missing_tex_gap_decoder_control_promotion_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_decoder_control_promotion_probe",
            ok,
            expected=".tex decoder seed decisions are promoted only through false-free control signatures",
            actual=(
                f"promoted={combined_promoted}, literal={literal_promoted}, zero={zero_promoted}, "
                f"ambiguous_groups={ambiguous_groups}, seed_false={seed_false}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        combined_promoted if ok else 0,
        literal_promoted if ok else 0,
        zero_promoted if ok else 0,
        ambiguous_groups if ok else 0,
    )


def audit_tex_gap_decoder_false_risk_queue(
    summary: Path,
    queue_rows_path: Path,
    rejector_rows_path: Path,
    fixture_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_decoder_false_risk_queue", summary), 0, 0, 0, 0
    if not queue_rows_path.exists():
        return missing_gate("tex_gap_decoder_false_risk_queue", queue_rows_path), 0, 0, 0, 0
    if not rejector_rows_path.exists():
        return missing_gate("tex_gap_decoder_false_risk_queue", rejector_rows_path), 0, 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate("tex_gap_decoder_false_risk_queue", fixture_rows_path), 0, 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_decoder_false_risk_queue", html_report), 0, 0, 0, 0

    summary_rows = read_csv(summary)
    queue_rows = read_csv(queue_rows_path)
    rejector_rows = read_csv(rejector_rows_path)
    fixture_rows = read_csv(fixture_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    operation_rows = int_value(total, "operation_rows")
    decision_rows = int_value(total, "decision_rows")
    fixture_count = int_value(total, "fixture_rows")
    selected_ops = int_value(total, "selected_ops")
    selected_bytes = int_value(total, "selected_bytes")
    promoted_ops = int_value(total, "promoted_ops")
    promoted_bytes = int_value(total, "promoted_bytes")
    promoted_literal = int_value(total, "promoted_literal_bytes")
    promoted_zero = int_value(total, "promoted_zero_bytes")
    rejected_ops = int_value(total, "rejected_ops")
    rejected_false = int_value(total, "rejected_false_bytes")
    review_ops = int_value(total, "review_ops")
    review_bytes = int_value(total, "review_bytes")
    trusted_unpromoted = int_value(total, "trusted_unpromoted_bytes")
    false_remaining = int_value(total, "false_remaining_bytes")
    safe_rejectors = int_value(total, "safe_rejector_groups")
    mixed_rejectors = int_value(total, "mixed_rejector_groups")
    issue_rows = int_value(total, "issue_rows")

    queue_selected_bytes = sum(int_value(row, "selected_bytes") for row in queue_rows)
    queue_promoted = [row for row in queue_rows if row.get("verdict") == "promoted"]
    queue_rejected = [row for row in queue_rows if row.get("verdict") == "reject_false_risk"]
    queue_review = [row for row in queue_rows if row.get("verdict") == "review"]
    queue_promoted_bytes = sum(int_value(row, "selected_bytes") for row in queue_promoted)
    queue_promoted_literal = sum(
        int_value(row, "selected_bytes")
        for row in queue_promoted
        if row.get("promotion_selector") == "pre4_next2"
    )
    queue_promoted_zero = sum(
        int_value(row, "selected_bytes")
        for row in queue_promoted
        if row.get("promotion_selector") == "zero_len64_and_u8"
    )
    queue_rejected_false = sum(int_value(row, "false_bytes") for row in queue_rejected)
    queue_review_bytes = sum(int_value(row, "selected_bytes") for row in queue_review)
    queue_trusted_unpromoted = sum(
        int_value(row, "trusted_bytes") for row in queue_rows if row.get("verdict") != "promoted"
    )
    queue_false_remaining = sum(
        int_value(row, "false_bytes") for row in queue_rows if row.get("verdict") != "reject_false_risk"
    )

    fixture_selected = sum(int_value(row, "selected_bytes") for row in fixture_rows)
    fixture_promoted = sum(int_value(row, "promoted_bytes") for row in fixture_rows)
    fixture_rejected = sum(int_value(row, "rejected_false_bytes") for row in fixture_rows)
    fixture_review = sum(int_value(row, "review_bytes") for row in fixture_rows)
    fixture_trusted_unpromoted = sum(int_value(row, "trusted_unpromoted_bytes") for row in fixture_rows)
    fixture_false_remaining = sum(int_value(row, "false_remaining_bytes") for row in fixture_rows)

    if operation_rows != 984 or decision_rows != 984:
        issues.append("false_risk_queue_operation_count_changed")
    if fixture_count != len(fixture_rows) or fixture_count != 32:
        issues.append("false_risk_queue_fixture_count_mismatch")
    if selected_ops != len(queue_rows) or selected_ops != 162:
        issues.append("false_risk_queue_selected_op_mismatch")
    if selected_bytes != queue_selected_bytes or selected_bytes != fixture_selected or selected_bytes != 1667:
        issues.append("false_risk_queue_selected_byte_mismatch")
    if promoted_ops != len(queue_promoted) or promoted_ops != 150:
        issues.append("false_risk_queue_promoted_op_mismatch")
    if promoted_bytes != queue_promoted_bytes or promoted_bytes != fixture_promoted or promoted_bytes != 1610:
        issues.append("false_risk_queue_promoted_byte_mismatch")
    if promoted_literal != queue_promoted_literal or promoted_literal != 1034:
        issues.append("false_risk_queue_literal_promoted_mismatch")
    if promoted_zero != queue_promoted_zero or promoted_zero != 576:
        issues.append("false_risk_queue_zero_promoted_mismatch")
    if rejected_ops != len(queue_rejected) or rejected_ops != 12:
        issues.append("false_risk_queue_rejected_op_mismatch")
    if rejected_false != queue_rejected_false or rejected_false != fixture_rejected or rejected_false != 57:
        issues.append("false_risk_queue_rejected_false_mismatch")
    if review_ops != len(queue_review) or review_ops != 0:
        issues.append("false_risk_queue_review_op_mismatch")
    if review_bytes != queue_review_bytes or review_bytes != fixture_review or review_bytes != 0:
        issues.append("false_risk_queue_review_byte_mismatch")
    if trusted_unpromoted != queue_trusted_unpromoted or trusted_unpromoted != fixture_trusted_unpromoted:
        issues.append("false_risk_queue_trusted_unpromoted_mismatch")
    if trusted_unpromoted:
        issues.append("false_risk_queue_has_trusted_unpromoted_bytes")
    if false_remaining != queue_false_remaining or false_remaining != fixture_false_remaining:
        issues.append("false_risk_queue_false_remaining_mismatch")
    if false_remaining:
        issues.append("false_risk_queue_has_false_remaining_bytes")
    if promoted_bytes + rejected_false + review_bytes != selected_bytes:
        issues.append("false_risk_queue_selected_bytes_not_partitioned")
    if any(int_value(row, "false_bytes") for row in queue_promoted):
        issues.append("false_risk_queue_promoted_false_bytes")
    if any(int_value(row, "trusted_bytes") for row in queue_rejected):
        issues.append("false_risk_queue_rejected_trusted_bytes")
    if any(row.get("risk_class", "").startswith("true_") for row in queue_rejected):
        issues.append("false_risk_queue_rejected_true_rows")
    if safe_rejectors != sum(1 for row in rejector_rows if row.get("verdict") == "safe_reject") or safe_rejectors != 59:
        issues.append("false_risk_queue_safe_rejector_mismatch")
    if mixed_rejectors != sum(1 for row in rejector_rows if row.get("verdict") == "mixed_review") or mixed_rejectors != 16:
        issues.append("false_risk_queue_mixed_rejector_mismatch")
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    if "const TEX_GAP_DECODER_FALSE_RISK_QUEUE = " not in text:
        issues.append("missing_tex_gap_decoder_false_risk_queue_json")

    ok = not issues
    return (
        gate(
            "tex_gap_decoder_false_risk_queue",
            ok,
            expected=".tex decoder seed false-risk bytes are rejected after control-signature promotion",
            actual=(
                f"selected={selected_bytes}, promoted={promoted_bytes}, rejected_false={rejected_false}, "
                f"review={review_bytes}, safe_rejectors={safe_rejectors}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        promoted_bytes if ok else 0,
        rejected_false if ok else 0,
        review_bytes if ok else 0,
        safe_rejectors if ok else 0,
    )


def audit_tex_gap_decoder_clean_replay(
    summary: Path,
    fixture_rows_path: Path,
    decision_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_decoder_clean_replay", summary), 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate("tex_gap_decoder_clean_replay", fixture_rows_path), 0, 0, 0
    if not decision_rows_path.exists():
        return missing_gate("tex_gap_decoder_clean_replay", decision_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_decoder_clean_replay", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    fixture_rows = read_csv(fixture_rows_path)
    decision_rows = read_csv(decision_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    queue_rows = int_value(total, "queue_rows")
    promoted_ops = int_value(total, "promoted_ops")
    rejected_ops = int_value(total, "rejected_ops")
    selected_bytes = int_value(total, "selected_bytes")
    clean_bytes = int_value(total, "clean_bytes")
    rejected_false = int_value(total, "rejected_false_bytes")
    false_bytes = int_value(total, "false_bytes")
    output_exact = int_value(total, "output_exact_bytes")
    unselected_bytes = int_value(total, "unselected_bytes")
    native_previews = int_value(total, "native_previews")
    fullhd_previews = int_value(total, "fullhd_previews")
    issue_rows = int_value(total, "issue_rows")

    decision_promoted = [row for row in decision_rows if row.get("queue_verdict") == "promoted"]
    decision_rejected = [row for row in decision_rows if row.get("queue_verdict") == "reject_false_risk"]
    decision_clean_bytes = sum(int_value(row, "clean_bytes") for row in decision_rows)
    decision_rejected_false = sum(int_value(row, "rejected_false_bytes") for row in decision_rows)
    decision_false = sum(int_value(row, "false_bytes") for row in decision_rows)
    decision_exact = sum(int_value(row, "output_exact_bytes") for row in decision_rows)
    decision_selected = sum(int_value(row, "selected_bytes") for row in decision_rows)

    fixture_clean = sum(int_value(row, "clean_bytes") for row in fixture_rows)
    fixture_rejected = sum(int_value(row, "rejected_false_bytes") for row in fixture_rows)
    fixture_false = sum(int_value(row, "false_bytes") for row in fixture_rows)
    fixture_exact = sum(int_value(row, "output_exact_bytes") for row in fixture_rows)
    fixture_selected = sum(int_value(row, "selected_bytes") for row in fixture_rows)
    fixture_unselected = sum(int_value(row, "unselected_bytes") for row in fixture_rows)

    if fixture_count != len(fixture_rows) or fixture_count != 32:
        issues.append("clean_replay_fixture_count_mismatch")
    if queue_rows != len(decision_rows) or queue_rows != 162:
        issues.append("clean_replay_queue_count_mismatch")
    if promoted_ops != len(decision_promoted) or promoted_ops != 150:
        issues.append("clean_replay_promoted_op_mismatch")
    if rejected_ops != len(decision_rejected) or rejected_ops != 12:
        issues.append("clean_replay_rejected_op_mismatch")
    if selected_bytes != decision_selected or selected_bytes != fixture_selected or selected_bytes != 1667:
        issues.append("clean_replay_selected_byte_mismatch")
    if clean_bytes != decision_clean_bytes or clean_bytes != fixture_clean or clean_bytes != 1610:
        issues.append("clean_replay_clean_byte_mismatch")
    if rejected_false != decision_rejected_false or rejected_false != fixture_rejected or rejected_false != 57:
        issues.append("clean_replay_rejected_false_mismatch")
    if false_bytes != decision_false or false_bytes != fixture_false or false_bytes != 0:
        issues.append("clean_replay_false_byte_mismatch")
    if output_exact != decision_exact or output_exact != fixture_exact or output_exact != clean_bytes:
        issues.append("clean_replay_exact_byte_mismatch")
    if unselected_bytes != fixture_unselected or unselected_bytes != 15893:
        issues.append("clean_replay_unselected_byte_mismatch")
    if clean_bytes + rejected_false != selected_bytes:
        issues.append("clean_replay_selected_bytes_not_partitioned")
    if any(int_value(row, "clean_bytes") != int_value(row, "selected_bytes") for row in decision_promoted):
        issues.append("clean_replay_promoted_clean_byte_mismatch")
    if any(int_value(row, "output_exact_bytes") != int_value(row, "clean_bytes") for row in decision_promoted):
        issues.append("clean_replay_promoted_exact_mismatch")
    if any(int_value(row, "clean_bytes") for row in decision_rejected):
        issues.append("clean_replay_rejected_clean_bytes")
    if any(row.get("risk_class", "").startswith("true_") for row in decision_rejected):
        issues.append("clean_replay_rejected_true_rows")
    if issue_rows or issue_rows != (
        sum(1 for row in fixture_rows if row.get("issues"))
        + sum(1 for row in decision_rows if row.get("issues"))
    ):
        issues.append(f"issue_rows:{issue_rows}")

    missing_paths = 0
    wrong_size_paths = 0
    fullhd_preview_rows = 0
    for row in fixture_rows:
        fixture_bytes = int_value(row, "fixture_bytes")
        for field in ("decoded_path", "known_mask_path", "accepted_mask_path"):
            value = row.get(field, "")
            if not value or not Path(value).exists():
                missing_paths += 1
                continue
            if Path(value).stat().st_size != fixture_bytes:
                wrong_size_paths += 1
        for field in ("native_preview_path", "fullhd_preview_path"):
            value = row.get(field, "")
            if not value or not Path(value).exists():
                missing_paths += 1
        if (row.get("fullhd_width"), row.get("fullhd_height")) == (
            str(TARGET_SIZE[0]),
            str(TARGET_SIZE[1]),
        ):
            fullhd_preview_rows += 1
    if missing_paths:
        issues.append(f"missing_clean_replay_paths:{missing_paths}")
    if wrong_size_paths:
        issues.append(f"clean_replay_path_size_mismatch:{wrong_size_paths}")
    if native_previews != len(fixture_rows):
        issues.append("clean_replay_native_preview_count_mismatch")
    if fullhd_previews != fullhd_preview_rows or fullhd_previews != 32:
        issues.append("clean_replay_fullhd_preview_count_mismatch")
    if "const TEX_GAP_DECODER_CLEAN_REPLAY = " not in text:
        issues.append("missing_tex_gap_decoder_clean_replay_json")

    ok = not issues
    return (
        gate(
            "tex_gap_decoder_clean_replay",
            ok,
            expected=".tex decoder clean replay writes only promoted false-free bytes",
            actual=(
                f"fixtures={fixture_count}, clean={clean_bytes}, rejected_false={rejected_false}, "
                f"false_written={false_bytes}, exact={output_exact}, fullhd={fullhd_previews}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        clean_bytes if ok else 0,
        rejected_false if ok else 0,
        fullhd_previews if ok else 0,
    )


def audit_tex_gap_decoder_clean_gap_queue(
    summary: Path,
    span_rows_path: Path,
    fixture_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_decoder_clean_gap_queue", summary), 0, 0, 0
    if not span_rows_path.exists():
        return missing_gate("tex_gap_decoder_clean_gap_queue", span_rows_path), 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate("tex_gap_decoder_clean_gap_queue", fixture_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_decoder_clean_gap_queue", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    span_rows = read_csv(span_rows_path)
    fixture_rows = read_csv(fixture_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    total_bytes = int_value(total, "total_bytes")
    clean_bytes = int_value(total, "clean_bytes")
    rejected_false = int_value(total, "rejected_false_bytes")
    unresolved_bytes = int_value(total, "unresolved_bytes")
    unresolved_zero = int_value(total, "unresolved_zero_bytes")
    unresolved_nonzero = int_value(total, "unresolved_nonzero_bytes")
    unresolved_mixed = int_value(total, "unresolved_mixed_bytes")
    span_count = int_value(total, "span_rows")
    unresolved_spans = int_value(total, "unresolved_span_rows")
    rejected_spans = int_value(total, "rejected_span_rows")
    largest_unresolved = int_value(total, "largest_unresolved_span")
    issue_rows = int_value(total, "issue_rows")

    span_total = sum(int_value(row, "length") for row in span_rows)
    span_unresolved = [
        row for row in span_rows if row.get("span_class", "").startswith("unresolved")
    ]
    span_rejected = [
        row for row in span_rows if row.get("span_class", "").startswith("rejected_false_risk")
    ]
    span_unresolved_bytes = sum(int_value(row, "length") for row in span_unresolved)
    span_rejected_bytes = sum(int_value(row, "length") for row in span_rejected)
    span_largest_unresolved = max([int_value(row, "length") for row in span_unresolved] or [0])
    fixture_total = sum(int_value(row, "fixture_bytes") for row in fixture_rows)
    fixture_clean = sum(int_value(row, "clean_bytes") for row in fixture_rows)
    fixture_rejected = sum(int_value(row, "rejected_false_bytes") for row in fixture_rows)
    fixture_unresolved = sum(int_value(row, "unresolved_bytes") for row in fixture_rows)
    fixture_zero = sum(int_value(row, "unresolved_zero_bytes") for row in fixture_rows)
    fixture_nonzero = sum(int_value(row, "unresolved_nonzero_bytes") for row in fixture_rows)
    fixture_mixed = sum(int_value(row, "unresolved_mixed_bytes") for row in fixture_rows)

    if fixture_count != len(fixture_rows) or fixture_count != 32:
        issues.append("clean_gap_queue_fixture_count_mismatch")
    if total_bytes != fixture_total or total_bytes != 17503:
        issues.append("clean_gap_queue_total_byte_mismatch")
    if clean_bytes != fixture_clean or clean_bytes != 1610:
        issues.append("clean_gap_queue_clean_byte_mismatch")
    if rejected_false != fixture_rejected or rejected_false != span_rejected_bytes or rejected_false != 57:
        issues.append("clean_gap_queue_rejected_byte_mismatch")
    if unresolved_bytes != fixture_unresolved or unresolved_bytes != span_unresolved_bytes or unresolved_bytes != 15836:
        issues.append("clean_gap_queue_unresolved_byte_mismatch")
    if clean_bytes + rejected_false + unresolved_bytes != total_bytes:
        issues.append("clean_gap_queue_total_not_partitioned")
    if unresolved_zero != fixture_zero or unresolved_zero != 189:
        issues.append("clean_gap_queue_zero_byte_mismatch")
    if unresolved_nonzero != fixture_nonzero or unresolved_nonzero != 850:
        issues.append("clean_gap_queue_nonzero_byte_mismatch")
    if unresolved_mixed != fixture_mixed or unresolved_mixed != 14797:
        issues.append("clean_gap_queue_mixed_byte_mismatch")
    if span_count != len(span_rows) or span_count != 204:
        issues.append("clean_gap_queue_span_count_mismatch")
    if unresolved_spans != len(span_unresolved) or unresolved_spans != 192:
        issues.append("clean_gap_queue_unresolved_span_count_mismatch")
    if rejected_spans != len(span_rejected) or rejected_spans != 12:
        issues.append("clean_gap_queue_rejected_span_count_mismatch")
    if largest_unresolved != span_largest_unresolved or largest_unresolved != 459:
        issues.append("clean_gap_queue_largest_span_mismatch")
    if span_total != rejected_false + unresolved_bytes:
        issues.append("clean_gap_queue_span_total_mismatch")
    if issue_rows or issue_rows != sum(1 for row in fixture_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if "const TEX_GAP_DECODER_CLEAN_GAP_QUEUE = " not in text:
        issues.append("missing_tex_gap_decoder_clean_gap_queue_json")

    ok = not issues
    return (
        gate(
            "tex_gap_decoder_clean_gap_queue",
            ok,
            expected=".tex clean replay remaining gap queue partitions unresolved spans",
            actual=(
                f"clean={clean_bytes}, rejected={rejected_false}, unresolved={unresolved_bytes}, "
                f"spans={span_count}, largest={largest_unresolved}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        unresolved_bytes if ok else 0,
        span_count if ok else 0,
        largest_unresolved if ok else 0,
    )


def audit_tex_gap_decoder_unresolved_run_probe(
    summary: Path,
    span_rows_path: Path,
    run_rows_path: Path,
    fixture_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_decoder_unresolved_run_probe", summary), 0, 0, 0
    if not span_rows_path.exists():
        return missing_gate("tex_gap_decoder_unresolved_run_probe", span_rows_path), 0, 0, 0
    if not run_rows_path.exists():
        return missing_gate("tex_gap_decoder_unresolved_run_probe", run_rows_path), 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate("tex_gap_decoder_unresolved_run_probe", fixture_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_decoder_unresolved_run_probe", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    span_rows = read_csv(span_rows_path)
    run_rows = read_csv(run_rows_path)
    fixture_rows = read_csv(fixture_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    unresolved_span_count = int_value(total, "unresolved_span_rows")
    run_count = int_value(total, "run_rows")
    zero_run_count = int_value(total, "zero_run_rows")
    nonzero_run_count = int_value(total, "nonzero_run_rows")
    unresolved_bytes = int_value(total, "unresolved_bytes")
    zero_bytes = int_value(total, "zero_bytes")
    nonzero_bytes = int_value(total, "nonzero_bytes")
    pure_zero_span_bytes = int_value(total, "pure_zero_span_bytes")
    mixed_span_zero_bytes = int_value(total, "mixed_span_zero_bytes")
    max_zero_run = int_value(total, "max_zero_run_bytes")
    max_nonzero_run = int_value(total, "max_nonzero_run_bytes")
    largest_run = int_value(total, "largest_run_bytes")
    largest_run_class = total.get("largest_run_class", "")
    issue_rows = int_value(total, "issue_rows")

    zero_runs = [row for row in run_rows if row.get("run_class") == "zero"]
    nonzero_runs = [row for row in run_rows if row.get("run_class") == "nonzero"]
    span_unresolved_bytes = sum(int_value(row, "length") for row in span_rows)
    span_zero_bytes = sum(int_value(row, "zero_bytes") for row in span_rows)
    span_nonzero_bytes = sum(int_value(row, "nonzero_bytes") for row in span_rows)
    span_pure_zero_bytes = sum(
        int_value(row, "length")
        for row in span_rows
        if row.get("span_class") == "unresolved_zero"
    )
    span_mixed_zero_bytes = sum(
        int_value(row, "zero_bytes")
        for row in span_rows
        if row.get("span_class") == "unresolved_mixed"
    )
    span_run_count = sum(int_value(row, "run_rows") for row in span_rows)
    span_zero_run_count = sum(int_value(row, "zero_runs") for row in span_rows)
    span_nonzero_run_count = sum(int_value(row, "nonzero_runs") for row in span_rows)
    span_max_zero = max([int_value(row, "max_zero_run_bytes") for row in span_rows] or [0])
    span_max_nonzero = max([int_value(row, "max_nonzero_run_bytes") for row in span_rows] or [0])

    run_total_bytes = sum(int_value(row, "length") for row in run_rows)
    run_zero_bytes = sum(int_value(row, "length") for row in zero_runs)
    run_nonzero_bytes = sum(int_value(row, "length") for row in nonzero_runs)
    run_max_zero = max([int_value(row, "length") for row in zero_runs] or [0])
    run_max_nonzero = max([int_value(row, "length") for row in nonzero_runs] or [0])
    run_largest = max([int_value(row, "length") for row in run_rows] or [0])
    run_largest_classes = {
        row.get("run_class", "")
        for row in run_rows
        if int_value(row, "length") == run_largest
    }

    fixture_unresolved_bytes = sum(int_value(row, "unresolved_bytes") for row in fixture_rows)
    fixture_zero_bytes = sum(int_value(row, "zero_bytes") for row in fixture_rows)
    fixture_nonzero_bytes = sum(int_value(row, "nonzero_bytes") for row in fixture_rows)
    fixture_run_count = sum(int_value(row, "run_rows") for row in fixture_rows)
    fixture_zero_run_count = sum(int_value(row, "zero_run_rows") for row in fixture_rows)
    fixture_nonzero_run_count = sum(int_value(row, "nonzero_run_rows") for row in fixture_rows)
    fixture_max_zero = max([int_value(row, "max_zero_run_bytes") for row in fixture_rows] or [0])
    fixture_max_nonzero = max(
        [int_value(row, "max_nonzero_run_bytes") for row in fixture_rows] or [0]
    )

    if fixture_count != len(fixture_rows) or fixture_count != 32:
        issues.append("unresolved_run_fixture_count_mismatch")
    if unresolved_span_count != len(span_rows) or unresolved_span_count != 192:
        issues.append("unresolved_run_span_count_mismatch")
    if run_count != len(run_rows) or run_count != span_run_count or run_count != fixture_run_count or run_count != 729:
        issues.append("unresolved_run_count_mismatch")
    if (
        zero_run_count != len(zero_runs)
        or zero_run_count != span_zero_run_count
        or zero_run_count != fixture_zero_run_count
        or zero_run_count != 303
    ):
        issues.append("unresolved_run_zero_count_mismatch")
    if (
        nonzero_run_count != len(nonzero_runs)
        or nonzero_run_count != span_nonzero_run_count
        or nonzero_run_count != fixture_nonzero_run_count
        or nonzero_run_count != 426
    ):
        issues.append("unresolved_run_nonzero_count_mismatch")
    if (
        unresolved_bytes != span_unresolved_bytes
        or unresolved_bytes != run_total_bytes
        or unresolved_bytes != fixture_unresolved_bytes
        or unresolved_bytes != 15836
    ):
        issues.append("unresolved_run_byte_mismatch")
    if (
        zero_bytes != span_zero_bytes
        or zero_bytes != run_zero_bytes
        or zero_bytes != fixture_zero_bytes
        or zero_bytes != 7787
    ):
        issues.append("unresolved_run_zero_byte_mismatch")
    if (
        nonzero_bytes != span_nonzero_bytes
        or nonzero_bytes != run_nonzero_bytes
        or nonzero_bytes != fixture_nonzero_bytes
        or nonzero_bytes != 8049
    ):
        issues.append("unresolved_run_nonzero_byte_mismatch")
    if zero_bytes + nonzero_bytes != unresolved_bytes:
        issues.append("unresolved_run_bytes_not_partitioned")
    if pure_zero_span_bytes != span_pure_zero_bytes or pure_zero_span_bytes != 189:
        issues.append("unresolved_run_pure_zero_span_mismatch")
    if mixed_span_zero_bytes != span_mixed_zero_bytes or mixed_span_zero_bytes != 7598:
        issues.append("unresolved_run_mixed_zero_span_mismatch")
    if pure_zero_span_bytes + mixed_span_zero_bytes != zero_bytes:
        issues.append("unresolved_run_zero_span_bytes_not_partitioned")
    if (
        max_zero_run != span_max_zero
        or max_zero_run != run_max_zero
        or max_zero_run != fixture_max_zero
        or max_zero_run != 111
    ):
        issues.append("unresolved_run_max_zero_mismatch")
    if (
        max_nonzero_run != span_max_nonzero
        or max_nonzero_run != run_max_nonzero
        or max_nonzero_run != fixture_max_nonzero
        or max_nonzero_run != 128
    ):
        issues.append("unresolved_run_max_nonzero_mismatch")
    if largest_run != run_largest or largest_run != 128:
        issues.append("unresolved_run_largest_mismatch")
    if largest_run_class not in run_largest_classes or largest_run_class != "nonzero":
        issues.append("unresolved_run_largest_class_mismatch")
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    if "const TEX_GAP_DECODER_UNRESOLVED_RUN_PROBE = " not in text:
        issues.append("missing_tex_gap_decoder_unresolved_run_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_decoder_unresolved_run_probe",
            ok,
            expected=".tex unresolved clean-gap spans are split into internal zero/nonzero runs",
            actual=(
                f"spans={unresolved_span_count}, runs={run_count}, zero={zero_bytes}, "
                f"nonzero={nonzero_bytes}, max_zero={max_zero_run}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        zero_bytes if ok else 0,
        run_count if ok else 0,
        max_zero_run if ok else 0,
    )


def audit_tex_gap_decoder_len64_promoted_run_probe(
    summary: Path,
    span_rows_path: Path,
    run_rows_path: Path,
    fixture_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_decoder_len64_promoted_run_probe", summary), 0, 0, 0
    if not span_rows_path.exists():
        return missing_gate("tex_gap_decoder_len64_promoted_run_probe", span_rows_path), 0, 0, 0
    if not run_rows_path.exists():
        return missing_gate("tex_gap_decoder_len64_promoted_run_probe", run_rows_path), 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate("tex_gap_decoder_len64_promoted_run_probe", fixture_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_decoder_len64_promoted_run_probe", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    span_rows = read_csv(span_rows_path)
    run_rows = read_csv(run_rows_path)
    fixture_rows = read_csv(fixture_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    unresolved_span_count = int_value(total, "unresolved_span_rows")
    run_count = int_value(total, "run_rows")
    zero_run_count = int_value(total, "zero_run_rows")
    nonzero_run_count = int_value(total, "nonzero_run_rows")
    unresolved_bytes = int_value(total, "unresolved_bytes")
    zero_bytes = int_value(total, "zero_bytes")
    nonzero_bytes = int_value(total, "nonzero_bytes")
    pure_zero_span_bytes = int_value(total, "pure_zero_span_bytes")
    mixed_span_zero_bytes = int_value(total, "mixed_span_zero_bytes")
    max_zero_run = int_value(total, "max_zero_run_bytes")
    max_nonzero_run = int_value(total, "max_nonzero_run_bytes")
    largest_run = int_value(total, "largest_run_bytes")
    largest_run_class = total.get("largest_run_class", "")
    issue_rows = int_value(total, "issue_rows")

    zero_runs = [row for row in run_rows if row.get("run_class") == "zero"]
    nonzero_runs = [row for row in run_rows if row.get("run_class") == "nonzero"]
    span_unresolved_bytes = sum(int_value(row, "length") for row in span_rows)
    span_zero_bytes = sum(int_value(row, "zero_bytes") for row in span_rows)
    span_nonzero_bytes = sum(int_value(row, "nonzero_bytes") for row in span_rows)
    span_pure_zero_bytes = sum(
        int_value(row, "length")
        for row in span_rows
        if row.get("span_class") == "unresolved_zero"
    )
    span_mixed_zero_bytes = sum(
        int_value(row, "zero_bytes")
        for row in span_rows
        if row.get("span_class") == "unresolved_mixed"
    )
    span_run_count = sum(int_value(row, "run_rows") for row in span_rows)
    span_zero_run_count = sum(int_value(row, "zero_runs") for row in span_rows)
    span_nonzero_run_count = sum(int_value(row, "nonzero_runs") for row in span_rows)
    span_max_zero = max([int_value(row, "max_zero_run_bytes") for row in span_rows] or [0])
    span_max_nonzero = max([int_value(row, "max_nonzero_run_bytes") for row in span_rows] or [0])

    run_total_bytes = sum(int_value(row, "length") for row in run_rows)
    run_zero_bytes = sum(int_value(row, "length") for row in zero_runs)
    run_nonzero_bytes = sum(int_value(row, "length") for row in nonzero_runs)
    run_max_zero = max([int_value(row, "length") for row in zero_runs] or [0])
    run_max_nonzero = max([int_value(row, "length") for row in nonzero_runs] or [0])
    run_largest = max([int_value(row, "length") for row in run_rows] or [0])
    run_largest_classes = {
        row.get("run_class", "")
        for row in run_rows
        if int_value(row, "length") == run_largest
    }

    fixture_unresolved_bytes = sum(int_value(row, "unresolved_bytes") for row in fixture_rows)
    fixture_zero_bytes = sum(int_value(row, "zero_bytes") for row in fixture_rows)
    fixture_nonzero_bytes = sum(int_value(row, "nonzero_bytes") for row in fixture_rows)
    fixture_run_count = sum(int_value(row, "run_rows") for row in fixture_rows)
    fixture_zero_run_count = sum(int_value(row, "zero_run_rows") for row in fixture_rows)
    fixture_nonzero_run_count = sum(int_value(row, "nonzero_run_rows") for row in fixture_rows)
    fixture_max_zero = max([int_value(row, "max_zero_run_bytes") for row in fixture_rows] or [0])
    fixture_max_nonzero = max(
        [int_value(row, "max_nonzero_run_bytes") for row in fixture_rows] or [0]
    )

    if fixture_count != len(fixture_rows) or fixture_count != 32:
        issues.append("len64_promoted_run_fixture_count_mismatch")
    if unresolved_span_count != len(span_rows) or unresolved_span_count != 236:
        issues.append("len64_promoted_run_span_count_mismatch")
    if (
        run_count != len(run_rows)
        or run_count != span_run_count
        or run_count != fixture_run_count
        or run_count != 685
    ):
        issues.append("len64_promoted_run_count_mismatch")
    if (
        zero_run_count != len(zero_runs)
        or zero_run_count != span_zero_run_count
        or zero_run_count != fixture_zero_run_count
        or zero_run_count != 259
    ):
        issues.append("len64_promoted_run_zero_count_mismatch")
    if (
        nonzero_run_count != len(nonzero_runs)
        or nonzero_run_count != span_nonzero_run_count
        or nonzero_run_count != fixture_nonzero_run_count
        or nonzero_run_count != 426
    ):
        issues.append("len64_promoted_run_nonzero_count_mismatch")
    if (
        unresolved_bytes != span_unresolved_bytes
        or unresolved_bytes != run_total_bytes
        or unresolved_bytes != fixture_unresolved_bytes
        or unresolved_bytes != 13020
    ):
        issues.append("len64_promoted_run_byte_mismatch")
    if (
        zero_bytes != span_zero_bytes
        or zero_bytes != run_zero_bytes
        or zero_bytes != fixture_zero_bytes
        or zero_bytes != 4971
    ):
        issues.append("len64_promoted_run_zero_byte_mismatch")
    if (
        nonzero_bytes != span_nonzero_bytes
        or nonzero_bytes != run_nonzero_bytes
        or nonzero_bytes != fixture_nonzero_bytes
        or nonzero_bytes != 8049
    ):
        issues.append("len64_promoted_run_nonzero_byte_mismatch")
    if zero_bytes + nonzero_bytes != unresolved_bytes:
        issues.append("len64_promoted_run_bytes_not_partitioned")
    if pure_zero_span_bytes != span_pure_zero_bytes or pure_zero_span_bytes != 189:
        issues.append("len64_promoted_run_pure_zero_span_mismatch")
    if mixed_span_zero_bytes != span_mixed_zero_bytes or mixed_span_zero_bytes != 4782:
        issues.append("len64_promoted_run_mixed_zero_span_mismatch")
    if pure_zero_span_bytes + mixed_span_zero_bytes != zero_bytes:
        issues.append("len64_promoted_run_zero_span_bytes_not_partitioned")
    if (
        max_zero_run != span_max_zero
        or max_zero_run != run_max_zero
        or max_zero_run != fixture_max_zero
        or max_zero_run != 111
    ):
        issues.append("len64_promoted_run_max_zero_mismatch")
    if (
        max_nonzero_run != span_max_nonzero
        or max_nonzero_run != run_max_nonzero
        or max_nonzero_run != fixture_max_nonzero
        or max_nonzero_run != 128
    ):
        issues.append("len64_promoted_run_max_nonzero_mismatch")
    if largest_run != run_largest or largest_run != 128:
        issues.append("len64_promoted_run_largest_mismatch")
    if largest_run_class not in run_largest_classes or largest_run_class != "nonzero":
        issues.append("len64_promoted_run_largest_class_mismatch")
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    if "const TEX_GAP_DECODER_LEN64_PROMOTED_RUN_PROBE = " not in text:
        issues.append("missing_tex_gap_decoder_len64_promoted_run_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_decoder_len64_promoted_run_probe",
            ok,
            expected=".tex len64 promoted remaining spans are split into zero/nonzero runs",
            actual=(
                f"spans={unresolved_span_count}, runs={run_count}, zero={zero_bytes}, "
                f"nonzero={nonzero_bytes}, max_zero={max_zero_run}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        zero_bytes if ok else 0,
        run_count if ok else 0,
        max_zero_run if ok else 0,
    )


def audit_tex_gap_decoder_len64_promoted_large32_run_probe(
    summary: Path,
    span_rows_path: Path,
    run_rows_path: Path,
    fixture_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    gate_name = "tex_gap_decoder_len64_promoted_large32_run_probe"
    if not summary.exists():
        return missing_gate(gate_name, summary), 0, 0, 0
    if not span_rows_path.exists():
        return missing_gate(gate_name, span_rows_path), 0, 0, 0
    if not run_rows_path.exists():
        return missing_gate(gate_name, run_rows_path), 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate(gate_name, fixture_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate(gate_name, html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    span_rows = read_csv(span_rows_path)
    run_rows = read_csv(run_rows_path)
    fixture_rows = read_csv(fixture_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    unresolved_span_count = int_value(total, "unresolved_span_rows")
    run_count = int_value(total, "run_rows")
    zero_run_count = int_value(total, "zero_run_rows")
    nonzero_run_count = int_value(total, "nonzero_run_rows")
    unresolved_bytes = int_value(total, "unresolved_bytes")
    zero_bytes = int_value(total, "zero_bytes")
    nonzero_bytes = int_value(total, "nonzero_bytes")
    pure_zero_span_bytes = int_value(total, "pure_zero_span_bytes")
    mixed_span_zero_bytes = int_value(total, "mixed_span_zero_bytes")
    max_zero_run = int_value(total, "max_zero_run_bytes")
    max_nonzero_run = int_value(total, "max_nonzero_run_bytes")
    largest_run = int_value(total, "largest_run_bytes")
    largest_run_class = total.get("largest_run_class", "")
    issue_rows = int_value(total, "issue_rows")

    zero_runs = [row for row in run_rows if row.get("run_class") == "zero"]
    nonzero_runs = [row for row in run_rows if row.get("run_class") == "nonzero"]
    span_unresolved_bytes = sum(int_value(row, "length") for row in span_rows)
    span_zero_bytes = sum(int_value(row, "zero_bytes") for row in span_rows)
    span_nonzero_bytes = sum(int_value(row, "nonzero_bytes") for row in span_rows)
    span_pure_zero_bytes = sum(
        int_value(row, "length")
        for row in span_rows
        if row.get("span_class") == "unresolved_zero"
    )
    span_mixed_zero_bytes = sum(
        int_value(row, "zero_bytes")
        for row in span_rows
        if row.get("span_class") == "unresolved_mixed"
    )
    span_run_count = sum(int_value(row, "run_rows") for row in span_rows)
    span_zero_run_count = sum(int_value(row, "zero_runs") for row in span_rows)
    span_nonzero_run_count = sum(int_value(row, "nonzero_runs") for row in span_rows)
    span_max_zero = max([int_value(row, "max_zero_run_bytes") for row in span_rows] or [0])
    span_max_nonzero = max([int_value(row, "max_nonzero_run_bytes") for row in span_rows] or [0])

    run_total_bytes = sum(int_value(row, "length") for row in run_rows)
    run_zero_bytes = sum(int_value(row, "length") for row in zero_runs)
    run_nonzero_bytes = sum(int_value(row, "length") for row in nonzero_runs)
    run_max_zero = max([int_value(row, "length") for row in zero_runs] or [0])
    run_max_nonzero = max([int_value(row, "length") for row in nonzero_runs] or [0])
    run_largest = max([int_value(row, "length") for row in run_rows] or [0])
    run_largest_classes = {
        row.get("run_class", "")
        for row in run_rows
        if int_value(row, "length") == run_largest
    }

    fixture_unresolved_bytes = sum(int_value(row, "unresolved_bytes") for row in fixture_rows)
    fixture_zero_bytes = sum(int_value(row, "zero_bytes") for row in fixture_rows)
    fixture_nonzero_bytes = sum(int_value(row, "nonzero_bytes") for row in fixture_rows)
    fixture_run_count = sum(int_value(row, "run_rows") for row in fixture_rows)
    fixture_zero_run_count = sum(int_value(row, "zero_run_rows") for row in fixture_rows)
    fixture_nonzero_run_count = sum(int_value(row, "nonzero_run_rows") for row in fixture_rows)
    fixture_max_zero = max([int_value(row, "max_zero_run_bytes") for row in fixture_rows] or [0])
    fixture_max_nonzero = max(
        [int_value(row, "max_nonzero_run_bytes") for row in fixture_rows] or [0]
    )

    if fixture_count != len(fixture_rows) or fixture_count != 32:
        issues.append("large32_promoted_run_fixture_count_mismatch")
    if unresolved_span_count != len(span_rows) or unresolved_span_count != 261:
        issues.append("large32_promoted_run_span_count_mismatch")
    if (
        run_count != len(run_rows)
        or run_count != span_run_count
        or run_count != fixture_run_count
        or run_count != 660
    ):
        issues.append("large32_promoted_run_count_mismatch")
    if (
        zero_run_count != len(zero_runs)
        or zero_run_count != span_zero_run_count
        or zero_run_count != fixture_zero_run_count
        or zero_run_count != 234
    ):
        issues.append("large32_promoted_run_zero_count_mismatch")
    if (
        nonzero_run_count != len(nonzero_runs)
        or nonzero_run_count != span_nonzero_run_count
        or nonzero_run_count != fixture_nonzero_run_count
        or nonzero_run_count != 426
    ):
        issues.append("large32_promoted_run_nonzero_count_mismatch")
    if (
        unresolved_bytes != span_unresolved_bytes
        or unresolved_bytes != run_total_bytes
        or unresolved_bytes != fixture_unresolved_bytes
        or unresolved_bytes != 11984
    ):
        issues.append("large32_promoted_run_byte_mismatch")
    if (
        zero_bytes != span_zero_bytes
        or zero_bytes != run_zero_bytes
        or zero_bytes != fixture_zero_bytes
        or zero_bytes != 3935
    ):
        issues.append("large32_promoted_run_zero_byte_mismatch")
    if (
        nonzero_bytes != span_nonzero_bytes
        or nonzero_bytes != run_nonzero_bytes
        or nonzero_bytes != fixture_nonzero_bytes
        or nonzero_bytes != 8049
    ):
        issues.append("large32_promoted_run_nonzero_byte_mismatch")
    if zero_bytes + nonzero_bytes != unresolved_bytes:
        issues.append("large32_promoted_run_bytes_not_partitioned")
    if pure_zero_span_bytes != span_pure_zero_bytes or pure_zero_span_bytes != 189:
        issues.append("large32_promoted_run_pure_zero_span_mismatch")
    if mixed_span_zero_bytes != span_mixed_zero_bytes or mixed_span_zero_bytes != 3746:
        issues.append("large32_promoted_run_mixed_zero_span_mismatch")
    if pure_zero_span_bytes + mixed_span_zero_bytes != zero_bytes:
        issues.append("large32_promoted_run_zero_span_bytes_not_partitioned")
    if (
        max_zero_run != span_max_zero
        or max_zero_run != run_max_zero
        or max_zero_run != fixture_max_zero
        or max_zero_run != 111
    ):
        issues.append("large32_promoted_run_max_zero_mismatch")
    if (
        max_nonzero_run != span_max_nonzero
        or max_nonzero_run != run_max_nonzero
        or max_nonzero_run != fixture_max_nonzero
        or max_nonzero_run != 128
    ):
        issues.append("large32_promoted_run_max_nonzero_mismatch")
    if largest_run != run_largest or largest_run != 128:
        issues.append("large32_promoted_run_largest_mismatch")
    if largest_run_class not in run_largest_classes or largest_run_class != "nonzero":
        issues.append("large32_promoted_run_largest_class_mismatch")
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    if "const TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_RUN_PROBE = " not in text:
        issues.append("missing_tex_gap_decoder_len64_promoted_large32_run_probe_json")

    ok = not issues
    return (
        gate(
            gate_name,
            ok,
            expected=".tex large32 promoted remaining spans are split into zero/nonzero runs",
            actual=(
                f"spans={unresolved_span_count}, runs={run_count}, zero={zero_bytes}, "
                f"nonzero={nonzero_bytes}, max_zero={max_zero_run}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        zero_bytes if ok else 0,
        run_count if ok else 0,
        max_zero_run if ok else 0,
    )


def audit_tex_gap_decoder_len64_promoted_medium8_run_probe(
    summary: Path,
    span_rows_path: Path,
    run_rows_path: Path,
    fixture_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    gate_name = "tex_gap_decoder_len64_promoted_medium8_run_probe"
    if not summary.exists():
        return missing_gate(gate_name, summary), 0, 0, 0
    if not span_rows_path.exists():
        return missing_gate(gate_name, span_rows_path), 0, 0, 0
    if not run_rows_path.exists():
        return missing_gate(gate_name, run_rows_path), 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate(gate_name, fixture_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate(gate_name, html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    span_rows = read_csv(span_rows_path)
    run_rows = read_csv(run_rows_path)
    fixture_rows = read_csv(fixture_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    unresolved_span_count = int_value(total, "unresolved_span_rows")
    run_count = int_value(total, "run_rows")
    zero_run_count = int_value(total, "zero_run_rows")
    nonzero_run_count = int_value(total, "nonzero_run_rows")
    unresolved_bytes = int_value(total, "unresolved_bytes")
    zero_bytes = int_value(total, "zero_bytes")
    nonzero_bytes = int_value(total, "nonzero_bytes")
    pure_zero_span_bytes = int_value(total, "pure_zero_span_bytes")
    mixed_span_zero_bytes = int_value(total, "mixed_span_zero_bytes")
    max_zero_run = int_value(total, "max_zero_run_bytes")
    max_nonzero_run = int_value(total, "max_nonzero_run_bytes")
    largest_run = int_value(total, "largest_run_bytes")
    largest_run_class = total.get("largest_run_class", "")
    issue_rows = int_value(total, "issue_rows")

    zero_runs = [row for row in run_rows if row.get("run_class") == "zero"]
    nonzero_runs = [row for row in run_rows if row.get("run_class") == "nonzero"]
    span_unresolved_bytes = sum(int_value(row, "length") for row in span_rows)
    span_zero_bytes = sum(int_value(row, "zero_bytes") for row in span_rows)
    span_nonzero_bytes = sum(int_value(row, "nonzero_bytes") for row in span_rows)
    span_pure_zero_bytes = sum(
        int_value(row, "length")
        for row in span_rows
        if row.get("span_class") == "unresolved_zero"
    )
    span_mixed_zero_bytes = sum(
        int_value(row, "zero_bytes")
        for row in span_rows
        if row.get("span_class") == "unresolved_mixed"
    )
    span_run_count = sum(int_value(row, "run_rows") for row in span_rows)
    span_zero_run_count = sum(int_value(row, "zero_runs") for row in span_rows)
    span_nonzero_run_count = sum(int_value(row, "nonzero_runs") for row in span_rows)
    span_max_zero = max([int_value(row, "max_zero_run_bytes") for row in span_rows] or [0])
    span_max_nonzero = max([int_value(row, "max_nonzero_run_bytes") for row in span_rows] or [0])

    run_total_bytes = sum(int_value(row, "length") for row in run_rows)
    run_zero_bytes = sum(int_value(row, "length") for row in zero_runs)
    run_nonzero_bytes = sum(int_value(row, "length") for row in nonzero_runs)
    run_max_zero = max([int_value(row, "length") for row in zero_runs] or [0])
    run_max_nonzero = max([int_value(row, "length") for row in nonzero_runs] or [0])
    run_largest = max([int_value(row, "length") for row in run_rows] or [0])
    run_largest_classes = {
        row.get("run_class", "")
        for row in run_rows
        if int_value(row, "length") == run_largest
    }

    fixture_unresolved_bytes = sum(int_value(row, "unresolved_bytes") for row in fixture_rows)
    fixture_zero_bytes = sum(int_value(row, "zero_bytes") for row in fixture_rows)
    fixture_nonzero_bytes = sum(int_value(row, "nonzero_bytes") for row in fixture_rows)
    fixture_run_count = sum(int_value(row, "run_rows") for row in fixture_rows)
    fixture_zero_run_count = sum(int_value(row, "zero_run_rows") for row in fixture_rows)
    fixture_nonzero_run_count = sum(int_value(row, "nonzero_run_rows") for row in fixture_rows)
    fixture_max_zero = max([int_value(row, "max_zero_run_bytes") for row in fixture_rows] or [0])
    fixture_max_nonzero = max(
        [int_value(row, "max_nonzero_run_bytes") for row in fixture_rows] or [0]
    )

    if fixture_count != len(fixture_rows) or fixture_count != 32:
        issues.append("medium8_promoted_run_fixture_count_mismatch")
    if unresolved_span_count != len(span_rows) or unresolved_span_count != 269:
        issues.append("medium8_promoted_run_span_count_mismatch")
    if (
        run_count != len(run_rows)
        or run_count != span_run_count
        or run_count != fixture_run_count
        or run_count != 652
    ):
        issues.append("medium8_promoted_run_count_mismatch")
    if (
        zero_run_count != len(zero_runs)
        or zero_run_count != span_zero_run_count
        or zero_run_count != fixture_zero_run_count
        or zero_run_count != 226
    ):
        issues.append("medium8_promoted_run_zero_count_mismatch")
    if (
        nonzero_run_count != len(nonzero_runs)
        or nonzero_run_count != span_nonzero_run_count
        or nonzero_run_count != fixture_nonzero_run_count
        or nonzero_run_count != 426
    ):
        issues.append("medium8_promoted_run_nonzero_count_mismatch")
    if (
        unresolved_bytes != span_unresolved_bytes
        or unresolved_bytes != run_total_bytes
        or unresolved_bytes != fixture_unresolved_bytes
        or unresolved_bytes != 11866
    ):
        issues.append("medium8_promoted_run_byte_mismatch")
    if (
        zero_bytes != span_zero_bytes
        or zero_bytes != run_zero_bytes
        or zero_bytes != fixture_zero_bytes
        or zero_bytes != 3817
    ):
        issues.append("medium8_promoted_run_zero_byte_mismatch")
    if (
        nonzero_bytes != span_nonzero_bytes
        or nonzero_bytes != run_nonzero_bytes
        or nonzero_bytes != fixture_nonzero_bytes
        or nonzero_bytes != 8049
    ):
        issues.append("medium8_promoted_run_nonzero_byte_mismatch")
    if zero_bytes + nonzero_bytes != unresolved_bytes:
        issues.append("medium8_promoted_run_bytes_not_partitioned")
    if pure_zero_span_bytes != span_pure_zero_bytes or pure_zero_span_bytes != 189:
        issues.append("medium8_promoted_run_pure_zero_span_mismatch")
    if mixed_span_zero_bytes != span_mixed_zero_bytes or mixed_span_zero_bytes != 3628:
        issues.append("medium8_promoted_run_mixed_zero_span_mismatch")
    if pure_zero_span_bytes + mixed_span_zero_bytes != zero_bytes:
        issues.append("medium8_promoted_run_zero_span_bytes_not_partitioned")
    if (
        max_zero_run != span_max_zero
        or max_zero_run != run_max_zero
        or max_zero_run != fixture_max_zero
        or max_zero_run != 111
    ):
        issues.append("medium8_promoted_run_max_zero_mismatch")
    if (
        max_nonzero_run != span_max_nonzero
        or max_nonzero_run != run_max_nonzero
        or max_nonzero_run != fixture_max_nonzero
        or max_nonzero_run != 128
    ):
        issues.append("medium8_promoted_run_max_nonzero_mismatch")
    if largest_run != run_largest or largest_run != 128:
        issues.append("medium8_promoted_run_largest_mismatch")
    if largest_run_class not in run_largest_classes or largest_run_class != "nonzero":
        issues.append("medium8_promoted_run_largest_class_mismatch")
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    if "const TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_RUN_PROBE = " not in text:
        issues.append("missing_tex_gap_decoder_len64_promoted_medium8_run_probe_json")

    ok = not issues
    return (
        gate(
            gate_name,
            ok,
            expected=".tex medium8 promoted remaining spans are split into zero/nonzero runs",
            actual=(
                f"spans={unresolved_span_count}, runs={run_count}, zero={zero_bytes}, "
                f"nonzero={nonzero_bytes}, max_zero={max_zero_run}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        zero_bytes if ok else 0,
        run_count if ok else 0,
        max_zero_run if ok else 0,
    )


def audit_tex_gap_decoder_len64_promoted_large32_zero_queue(
    summary: Path,
    queue_rows_path: Path,
    signature_rows_path: Path,
    fixture_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    gate_name = "tex_gap_decoder_len64_promoted_large32_zero_queue"
    if not summary.exists():
        return missing_gate(gate_name, summary), 0, 0, 0
    if not queue_rows_path.exists():
        return missing_gate(gate_name, queue_rows_path), 0, 0, 0
    if not signature_rows_path.exists():
        return missing_gate(gate_name, signature_rows_path), 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate(gate_name, fixture_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate(gate_name, html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    queue_rows = read_csv(queue_rows_path)
    signature_rows = read_csv(signature_rows_path)
    fixture_rows = read_csv(fixture_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    span_count = int_value(total, "span_rows")
    zero_run_count = int_value(total, "zero_run_rows")
    zero_bytes = int_value(total, "zero_bytes")
    pure_rows = int_value(total, "pure_zero_span_rows")
    pure_bytes = int_value(total, "pure_zero_span_bytes")
    internal_rows = int_value(total, "internal_zero_run_rows")
    internal_bytes = int_value(total, "internal_zero_bytes")
    boundary_rows = int_value(total, "boundary_zero_run_rows")
    boundary_bytes = int_value(total, "boundary_zero_bytes")
    len64_rows = int_value(total, "len64_run_rows")
    len64_bytes = int_value(total, "len64_bytes")
    large_rows = int_value(total, "large_run_rows")
    large_bytes = int_value(total, "large_run_bytes")
    max_zero = int_value(total, "max_zero_run_bytes")
    signature_count = int_value(total, "signature_rows")
    issue_rows = int_value(total, "issue_rows")

    queue_total_bytes = sum(int_value(row, "length") for row in queue_rows)
    queue_pure = [row for row in queue_rows if row.get("queue_class") == "review_pure_zero_span"]
    queue_internal = [
        row for row in queue_rows if row.get("queue_class") == "review_internal_zero"
    ]
    queue_boundary = [
        row for row in queue_rows if row.get("queue_class") == "review_boundary_zero"
    ]
    queue_len64 = [row for row in queue_rows if row.get("length_bucket") == "len64"]
    queue_large = [
        row
        for row in queue_rows
        if row.get("length_bucket") in {"len64", "multiple64", "large96", "large32"}
    ]
    queue_max_zero = max([int_value(row, "length") for row in queue_rows] or [0])

    signature_total_rows = sum(int_value(row, "rows") for row in signature_rows)
    signature_total_bytes = sum(int_value(row, "bytes") for row in signature_rows)
    signature_max_zero = max([int_value(row, "max_run_bytes") for row in signature_rows] or [0])
    fixture_total_rows = sum(int_value(row, "zero_run_rows") for row in fixture_rows)
    fixture_total_bytes = sum(int_value(row, "zero_bytes") for row in fixture_rows)
    fixture_internal_bytes = sum(int_value(row, "internal_zero_bytes") for row in fixture_rows)
    fixture_boundary_bytes = sum(int_value(row, "boundary_zero_bytes") for row in fixture_rows)
    fixture_pure_bytes = sum(int_value(row, "pure_zero_span_bytes") for row in fixture_rows)
    fixture_max_zero = max([int_value(row, "max_zero_run_bytes") for row in fixture_rows] or [0])
    top_signature = signature_rows[0] if signature_rows else {}

    if fixture_count != len(fixture_rows) or fixture_count != 32:
        issues.append("large32_promoted_zero_queue_fixture_count_mismatch")
    if span_count != 261:
        issues.append("large32_promoted_zero_queue_span_count_mismatch")
    if (
        zero_run_count != len(queue_rows)
        or zero_run_count != signature_total_rows
        or zero_run_count != fixture_total_rows
        or zero_run_count != 234
    ):
        issues.append("large32_promoted_zero_queue_row_count_mismatch")
    if (
        zero_bytes != queue_total_bytes
        or zero_bytes != signature_total_bytes
        or zero_bytes != fixture_total_bytes
        or zero_bytes != 3935
    ):
        issues.append("large32_promoted_zero_queue_byte_mismatch")
    if pure_rows != len(queue_pure) or pure_rows != 3:
        issues.append("large32_promoted_zero_queue_pure_row_mismatch")
    if (
        pure_bytes != sum(int_value(row, "length") for row in queue_pure)
        or pure_bytes != fixture_pure_bytes
        or pure_bytes != 189
    ):
        issues.append("large32_promoted_zero_queue_pure_byte_mismatch")
    if internal_rows != len(queue_internal) or internal_rows != 168:
        issues.append("large32_promoted_zero_queue_internal_row_mismatch")
    if (
        internal_bytes != sum(int_value(row, "length") for row in queue_internal)
        or internal_bytes != fixture_internal_bytes
        or internal_bytes != 2120
    ):
        issues.append("large32_promoted_zero_queue_internal_byte_mismatch")
    if boundary_rows != len(queue_boundary) or boundary_rows != 63:
        issues.append("large32_promoted_zero_queue_boundary_row_mismatch")
    if (
        boundary_bytes != sum(int_value(row, "length") for row in queue_boundary)
        or boundary_bytes != fixture_boundary_bytes
        or boundary_bytes != 1626
    ):
        issues.append("large32_promoted_zero_queue_boundary_byte_mismatch")
    if pure_bytes + internal_bytes + boundary_bytes != zero_bytes:
        issues.append("large32_promoted_zero_queue_bytes_not_partitioned")
    if len64_rows != len(queue_len64) or len64_rows != 5:
        issues.append("large32_promoted_zero_queue_len64_row_mismatch")
    if len64_bytes != sum(int_value(row, "length") for row in queue_len64) or len64_bytes != 320:
        issues.append("large32_promoted_zero_queue_len64_byte_mismatch")
    if large_rows != len(queue_large) or large_rows != 38:
        issues.append("large32_promoted_zero_queue_large_row_mismatch")
    if large_bytes != sum(int_value(row, "length") for row in queue_large) or large_bytes != 1858:
        issues.append("large32_promoted_zero_queue_large_byte_mismatch")
    if (
        max_zero != queue_max_zero
        or max_zero != signature_max_zero
        or max_zero != fixture_max_zero
        or max_zero != 111
    ):
        issues.append("large32_promoted_zero_queue_max_mismatch")
    if signature_count != len(signature_rows) or signature_count != 18:
        issues.append("large32_promoted_zero_queue_signature_count_mismatch")
    if top_signature.get("signature") != "internal|medium8|left_nonzero|right_nonzero":
        issues.append("large32_promoted_zero_queue_top_signature_mismatch")
    if int_value(top_signature, "rows") != 83 or int_value(top_signature, "bytes") != 1421:
        issues.append("large32_promoted_zero_queue_top_signature_value_mismatch")
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    if "const TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_ZERO_QUEUE = " not in text:
        issues.append("missing_tex_gap_decoder_len64_promoted_large32_zero_queue_json")

    ok = not issues
    return (
        gate(
            gate_name,
            ok,
            expected=".tex large32 promoted zero runs are queued by context",
            actual=(
                f"runs={zero_run_count}, bytes={zero_bytes}, internal={internal_bytes}, "
                f"len64={len64_rows}, signatures={signature_count}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        zero_bytes if ok else 0,
        internal_bytes if ok else 0,
        signature_count if ok else 0,
    )


def audit_tex_gap_decoder_len64_promoted_medium8_zero_queue(
    summary: Path,
    queue_rows_path: Path,
    signature_rows_path: Path,
    fixture_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    gate_name = "tex_gap_decoder_len64_promoted_medium8_zero_queue"
    if not summary.exists():
        return missing_gate(gate_name, summary), 0, 0, 0
    if not queue_rows_path.exists():
        return missing_gate(gate_name, queue_rows_path), 0, 0, 0
    if not signature_rows_path.exists():
        return missing_gate(gate_name, signature_rows_path), 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate(gate_name, fixture_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate(gate_name, html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    queue_rows = read_csv(queue_rows_path)
    signature_rows = read_csv(signature_rows_path)
    fixture_rows = read_csv(fixture_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    span_count = int_value(total, "span_rows")
    zero_run_count = int_value(total, "zero_run_rows")
    zero_bytes = int_value(total, "zero_bytes")
    pure_rows = int_value(total, "pure_zero_span_rows")
    pure_bytes = int_value(total, "pure_zero_span_bytes")
    internal_rows = int_value(total, "internal_zero_run_rows")
    internal_bytes = int_value(total, "internal_zero_bytes")
    boundary_rows = int_value(total, "boundary_zero_run_rows")
    boundary_bytes = int_value(total, "boundary_zero_bytes")
    len64_rows = int_value(total, "len64_run_rows")
    len64_bytes = int_value(total, "len64_bytes")
    large_rows = int_value(total, "large_run_rows")
    large_bytes = int_value(total, "large_run_bytes")
    max_zero = int_value(total, "max_zero_run_bytes")
    signature_count = int_value(total, "signature_rows")
    issue_rows = int_value(total, "issue_rows")

    queue_total_bytes = sum(int_value(row, "length") for row in queue_rows)
    queue_pure = [row for row in queue_rows if row.get("queue_class") == "review_pure_zero_span"]
    queue_internal = [
        row for row in queue_rows if row.get("queue_class") == "review_internal_zero"
    ]
    queue_boundary = [
        row for row in queue_rows if row.get("queue_class") == "review_boundary_zero"
    ]
    queue_len64 = [row for row in queue_rows if row.get("length_bucket") == "len64"]
    queue_large = [
        row
        for row in queue_rows
        if row.get("length_bucket") in {"len64", "multiple64", "large96", "large32"}
    ]
    queue_max_zero = max([int_value(row, "length") for row in queue_rows] or [0])

    signature_total_rows = sum(int_value(row, "rows") for row in signature_rows)
    signature_total_bytes = sum(int_value(row, "bytes") for row in signature_rows)
    signature_max_zero = max([int_value(row, "max_run_bytes") for row in signature_rows] or [0])
    fixture_total_rows = sum(int_value(row, "zero_run_rows") for row in fixture_rows)
    fixture_total_bytes = sum(int_value(row, "zero_bytes") for row in fixture_rows)
    fixture_internal_bytes = sum(int_value(row, "internal_zero_bytes") for row in fixture_rows)
    fixture_boundary_bytes = sum(int_value(row, "boundary_zero_bytes") for row in fixture_rows)
    fixture_pure_bytes = sum(int_value(row, "pure_zero_span_bytes") for row in fixture_rows)
    fixture_max_zero = max([int_value(row, "max_zero_run_bytes") for row in fixture_rows] or [0])
    top_signature = signature_rows[0] if signature_rows else {}

    if fixture_count != len(fixture_rows) or fixture_count != 32:
        issues.append("medium8_promoted_zero_queue_fixture_count_mismatch")
    if span_count != 269:
        issues.append("medium8_promoted_zero_queue_span_count_mismatch")
    if (
        zero_run_count != len(queue_rows)
        or zero_run_count != signature_total_rows
        or zero_run_count != fixture_total_rows
        or zero_run_count != 226
    ):
        issues.append("medium8_promoted_zero_queue_row_count_mismatch")
    if (
        zero_bytes != queue_total_bytes
        or zero_bytes != signature_total_bytes
        or zero_bytes != fixture_total_bytes
        or zero_bytes != 3817
    ):
        issues.append("medium8_promoted_zero_queue_byte_mismatch")
    if pure_rows != len(queue_pure) or pure_rows != 3:
        issues.append("medium8_promoted_zero_queue_pure_row_mismatch")
    if (
        pure_bytes != sum(int_value(row, "length") for row in queue_pure)
        or pure_bytes != fixture_pure_bytes
        or pure_bytes != 189
    ):
        issues.append("medium8_promoted_zero_queue_pure_byte_mismatch")
    if internal_rows != len(queue_internal) or internal_rows != 160:
        issues.append("medium8_promoted_zero_queue_internal_row_mismatch")
    if (
        internal_bytes != sum(int_value(row, "length") for row in queue_internal)
        or internal_bytes != fixture_internal_bytes
        or internal_bytes != 2002
    ):
        issues.append("medium8_promoted_zero_queue_internal_byte_mismatch")
    if boundary_rows != len(queue_boundary) or boundary_rows != 63:
        issues.append("medium8_promoted_zero_queue_boundary_row_mismatch")
    if (
        boundary_bytes != sum(int_value(row, "length") for row in queue_boundary)
        or boundary_bytes != fixture_boundary_bytes
        or boundary_bytes != 1626
    ):
        issues.append("medium8_promoted_zero_queue_boundary_byte_mismatch")
    if pure_bytes + internal_bytes + boundary_bytes != zero_bytes:
        issues.append("medium8_promoted_zero_queue_bytes_not_partitioned")
    if len64_rows != len(queue_len64) or len64_rows != 5:
        issues.append("medium8_promoted_zero_queue_len64_row_mismatch")
    if len64_bytes != sum(int_value(row, "length") for row in queue_len64) or len64_bytes != 320:
        issues.append("medium8_promoted_zero_queue_len64_byte_mismatch")
    if large_rows != len(queue_large) or large_rows != 38:
        issues.append("medium8_promoted_zero_queue_large_row_mismatch")
    if large_bytes != sum(int_value(row, "length") for row in queue_large) or large_bytes != 1858:
        issues.append("medium8_promoted_zero_queue_large_byte_mismatch")
    if (
        max_zero != queue_max_zero
        or max_zero != signature_max_zero
        or max_zero != fixture_max_zero
        or max_zero != 111
    ):
        issues.append("medium8_promoted_zero_queue_max_mismatch")
    if signature_count != len(signature_rows) or signature_count != 18:
        issues.append("medium8_promoted_zero_queue_signature_count_mismatch")
    if top_signature.get("signature") != "internal|medium8|left_nonzero|right_nonzero":
        issues.append("medium8_promoted_zero_queue_top_signature_mismatch")
    if int_value(top_signature, "rows") != 75 or int_value(top_signature, "bytes") != 1303:
        issues.append("medium8_promoted_zero_queue_top_signature_value_mismatch")
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    if "const TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_ZERO_QUEUE = " not in text:
        issues.append("missing_tex_gap_decoder_len64_promoted_medium8_zero_queue_json")

    ok = not issues
    return (
        gate(
            gate_name,
            ok,
            expected=".tex medium8 promoted zero runs are queued by context",
            actual=(
                f"runs={zero_run_count}, bytes={zero_bytes}, internal={internal_bytes}, "
                f"len64={len64_rows}, signatures={signature_count}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        zero_bytes if ok else 0,
        internal_bytes if ok else 0,
        signature_count if ok else 0,
    )


def audit_tex_gap_decoder_len64_promoted_zero_queue(
    summary: Path,
    queue_rows_path: Path,
    signature_rows_path: Path,
    fixture_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_decoder_len64_promoted_zero_queue", summary), 0, 0, 0
    if not queue_rows_path.exists():
        return missing_gate("tex_gap_decoder_len64_promoted_zero_queue", queue_rows_path), 0, 0, 0
    if not signature_rows_path.exists():
        return missing_gate("tex_gap_decoder_len64_promoted_zero_queue", signature_rows_path), 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate("tex_gap_decoder_len64_promoted_zero_queue", fixture_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_decoder_len64_promoted_zero_queue", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    queue_rows = read_csv(queue_rows_path)
    signature_rows = read_csv(signature_rows_path)
    fixture_rows = read_csv(fixture_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    span_count = int_value(total, "span_rows")
    zero_run_count = int_value(total, "zero_run_rows")
    zero_bytes = int_value(total, "zero_bytes")
    pure_rows = int_value(total, "pure_zero_span_rows")
    pure_bytes = int_value(total, "pure_zero_span_bytes")
    internal_rows = int_value(total, "internal_zero_run_rows")
    internal_bytes = int_value(total, "internal_zero_bytes")
    boundary_rows = int_value(total, "boundary_zero_run_rows")
    boundary_bytes = int_value(total, "boundary_zero_bytes")
    len64_rows = int_value(total, "len64_run_rows")
    len64_bytes = int_value(total, "len64_bytes")
    large_rows = int_value(total, "large_run_rows")
    large_bytes = int_value(total, "large_run_bytes")
    max_zero = int_value(total, "max_zero_run_bytes")
    signature_count = int_value(total, "signature_rows")
    issue_rows = int_value(total, "issue_rows")

    queue_total_bytes = sum(int_value(row, "length") for row in queue_rows)
    queue_pure = [row for row in queue_rows if row.get("queue_class") == "review_pure_zero_span"]
    queue_internal = [
        row for row in queue_rows if row.get("queue_class") == "review_internal_zero"
    ]
    queue_boundary = [
        row for row in queue_rows if row.get("queue_class") == "review_boundary_zero"
    ]
    queue_len64 = [row for row in queue_rows if row.get("length_bucket") == "len64"]
    queue_large = [
        row
        for row in queue_rows
        if row.get("length_bucket") in {"len64", "multiple64", "large96", "large32"}
    ]
    queue_max_zero = max([int_value(row, "length") for row in queue_rows] or [0])

    signature_total_rows = sum(int_value(row, "rows") for row in signature_rows)
    signature_total_bytes = sum(int_value(row, "bytes") for row in signature_rows)
    signature_max_zero = max([int_value(row, "max_run_bytes") for row in signature_rows] or [0])
    fixture_total_rows = sum(int_value(row, "zero_run_rows") for row in fixture_rows)
    fixture_total_bytes = sum(int_value(row, "zero_bytes") for row in fixture_rows)
    fixture_internal_bytes = sum(int_value(row, "internal_zero_bytes") for row in fixture_rows)
    fixture_boundary_bytes = sum(int_value(row, "boundary_zero_bytes") for row in fixture_rows)
    fixture_pure_bytes = sum(int_value(row, "pure_zero_span_bytes") for row in fixture_rows)
    fixture_max_zero = max([int_value(row, "max_zero_run_bytes") for row in fixture_rows] or [0])
    top_signature = signature_rows[0] if signature_rows else {}

    if fixture_count != len(fixture_rows) or fixture_count != 32:
        issues.append("len64_promoted_zero_queue_fixture_count_mismatch")
    if span_count != 236:
        issues.append("len64_promoted_zero_queue_span_count_mismatch")
    if (
        zero_run_count != len(queue_rows)
        or zero_run_count != signature_total_rows
        or zero_run_count != fixture_total_rows
        or zero_run_count != 259
    ):
        issues.append("len64_promoted_zero_queue_row_count_mismatch")
    if (
        zero_bytes != queue_total_bytes
        or zero_bytes != signature_total_bytes
        or zero_bytes != fixture_total_bytes
        or zero_bytes != 4971
    ):
        issues.append("len64_promoted_zero_queue_byte_mismatch")
    if pure_rows != len(queue_pure) or pure_rows != 3:
        issues.append("len64_promoted_zero_queue_pure_row_mismatch")
    if (
        pure_bytes != sum(int_value(row, "length") for row in queue_pure)
        or pure_bytes != fixture_pure_bytes
        or pure_bytes != 189
    ):
        issues.append("len64_promoted_zero_queue_pure_byte_mismatch")
    if internal_rows != len(queue_internal) or internal_rows != 193:
        issues.append("len64_promoted_zero_queue_internal_row_mismatch")
    if (
        internal_bytes != sum(int_value(row, "length") for row in queue_internal)
        or internal_bytes != fixture_internal_bytes
        or internal_bytes != 3156
    ):
        issues.append("len64_promoted_zero_queue_internal_byte_mismatch")
    if boundary_rows != len(queue_boundary) or boundary_rows != 63:
        issues.append("len64_promoted_zero_queue_boundary_row_mismatch")
    if (
        boundary_bytes != sum(int_value(row, "length") for row in queue_boundary)
        or boundary_bytes != fixture_boundary_bytes
        or boundary_bytes != 1626
    ):
        issues.append("len64_promoted_zero_queue_boundary_byte_mismatch")
    if pure_bytes + internal_bytes + boundary_bytes != zero_bytes:
        issues.append("len64_promoted_zero_queue_bytes_not_partitioned")
    if len64_rows != len(queue_len64) or len64_rows != 5:
        issues.append("len64_promoted_zero_queue_len64_row_mismatch")
    if len64_bytes != sum(int_value(row, "length") for row in queue_len64) or len64_bytes != 320:
        issues.append("len64_promoted_zero_queue_len64_byte_mismatch")
    if large_rows != len(queue_large) or large_rows != 63:
        issues.append("len64_promoted_zero_queue_large_row_mismatch")
    if large_bytes != sum(int_value(row, "length") for row in queue_large) or large_bytes != 2894:
        issues.append("len64_promoted_zero_queue_large_byte_mismatch")
    if (
        max_zero != queue_max_zero
        or max_zero != signature_max_zero
        or max_zero != fixture_max_zero
        or max_zero != 111
    ):
        issues.append("len64_promoted_zero_queue_max_mismatch")
    if signature_count != len(signature_rows) or signature_count != 18:
        issues.append("len64_promoted_zero_queue_signature_count_mismatch")
    if top_signature.get("signature") != "internal|large32|left_nonzero|right_nonzero":
        issues.append("len64_promoted_zero_queue_top_signature_mismatch")
    if int_value(top_signature, "rows") != 35 or int_value(top_signature, "bytes") != 1451:
        issues.append("len64_promoted_zero_queue_top_signature_value_mismatch")
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    if "const TEX_GAP_DECODER_LEN64_PROMOTED_ZERO_QUEUE = " not in text:
        issues.append("missing_tex_gap_decoder_len64_promoted_zero_queue_json")

    ok = not issues
    return (
        gate(
            "tex_gap_decoder_len64_promoted_zero_queue",
            ok,
            expected=".tex len64 promoted zero runs are queued by context",
            actual=(
                f"runs={zero_run_count}, bytes={zero_bytes}, internal={internal_bytes}, "
                f"len64={len64_rows}, signatures={signature_count}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        zero_bytes if ok else 0,
        internal_bytes if ok else 0,
        signature_count if ok else 0,
    )


def audit_tex_gap_decoder_len64_promoted_zero_source_probe(
    summary: Path,
    target_rows_path: Path,
    control_rows_path: Path,
    ref_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    gate_name = "tex_gap_decoder_len64_promoted_zero_source_probe"
    if not summary.exists():
        return missing_gate(gate_name, summary), 0, 0, 0
    if not target_rows_path.exists():
        return missing_gate(gate_name, target_rows_path), 0, 0, 0
    if not control_rows_path.exists():
        return missing_gate(gate_name, control_rows_path), 0, 0, 0
    if not ref_rows_path.exists():
        return missing_gate(gate_name, ref_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate(gate_name, html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    target_rows = read_csv(target_rows_path)
    control_rows = read_csv(control_rows_path)
    ref_rows = read_csv(ref_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    target_row_count = int_value(total, "target_rows")
    joined_rows = int_value(total, "joined_rows")
    target_bytes = int_value(total, "target_bytes")
    joined_bytes = int_value(total, "joined_bytes")
    missing_rows = int_value(total, "missing_rows")
    missing_bytes = int_value(total, "missing_bytes")
    length_u8_hit_rows = int_value(total, "length_u8_hit_rows")
    length_u16le_hit_rows = int_value(total, "length_u16le_hit_rows")
    source_delta_u8_hit_rows = int_value(total, "source_delta_u8_hit_rows")
    control_ref_rows = int_value(total, "control_ref_rows")
    unique_control_refs = int_value(total, "unique_control_refs")
    unique_control_windows = int_value(total, "unique_control_windows")
    top_control_window_rows = int_value(total, "top_control_window_rows")
    top_control_window_bytes = int_value(total, "top_control_window_bytes")
    top_control_ref_offset = total.get("top_control_ref_offset", "")
    top_control_ref_rows = int_value(total, "top_control_ref_rows")
    issue_rows = int_value(total, "issue_rows")

    joined_targets = [row for row in target_rows if not row.get("issues")]
    missing_targets = [row for row in target_rows if row.get("issues")]
    target_total_bytes = sum(int_value(row, "length") for row in target_rows)
    joined_total_bytes = sum(int_value(row, "length") for row in joined_targets)
    missing_total_bytes = sum(int_value(row, "length") for row in missing_targets)
    control_total_rows = sum(int_value(row, "rows") for row in control_rows)
    control_total_bytes = sum(int_value(row, "bytes") for row in control_rows)
    ref_total_rows = sum(int_value(row, "rows") for row in ref_rows)
    ref_total_bytes = sum(int_value(row, "bytes") for row in ref_rows)
    top_control = control_rows[0] if control_rows else {}
    top_ref = ref_rows[0] if ref_rows else {}

    if target_row_count != len(target_rows) or target_row_count != 259:
        issues.append("len64_promoted_zero_source_target_count_mismatch")
    if joined_rows != len(joined_targets) or joined_rows != 239:
        issues.append("len64_promoted_zero_source_joined_count_mismatch")
    if missing_rows != len(missing_targets) or missing_rows != 20:
        issues.append("len64_promoted_zero_source_missing_count_mismatch")
    if target_bytes != target_total_bytes or target_bytes != 4971:
        issues.append("len64_promoted_zero_source_target_bytes_mismatch")
    if joined_bytes != joined_total_bytes or joined_bytes != 4950:
        issues.append("len64_promoted_zero_source_joined_bytes_mismatch")
    if missing_bytes != missing_total_bytes or missing_bytes != 21:
        issues.append("len64_promoted_zero_source_missing_bytes_mismatch")
    if joined_bytes + missing_bytes != target_bytes:
        issues.append("len64_promoted_zero_source_bytes_not_partitioned")
    if length_u8_hit_rows != 22:
        issues.append("len64_promoted_zero_source_length_u8_hits_mismatch")
    if length_u16le_hit_rows != 4:
        issues.append("len64_promoted_zero_source_length_u16_hits_mismatch")
    if source_delta_u8_hit_rows != 0:
        issues.append("len64_promoted_zero_source_delta_hits_mismatch")
    if control_ref_rows != 194:
        issues.append("len64_promoted_zero_source_control_ref_rows_mismatch")
    if unique_control_refs != 74 or len(ref_rows) != 75:
        issues.append("len64_promoted_zero_source_ref_count_mismatch")
    if unique_control_windows != len(control_rows) or unique_control_windows != 80:
        issues.append("len64_promoted_zero_source_window_count_mismatch")
    if top_control_window_rows != 45 or top_control_window_bytes != 888:
        issues.append("len64_promoted_zero_source_top_window_summary_mismatch")
    if top_control_ref_offset != "missing" or top_control_ref_rows != 45:
        issues.append("len64_promoted_zero_source_top_ref_summary_mismatch")
    if control_total_rows != joined_rows or control_total_bytes != joined_bytes:
        issues.append("len64_promoted_zero_source_control_totals_mismatch")
    if ref_total_rows != joined_rows or ref_total_bytes != joined_bytes:
        issues.append("len64_promoted_zero_source_ref_totals_mismatch")
    if top_control.get("control_window_signature") != "missing":
        issues.append("len64_promoted_zero_source_top_window_mismatch")
    if int_value(top_control, "rows") != 45 or int_value(top_control, "bytes") != 888:
        issues.append("len64_promoted_zero_source_top_window_value_mismatch")
    if top_ref.get("control_ref_offset") != "missing":
        issues.append("len64_promoted_zero_source_top_ref_mismatch")
    if int_value(top_ref, "rows") != 45 or int_value(top_ref, "bytes") != 888:
        issues.append("len64_promoted_zero_source_top_ref_value_mismatch")
    if any(row.get("issues") != "missing_operation" for row in missing_targets):
        issues.append("len64_promoted_zero_source_unexpected_missing_issue")
    if any(row.get("op_kind") != "zero" for row in joined_targets):
        issues.append("len64_promoted_zero_source_unexpected_join_kind")
    if issue_rows != len(missing_targets) or issue_rows != 20:
        issues.append("len64_promoted_zero_source_issue_count_mismatch")
    if "const TEX_GAP_DECODER_LEN64_PROMOTED_ZERO_SOURCE_PROBE = " not in text:
        issues.append("missing_tex_gap_decoder_len64_promoted_zero_source_probe_json")

    ok = not issues
    return (
        gate(
            gate_name,
            ok,
            expected=".tex len64 promoted zero queue is joined to source operations",
            actual=(
                f"joined={joined_rows}/{target_row_count}, bytes={joined_bytes}/{target_bytes}, "
                f"refs={unique_control_refs}, windows={unique_control_windows}, missing={missing_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        joined_rows if ok else 0,
        joined_bytes if ok else 0,
        unique_control_refs if ok else 0,
    )


def audit_tex_gap_decoder_len64_promoted_large32_zero_source_probe(
    summary: Path,
    target_rows_path: Path,
    control_rows_path: Path,
    ref_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    gate_name = "tex_gap_decoder_len64_promoted_large32_zero_source_probe"
    if not summary.exists():
        return missing_gate(gate_name, summary), 0, 0, 0
    if not target_rows_path.exists():
        return missing_gate(gate_name, target_rows_path), 0, 0, 0
    if not control_rows_path.exists():
        return missing_gate(gate_name, control_rows_path), 0, 0, 0
    if not ref_rows_path.exists():
        return missing_gate(gate_name, ref_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate(gate_name, html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    target_rows = read_csv(target_rows_path)
    control_rows = read_csv(control_rows_path)
    ref_rows = read_csv(ref_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    target_row_count = int_value(total, "target_rows")
    joined_rows = int_value(total, "joined_rows")
    target_bytes = int_value(total, "target_bytes")
    joined_bytes = int_value(total, "joined_bytes")
    missing_rows = int_value(total, "missing_rows")
    missing_bytes = int_value(total, "missing_bytes")
    length_u8_hit_rows = int_value(total, "length_u8_hit_rows")
    length_u16le_hit_rows = int_value(total, "length_u16le_hit_rows")
    source_delta_u8_hit_rows = int_value(total, "source_delta_u8_hit_rows")
    control_ref_rows = int_value(total, "control_ref_rows")
    unique_control_refs = int_value(total, "unique_control_refs")
    unique_control_windows = int_value(total, "unique_control_windows")
    top_control_window_rows = int_value(total, "top_control_window_rows")
    top_control_window_bytes = int_value(total, "top_control_window_bytes")
    top_control_ref_offset = total.get("top_control_ref_offset", "")
    top_control_ref_rows = int_value(total, "top_control_ref_rows")
    issue_rows = int_value(total, "issue_rows")

    joined_targets = [row for row in target_rows if not row.get("issues")]
    missing_targets = [row for row in target_rows if row.get("issues")]
    target_total_bytes = sum(int_value(row, "length") for row in target_rows)
    joined_total_bytes = sum(int_value(row, "length") for row in joined_targets)
    missing_total_bytes = sum(int_value(row, "length") for row in missing_targets)
    control_total_rows = sum(int_value(row, "rows") for row in control_rows)
    control_total_bytes = sum(int_value(row, "bytes") for row in control_rows)
    ref_total_rows = sum(int_value(row, "rows") for row in ref_rows)
    ref_total_bytes = sum(int_value(row, "bytes") for row in ref_rows)
    top_control = control_rows[0] if control_rows else {}
    top_ref = ref_rows[0] if ref_rows else {}

    if target_row_count != len(target_rows) or target_row_count != 234:
        issues.append("large32_promoted_zero_source_target_count_mismatch")
    if joined_rows != len(joined_targets) or joined_rows != 214:
        issues.append("large32_promoted_zero_source_joined_count_mismatch")
    if missing_rows != len(missing_targets) or missing_rows != 20:
        issues.append("large32_promoted_zero_source_missing_count_mismatch")
    if target_bytes != target_total_bytes or target_bytes != 3935:
        issues.append("large32_promoted_zero_source_target_bytes_mismatch")
    if joined_bytes != joined_total_bytes or joined_bytes != 3914:
        issues.append("large32_promoted_zero_source_joined_bytes_mismatch")
    if missing_bytes != missing_total_bytes or missing_bytes != 21:
        issues.append("large32_promoted_zero_source_missing_bytes_mismatch")
    if joined_bytes + missing_bytes != target_bytes:
        issues.append("large32_promoted_zero_source_bytes_not_partitioned")
    if length_u8_hit_rows != 19:
        issues.append("large32_promoted_zero_source_length_u8_hits_mismatch")
    if length_u16le_hit_rows != 4:
        issues.append("large32_promoted_zero_source_length_u16_hits_mismatch")
    if source_delta_u8_hit_rows != 0:
        issues.append("large32_promoted_zero_source_delta_hits_mismatch")
    if control_ref_rows != 175:
        issues.append("large32_promoted_zero_source_control_ref_rows_mismatch")
    if unique_control_refs != 71 or len(ref_rows) != 72:
        issues.append("large32_promoted_zero_source_ref_count_mismatch")
    if unique_control_windows != len(control_rows) or unique_control_windows != 77:
        issues.append("large32_promoted_zero_source_window_count_mismatch")
    if top_control_window_rows != 39 or top_control_window_bytes != 657:
        issues.append("large32_promoted_zero_source_top_window_summary_mismatch")
    if top_control_ref_offset != "missing" or top_control_ref_rows != 39:
        issues.append("large32_promoted_zero_source_top_ref_summary_mismatch")
    if control_total_rows != joined_rows or control_total_bytes != joined_bytes:
        issues.append("large32_promoted_zero_source_control_totals_mismatch")
    if ref_total_rows != joined_rows or ref_total_bytes != joined_bytes:
        issues.append("large32_promoted_zero_source_ref_totals_mismatch")
    if top_control.get("control_window_signature") != "missing":
        issues.append("large32_promoted_zero_source_top_window_mismatch")
    if int_value(top_control, "rows") != 39 or int_value(top_control, "bytes") != 657:
        issues.append("large32_promoted_zero_source_top_window_value_mismatch")
    if top_ref.get("control_ref_offset") != "missing":
        issues.append("large32_promoted_zero_source_top_ref_mismatch")
    if int_value(top_ref, "rows") != 39 or int_value(top_ref, "bytes") != 657:
        issues.append("large32_promoted_zero_source_top_ref_value_mismatch")
    if any(row.get("issues") != "missing_operation" for row in missing_targets):
        issues.append("large32_promoted_zero_source_unexpected_missing_issue")
    if any(row.get("op_kind") != "zero" for row in joined_targets):
        issues.append("large32_promoted_zero_source_unexpected_join_kind")
    if issue_rows != len(missing_targets) or issue_rows != 20:
        issues.append("large32_promoted_zero_source_issue_count_mismatch")
    if "const TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_ZERO_SOURCE_PROBE = " not in text:
        issues.append("missing_tex_gap_decoder_len64_promoted_large32_zero_source_probe_json")

    ok = not issues
    return (
        gate(
            gate_name,
            ok,
            expected=".tex large32 promoted zero queue is joined to source operations",
            actual=(
                f"joined={joined_rows}/{target_row_count}, bytes={joined_bytes}/{target_bytes}, "
                f"refs={unique_control_refs}, windows={unique_control_windows}, missing={missing_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        joined_rows if ok else 0,
        joined_bytes if ok else 0,
        unique_control_refs if ok else 0,
    )


def audit_tex_gap_decoder_len64_promoted_medium8_zero_source_probe(
    summary: Path,
    target_rows_path: Path,
    control_rows_path: Path,
    ref_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    gate_name = "tex_gap_decoder_len64_promoted_medium8_zero_source_probe"
    if not summary.exists():
        return missing_gate(gate_name, summary), 0, 0, 0
    if not target_rows_path.exists():
        return missing_gate(gate_name, target_rows_path), 0, 0, 0
    if not control_rows_path.exists():
        return missing_gate(gate_name, control_rows_path), 0, 0, 0
    if not ref_rows_path.exists():
        return missing_gate(gate_name, ref_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate(gate_name, html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    target_rows = read_csv(target_rows_path)
    control_rows = read_csv(control_rows_path)
    ref_rows = read_csv(ref_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    target_row_count = int_value(total, "target_rows")
    joined_rows = int_value(total, "joined_rows")
    target_bytes = int_value(total, "target_bytes")
    joined_bytes = int_value(total, "joined_bytes")
    missing_rows = int_value(total, "missing_rows")
    missing_bytes = int_value(total, "missing_bytes")
    length_u8_hit_rows = int_value(total, "length_u8_hit_rows")
    length_u16le_hit_rows = int_value(total, "length_u16le_hit_rows")
    source_delta_u8_hit_rows = int_value(total, "source_delta_u8_hit_rows")
    control_ref_rows = int_value(total, "control_ref_rows")
    unique_control_refs = int_value(total, "unique_control_refs")
    unique_control_windows = int_value(total, "unique_control_windows")
    top_control_window_rows = int_value(total, "top_control_window_rows")
    top_control_window_bytes = int_value(total, "top_control_window_bytes")
    top_control_ref_offset = total.get("top_control_ref_offset", "")
    top_control_ref_rows = int_value(total, "top_control_ref_rows")
    issue_rows = int_value(total, "issue_rows")

    joined_targets = [row for row in target_rows if not row.get("issues")]
    missing_targets = [row for row in target_rows if row.get("issues")]
    target_total_bytes = sum(int_value(row, "length") for row in target_rows)
    joined_total_bytes = sum(int_value(row, "length") for row in joined_targets)
    missing_total_bytes = sum(int_value(row, "length") for row in missing_targets)
    control_total_rows = sum(int_value(row, "rows") for row in control_rows)
    control_total_bytes = sum(int_value(row, "bytes") for row in control_rows)
    ref_total_rows = sum(int_value(row, "rows") for row in ref_rows)
    ref_total_bytes = sum(int_value(row, "bytes") for row in ref_rows)
    top_control = control_rows[0] if control_rows else {}
    top_ref = ref_rows[0] if ref_rows else {}

    if target_row_count != len(target_rows) or target_row_count != 226:
        issues.append("medium8_promoted_zero_source_target_count_mismatch")
    if joined_rows != len(joined_targets) or joined_rows != 206:
        issues.append("medium8_promoted_zero_source_joined_count_mismatch")
    if missing_rows != len(missing_targets) or missing_rows != 20:
        issues.append("medium8_promoted_zero_source_missing_count_mismatch")
    if target_bytes != target_total_bytes or target_bytes != 3817:
        issues.append("medium8_promoted_zero_source_target_bytes_mismatch")
    if joined_bytes != joined_total_bytes or joined_bytes != 3796:
        issues.append("medium8_promoted_zero_source_joined_bytes_mismatch")
    if missing_bytes != missing_total_bytes or missing_bytes != 21:
        issues.append("medium8_promoted_zero_source_missing_bytes_mismatch")
    if joined_bytes + missing_bytes != target_bytes:
        issues.append("medium8_promoted_zero_source_bytes_not_partitioned")
    if length_u8_hit_rows != 17:
        issues.append("medium8_promoted_zero_source_length_u8_hits_mismatch")
    if length_u16le_hit_rows != 3:
        issues.append("medium8_promoted_zero_source_length_u16_hits_mismatch")
    if source_delta_u8_hit_rows != 0:
        issues.append("medium8_promoted_zero_source_delta_hits_mismatch")
    if control_ref_rows != 167:
        issues.append("medium8_promoted_zero_source_control_ref_rows_mismatch")
    if unique_control_refs != 69 or len(ref_rows) != 70:
        issues.append("medium8_promoted_zero_source_ref_count_mismatch")
    if unique_control_windows != len(control_rows) or unique_control_windows != 75:
        issues.append("medium8_promoted_zero_source_window_count_mismatch")
    if top_control_window_rows != 39 or top_control_window_bytes != 657:
        issues.append("medium8_promoted_zero_source_top_window_summary_mismatch")
    if top_control_ref_offset != "missing" or top_control_ref_rows != 39:
        issues.append("medium8_promoted_zero_source_top_ref_summary_mismatch")
    if control_total_rows != joined_rows or control_total_bytes != joined_bytes:
        issues.append("medium8_promoted_zero_source_control_totals_mismatch")
    if ref_total_rows != joined_rows or ref_total_bytes != joined_bytes:
        issues.append("medium8_promoted_zero_source_ref_totals_mismatch")
    if top_control.get("control_window_signature") != "missing":
        issues.append("medium8_promoted_zero_source_top_window_mismatch")
    if int_value(top_control, "rows") != 39 or int_value(top_control, "bytes") != 657:
        issues.append("medium8_promoted_zero_source_top_window_value_mismatch")
    if top_ref.get("control_ref_offset") != "missing":
        issues.append("medium8_promoted_zero_source_top_ref_mismatch")
    if int_value(top_ref, "rows") != 39 or int_value(top_ref, "bytes") != 657:
        issues.append("medium8_promoted_zero_source_top_ref_value_mismatch")
    if any(row.get("issues") != "missing_operation" for row in missing_targets):
        issues.append("medium8_promoted_zero_source_unexpected_missing_issue")
    if any(row.get("op_kind") != "zero" for row in joined_targets):
        issues.append("medium8_promoted_zero_source_unexpected_join_kind")
    if issue_rows != len(missing_targets) or issue_rows != 20:
        issues.append("medium8_promoted_zero_source_issue_count_mismatch")
    if "const TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_ZERO_SOURCE_PROBE = " not in text:
        issues.append("missing_tex_gap_decoder_len64_promoted_medium8_zero_source_probe_json")

    ok = not issues
    return (
        gate(
            gate_name,
            ok,
            expected=".tex medium8 promoted zero queue is joined to source operations",
            actual=(
                f"joined={joined_rows}/{target_row_count}, bytes={joined_bytes}/{target_bytes}, "
                f"refs={unique_control_refs}, windows={unique_control_windows}, missing={missing_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        joined_rows if ok else 0,
        joined_bytes if ok else 0,
        unique_control_refs if ok else 0,
    )


def audit_tex_gap_decoder_len64_promoted_large32_selector_probe(
    summary: Path,
    candidate_rows_path: Path,
    greedy_rows_path: Path,
    target_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    gate_name = "tex_gap_decoder_len64_promoted_large32_selector_probe"
    if not summary.exists():
        return missing_gate(gate_name, summary), 0, 0, 0
    if not candidate_rows_path.exists():
        return missing_gate(gate_name, candidate_rows_path), 0, 0, 0
    if not greedy_rows_path.exists():
        return missing_gate(gate_name, greedy_rows_path), 0, 0, 0
    if not target_rows_path.exists():
        return missing_gate(gate_name, target_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate(gate_name, html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    candidate_rows = read_csv(candidate_rows_path)
    greedy_rows = read_csv(greedy_rows_path)
    target_rows = read_csv(target_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    target_signature = total.get("target_signature", "")
    operation_rows = int_value(total, "operation_rows")
    source_target_rows = int_value(total, "source_target_rows")
    target_count = int_value(total, "target_rows")
    target_bytes = int_value(total, "target_bytes")
    joined_target_rows = int_value(total, "joined_target_rows")
    large32_operation_rows = int_value(total, "large32_operation_rows")
    large32_zero_rows = int_value(total, "large32_zero_rows")
    large32_false_rows = int_value(total, "large32_false_rows")
    candidate_count = int_value(total, "candidate_rows")
    false_free_count = int_value(total, "false_free_candidate_rows")
    best_selector = total.get("best_selector", "")
    best_family = total.get("best_selector_family", "")
    best_target_rows = int_value(total, "best_selector_target_rows")
    best_target_bytes = int_value(total, "best_selector_target_bytes")
    best_operation_rows = int_value(total, "best_selector_operation_rows")
    best_zero_bytes = int_value(total, "best_selector_zero_bytes")
    best_false_bytes = int_value(total, "best_selector_false_bytes")
    greedy_min_rows = int_value(total, "greedy_min_target_rows")
    greedy_selector_rows = int_value(total, "greedy_selector_rows")
    greedy_target_rows = int_value(total, "greedy_target_rows")
    greedy_target_bytes = int_value(total, "greedy_target_bytes")
    greedy_operation_rows = int_value(total, "greedy_operation_rows")
    greedy_zero_bytes = int_value(total, "greedy_zero_bytes")
    greedy_false_bytes = int_value(total, "greedy_false_bytes")
    issue_rows = int_value(total, "issue_rows")

    false_free_rows = [
        row
        for row in candidate_rows
        if row.get("promotion_class") in {"source_false_free", "target_only_false_free"}
    ]
    top_candidate = candidate_rows[0] if candidate_rows else {}
    greedy_covered = [row for row in target_rows if row.get("greedy_selector")]
    best_hits = [row for row in target_rows if row.get("best_selector_hit") == "1"]
    greedy_target_sum = sum(int_value(row, "length") for row in greedy_covered)
    best_target_sum = sum(int_value(row, "length") for row in best_hits)

    if target_signature != "internal|large32|left_nonzero|right_nonzero":
        issues.append("len64_promoted_large32_selector_signature_mismatch")
    if operation_rows != 984 or source_target_rows != 259:
        issues.append("len64_promoted_large32_selector_input_count_mismatch")
    if target_count != len(target_rows) or target_count != 35:
        issues.append("len64_promoted_large32_selector_target_count_mismatch")
    if target_bytes != sum(int_value(row, "length") for row in target_rows) or target_bytes != 1451:
        issues.append("len64_promoted_large32_selector_target_bytes_mismatch")
    if joined_target_rows != target_count:
        issues.append("len64_promoted_large32_selector_joined_count_mismatch")
    if large32_operation_rows != 130 or large32_zero_rows != 57 or large32_false_rows != 73:
        issues.append("len64_promoted_large32_selector_large32_partition_mismatch")
    if candidate_count != len(candidate_rows) or candidate_count != 1759:
        issues.append("len64_promoted_large32_selector_candidate_count_mismatch")
    if false_free_count != len(false_free_rows) or false_free_count != 463:
        issues.append("len64_promoted_large32_selector_false_free_count_mismatch")
    if best_selector != "bucket=large32&cw_b13=b6" or best_family != "large32_pair":
        issues.append("len64_promoted_large32_selector_best_selector_mismatch")
    if top_candidate.get("selector") != best_selector:
        issues.append("len64_promoted_large32_selector_top_candidate_mismatch")
    if best_target_rows != 6 or len(best_hits) != 6:
        issues.append("len64_promoted_large32_selector_best_row_mismatch")
    if best_target_bytes != 291 or best_target_sum != 291:
        issues.append("len64_promoted_large32_selector_best_byte_mismatch")
    if best_operation_rows != 8 or best_zero_bytes != 359 or best_false_bytes != 0:
        issues.append("len64_promoted_large32_selector_best_operation_mismatch")
    if greedy_min_rows != 2:
        issues.append("len64_promoted_large32_selector_greedy_min_mismatch")
    if greedy_selector_rows != len(greedy_rows) or greedy_selector_rows != 9:
        issues.append("len64_promoted_large32_selector_greedy_count_mismatch")
    if greedy_target_rows != len(greedy_covered) or greedy_target_rows != 25:
        issues.append("len64_promoted_large32_selector_greedy_target_mismatch")
    if greedy_target_bytes != greedy_target_sum or greedy_target_bytes != 1036:
        issues.append("len64_promoted_large32_selector_greedy_byte_mismatch")
    if greedy_operation_rows != 33 or greedy_zero_bytes != 1345 or greedy_false_bytes != 0:
        issues.append("len64_promoted_large32_selector_greedy_operation_mismatch")
    if any(int_value(row, "false_bytes") for row in greedy_rows):
        issues.append("len64_promoted_large32_selector_greedy_false_rows")
    if any(row.get("signature") != target_signature for row in target_rows):
        issues.append("len64_promoted_large32_selector_target_signature_mismatch")
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    if "const TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_SELECTOR_PROBE = " not in text:
        issues.append("missing_tex_gap_decoder_len64_promoted_large32_selector_probe_json")

    ok = not issues
    return (
        gate(
            gate_name,
            ok,
            expected=".tex promoted large32 internal zero targets have false-free selectors",
            actual=(
                f"targets={target_count}, best={best_target_bytes}, "
                f"greedy={greedy_target_bytes}/{target_bytes}, selectors={greedy_selector_rows}, false=0"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        best_target_bytes if ok else 0,
        greedy_target_bytes if ok else 0,
        greedy_selector_rows if ok else 0,
    )


def audit_tex_gap_decoder_len64_promoted_medium8_selector_probe(
    summary: Path,
    candidate_rows_path: Path,
    greedy_rows_path: Path,
    target_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    gate_name = "tex_gap_decoder_len64_promoted_medium8_selector_probe"
    if not summary.exists():
        return missing_gate(gate_name, summary), 0, 0, 0
    if not candidate_rows_path.exists():
        return missing_gate(gate_name, candidate_rows_path), 0, 0, 0
    if not greedy_rows_path.exists():
        return missing_gate(gate_name, greedy_rows_path), 0, 0, 0
    if not target_rows_path.exists():
        return missing_gate(gate_name, target_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate(gate_name, html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    candidate_rows = read_csv(candidate_rows_path)
    greedy_rows = read_csv(greedy_rows_path)
    target_rows = read_csv(target_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    target_signature = total.get("target_signature", "")
    target_bucket = total.get("target_bucket", "")
    operation_rows = int_value(total, "operation_rows")
    source_target_rows = int_value(total, "source_target_rows")
    target_count = int_value(total, "target_rows")
    target_bytes = int_value(total, "target_bytes")
    joined_target_rows = int_value(total, "joined_target_rows")
    bucket_operation_rows = int_value(total, "bucket_operation_rows")
    bucket_zero_rows = int_value(total, "bucket_zero_rows")
    bucket_false_rows = int_value(total, "bucket_false_rows")
    candidate_count = int_value(total, "candidate_rows")
    false_free_count = int_value(total, "false_free_candidate_rows")
    best_selector = total.get("best_selector", "")
    best_family = total.get("best_selector_family", "")
    best_target_rows = int_value(total, "best_selector_target_rows")
    best_target_bytes = int_value(total, "best_selector_target_bytes")
    best_operation_rows = int_value(total, "best_selector_operation_rows")
    best_zero_bytes = int_value(total, "best_selector_zero_bytes")
    best_false_bytes = int_value(total, "best_selector_false_bytes")
    greedy_min_rows = int_value(total, "greedy_min_target_rows")
    greedy_selector_rows = int_value(total, "greedy_selector_rows")
    greedy_target_rows = int_value(total, "greedy_target_rows")
    greedy_target_bytes = int_value(total, "greedy_target_bytes")
    greedy_operation_rows = int_value(total, "greedy_operation_rows")
    greedy_zero_bytes = int_value(total, "greedy_zero_bytes")
    greedy_false_bytes = int_value(total, "greedy_false_bytes")
    issue_rows = int_value(total, "issue_rows")

    false_free_rows = [
        row
        for row in candidate_rows
        if row.get("promotion_class") in {"source_false_free", "target_only_false_free"}
    ]
    top_candidate = candidate_rows[0] if candidate_rows else {}
    greedy_covered = [row for row in target_rows if row.get("greedy_selector")]
    best_hits = [row for row in target_rows if row.get("best_selector_hit") == "1"]
    greedy_target_sum = sum(int_value(row, "length") for row in greedy_covered)
    best_target_sum = sum(int_value(row, "length") for row in best_hits)

    if target_signature != "internal|medium8|left_nonzero|right_nonzero":
        issues.append("len64_promoted_medium8_selector_signature_mismatch")
    if target_bucket != "medium8":
        issues.append("len64_promoted_medium8_selector_bucket_mismatch")
    if operation_rows != 984 or source_target_rows != 234:
        issues.append("len64_promoted_medium8_selector_input_count_mismatch")
    if target_count != len(target_rows) or target_count != 83:
        issues.append("len64_promoted_medium8_selector_target_count_mismatch")
    if target_bytes != sum(int_value(row, "length") for row in target_rows) or target_bytes != 1421:
        issues.append("len64_promoted_medium8_selector_target_bytes_mismatch")
    if joined_target_rows != target_count:
        issues.append("len64_promoted_medium8_selector_joined_count_mismatch")
    if bucket_operation_rows != 328 or bucket_zero_rows != 102 or bucket_false_rows != 226:
        issues.append("len64_promoted_medium8_selector_bucket_partition_mismatch")
    if candidate_count != len(candidate_rows) or candidate_count != 3907:
        issues.append("len64_promoted_medium8_selector_candidate_count_mismatch")
    if false_free_count != len(false_free_rows) or false_free_count != 173:
        issues.append("len64_promoted_medium8_selector_false_free_count_mismatch")
    if best_selector != "bucket=medium8&cw_b13=e7" or best_family != "medium8_pair":
        issues.append("len64_promoted_medium8_selector_best_selector_mismatch")
    if top_candidate.get("selector") != best_selector:
        issues.append("len64_promoted_medium8_selector_top_candidate_mismatch")
    if best_target_rows != 6 or len(best_hits) != 6:
        issues.append("len64_promoted_medium8_selector_best_row_mismatch")
    if best_target_bytes != 91 or best_target_sum != 91:
        issues.append("len64_promoted_medium8_selector_best_byte_mismatch")
    if best_operation_rows != 7 or best_zero_bytes != 109 or best_false_bytes != 0:
        issues.append("len64_promoted_medium8_selector_best_operation_mismatch")
    if greedy_min_rows != 2:
        issues.append("len64_promoted_medium8_selector_greedy_min_mismatch")
    if greedy_selector_rows != len(greedy_rows) or greedy_selector_rows != 3:
        issues.append("len64_promoted_medium8_selector_greedy_count_mismatch")
    if greedy_target_rows != len(greedy_covered) or greedy_target_rows != 8:
        issues.append("len64_promoted_medium8_selector_greedy_target_mismatch")
    if greedy_target_bytes != greedy_target_sum or greedy_target_bytes != 118:
        issues.append("len64_promoted_medium8_selector_greedy_byte_mismatch")
    if greedy_operation_rows != 9 or greedy_zero_bytes != 136 or greedy_false_bytes != 0:
        issues.append("len64_promoted_medium8_selector_greedy_operation_mismatch")
    if any(int_value(row, "false_bytes") for row in greedy_rows):
        issues.append("len64_promoted_medium8_selector_greedy_false_rows")
    if any(row.get("signature") != target_signature for row in target_rows):
        issues.append("len64_promoted_medium8_selector_target_signature_mismatch")
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    if "const TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_SELECTOR_PROBE = " not in text:
        issues.append("missing_tex_gap_decoder_len64_promoted_medium8_selector_probe_json")

    ok = not issues
    return (
        gate(
            gate_name,
            ok,
            expected=".tex post-large32 medium8 internal zero targets have false-free selectors",
            actual=(
                f"targets={target_count}, best={best_target_bytes}, "
                f"greedy={greedy_target_bytes}/{target_bytes}, selectors={greedy_selector_rows}, false=0"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        best_target_bytes if ok else 0,
        greedy_target_bytes if ok else 0,
        greedy_selector_rows if ok else 0,
    )


def audit_tex_gap_decoder_len64_promoted_medium8_remaining_selector_probe(
    summary: Path,
    candidate_rows_path: Path,
    greedy_rows_path: Path,
    target_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    gate_name = "tex_gap_decoder_len64_promoted_medium8_remaining_selector_probe"
    if not summary.exists():
        return missing_gate(gate_name, summary), 0, 0, 0
    if not candidate_rows_path.exists():
        return missing_gate(gate_name, candidate_rows_path), 0, 0, 0
    if not greedy_rows_path.exists():
        return missing_gate(gate_name, greedy_rows_path), 0, 0, 0
    if not target_rows_path.exists():
        return missing_gate(gate_name, target_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate(gate_name, html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    candidate_rows = read_csv(candidate_rows_path)
    greedy_rows = read_csv(greedy_rows_path)
    target_rows = read_csv(target_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    target_signature = total.get("target_signature", "")
    target_bucket = total.get("target_bucket", "")
    operation_rows = int_value(total, "operation_rows")
    source_target_rows = int_value(total, "source_target_rows")
    target_count = int_value(total, "target_rows")
    target_bytes = int_value(total, "target_bytes")
    joined_target_rows = int_value(total, "joined_target_rows")
    bucket_operation_rows = int_value(total, "bucket_operation_rows")
    bucket_zero_rows = int_value(total, "bucket_zero_rows")
    bucket_false_rows = int_value(total, "bucket_false_rows")
    candidate_count = int_value(total, "candidate_rows")
    false_free_count = int_value(total, "false_free_candidate_rows")
    best_selector = total.get("best_selector", "")
    best_family = total.get("best_selector_family", "")
    best_target_rows = int_value(total, "best_selector_target_rows")
    best_target_bytes = int_value(total, "best_selector_target_bytes")
    best_operation_rows = int_value(total, "best_selector_operation_rows")
    best_zero_bytes = int_value(total, "best_selector_zero_bytes")
    best_false_bytes = int_value(total, "best_selector_false_bytes")
    greedy_min_rows = int_value(total, "greedy_min_target_rows")
    greedy_selector_rows = int_value(total, "greedy_selector_rows")
    greedy_target_rows = int_value(total, "greedy_target_rows")
    greedy_target_bytes = int_value(total, "greedy_target_bytes")
    greedy_operation_rows = int_value(total, "greedy_operation_rows")
    greedy_zero_bytes = int_value(total, "greedy_zero_bytes")
    greedy_false_bytes = int_value(total, "greedy_false_bytes")
    issue_rows = int_value(total, "issue_rows")

    false_free_rows = [
        row
        for row in candidate_rows
        if row.get("promotion_class") in {"source_false_free", "target_only_false_free"}
    ]
    top_candidate = candidate_rows[0] if candidate_rows else {}
    greedy_covered = [row for row in target_rows if row.get("greedy_selector")]
    best_hits = [row for row in target_rows if row.get("best_selector_hit") == "1"]
    greedy_target_sum = sum(int_value(row, "length") for row in greedy_covered)
    best_target_sum = sum(int_value(row, "length") for row in best_hits)

    if target_signature != "internal|medium8|left_nonzero|right_nonzero":
        issues.append("medium8_remaining_selector_signature_mismatch")
    if target_bucket != "medium8":
        issues.append("medium8_remaining_selector_bucket_mismatch")
    if operation_rows != 984 or source_target_rows != 226:
        issues.append("medium8_remaining_selector_input_count_mismatch")
    if target_count != len(target_rows) or target_count != 75:
        issues.append("medium8_remaining_selector_target_count_mismatch")
    if target_bytes != sum(int_value(row, "length") for row in target_rows) or target_bytes != 1303:
        issues.append("medium8_remaining_selector_target_bytes_mismatch")
    if joined_target_rows != target_count:
        issues.append("medium8_remaining_selector_joined_count_mismatch")
    if bucket_operation_rows != 328 or bucket_zero_rows != 102 or bucket_false_rows != 226:
        issues.append("medium8_remaining_selector_bucket_partition_mismatch")
    if candidate_count != len(candidate_rows) or candidate_count != 3521:
        issues.append("medium8_remaining_selector_candidate_count_mismatch")
    if false_free_count != len(false_free_rows) or false_free_count != 4:
        issues.append("medium8_remaining_selector_false_free_count_mismatch")
    if best_selector != "length_u8_hit_offsets=4121" or best_family != "single":
        issues.append("medium8_remaining_selector_best_selector_mismatch")
    if top_candidate.get("selector") != best_selector:
        issues.append("medium8_remaining_selector_top_candidate_mismatch")
    if best_target_rows != 1 or len(best_hits) != 1:
        issues.append("medium8_remaining_selector_best_row_mismatch")
    if best_target_bytes != 23 or best_target_sum != 23:
        issues.append("medium8_remaining_selector_best_byte_mismatch")
    if best_operation_rows != 1 or best_zero_bytes != 23 or best_false_bytes != 0:
        issues.append("medium8_remaining_selector_best_operation_mismatch")
    if greedy_min_rows != 2:
        issues.append("medium8_remaining_selector_greedy_min_mismatch")
    if greedy_selector_rows != len(greedy_rows) or greedy_selector_rows != 0:
        issues.append("medium8_remaining_selector_greedy_count_mismatch")
    if greedy_target_rows != len(greedy_covered) or greedy_target_rows != 0:
        issues.append("medium8_remaining_selector_greedy_target_mismatch")
    if greedy_target_bytes != greedy_target_sum or greedy_target_bytes != 0:
        issues.append("medium8_remaining_selector_greedy_byte_mismatch")
    if greedy_operation_rows or greedy_zero_bytes or greedy_false_bytes:
        issues.append("medium8_remaining_selector_greedy_operation_mismatch")
    if any(row.get("signature") != target_signature for row in target_rows):
        issues.append("medium8_remaining_selector_target_signature_mismatch")
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    if "const TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_REMAINING_SELECTOR_PROBE = " not in text:
        issues.append("missing_tex_gap_decoder_len64_promoted_medium8_remaining_selector_probe_json")

    ok = not issues
    return (
        gate(
            gate_name,
            ok,
            expected=".tex post-medium8 remaining targets have no grouped false-free selector",
            actual=(
                f"targets={target_count}, best={best_target_bytes}, "
                f"greedy={greedy_target_bytes}/{target_bytes}, selectors={greedy_selector_rows}, false=0"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        best_target_bytes if ok else 0,
        greedy_target_bytes if ok else 0,
        greedy_selector_rows if ok else 0,
    )


def audit_tex_gap_decoder_len64_promoted_large32_remaining_selector_probe(
    summary: Path,
    candidate_rows_path: Path,
    greedy_rows_path: Path,
    target_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    gate_name = "tex_gap_decoder_len64_promoted_large32_remaining_selector_probe"
    if not summary.exists():
        return missing_gate(gate_name, summary), 0, 0, 0
    if not candidate_rows_path.exists():
        return missing_gate(gate_name, candidate_rows_path), 0, 0, 0
    if not greedy_rows_path.exists():
        return missing_gate(gate_name, greedy_rows_path), 0, 0, 0
    if not target_rows_path.exists():
        return missing_gate(gate_name, target_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate(gate_name, html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    candidate_rows = read_csv(candidate_rows_path)
    greedy_rows = read_csv(greedy_rows_path)
    target_rows = read_csv(target_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    target_signature = total.get("target_signature", "")
    operation_rows = int_value(total, "operation_rows")
    source_target_rows = int_value(total, "source_target_rows")
    target_count = int_value(total, "target_rows")
    target_bytes = int_value(total, "target_bytes")
    joined_target_rows = int_value(total, "joined_target_rows")
    large32_operation_rows = int_value(total, "large32_operation_rows")
    large32_zero_rows = int_value(total, "large32_zero_rows")
    large32_false_rows = int_value(total, "large32_false_rows")
    candidate_count = int_value(total, "candidate_rows")
    false_free_count = int_value(total, "false_free_candidate_rows")
    best_selector = total.get("best_selector", "")
    best_family = total.get("best_selector_family", "")
    best_target_rows = int_value(total, "best_selector_target_rows")
    best_target_bytes = int_value(total, "best_selector_target_bytes")
    best_operation_rows = int_value(total, "best_selector_operation_rows")
    best_zero_bytes = int_value(total, "best_selector_zero_bytes")
    best_false_bytes = int_value(total, "best_selector_false_bytes")
    greedy_min_rows = int_value(total, "greedy_min_target_rows")
    greedy_selector_rows = int_value(total, "greedy_selector_rows")
    greedy_target_rows = int_value(total, "greedy_target_rows")
    greedy_target_bytes = int_value(total, "greedy_target_bytes")
    greedy_operation_rows = int_value(total, "greedy_operation_rows")
    greedy_zero_bytes = int_value(total, "greedy_zero_bytes")
    greedy_false_bytes = int_value(total, "greedy_false_bytes")
    issue_rows = int_value(total, "issue_rows")

    false_free_rows = [
        row
        for row in candidate_rows
        if row.get("promotion_class") in {"source_false_free", "target_only_false_free"}
    ]
    top_candidate = candidate_rows[0] if candidate_rows else {}
    greedy_covered = [row for row in target_rows if row.get("greedy_selector")]
    best_hits = [row for row in target_rows if row.get("best_selector_hit") == "1"]
    greedy_target_sum = sum(int_value(row, "length") for row in greedy_covered)
    best_target_sum = sum(int_value(row, "length") for row in best_hits)

    if target_signature != "internal|large32|left_nonzero|right_nonzero":
        issues.append("large32_remaining_selector_signature_mismatch")
    if operation_rows != 984 or source_target_rows != 226:
        issues.append("large32_remaining_selector_input_count_mismatch")
    if target_count != len(target_rows) or target_count != 10:
        issues.append("large32_remaining_selector_target_count_mismatch")
    if target_bytes != sum(int_value(row, "length") for row in target_rows) or target_bytes != 415:
        issues.append("large32_remaining_selector_target_bytes_mismatch")
    if joined_target_rows != target_count:
        issues.append("large32_remaining_selector_joined_count_mismatch")
    if large32_operation_rows != 130 or large32_zero_rows != 57 or large32_false_rows != 73:
        issues.append("large32_remaining_selector_large32_partition_mismatch")
    if candidate_count != len(candidate_rows) or candidate_count != 591:
        issues.append("large32_remaining_selector_candidate_count_mismatch")
    if false_free_count != len(false_free_rows) or false_free_count != 109:
        issues.append("large32_remaining_selector_false_free_count_mismatch")
    if best_selector != "bucket_mod=large32|19" or best_family != "single":
        issues.append("large32_remaining_selector_best_selector_mismatch")
    if top_candidate.get("selector") != best_selector:
        issues.append("large32_remaining_selector_top_candidate_mismatch")
    if best_target_rows != 1 or len(best_hits) != 1:
        issues.append("large32_remaining_selector_best_row_mismatch")
    if best_target_bytes != 46 or best_target_sum != 46:
        issues.append("large32_remaining_selector_best_byte_mismatch")
    if best_operation_rows != 2 or best_zero_bytes != 103 or best_false_bytes != 0:
        issues.append("large32_remaining_selector_best_operation_mismatch")
    if greedy_min_rows != 2:
        issues.append("large32_remaining_selector_greedy_min_mismatch")
    if greedy_selector_rows != len(greedy_rows) or greedy_selector_rows != 0:
        issues.append("large32_remaining_selector_greedy_count_mismatch")
    if greedy_target_rows != len(greedy_covered) or greedy_target_rows != 0:
        issues.append("large32_remaining_selector_greedy_target_mismatch")
    if greedy_target_bytes != greedy_target_sum or greedy_target_bytes != 0:
        issues.append("large32_remaining_selector_greedy_byte_mismatch")
    if greedy_operation_rows or greedy_zero_bytes or greedy_false_bytes:
        issues.append("large32_remaining_selector_greedy_operation_mismatch")
    if any(row.get("signature") != target_signature for row in target_rows):
        issues.append("large32_remaining_selector_target_signature_mismatch")
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    if "const TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_REMAINING_SELECTOR_PROBE = " not in text:
        issues.append("missing_tex_gap_decoder_len64_promoted_large32_remaining_selector_probe_json")

    ok = not issues
    return (
        gate(
            gate_name,
            ok,
            expected=".tex post-medium8 remaining large32 targets have no grouped false-free selector",
            actual=(
                f"targets={target_count}, best={best_target_bytes}, "
                f"greedy={greedy_target_bytes}/{target_bytes}, selectors={greedy_selector_rows}, false=0"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        best_target_bytes if ok else 0,
        greedy_target_bytes if ok else 0,
        greedy_selector_rows if ok else 0,
    )


def audit_tex_gap_decoder_len64_promoted_large32_replay(
    summary: Path,
    fixture_rows_path: Path,
    promotion_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    gate_name = "tex_gap_decoder_len64_promoted_large32_replay"
    if not summary.exists():
        return missing_gate(gate_name, summary), 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate(gate_name, fixture_rows_path), 0, 0, 0
    if not promotion_rows_path.exists():
        return missing_gate(gate_name, promotion_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate(gate_name, html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    fixture_rows = read_csv(fixture_rows_path)
    promotion_rows = read_csv(promotion_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    target_rows = int_value(total, "target_rows")
    promoted_rows = int_value(total, "promoted_target_rows")
    base_clean = int_value(total, "base_clean_bytes")
    selector_added = int_value(total, "selector_added_bytes")
    selector_exact = int_value(total, "selector_exact_bytes")
    selector_false = int_value(total, "selector_false_bytes")
    total_clean = int_value(total, "total_clean_bytes")
    rejected_false = int_value(total, "rejected_false_bytes")
    remaining_unresolved = int_value(total, "remaining_unresolved_bytes")
    native_previews = int_value(total, "native_previews")
    fullhd_previews = int_value(total, "fullhd_previews")
    issue_rows = int_value(total, "issue_rows")

    fixture_targets = sum(int_value(row, "selector_target_rows") for row in fixture_rows)
    fixture_added = sum(int_value(row, "selector_added_bytes") for row in fixture_rows)
    fixture_exact = sum(int_value(row, "selector_exact_bytes") for row in fixture_rows)
    fixture_false = sum(int_value(row, "selector_false_bytes") for row in fixture_rows)
    fixture_base = sum(int_value(row, "base_clean_bytes") for row in fixture_rows)
    fixture_total_clean = sum(int_value(row, "total_clean_bytes") for row in fixture_rows)
    fixture_rejected = sum(int_value(row, "rejected_false_bytes") for row in fixture_rows)
    fixture_remaining = sum(int_value(row, "remaining_unresolved_bytes") for row in fixture_rows)

    promotion_added = sum(int_value(row, "selector_added_bytes") for row in promotion_rows)
    promotion_exact = sum(int_value(row, "selector_exact_bytes") for row in promotion_rows)
    promotion_false = sum(int_value(row, "selector_false_bytes") for row in promotion_rows)
    promotion_issue_rows = sum(1 for row in promotion_rows if row.get("issues"))
    fixture_issue_rows = sum(1 for row in fixture_rows if row.get("issues"))

    if fixture_count != len(fixture_rows) or fixture_count != 32:
        issues.append("large32_promoted_fixture_count_mismatch")
    if target_rows != len(promotion_rows) or target_rows != fixture_targets or target_rows != 25:
        issues.append("large32_promoted_target_count_mismatch")
    if promoted_rows != sum(1 for row in promotion_rows if int_value(row, "selector_added_bytes")) or promoted_rows != 25:
        issues.append("large32_promoted_target_promoted_count_mismatch")
    if base_clean != fixture_base or base_clean != 4426:
        issues.append("large32_promoted_base_clean_mismatch")
    if selector_added != fixture_added or selector_added != promotion_added or selector_added != 1036:
        issues.append("large32_promoted_added_byte_mismatch")
    if selector_exact != fixture_exact or selector_exact != promotion_exact or selector_exact != 1036:
        issues.append("large32_promoted_exact_byte_mismatch")
    if selector_false != fixture_false or selector_false != promotion_false or selector_false != 0:
        issues.append("large32_promoted_false_byte_mismatch")
    if total_clean != fixture_total_clean or total_clean != 5462:
        issues.append("large32_promoted_total_clean_mismatch")
    if rejected_false != fixture_rejected or rejected_false != 57:
        issues.append("large32_promoted_rejected_false_mismatch")
    if remaining_unresolved != fixture_remaining or remaining_unresolved != 11984:
        issues.append("large32_promoted_remaining_unresolved_mismatch")
    if issue_rows or issue_rows != fixture_issue_rows + promotion_issue_rows:
        issues.append(f"issue_rows:{issue_rows}")

    if any(int_value(row, "length") < 32 or int_value(row, "length") >= 64 for row in promotion_rows):
        issues.append("large32_promoted_non_large32_target")
    if any(row.get("signature") != "internal|large32|left_nonzero|right_nonzero" for row in promotion_rows):
        issues.append("large32_promoted_signature_mismatch")
    if any(not row.get("greedy_selector") for row in promotion_rows):
        issues.append("large32_promoted_missing_selector")
    if any(int_value(row, "base_known_overlap_bytes") for row in promotion_rows):
        issues.append("large32_promoted_base_overlap")
    if any(int_value(row, "rejected_overlap_bytes") for row in promotion_rows):
        issues.append("large32_promoted_rejected_overlap")
    if any(int_value(row, "selector_added_bytes") != int_value(row, "length") for row in promotion_rows):
        issues.append("large32_promoted_added_target_size_mismatch")
    if any(int_value(row, "selector_exact_bytes") != int_value(row, "length") for row in promotion_rows):
        issues.append("large32_promoted_exact_target_size_mismatch")
    if any(int_value(row, "selector_false_bytes") for row in promotion_rows):
        issues.append("large32_promoted_false_target_bytes")

    missing_paths = 0
    wrong_size_paths = 0
    fullhd_preview_rows = 0
    for row in fixture_rows:
        fixture_bytes = int_value(row, "fixture_bytes")
        for field in ("decoded_path", "known_mask_path", "selector_mask_path"):
            value = row.get(field, "")
            if not value or not Path(value).exists():
                missing_paths += 1
                continue
            if Path(value).stat().st_size != fixture_bytes:
                wrong_size_paths += 1
        for field in ("native_preview_path", "fullhd_preview_path"):
            value = row.get(field, "")
            if not value or not Path(value).exists():
                missing_paths += 1
        if (row.get("fullhd_width"), row.get("fullhd_height")) == (
            str(TARGET_SIZE[0]),
            str(TARGET_SIZE[1]),
        ):
            fullhd_preview_rows += 1
    if missing_paths:
        issues.append(f"missing_large32_promoted_paths:{missing_paths}")
    if wrong_size_paths:
        issues.append(f"large32_promoted_path_size_mismatch:{wrong_size_paths}")
    if native_previews != len(fixture_rows) or native_previews != 32:
        issues.append("large32_promoted_native_preview_count_mismatch")
    if fullhd_previews != fullhd_preview_rows or fullhd_previews != 32:
        issues.append("large32_promoted_fullhd_preview_count_mismatch")
    if "const TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_REPLAY = " not in text:
        issues.append("missing_tex_gap_decoder_len64_promoted_large32_replay_json")

    ok = not issues
    return (
        gate(
            gate_name,
            ok,
            expected=".tex large32 selector targets replay cleanly after len64 promotion",
            actual=(
                f"added={selector_added}, total_clean={total_clean}, "
                f"remaining={remaining_unresolved}, false={selector_false}, fullhd={fullhd_previews}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        selector_added if ok else 0,
        total_clean if ok else 0,
        remaining_unresolved if ok else 0,
    )


def audit_tex_gap_decoder_len64_promoted_medium8_replay(
    summary: Path,
    fixture_rows_path: Path,
    promotion_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    gate_name = "tex_gap_decoder_len64_promoted_medium8_replay"
    if not summary.exists():
        return missing_gate(gate_name, summary), 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate(gate_name, fixture_rows_path), 0, 0, 0
    if not promotion_rows_path.exists():
        return missing_gate(gate_name, promotion_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate(gate_name, html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    fixture_rows = read_csv(fixture_rows_path)
    promotion_rows = read_csv(promotion_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    target_rows = int_value(total, "target_rows")
    promoted_rows = int_value(total, "promoted_target_rows")
    base_clean = int_value(total, "base_clean_bytes")
    selector_added = int_value(total, "selector_added_bytes")
    selector_exact = int_value(total, "selector_exact_bytes")
    selector_false = int_value(total, "selector_false_bytes")
    total_clean = int_value(total, "total_clean_bytes")
    rejected_false = int_value(total, "rejected_false_bytes")
    remaining_unresolved = int_value(total, "remaining_unresolved_bytes")
    native_previews = int_value(total, "native_previews")
    fullhd_previews = int_value(total, "fullhd_previews")
    issue_rows = int_value(total, "issue_rows")

    fixture_targets = sum(int_value(row, "selector_target_rows") for row in fixture_rows)
    fixture_added = sum(int_value(row, "selector_added_bytes") for row in fixture_rows)
    fixture_exact = sum(int_value(row, "selector_exact_bytes") for row in fixture_rows)
    fixture_false = sum(int_value(row, "selector_false_bytes") for row in fixture_rows)
    fixture_base = sum(int_value(row, "base_clean_bytes") for row in fixture_rows)
    fixture_total_clean = sum(int_value(row, "total_clean_bytes") for row in fixture_rows)
    fixture_rejected = sum(int_value(row, "rejected_false_bytes") for row in fixture_rows)
    fixture_remaining = sum(int_value(row, "remaining_unresolved_bytes") for row in fixture_rows)

    promotion_added = sum(int_value(row, "selector_added_bytes") for row in promotion_rows)
    promotion_exact = sum(int_value(row, "selector_exact_bytes") for row in promotion_rows)
    promotion_false = sum(int_value(row, "selector_false_bytes") for row in promotion_rows)
    promotion_issue_rows = sum(1 for row in promotion_rows if row.get("issues"))
    fixture_issue_rows = sum(1 for row in fixture_rows if row.get("issues"))

    if fixture_count != len(fixture_rows) or fixture_count != 32:
        issues.append("medium8_promoted_fixture_count_mismatch")
    if target_rows != len(promotion_rows) or target_rows != fixture_targets or target_rows != 8:
        issues.append("medium8_promoted_target_count_mismatch")
    if promoted_rows != sum(1 for row in promotion_rows if int_value(row, "selector_added_bytes")) or promoted_rows != 8:
        issues.append("medium8_promoted_target_promoted_count_mismatch")
    if base_clean != fixture_base or base_clean != 5462:
        issues.append("medium8_promoted_base_clean_mismatch")
    if selector_added != fixture_added or selector_added != promotion_added or selector_added != 118:
        issues.append("medium8_promoted_added_byte_mismatch")
    if selector_exact != fixture_exact or selector_exact != promotion_exact or selector_exact != 118:
        issues.append("medium8_promoted_exact_byte_mismatch")
    if selector_false != fixture_false or selector_false != promotion_false or selector_false != 0:
        issues.append("medium8_promoted_false_byte_mismatch")
    if total_clean != fixture_total_clean or total_clean != 5580:
        issues.append("medium8_promoted_total_clean_mismatch")
    if rejected_false != fixture_rejected or rejected_false != 57:
        issues.append("medium8_promoted_rejected_false_mismatch")
    if remaining_unresolved != fixture_remaining or remaining_unresolved != 11866:
        issues.append("medium8_promoted_remaining_unresolved_mismatch")
    if issue_rows or issue_rows != fixture_issue_rows + promotion_issue_rows:
        issues.append(f"issue_rows:{issue_rows}")

    if any(int_value(row, "length") < 8 or int_value(row, "length") >= 32 for row in promotion_rows):
        issues.append("medium8_promoted_non_medium8_target")
    if any(row.get("signature") != "internal|medium8|left_nonzero|right_nonzero" for row in promotion_rows):
        issues.append("medium8_promoted_signature_mismatch")
    if any(not row.get("greedy_selector") for row in promotion_rows):
        issues.append("medium8_promoted_missing_selector")
    if any(int_value(row, "base_known_overlap_bytes") for row in promotion_rows):
        issues.append("medium8_promoted_base_overlap")
    if any(int_value(row, "rejected_overlap_bytes") for row in promotion_rows):
        issues.append("medium8_promoted_rejected_overlap")
    if any(int_value(row, "selector_added_bytes") != int_value(row, "length") for row in promotion_rows):
        issues.append("medium8_promoted_added_target_size_mismatch")
    if any(int_value(row, "selector_exact_bytes") != int_value(row, "length") for row in promotion_rows):
        issues.append("medium8_promoted_exact_target_size_mismatch")
    if any(int_value(row, "selector_false_bytes") for row in promotion_rows):
        issues.append("medium8_promoted_false_target_bytes")

    missing_paths = 0
    wrong_size_paths = 0
    fullhd_preview_rows = 0
    for row in fixture_rows:
        fixture_bytes = int_value(row, "fixture_bytes")
        for field in ("decoded_path", "known_mask_path", "selector_mask_path"):
            value = row.get(field, "")
            if not value or not Path(value).exists():
                missing_paths += 1
                continue
            if Path(value).stat().st_size != fixture_bytes:
                wrong_size_paths += 1
        for field in ("native_preview_path", "fullhd_preview_path"):
            value = row.get(field, "")
            if not value or not Path(value).exists():
                missing_paths += 1
        if (row.get("fullhd_width"), row.get("fullhd_height")) == (
            str(TARGET_SIZE[0]),
            str(TARGET_SIZE[1]),
        ):
            fullhd_preview_rows += 1
    if missing_paths:
        issues.append(f"missing_medium8_promoted_paths:{missing_paths}")
    if wrong_size_paths:
        issues.append(f"medium8_promoted_path_size_mismatch:{wrong_size_paths}")
    if native_previews != len(fixture_rows) or native_previews != 32:
        issues.append("medium8_promoted_native_preview_count_mismatch")
    if fullhd_previews != fullhd_preview_rows or fullhd_previews != 32:
        issues.append("medium8_promoted_fullhd_preview_count_mismatch")
    if "const TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_REPLAY = " not in text:
        issues.append("missing_tex_gap_decoder_len64_promoted_medium8_replay_json")

    ok = not issues
    return (
        gate(
            gate_name,
            ok,
            expected=".tex medium8 selector targets replay cleanly after large32 promotion",
            actual=(
                f"added={selector_added}, total_clean={total_clean}, "
                f"remaining={remaining_unresolved}, false={selector_false}, fullhd={fullhd_previews}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        selector_added if ok else 0,
        total_clean if ok else 0,
        remaining_unresolved if ok else 0,
    )


def audit_tex_gap_decoder_unresolved_zero_queue(
    summary: Path,
    queue_rows_path: Path,
    signature_rows_path: Path,
    fixture_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_decoder_unresolved_zero_queue", summary), 0, 0, 0
    if not queue_rows_path.exists():
        return missing_gate("tex_gap_decoder_unresolved_zero_queue", queue_rows_path), 0, 0, 0
    if not signature_rows_path.exists():
        return missing_gate("tex_gap_decoder_unresolved_zero_queue", signature_rows_path), 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate("tex_gap_decoder_unresolved_zero_queue", fixture_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_decoder_unresolved_zero_queue", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    queue_rows = read_csv(queue_rows_path)
    signature_rows = read_csv(signature_rows_path)
    fixture_rows = read_csv(fixture_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    span_count = int_value(total, "span_rows")
    zero_run_count = int_value(total, "zero_run_rows")
    zero_bytes = int_value(total, "zero_bytes")
    pure_rows = int_value(total, "pure_zero_span_rows")
    pure_bytes = int_value(total, "pure_zero_span_bytes")
    internal_rows = int_value(total, "internal_zero_run_rows")
    internal_bytes = int_value(total, "internal_zero_bytes")
    boundary_rows = int_value(total, "boundary_zero_run_rows")
    boundary_bytes = int_value(total, "boundary_zero_bytes")
    len64_rows = int_value(total, "len64_run_rows")
    len64_bytes = int_value(total, "len64_bytes")
    large_rows = int_value(total, "large_run_rows")
    large_bytes = int_value(total, "large_run_bytes")
    max_zero = int_value(total, "max_zero_run_bytes")
    signature_count = int_value(total, "signature_rows")
    issue_rows = int_value(total, "issue_rows")

    queue_total_bytes = sum(int_value(row, "length") for row in queue_rows)
    queue_pure = [row for row in queue_rows if row.get("queue_class") == "review_pure_zero_span"]
    queue_internal = [
        row for row in queue_rows if row.get("queue_class") == "review_internal_zero"
    ]
    queue_boundary = [
        row for row in queue_rows if row.get("queue_class") == "review_boundary_zero"
    ]
    queue_len64 = [row for row in queue_rows if row.get("length_bucket") == "len64"]
    queue_large = [
        row
        for row in queue_rows
        if row.get("length_bucket") in {"len64", "multiple64", "large96", "large32"}
    ]
    queue_max_zero = max([int_value(row, "length") for row in queue_rows] or [0])

    signature_total_rows = sum(int_value(row, "rows") for row in signature_rows)
    signature_total_bytes = sum(int_value(row, "bytes") for row in signature_rows)
    signature_max_zero = max([int_value(row, "max_run_bytes") for row in signature_rows] or [0])
    fixture_total_rows = sum(int_value(row, "zero_run_rows") for row in fixture_rows)
    fixture_total_bytes = sum(int_value(row, "zero_bytes") for row in fixture_rows)
    fixture_internal_bytes = sum(int_value(row, "internal_zero_bytes") for row in fixture_rows)
    fixture_boundary_bytes = sum(int_value(row, "boundary_zero_bytes") for row in fixture_rows)
    fixture_pure_bytes = sum(int_value(row, "pure_zero_span_bytes") for row in fixture_rows)
    fixture_max_zero = max([int_value(row, "max_zero_run_bytes") for row in fixture_rows] or [0])
    top_signature = signature_rows[0] if signature_rows else {}

    if fixture_count != len(fixture_rows) or fixture_count != 32:
        issues.append("unresolved_zero_queue_fixture_count_mismatch")
    if span_count != 192:
        issues.append("unresolved_zero_queue_span_count_mismatch")
    if (
        zero_run_count != len(queue_rows)
        or zero_run_count != signature_total_rows
        or zero_run_count != fixture_total_rows
        or zero_run_count != 303
    ):
        issues.append("unresolved_zero_queue_row_count_mismatch")
    if (
        zero_bytes != queue_total_bytes
        or zero_bytes != signature_total_bytes
        or zero_bytes != fixture_total_bytes
        or zero_bytes != 7787
    ):
        issues.append("unresolved_zero_queue_byte_mismatch")
    if pure_rows != len(queue_pure) or pure_rows != 3:
        issues.append("unresolved_zero_queue_pure_row_mismatch")
    if pure_bytes != sum(int_value(row, "length") for row in queue_pure) or pure_bytes != fixture_pure_bytes or pure_bytes != 189:
        issues.append("unresolved_zero_queue_pure_byte_mismatch")
    if internal_rows != len(queue_internal) or internal_rows != 237:
        issues.append("unresolved_zero_queue_internal_row_mismatch")
    if internal_bytes != sum(int_value(row, "length") for row in queue_internal) or internal_bytes != fixture_internal_bytes or internal_bytes != 5972:
        issues.append("unresolved_zero_queue_internal_byte_mismatch")
    if boundary_rows != len(queue_boundary) or boundary_rows != 63:
        issues.append("unresolved_zero_queue_boundary_row_mismatch")
    if boundary_bytes != sum(int_value(row, "length") for row in queue_boundary) or boundary_bytes != fixture_boundary_bytes or boundary_bytes != 1626:
        issues.append("unresolved_zero_queue_boundary_byte_mismatch")
    if pure_bytes + internal_bytes + boundary_bytes != zero_bytes:
        issues.append("unresolved_zero_queue_bytes_not_partitioned")
    if len64_rows != len(queue_len64) or len64_rows != 49:
        issues.append("unresolved_zero_queue_len64_row_mismatch")
    if len64_bytes != sum(int_value(row, "length") for row in queue_len64) or len64_bytes != 3136:
        issues.append("unresolved_zero_queue_len64_byte_mismatch")
    if large_rows != len(queue_large) or large_rows != 107:
        issues.append("unresolved_zero_queue_large_row_mismatch")
    if large_bytes != sum(int_value(row, "length") for row in queue_large) or large_bytes != 5710:
        issues.append("unresolved_zero_queue_large_byte_mismatch")
    if (
        max_zero != queue_max_zero
        or max_zero != signature_max_zero
        or max_zero != fixture_max_zero
        or max_zero != 111
    ):
        issues.append("unresolved_zero_queue_max_mismatch")
    if signature_count != len(signature_rows) or signature_count != 19:
        issues.append("unresolved_zero_queue_signature_count_mismatch")
    if top_signature.get("signature") != "internal|len64|left_nonzero|right_nonzero":
        issues.append("unresolved_zero_queue_top_signature_mismatch")
    if int_value(top_signature, "rows") != 44 or int_value(top_signature, "bytes") != 2816:
        issues.append("unresolved_zero_queue_top_signature_value_mismatch")
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    if "const TEX_GAP_DECODER_UNRESOLVED_ZERO_QUEUE = " not in text:
        issues.append("missing_tex_gap_decoder_unresolved_zero_queue_json")

    ok = not issues
    return (
        gate(
            "tex_gap_decoder_unresolved_zero_queue",
            ok,
            expected=".tex unresolved zero runs are queued by context without promotion",
            actual=(
                f"runs={zero_run_count}, bytes={zero_bytes}, internal={internal_bytes}, "
                f"len64={len64_rows}, signatures={signature_count}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        zero_bytes if ok else 0,
        internal_bytes if ok else 0,
        signature_count if ok else 0,
    )


def audit_tex_gap_decoder_len64_internal_probe(
    summary: Path,
    target_rows_path: Path,
    neighbor_rows_path: Path,
    fixture_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_decoder_len64_internal_probe", summary), 0, 0, 0
    if not target_rows_path.exists():
        return missing_gate("tex_gap_decoder_len64_internal_probe", target_rows_path), 0, 0, 0
    if not neighbor_rows_path.exists():
        return missing_gate("tex_gap_decoder_len64_internal_probe", neighbor_rows_path), 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate("tex_gap_decoder_len64_internal_probe", fixture_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_decoder_len64_internal_probe", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    target_rows = read_csv(target_rows_path)
    neighbor_rows = read_csv(neighbor_rows_path)
    fixture_rows = read_csv(fixture_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    target_signature = total.get("target_signature", "")
    target_count = int_value(total, "target_rows")
    target_bytes = int_value(total, "target_bytes")
    fixture_count = int_value(total, "fixture_rows")
    span_count = int_value(total, "span_rows")
    barrel_rows = int_value(total, "barrel_rows")
    dinodead_rows = int_value(total, "dinodead_rows")
    neighbor_count = int_value(total, "neighbor_signature_rows")
    top_neighbor = total.get("top_neighbor_signature", "")
    top_neighbor_rows = int_value(total, "top_neighbor_rows")
    top_neighbor_bytes = int_value(total, "top_neighbor_bytes")
    prev29_rows = int_value(total, "prev29_next29_rows")
    prev29_bytes = int_value(total, "prev29_next29_bytes")
    context_files = int_value(total, "context_files")
    issue_rows = int_value(total, "issue_rows")

    target_total_bytes = sum(int_value(row, "length") for row in target_rows)
    target_context_files = sum(1 for row in target_rows if row.get("context_path"))
    missing_contexts = 0
    bad_contexts = 0
    for row in target_rows:
        context_path = Path(row.get("context_path", ""))
        if not context_path.exists():
            missing_contexts += 1
            continue
        expected_size = (
            int_value(row, "prev_run_length")
            + int_value(row, "length")
            + int_value(row, "next_run_length")
        )
        if context_path.stat().st_size != expected_size:
            bad_contexts += 1
    target_barrel = sum(1 for row in target_rows if row.get("pcx_name") == "barrel.pcx")
    target_dinodead = sum(1 for row in target_rows if row.get("pcx_name") == "dinodead.pcx")
    target_spans = {
        (
            row.get("rank", ""),
            row.get("pcx_name", ""),
            row.get("frontier_id", ""),
            row.get("span_index", ""),
        )
        for row in target_rows
    }
    prev29_targets = [
        row for row in target_rows if row.get("neighbor_signature") == "prev29|zero64|next29"
    ]
    neighbor_total_rows = sum(int_value(row, "rows") for row in neighbor_rows)
    neighbor_total_bytes = sum(int_value(row, "bytes") for row in neighbor_rows)
    neighbor_context_files = sum(int_value(row, "context_files") for row in neighbor_rows)
    top_neighbor_row = neighbor_rows[0] if neighbor_rows else {}
    fixture_total_rows = sum(int_value(row, "target_rows") for row in fixture_rows)
    fixture_total_bytes = sum(int_value(row, "target_bytes") for row in fixture_rows)
    fixture_context_files = sum(int_value(row, "context_files") for row in fixture_rows)

    if target_signature != "internal|len64|left_nonzero|right_nonzero":
        issues.append("len64_internal_target_signature_mismatch")
    if target_count != len(target_rows) or target_count != neighbor_total_rows or target_count != fixture_total_rows or target_count != 44:
        issues.append("len64_internal_target_count_mismatch")
    if target_bytes != target_total_bytes or target_bytes != neighbor_total_bytes or target_bytes != fixture_total_bytes or target_bytes != 2816:
        issues.append("len64_internal_byte_mismatch")
    if any(int_value(row, "length") != 64 for row in target_rows):
        issues.append("len64_internal_non_len64_target")
    if any(row.get("issues") for row in target_rows):
        issues.append("len64_internal_target_issue_rows")
    if fixture_count != len(fixture_rows) or fixture_count != 2:
        issues.append("len64_internal_fixture_count_mismatch")
    if span_count != len(target_spans) or span_count != 28:
        issues.append("len64_internal_span_count_mismatch")
    if barrel_rows != target_barrel or barrel_rows != 43:
        issues.append("len64_internal_barrel_count_mismatch")
    if dinodead_rows != target_dinodead or dinodead_rows != 1:
        issues.append("len64_internal_dinodead_count_mismatch")
    if neighbor_count != len(neighbor_rows) or neighbor_count != 29:
        issues.append("len64_internal_neighbor_count_mismatch")
    if top_neighbor != "prev29|zero64|next29" or top_neighbor_row.get("neighbor_signature") != top_neighbor:
        issues.append("len64_internal_top_neighbor_mismatch")
    if top_neighbor_rows != int_value(top_neighbor_row, "rows") or top_neighbor_rows != 10:
        issues.append("len64_internal_top_neighbor_row_mismatch")
    if top_neighbor_bytes != int_value(top_neighbor_row, "bytes") or top_neighbor_bytes != 640:
        issues.append("len64_internal_top_neighbor_byte_mismatch")
    if prev29_rows != len(prev29_targets) or prev29_rows != 10:
        issues.append("len64_internal_prev29_row_mismatch")
    if prev29_bytes != sum(int_value(row, "length") for row in prev29_targets) or prev29_bytes != 640:
        issues.append("len64_internal_prev29_byte_mismatch")
    if context_files != target_context_files or context_files != neighbor_context_files or context_files != fixture_context_files or context_files != 44:
        issues.append("len64_internal_context_count_mismatch")
    if missing_contexts:
        issues.append(f"missing_len64_contexts:{missing_contexts}")
    if bad_contexts:
        issues.append(f"bad_len64_context_sizes:{bad_contexts}")
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    if "const TEX_GAP_DECODER_LEN64_INTERNAL_PROBE = " not in text:
        issues.append("missing_tex_gap_decoder_len64_internal_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_decoder_len64_internal_probe",
            ok,
            expected=".tex internal len64 zero-run signature is isolated with byte contexts",
            actual=(
                f"targets={target_count}, bytes={target_bytes}, spans={span_count}, "
                f"top={top_neighbor}:{top_neighbor_rows}, contexts={context_files}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        target_count if ok else 0,
        target_bytes if ok else 0,
        top_neighbor_rows if ok else 0,
    )


def audit_tex_gap_decoder_len64_source_probe(
    summary: Path,
    target_rows_path: Path,
    control_rows_path: Path,
    ref_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_decoder_len64_source_probe", summary), 0, 0, 0
    if not target_rows_path.exists():
        return missing_gate("tex_gap_decoder_len64_source_probe", target_rows_path), 0, 0, 0
    if not control_rows_path.exists():
        return missing_gate("tex_gap_decoder_len64_source_probe", control_rows_path), 0, 0, 0
    if not ref_rows_path.exists():
        return missing_gate("tex_gap_decoder_len64_source_probe", ref_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_decoder_len64_source_probe", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    target_rows = read_csv(target_rows_path)
    control_rows = read_csv(control_rows_path)
    ref_rows = read_csv(ref_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    target_count = int_value(total, "target_rows")
    joined_count = int_value(total, "joined_rows")
    target_bytes = int_value(total, "target_bytes")
    u8_hits = int_value(total, "length_u8_hit_rows")
    u16_hits = int_value(total, "length_u16le_hit_rows")
    source_delta_u8_hits = int_value(total, "source_delta_u8_hit_rows")
    control_ref_rows = int_value(total, "control_ref_rows")
    unique_refs = int_value(total, "unique_control_refs")
    unique_windows = int_value(total, "unique_control_windows")
    top_window_rows = int_value(total, "top_control_window_rows")
    top_window_bytes = int_value(total, "top_control_window_bytes")
    top_ref_offset = total.get("top_control_ref_offset", "")
    top_ref_rows = int_value(total, "top_control_ref_rows")
    issue_rows = int_value(total, "issue_rows")

    target_total_bytes = sum(int_value(row, "length") for row in target_rows)
    target_joined = [row for row in target_rows if not row.get("issues")]
    target_u8_hits = sum(1 for row in target_rows if row.get("length_u8_hit_offsets"))
    target_u16_hits = sum(1 for row in target_rows if row.get("length_u16le_hit_offsets"))
    target_source_delta_u8_hits = sum(
        1 for row in target_rows if row.get("source_delta_u8_hit_offsets")
    )
    target_control_ref_rows = sum(1 for row in target_rows if row.get("control_ref_offset"))
    target_unique_refs = {
        row.get("control_ref_offset", "")
        for row in target_rows
        if row.get("control_ref_offset")
    }
    target_unique_windows = {
        row.get("control_window_signature", "")
        for row in target_rows
        if row.get("control_window_signature")
    }
    control_total_rows = sum(int_value(row, "rows") for row in control_rows)
    control_total_bytes = sum(int_value(row, "bytes") for row in control_rows)
    control_u8_hits = sum(int_value(row, "length_u8_hit_rows") for row in control_rows)
    ref_total_rows = sum(int_value(row, "rows") for row in ref_rows)
    ref_total_bytes = sum(int_value(row, "bytes") for row in ref_rows)
    top_control = control_rows[0] if control_rows else {}
    top_ref = ref_rows[0] if ref_rows else {}

    if target_count != len(target_rows) or target_count != control_total_rows or target_count != ref_total_rows or target_count != 44:
        issues.append("len64_source_target_count_mismatch")
    if joined_count != len(target_joined) or joined_count != 44:
        issues.append("len64_source_join_count_mismatch")
    if target_bytes != target_total_bytes or target_bytes != control_total_bytes or target_bytes != ref_total_bytes or target_bytes != 2816:
        issues.append("len64_source_byte_mismatch")
    if any(int_value(row, "length") != 64 for row in target_rows):
        issues.append("len64_source_non_len64_target")
    if u8_hits != target_u8_hits or u8_hits != control_u8_hits or u8_hits != 0:
        issues.append("len64_source_u8_hit_mismatch")
    if u16_hits != target_u16_hits or u16_hits != 0:
        issues.append("len64_source_u16_hit_mismatch")
    if source_delta_u8_hits != target_source_delta_u8_hits or source_delta_u8_hits != 0:
        issues.append("len64_source_delta_u8_hit_mismatch")
    if control_ref_rows != target_control_ref_rows or control_ref_rows != 44:
        issues.append("len64_source_control_ref_row_mismatch")
    if unique_refs != len(target_unique_refs) or unique_refs != len(ref_rows) or unique_refs != 34:
        issues.append("len64_source_unique_ref_mismatch")
    if unique_windows != len(target_unique_windows) or unique_windows != len(control_rows) or unique_windows != 34:
        issues.append("len64_source_unique_window_mismatch")
    if top_window_rows != int_value(top_control, "rows") or top_window_rows != 5:
        issues.append("len64_source_top_window_row_mismatch")
    if top_window_bytes != int_value(top_control, "bytes") or top_window_bytes != 320:
        issues.append("len64_source_top_window_byte_mismatch")
    if top_ref_offset != top_ref.get("control_ref_offset", "") or top_ref_offset != "506":
        issues.append("len64_source_top_ref_mismatch")
    if top_ref_rows != int_value(top_ref, "rows") or top_ref_rows != 5:
        issues.append("len64_source_top_ref_row_mismatch")
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    if "const TEX_GAP_DECODER_LEN64_SOURCE_PROBE = " not in text:
        issues.append("missing_tex_gap_decoder_len64_source_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_decoder_len64_source_probe",
            ok,
            expected=".tex internal len64 targets are joined to source control evidence",
            actual=(
                f"joined={joined_count}/{target_count}, bytes={target_bytes}, u8_hits={u8_hits}, "
                f"refs={unique_refs}, top_ref={top_ref_offset}:{top_ref_rows}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        joined_count if ok else 0,
        unique_refs if ok else 0,
        top_ref_rows if ok else 0,
    )


def audit_tex_gap_decoder_len64_selector_probe(
    summary: Path,
    candidate_rows_path: Path,
    greedy_rows_path: Path,
    target_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_decoder_len64_selector_probe", summary), 0, 0, 0
    if not candidate_rows_path.exists():
        return missing_gate("tex_gap_decoder_len64_selector_probe", candidate_rows_path), 0, 0, 0
    if not greedy_rows_path.exists():
        return missing_gate("tex_gap_decoder_len64_selector_probe", greedy_rows_path), 0, 0, 0
    if not target_rows_path.exists():
        return missing_gate("tex_gap_decoder_len64_selector_probe", target_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_decoder_len64_selector_probe", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    candidate_rows = read_csv(candidate_rows_path)
    greedy_rows = read_csv(greedy_rows_path)
    target_rows = read_csv(target_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    operation_rows = int_value(total, "operation_rows")
    target_count = int_value(total, "target_rows")
    target_bytes = int_value(total, "target_bytes")
    joined_targets = int_value(total, "joined_target_rows")
    len64_operation_rows = int_value(total, "len64_operation_rows")
    len64_zero_rows = int_value(total, "len64_zero_rows")
    len64_false_rows = int_value(total, "len64_false_rows")
    candidate_count = int_value(total, "candidate_rows")
    false_free_count = int_value(total, "false_free_candidate_rows")
    best_selector = total.get("best_selector", "")
    best_family = total.get("best_selector_family", "")
    best_target_rows = int_value(total, "best_selector_target_rows")
    best_target_bytes = int_value(total, "best_selector_target_bytes")
    best_operation_rows = int_value(total, "best_selector_operation_rows")
    best_zero_bytes = int_value(total, "best_selector_zero_bytes")
    best_false_bytes = int_value(total, "best_selector_false_bytes")
    greedy_min = int_value(total, "greedy_min_target_rows")
    greedy_selector_rows = int_value(total, "greedy_selector_rows")
    greedy_target_rows = int_value(total, "greedy_target_rows")
    greedy_target_bytes = int_value(total, "greedy_target_bytes")
    greedy_operation_rows = int_value(total, "greedy_operation_rows")
    greedy_zero_bytes = int_value(total, "greedy_zero_bytes")
    greedy_false_bytes = int_value(total, "greedy_false_bytes")
    issue_rows = int_value(total, "issue_rows")

    best_row = candidate_rows[0] if candidate_rows else {}
    greedy_target_total = 0
    previous_cumulative = 0
    for row in greedy_rows:
        added = int_value(row, "added_target_rows")
        cumulative = int_value(row, "cumulative_target_rows")
        if cumulative < previous_cumulative or cumulative != previous_cumulative + added:
            issues.append("len64_selector_greedy_cumulative_mismatch")
            break
        previous_cumulative = cumulative
        greedy_target_total = cumulative
    targets_with_greedy = sum(1 for row in target_rows if row.get("greedy_selector"))
    targets_best_hit = sum(1 for row in target_rows if row.get("best_selector_hit") == "1")
    target_total_bytes = sum(int_value(row, "length") for row in target_rows)

    if operation_rows != 984:
        issues.append("len64_selector_operation_count_mismatch")
    if target_count != len(target_rows) or target_count != 44:
        issues.append("len64_selector_target_count_mismatch")
    if target_bytes != target_total_bytes or target_bytes != 2816:
        issues.append("len64_selector_target_byte_mismatch")
    if joined_targets != target_count or joined_targets != 44:
        issues.append("len64_selector_join_count_mismatch")
    if len64_operation_rows != 61 or len64_zero_rows != 58 or len64_false_rows != 3:
        issues.append("len64_selector_len64_partition_mismatch")
    if candidate_count != len(candidate_rows) or candidate_count != 3235:
        issues.append("len64_selector_candidate_count_mismatch")
    if false_free_count != sum(
        1
        for row in candidate_rows
        if row.get("promotion_class") in {"source_false_free", "target_only_false_free"}
    ) or false_free_count != 1631:
        issues.append("len64_selector_false_free_count_mismatch")
    if best_selector != "cw_b16=6f&len=64" or best_row.get("selector") != best_selector:
        issues.append("len64_selector_best_signature_mismatch")
    if best_family != "len64_pair" or best_row.get("family") != best_family:
        issues.append("len64_selector_best_family_mismatch")
    if best_target_rows != int_value(best_row, "target_rows") or best_target_rows != targets_best_hit or best_target_rows != 12:
        issues.append("len64_selector_best_target_row_mismatch")
    if best_target_bytes != int_value(best_row, "target_bytes") or best_target_bytes != 768:
        issues.append("len64_selector_best_target_byte_mismatch")
    if best_operation_rows != int_value(best_row, "operation_rows") or best_operation_rows != 13:
        issues.append("len64_selector_best_operation_row_mismatch")
    if best_zero_bytes != int_value(best_row, "zero_bytes") or best_zero_bytes != 832:
        issues.append("len64_selector_best_zero_byte_mismatch")
    if best_false_bytes != int_value(best_row, "false_bytes") or best_false_bytes != 0:
        issues.append("len64_selector_best_false_byte_mismatch")
    if greedy_min != 3:
        issues.append("len64_selector_greedy_min_mismatch")
    if greedy_selector_rows != len(greedy_rows) or greedy_selector_rows != 12:
        issues.append("len64_selector_greedy_selector_count_mismatch")
    if greedy_target_rows != greedy_target_total or greedy_target_rows != targets_with_greedy or greedy_target_rows != 44:
        issues.append("len64_selector_greedy_target_count_mismatch")
    if greedy_target_bytes != 2816:
        issues.append("len64_selector_greedy_target_byte_mismatch")
    if greedy_operation_rows != 52:
        issues.append("len64_selector_greedy_operation_count_mismatch")
    if greedy_zero_bytes != 3328:
        issues.append("len64_selector_greedy_zero_byte_mismatch")
    if greedy_false_bytes != 0:
        issues.append("len64_selector_greedy_false_byte_mismatch")
    if any(int_value(row, "length") != 64 for row in target_rows):
        issues.append("len64_selector_non_len64_target")
    if any(row.get("issues") for row in target_rows):
        issues.append("len64_selector_target_issue_rows")
    if issue_rows:
        issues.append(f"issue_rows:{issue_rows}")
    if "const TEX_GAP_DECODER_LEN64_SELECTOR_PROBE = " not in text:
        issues.append("missing_tex_gap_decoder_len64_selector_probe_json")

    ok = not issues
    return (
        gate(
            "tex_gap_decoder_len64_selector_probe",
            ok,
            expected=".tex internal len64 targets have source-side selector candidates scored",
            actual=(
                f"best={best_selector}:{best_target_bytes}b, greedy={greedy_target_rows}/"
                f"{target_count}:{greedy_target_bytes}b, false={greedy_false_bytes}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        best_target_bytes if ok else 0,
        greedy_target_bytes if ok else 0,
        greedy_selector_rows if ok else 0,
    )


def audit_tex_gap_decoder_len64_promoted_replay(
    summary: Path,
    fixture_rows_path: Path,
    promotion_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_decoder_len64_promoted_replay", summary), 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate("tex_gap_decoder_len64_promoted_replay", fixture_rows_path), 0, 0, 0
    if not promotion_rows_path.exists():
        return missing_gate("tex_gap_decoder_len64_promoted_replay", promotion_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_decoder_len64_promoted_replay", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    fixture_rows = read_csv(fixture_rows_path)
    promotion_rows = read_csv(promotion_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    target_rows = int_value(total, "target_rows")
    promoted_rows = int_value(total, "promoted_target_rows")
    base_clean = int_value(total, "base_clean_bytes")
    selector_added = int_value(total, "selector_added_bytes")
    selector_exact = int_value(total, "selector_exact_bytes")
    selector_false = int_value(total, "selector_false_bytes")
    total_clean = int_value(total, "total_clean_bytes")
    rejected_false = int_value(total, "rejected_false_bytes")
    remaining_unresolved = int_value(total, "remaining_unresolved_bytes")
    native_previews = int_value(total, "native_previews")
    fullhd_previews = int_value(total, "fullhd_previews")
    issue_rows = int_value(total, "issue_rows")

    fixture_targets = sum(int_value(row, "selector_target_rows") for row in fixture_rows)
    fixture_added = sum(int_value(row, "selector_added_bytes") for row in fixture_rows)
    fixture_exact = sum(int_value(row, "selector_exact_bytes") for row in fixture_rows)
    fixture_false = sum(int_value(row, "selector_false_bytes") for row in fixture_rows)
    fixture_base = sum(int_value(row, "base_clean_bytes") for row in fixture_rows)
    fixture_total_clean = sum(int_value(row, "total_clean_bytes") for row in fixture_rows)
    fixture_rejected = sum(int_value(row, "rejected_false_bytes") for row in fixture_rows)
    fixture_remaining = sum(int_value(row, "remaining_unresolved_bytes") for row in fixture_rows)

    promotion_added = sum(int_value(row, "selector_added_bytes") for row in promotion_rows)
    promotion_exact = sum(int_value(row, "selector_exact_bytes") for row in promotion_rows)
    promotion_false = sum(int_value(row, "selector_false_bytes") for row in promotion_rows)
    promotion_issue_rows = sum(1 for row in promotion_rows if row.get("issues"))
    fixture_issue_rows = sum(1 for row in fixture_rows if row.get("issues"))

    if fixture_count != len(fixture_rows) or fixture_count != 32:
        issues.append("len64_promoted_fixture_count_mismatch")
    if target_rows != len(promotion_rows) or target_rows != fixture_targets or target_rows != 44:
        issues.append("len64_promoted_target_count_mismatch")
    if promoted_rows != sum(1 for row in promotion_rows if int_value(row, "selector_added_bytes")) or promoted_rows != 44:
        issues.append("len64_promoted_target_promoted_count_mismatch")
    if base_clean != fixture_base or base_clean != 1610:
        issues.append("len64_promoted_base_clean_mismatch")
    if selector_added != fixture_added or selector_added != promotion_added or selector_added != 2816:
        issues.append("len64_promoted_added_byte_mismatch")
    if selector_exact != fixture_exact or selector_exact != promotion_exact or selector_exact != 2816:
        issues.append("len64_promoted_exact_byte_mismatch")
    if selector_false != fixture_false or selector_false != promotion_false or selector_false != 0:
        issues.append("len64_promoted_false_byte_mismatch")
    if total_clean != fixture_total_clean or total_clean != 4426:
        issues.append("len64_promoted_total_clean_mismatch")
    if rejected_false != fixture_rejected or rejected_false != 57:
        issues.append("len64_promoted_rejected_false_mismatch")
    if remaining_unresolved != fixture_remaining or remaining_unresolved != 13020:
        issues.append("len64_promoted_remaining_unresolved_mismatch")
    if issue_rows or issue_rows != fixture_issue_rows + promotion_issue_rows:
        issues.append(f"issue_rows:{issue_rows}")

    if any(int_value(row, "length") != 64 for row in promotion_rows):
        issues.append("len64_promoted_non_len64_target")
    if any(not row.get("greedy_selector") for row in promotion_rows):
        issues.append("len64_promoted_missing_selector")
    if any(int_value(row, "base_known_overlap_bytes") for row in promotion_rows):
        issues.append("len64_promoted_base_overlap")
    if any(int_value(row, "rejected_overlap_bytes") for row in promotion_rows):
        issues.append("len64_promoted_rejected_overlap")
    if any(int_value(row, "selector_added_bytes") != 64 for row in promotion_rows):
        issues.append("len64_promoted_added_target_size_mismatch")
    if any(int_value(row, "selector_exact_bytes") != 64 for row in promotion_rows):
        issues.append("len64_promoted_exact_target_size_mismatch")
    if any(int_value(row, "selector_false_bytes") for row in promotion_rows):
        issues.append("len64_promoted_false_target_bytes")

    missing_paths = 0
    wrong_size_paths = 0
    fullhd_preview_rows = 0
    for row in fixture_rows:
        fixture_bytes = int_value(row, "fixture_bytes")
        for field in ("decoded_path", "known_mask_path", "selector_mask_path"):
            value = row.get(field, "")
            if not value or not Path(value).exists():
                missing_paths += 1
                continue
            if Path(value).stat().st_size != fixture_bytes:
                wrong_size_paths += 1
        for field in ("native_preview_path", "fullhd_preview_path"):
            value = row.get(field, "")
            if not value or not Path(value).exists():
                missing_paths += 1
        if (row.get("fullhd_width"), row.get("fullhd_height")) == (
            str(TARGET_SIZE[0]),
            str(TARGET_SIZE[1]),
        ):
            fullhd_preview_rows += 1
    if missing_paths:
        issues.append(f"missing_len64_promoted_paths:{missing_paths}")
    if wrong_size_paths:
        issues.append(f"len64_promoted_path_size_mismatch:{wrong_size_paths}")
    if native_previews != len(fixture_rows) or native_previews != 32:
        issues.append("len64_promoted_native_preview_count_mismatch")
    if fullhd_previews != fullhd_preview_rows or fullhd_previews != 32:
        issues.append("len64_promoted_fullhd_preview_count_mismatch")
    if "const TEX_GAP_DECODER_LEN64_PROMOTED_REPLAY = " not in text:
        issues.append("missing_tex_gap_decoder_len64_promoted_replay_json")

    ok = not issues
    return (
        gate(
            "tex_gap_decoder_len64_promoted_replay",
            ok,
            expected=".tex len64 selector targets replay cleanly without false bytes",
            actual=(
                f"added={selector_added}, total_clean={total_clean}, "
                f"remaining={remaining_unresolved}, false={selector_false}, "
                f"fullhd={fullhd_previews}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        selector_added if ok else 0,
        total_clean if ok else 0,
        remaining_unresolved if ok else 0,
    )


def audit_tex_gap_decoder_len64_promoted_gap_queue(
    summary: Path,
    span_rows_path: Path,
    fixture_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_decoder_len64_promoted_gap_queue", summary), 0, 0, 0
    if not span_rows_path.exists():
        return missing_gate("tex_gap_decoder_len64_promoted_gap_queue", span_rows_path), 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate("tex_gap_decoder_len64_promoted_gap_queue", fixture_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_decoder_len64_promoted_gap_queue", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    span_rows = read_csv(span_rows_path)
    fixture_rows = read_csv(fixture_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    total_bytes = int_value(total, "total_bytes")
    base_clean = int_value(total, "base_clean_bytes")
    selector_added = int_value(total, "selector_added_bytes")
    clean_bytes = int_value(total, "clean_bytes")
    rejected_false = int_value(total, "rejected_false_bytes")
    unresolved_bytes = int_value(total, "unresolved_bytes")
    unresolved_zero = int_value(total, "unresolved_zero_bytes")
    unresolved_nonzero = int_value(total, "unresolved_nonzero_bytes")
    unresolved_mixed = int_value(total, "unresolved_mixed_bytes")
    span_count = int_value(total, "span_rows")
    unresolved_spans = int_value(total, "unresolved_span_rows")
    rejected_spans = int_value(total, "rejected_span_rows")
    largest_unresolved = int_value(total, "largest_unresolved_span")
    issue_rows = int_value(total, "issue_rows")

    span_unresolved = [
        row for row in span_rows if row.get("span_class", "").startswith("unresolved")
    ]
    span_rejected = [
        row for row in span_rows if row.get("span_class", "").startswith("rejected_false_risk")
    ]
    span_unresolved_bytes = sum(int_value(row, "length") for row in span_unresolved)
    span_rejected_bytes = sum(int_value(row, "length") for row in span_rejected)
    span_largest_unresolved = max([int_value(row, "length") for row in span_unresolved] or [0])
    fixture_total = sum(int_value(row, "fixture_bytes") for row in fixture_rows)
    fixture_base = sum(int_value(row, "base_clean_bytes") for row in fixture_rows)
    fixture_added = sum(int_value(row, "selector_added_bytes") for row in fixture_rows)
    fixture_clean = sum(int_value(row, "clean_bytes") for row in fixture_rows)
    fixture_rejected = sum(int_value(row, "rejected_false_bytes") for row in fixture_rows)
    fixture_unresolved = sum(int_value(row, "unresolved_bytes") for row in fixture_rows)
    fixture_zero = sum(int_value(row, "unresolved_zero_bytes") for row in fixture_rows)
    fixture_nonzero = sum(int_value(row, "unresolved_nonzero_bytes") for row in fixture_rows)
    fixture_mixed = sum(int_value(row, "unresolved_mixed_bytes") for row in fixture_rows)

    if fixture_count != len(fixture_rows) or fixture_count != 32:
        issues.append("len64_promoted_gap_fixture_count_mismatch")
    if total_bytes != fixture_total or total_bytes != 17503:
        issues.append("len64_promoted_gap_total_byte_mismatch")
    if base_clean != fixture_base or base_clean != 1610:
        issues.append("len64_promoted_gap_base_clean_mismatch")
    if selector_added != fixture_added or selector_added != 2816:
        issues.append("len64_promoted_gap_added_byte_mismatch")
    if clean_bytes != fixture_clean or clean_bytes != 4426:
        issues.append("len64_promoted_gap_clean_byte_mismatch")
    if base_clean + selector_added != clean_bytes:
        issues.append("len64_promoted_gap_clean_partition_mismatch")
    if rejected_false != fixture_rejected or rejected_false != span_rejected_bytes or rejected_false != 57:
        issues.append("len64_promoted_gap_rejected_byte_mismatch")
    if unresolved_bytes != fixture_unresolved or unresolved_bytes != span_unresolved_bytes or unresolved_bytes != 13020:
        issues.append("len64_promoted_gap_unresolved_byte_mismatch")
    if clean_bytes + rejected_false + unresolved_bytes != total_bytes:
        issues.append("len64_promoted_gap_total_not_partitioned")
    if unresolved_zero != fixture_zero or unresolved_zero != 189:
        issues.append("len64_promoted_gap_zero_byte_mismatch")
    if unresolved_nonzero != fixture_nonzero or unresolved_nonzero != 2009:
        issues.append("len64_promoted_gap_nonzero_byte_mismatch")
    if unresolved_mixed != fixture_mixed or unresolved_mixed != 10822:
        issues.append("len64_promoted_gap_mixed_byte_mismatch")
    if span_count != len(span_rows) or span_count != 248:
        issues.append("len64_promoted_gap_span_count_mismatch")
    if unresolved_spans != len(span_unresolved) or unresolved_spans != 236:
        issues.append("len64_promoted_gap_unresolved_span_count_mismatch")
    if rejected_spans != len(span_rejected) or rejected_spans != 12:
        issues.append("len64_promoted_gap_rejected_span_count_mismatch")
    if largest_unresolved != span_largest_unresolved or largest_unresolved != 306:
        issues.append("len64_promoted_gap_largest_span_mismatch")
    if sum(int_value(row, "length") for row in span_rows) != rejected_false + unresolved_bytes:
        issues.append("len64_promoted_gap_span_total_mismatch")
    if issue_rows or issue_rows != sum(1 for row in fixture_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if "const TEX_GAP_DECODER_LEN64_PROMOTED_GAP_QUEUE = " not in text:
        issues.append("missing_tex_gap_decoder_len64_promoted_gap_queue_json")

    ok = not issues
    return (
        gate(
            "tex_gap_decoder_len64_promoted_gap_queue",
            ok,
            expected=".tex len64 promoted gap queue partitions remaining spans",
            actual=(
                f"clean={clean_bytes}, added={selector_added}, unresolved={unresolved_bytes}, "
                f"spans={span_count}, largest={largest_unresolved}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        unresolved_bytes if ok else 0,
        span_count if ok else 0,
        largest_unresolved if ok else 0,
    )


def audit_tex_gap_decoder_len64_promoted_large32_gap_queue(
    summary: Path,
    span_rows_path: Path,
    fixture_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    gate_name = "tex_gap_decoder_len64_promoted_large32_gap_queue"
    if not summary.exists():
        return missing_gate(gate_name, summary), 0, 0, 0
    if not span_rows_path.exists():
        return missing_gate(gate_name, span_rows_path), 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate(gate_name, fixture_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate(gate_name, html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    span_rows = read_csv(span_rows_path)
    fixture_rows = read_csv(fixture_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    total_bytes = int_value(total, "total_bytes")
    base_clean = int_value(total, "base_clean_bytes")
    selector_added = int_value(total, "selector_added_bytes")
    clean_bytes = int_value(total, "clean_bytes")
    rejected_false = int_value(total, "rejected_false_bytes")
    unresolved_bytes = int_value(total, "unresolved_bytes")
    unresolved_zero = int_value(total, "unresolved_zero_bytes")
    unresolved_nonzero = int_value(total, "unresolved_nonzero_bytes")
    unresolved_mixed = int_value(total, "unresolved_mixed_bytes")
    span_count = int_value(total, "span_rows")
    unresolved_spans = int_value(total, "unresolved_span_rows")
    rejected_spans = int_value(total, "rejected_span_rows")
    largest_unresolved = int_value(total, "largest_unresolved_span")
    issue_rows = int_value(total, "issue_rows")

    span_unresolved = [
        row for row in span_rows if row.get("span_class", "").startswith("unresolved")
    ]
    span_rejected = [
        row for row in span_rows if row.get("span_class", "").startswith("rejected_false_risk")
    ]
    span_unresolved_bytes = sum(int_value(row, "length") for row in span_unresolved)
    span_rejected_bytes = sum(int_value(row, "length") for row in span_rejected)
    span_largest_unresolved = max([int_value(row, "length") for row in span_unresolved] or [0])
    fixture_total = sum(int_value(row, "fixture_bytes") for row in fixture_rows)
    fixture_base = sum(int_value(row, "base_clean_bytes") for row in fixture_rows)
    fixture_added = sum(int_value(row, "selector_added_bytes") for row in fixture_rows)
    fixture_clean = sum(int_value(row, "clean_bytes") for row in fixture_rows)
    fixture_rejected = sum(int_value(row, "rejected_false_bytes") for row in fixture_rows)
    fixture_unresolved = sum(int_value(row, "unresolved_bytes") for row in fixture_rows)
    fixture_zero = sum(int_value(row, "unresolved_zero_bytes") for row in fixture_rows)
    fixture_nonzero = sum(int_value(row, "unresolved_nonzero_bytes") for row in fixture_rows)
    fixture_mixed = sum(int_value(row, "unresolved_mixed_bytes") for row in fixture_rows)

    if fixture_count != len(fixture_rows) or fixture_count != 32:
        issues.append("large32_promoted_gap_fixture_count_mismatch")
    if total_bytes != fixture_total or total_bytes != 17503:
        issues.append("large32_promoted_gap_total_byte_mismatch")
    if base_clean != fixture_base or base_clean != 4426:
        issues.append("large32_promoted_gap_base_clean_mismatch")
    if selector_added != fixture_added or selector_added != 1036:
        issues.append("large32_promoted_gap_added_byte_mismatch")
    if clean_bytes != fixture_clean or clean_bytes != 5462:
        issues.append("large32_promoted_gap_clean_byte_mismatch")
    if base_clean + selector_added != clean_bytes:
        issues.append("large32_promoted_gap_clean_partition_mismatch")
    if rejected_false != fixture_rejected or rejected_false != span_rejected_bytes or rejected_false != 57:
        issues.append("large32_promoted_gap_rejected_byte_mismatch")
    if unresolved_bytes != fixture_unresolved or unresolved_bytes != span_unresolved_bytes or unresolved_bytes != 11984:
        issues.append("large32_promoted_gap_unresolved_byte_mismatch")
    if clean_bytes + rejected_false + unresolved_bytes != total_bytes:
        issues.append("large32_promoted_gap_total_not_partitioned")
    if unresolved_zero != fixture_zero or unresolved_zero != 189:
        issues.append("large32_promoted_gap_zero_byte_mismatch")
    if unresolved_nonzero != fixture_nonzero or unresolved_nonzero != 2113:
        issues.append("large32_promoted_gap_nonzero_byte_mismatch")
    if unresolved_mixed != fixture_mixed or unresolved_mixed != 9682:
        issues.append("large32_promoted_gap_mixed_byte_mismatch")
    if span_count != len(span_rows) or span_count != 273:
        issues.append("large32_promoted_gap_span_count_mismatch")
    if unresolved_spans != len(span_unresolved) or unresolved_spans != 261:
        issues.append("large32_promoted_gap_unresolved_span_count_mismatch")
    if rejected_spans != len(span_rejected) or rejected_spans != 12:
        issues.append("large32_promoted_gap_rejected_span_count_mismatch")
    if largest_unresolved != span_largest_unresolved or largest_unresolved != 301:
        issues.append("large32_promoted_gap_largest_span_mismatch")
    if sum(int_value(row, "length") for row in span_rows) != rejected_false + unresolved_bytes:
        issues.append("large32_promoted_gap_span_total_mismatch")
    if issue_rows or issue_rows != sum(1 for row in fixture_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if "const TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_GAP_QUEUE = " not in text:
        issues.append("missing_tex_gap_decoder_len64_promoted_large32_gap_queue_json")

    ok = not issues
    return (
        gate(
            gate_name,
            ok,
            expected=".tex large32 promoted gap queue partitions remaining spans",
            actual=(
                f"clean={clean_bytes}, added={selector_added}, unresolved={unresolved_bytes}, "
                f"spans={span_count}, largest={largest_unresolved}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        unresolved_bytes if ok else 0,
        span_count if ok else 0,
        largest_unresolved if ok else 0,
    )


def audit_tex_gap_decoder_len64_promoted_medium8_gap_queue(
    summary: Path,
    span_rows_path: Path,
    fixture_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    gate_name = "tex_gap_decoder_len64_promoted_medium8_gap_queue"
    if not summary.exists():
        return missing_gate(gate_name, summary), 0, 0, 0
    if not span_rows_path.exists():
        return missing_gate(gate_name, span_rows_path), 0, 0, 0
    if not fixture_rows_path.exists():
        return missing_gate(gate_name, fixture_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate(gate_name, html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    span_rows = read_csv(span_rows_path)
    fixture_rows = read_csv(fixture_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    total_bytes = int_value(total, "total_bytes")
    base_clean = int_value(total, "base_clean_bytes")
    selector_added = int_value(total, "selector_added_bytes")
    clean_bytes = int_value(total, "clean_bytes")
    rejected_false = int_value(total, "rejected_false_bytes")
    unresolved_bytes = int_value(total, "unresolved_bytes")
    unresolved_zero = int_value(total, "unresolved_zero_bytes")
    unresolved_nonzero = int_value(total, "unresolved_nonzero_bytes")
    unresolved_mixed = int_value(total, "unresolved_mixed_bytes")
    span_count = int_value(total, "span_rows")
    unresolved_spans = int_value(total, "unresolved_span_rows")
    rejected_spans = int_value(total, "rejected_span_rows")
    largest_unresolved = int_value(total, "largest_unresolved_span")
    issue_rows = int_value(total, "issue_rows")

    span_unresolved = [
        row for row in span_rows if row.get("span_class", "").startswith("unresolved")
    ]
    span_rejected = [
        row for row in span_rows if row.get("span_class", "").startswith("rejected_false_risk")
    ]
    span_unresolved_bytes = sum(int_value(row, "length") for row in span_unresolved)
    span_rejected_bytes = sum(int_value(row, "length") for row in span_rejected)
    span_largest_unresolved = max([int_value(row, "length") for row in span_unresolved] or [0])
    fixture_total = sum(int_value(row, "fixture_bytes") for row in fixture_rows)
    fixture_base = sum(int_value(row, "base_clean_bytes") for row in fixture_rows)
    fixture_added = sum(int_value(row, "selector_added_bytes") for row in fixture_rows)
    fixture_clean = sum(int_value(row, "clean_bytes") for row in fixture_rows)
    fixture_rejected = sum(int_value(row, "rejected_false_bytes") for row in fixture_rows)
    fixture_unresolved = sum(int_value(row, "unresolved_bytes") for row in fixture_rows)
    fixture_zero = sum(int_value(row, "unresolved_zero_bytes") for row in fixture_rows)
    fixture_nonzero = sum(int_value(row, "unresolved_nonzero_bytes") for row in fixture_rows)
    fixture_mixed = sum(int_value(row, "unresolved_mixed_bytes") for row in fixture_rows)

    if fixture_count != len(fixture_rows) or fixture_count != 32:
        issues.append("medium8_promoted_gap_fixture_count_mismatch")
    if total_bytes != fixture_total or total_bytes != 17503:
        issues.append("medium8_promoted_gap_total_byte_mismatch")
    if base_clean != fixture_base or base_clean != 5462:
        issues.append("medium8_promoted_gap_base_clean_mismatch")
    if selector_added != fixture_added or selector_added != 118:
        issues.append("medium8_promoted_gap_added_byte_mismatch")
    if clean_bytes != fixture_clean or clean_bytes != 5580:
        issues.append("medium8_promoted_gap_clean_byte_mismatch")
    if base_clean + selector_added != clean_bytes:
        issues.append("medium8_promoted_gap_clean_partition_mismatch")
    if rejected_false != fixture_rejected or rejected_false != span_rejected_bytes or rejected_false != 57:
        issues.append("medium8_promoted_gap_rejected_byte_mismatch")
    if unresolved_bytes != fixture_unresolved or unresolved_bytes != span_unresolved_bytes or unresolved_bytes != 11866:
        issues.append("medium8_promoted_gap_unresolved_byte_mismatch")
    if clean_bytes + rejected_false + unresolved_bytes != total_bytes:
        issues.append("medium8_promoted_gap_total_not_partitioned")
    if unresolved_zero != fixture_zero or unresolved_zero != 189:
        issues.append("medium8_promoted_gap_zero_byte_mismatch")
    if unresolved_nonzero != fixture_nonzero or unresolved_nonzero != 2283:
        issues.append("medium8_promoted_gap_nonzero_byte_mismatch")
    if unresolved_mixed != fixture_mixed or unresolved_mixed != 9394:
        issues.append("medium8_promoted_gap_mixed_byte_mismatch")
    if span_count != len(span_rows) or span_count != 281:
        issues.append("medium8_promoted_gap_span_count_mismatch")
    if unresolved_spans != len(span_unresolved) or unresolved_spans != 269:
        issues.append("medium8_promoted_gap_unresolved_span_count_mismatch")
    if rejected_spans != len(span_rejected) or rejected_spans != 12:
        issues.append("medium8_promoted_gap_rejected_span_count_mismatch")
    if largest_unresolved != span_largest_unresolved or largest_unresolved != 301:
        issues.append("medium8_promoted_gap_largest_span_mismatch")
    if sum(int_value(row, "length") for row in span_rows) != rejected_false + unresolved_bytes:
        issues.append("medium8_promoted_gap_span_total_mismatch")
    if issue_rows or issue_rows != sum(1 for row in fixture_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if "const TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_GAP_QUEUE = " not in text:
        issues.append("missing_tex_gap_decoder_len64_promoted_medium8_gap_queue_json")

    ok = not issues
    return (
        gate(
            gate_name,
            ok,
            expected=".tex medium8 promoted gap queue partitions remaining spans",
            actual=(
                f"clean={clean_bytes}, added={selector_added}, unresolved={unresolved_bytes}, "
                f"spans={span_count}, largest={largest_unresolved}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        unresolved_bytes if ok else 0,
        span_count if ok else 0,
        largest_unresolved if ok else 0,
    )


def audit_tex_gap_fixture_replay(
    summary: Path,
    replay_rows_path: Path,
    best_rows_path: Path,
    html_report: Path,
) -> tuple[dict[str, str], int, int, int]:
    if not summary.exists():
        return missing_gate("tex_gap_fixture_replay", summary), 0, 0, 0
    if not replay_rows_path.exists():
        return missing_gate("tex_gap_fixture_replay", replay_rows_path), 0, 0, 0
    if not best_rows_path.exists():
        return missing_gate("tex_gap_fixture_replay", best_rows_path), 0, 0, 0
    if not html_report.exists():
        return missing_gate("tex_gap_fixture_replay", html_report), 0, 0, 0

    summary_rows = read_csv(summary)
    replay_rows = read_csv(replay_rows_path)
    best_rows = read_csv(best_rows_path)
    text = html_report.read_text(errors="replace")
    issues: list[str] = []
    if len(summary_rows) != 1:
        issues.append("summary_row_count_invalid")
        total = {}
    else:
        total = summary_rows[0]

    fixture_count = int_value(total, "fixture_rows")
    candidate_rows = int_value(total, "candidate_rows")
    variants = int_value(total, "tested_variants")
    exact_matches = int_value(total, "exact_match_rows")
    exact_match_fixtures = int_value(total, "exact_match_fixtures")
    best_prefix = int_value(total, "best_prefix_bytes")
    best_exact = int_value(total, "best_exact_bytes")
    issue_rows = int_value(total, "issue_rows")

    if fixture_count != len(best_rows):
        issues.append("gap_replay_fixture_count_mismatch")
    if candidate_rows != len(replay_rows):
        issues.append("gap_replay_candidate_count_mismatch")
    if variants != len({row.get("variant", "") for row in replay_rows if row.get("variant")}):
        issues.append("gap_replay_variant_count_mismatch")
    if exact_matches != sum(1 for row in replay_rows if row.get("full_match") == "1"):
        issues.append("gap_replay_exact_match_count_mismatch")
    if exact_match_fixtures != sum(1 for row in best_rows if row.get("full_match") == "1"):
        issues.append("gap_replay_exact_fixture_count_mismatch")
    if best_prefix != max([int_value(row, "prefix_bytes") for row in replay_rows] or [0]):
        issues.append("gap_replay_best_prefix_mismatch")
    if best_exact != max([int_value(row, "exact_bytes") for row in replay_rows] or [0]):
        issues.append("gap_replay_best_exact_mismatch")
    if issue_rows or issue_rows != sum(1 for row in replay_rows if row.get("issues")):
        issues.append(f"issue_rows:{issue_rows}")
    if fixture_count < 1:
        issues.append("missing_gap_fixture_replay_rows")
    if candidate_rows < fixture_count:
        issues.append("gap_replay_too_few_candidates")
    if "const TEX_GAP_FIXTURE_REPLAY = " not in text:
        issues.append("missing_tex_gap_fixture_replay_json")

    ok = not issues
    return (
        gate(
            "tex_gap_fixture_replay",
            ok,
            expected=".tex gap fixture replay report is internally consistent",
            actual=(
                f"fixtures={fixture_count}, candidates={candidate_rows}, variants={variants}, "
                f"exact={exact_matches}, best_prefix={best_prefix}, best_exact={best_exact}"
            ),
            evidence=f"{summary};{html_report}",
            issues=issues,
        ),
        candidate_rows if ok else 0,
        exact_matches if ok else 0,
        best_prefix if ok else 0,
    )


def audit_gallery(gallery: Path, manifest: Path) -> tuple[dict[str, str], int]:
    if not gallery.exists():
        return missing_gate("cdcache_hd_gallery", gallery), 0
    if not manifest.exists():
        return missing_gate("cdcache_hd_gallery", manifest), 0
    manifest_rows = read_csv(manifest)
    text = gallery.read_text(errors="replace")
    issues: list[str] = []
    match = re.search(r"const ASSETS = (.*?);\nconst grid", text)
    if not match:
        return (
            gate(
                "cdcache_hd_gallery",
                False,
                expected="embedded ASSETS JSON in gallery HTML",
                actual="missing",
                evidence=gallery,
                issues=["missing_assets_json"],
            ),
            0,
        )
    try:
        assets = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        return (
            gate(
                "cdcache_hd_gallery",
                False,
                expected="valid embedded ASSETS JSON",
                actual=f"JSON error at {exc.pos}",
                evidence=gallery,
                issues=[f"invalid_assets_json:{exc}"],
            ),
            0,
        )
    if len(assets) != len(manifest_rows):
        issues.append("manifest_gallery_count_mismatch")
    if "function escapeHtml" not in text:
        issues.append("missing_html_escape_function")
    missing_paths = 0
    for asset in assets:
        for field in ("image", "source"):
            value = asset.get(field, "")
            if value and not (gallery.parent / value).exists():
                missing_paths += 1
    if missing_paths:
        issues.append(f"missing_gallery_paths:{missing_paths}")
    linked_assets = sum(1 for asset in assets if asset.get("linked") == "yes")
    ok = not issues
    return (
        gate(
            "cdcache_hd_gallery",
            ok,
            expected=f"{len(manifest_rows)} gallery assets with valid image/source paths",
            actual=f"assets={len(assets)}, linked={linked_assets}, missing_paths={missing_paths}",
            evidence=gallery,
            issues=issues,
        ),
        len(assets) if ok else 0,
    )


def audit_dashboard(dashboard: Path) -> tuple[dict[str, str], int]:
    if not dashboard.exists():
        return missing_gate("fullhd_dashboard", dashboard), 0
    text = dashboard.read_text(errors="replace")
    issues: list[str] = []
    match = re.search(
        r'<script type="application/json" id="dashboard-data">(.*?)</script>',
        text,
        re.S,
    )
    if not match:
        return (
            gate(
                "fullhd_dashboard",
                False,
                expected="embedded dashboard JSON data",
                actual="missing",
                evidence=dashboard,
                issues=["missing_dashboard_json"],
            ),
            0,
        )
    try:
        payload = json.loads(html.unescape(match.group(1)))
    except json.JSONDecodeError as exc:
        return (
            gate(
                "fullhd_dashboard",
                False,
                expected="valid embedded dashboard JSON",
                actual=f"JSON error at {exc.pos}",
                evidence=dashboard,
                issues=[f"invalid_dashboard_json:{exc}"],
            ),
            0,
        )
    cards = payload.get("cards", [])
    links = payload.get("links", [])
    audit_summary = payload.get("auditSummary", {})
    if not isinstance(cards, list) or len(cards) < 4:
        issues.append("missing_dashboard_cards")
        cards = []
    if not isinstance(links, list):
        issues.append("invalid_dashboard_links")
        links = []
    if isinstance(audit_summary, dict) and audit_summary.get("status") != "pass":
        issues.append("dashboard_embeds_nonpassing_audit")

    missing_paths = 0
    for card in cards:
        if not isinstance(card, dict):
            continue
        for field in ("href", "image"):
            value = card.get(field, "")
            if value and not (dashboard.parent / value).exists():
                missing_paths += 1
    for link in links:
        if not isinstance(link, dict):
            continue
        value = link.get("href", "")
        if value and not (dashboard.parent / value).exists():
            missing_paths += 1
    if missing_paths:
        issues.append(f"missing_dashboard_paths:{missing_paths}")

    ok = not issues
    return (
        gate(
            "fullhd_dashboard",
            ok,
            expected="dashboard cards and links target existing local artifacts",
            actual=f"cards={len(cards)}, links={len(links)}, missing_paths={missing_paths}",
            evidence=dashboard,
            issues=issues,
        ),
        len(cards) if ok else 0,
    )


def audit_run_hd(path: Path, dosbox_conf: Path) -> dict[str, str]:
    if not path.exists():
        return missing_gate("run_hd_launcher", path)
    if not dosbox_conf.exists():
        return missing_gate("run_hd_launcher", dosbox_conf)
    text = path.read_text(errors="replace")
    config_text = dosbox_conf.read_text(errors="replace")
    issues: list[str] = []
    if not os.access(path, os.X_OK):
        issues.append("not_executable")
    for needle in ("1920x1080", "output = opengl"):
        if needle not in text:
            issues.append(f"missing_setting:{needle}")
    if (
        "glshader = interpolation/catmull-rom" not in text
        and "glshader = interpolation\\/catmull-rom" not in text
    ):
        issues.append("missing_setting:glshader = interpolation/catmull-rom")
    for needle in (
        "fullscreen = true",
        "fullresolution = 1920x1080",
        "windowresolution = 1920x1080",
        "viewport_resolution = 1920x1080",
        "output = opengl",
        "aspect = stretch",
        "scaler = none",
        "glshader = interpolation/catmull-rom",
    ):
        if needle not in config_text:
            issues.append(f"missing_config_setting:{needle}")
    if "wine" in text.lower():
        issues.append("contains_windows_compat_launcher")
    if 'exec "$DOSBOX_BIN" -conf "$DOSBOX_CONF"' not in text:
        issues.append("missing_direct_dosbox_exec")
    return gate(
        "run_hd_launcher",
        not issues,
        expected="direct DOSBox launcher with 1920x1080 HD settings",
        actual=f"launcher_size={len(text)} bytes, config_size={len(config_text)} bytes",
        evidence=f"{path};{dosbox_conf}",
        issues=issues,
    )


def write_outputs(output: Path, rows: list[dict[str, str]], summary_row: dict[str, str]) -> tuple[Path, Path]:
    output.mkdir(parents=True, exist_ok=True)
    audit_path = output / "audit.csv"
    summary_path = output / "summary.csv"
    with audit_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=AUDIT_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)
    with summary_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDNAMES)
        writer.writeheader()
        writer.writerow(summary_row)
    return audit_path, summary_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit generated Full HD game asset evidence.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--fail-on-issues", action="store_true")
    args = parser.parse_args()

    rows: list[dict[str, str]] = []
    still_gate, still_count = audit_still(DEFAULT_STILL_MANIFEST, DEFAULT_STILL_VERIFICATION)
    rows.append(still_gate)
    still_gallery_gate, still_gallery_count = audit_still_gallery(
        DEFAULT_STILL_GALLERY,
        DEFAULT_STILL_GALLERY_MANIFEST,
        DEFAULT_STILL_MANIFEST,
    )
    rows.append(still_gallery_gate)
    vqa_gate, vqa_count = audit_vqa(DEFAULT_VQA_MANIFEST, DEFAULT_VQA_VERIFICATION)
    rows.append(vqa_gate)
    vqa_gallery_gate, vqa_gallery_count = audit_vqa_gallery(
        DEFAULT_VQA_GALLERY,
        DEFAULT_VQA_GALLERY_MANIFEST,
        DEFAULT_VQA_MANIFEST,
    )
    rows.append(vqa_gallery_gate)
    vqa_status_gate, vqa_status_archives = audit_vqa_status_report(
        DEFAULT_VQA_STATUS_SUMMARY,
        DEFAULT_VQA_STATUS_BY_ARCHIVE,
        DEFAULT_VQA_STATUS_HTML,
        DEFAULT_VQA_MANIFEST,
    )
    rows.append(vqa_status_gate)
    archive_coverage_gate, archive_coverage_visual = audit_archive_coverage(
        DEFAULT_ARCHIVE_COVERAGE_SUMMARY,
        DEFAULT_ARCHIVE_COVERAGE_ARCHIVES,
        DEFAULT_ARCHIVE_COVERAGE_HTML,
        DEFAULT_VQA_MANIFEST,
        DEFAULT_STILL_MANIFEST,
    )
    rows.append(archive_coverage_gate)
    inventory_gate, total_fullhd = audit_inventory(DEFAULT_INVENTORY_SUMMARY)
    rows.append(inventory_gate)
    cdcache_descriptor_gate, cdcache_descriptor_count = audit_cdcache_export(
        "cdcache_rgba_descriptors",
        DEFAULT_CDCACHE_DESCRIPTOR_MANIFEST,
        DEFAULT_CDCACHE_DESCRIPTOR_VERIFICATION,
    )
    rows.append(cdcache_descriptor_gate)
    cdcache_tile_gate, cdcache_tile_count = audit_cdcache_export(
        "cdcache_rgba_tiles",
        DEFAULT_CDCACHE_TILE_MANIFEST,
        DEFAULT_CDCACHE_TILE_VERIFICATION,
    )
    rows.append(cdcache_tile_gate)
    pack_gate, pack_count, pack_linked = audit_pack(
        DEFAULT_PACK_MANIFEST,
        DEFAULT_PACK_VERIFICATION,
        DEFAULT_PACK_VERIFICATION_SUMMARY,
    )
    rows.append(pack_gate)
    tex_gate, tex_assets, tex_material_links = audit_tex_coverage(
        DEFAULT_TEX_COVERAGE_SUMMARY,
        DEFAULT_TEX_COVERAGE_CACHE,
        DEFAULT_TEX_COVERAGE_MATERIALS,
        DEFAULT_TEX_COVERAGE_HTML,
        DEFAULT_PACK_MANIFEST,
        DEFAULT_TEX_MATERIAL_LINKS,
    )
    rows.append(tex_gate)
    tex_reference_gate, tex_reference_unique, tex_reference_covered, tex_reference_missing = (
        audit_tex_reference_coverage(
            DEFAULT_TEX_REFERENCE_SUMMARY,
            DEFAULT_TEX_REFERENCE_REFERENCES,
            DEFAULT_TEX_REFERENCE_MISSING,
            DEFAULT_TEX_REFERENCE_ARCHIVES,
            DEFAULT_TEX_REFERENCE_HTML,
        )
    )
    rows.append(tex_reference_gate)
    tex_missing_gate, tex_missing_raw_unique, tex_missing_material_unique = (
        audit_tex_missing_reference_evidence(
            DEFAULT_TEX_MISSING_EVIDENCE_SUMMARY,
            DEFAULT_TEX_MISSING_EVIDENCE_ROWS,
            DEFAULT_TEX_MISSING_EVIDENCE_UNIQUE,
            DEFAULT_TEX_MISSING_EVIDENCE_HTML,
        )
    )
    rows.append(tex_missing_gate)
    raw_probe_gate, raw_probe_candidates = audit_raw_reference_probe(
        DEFAULT_RAW_REFERENCE_PROBE_SUMMARY,
        DEFAULT_RAW_REFERENCE_PROBE_ROWS,
        DEFAULT_RAW_REFERENCE_PROBE_HTML,
    )
    rows.append(raw_probe_gate)
    alias_candidate_gate, alias_candidate_count, alias_synthetic_descriptors = (
        audit_alias_candidates(
            DEFAULT_ALIAS_CANDIDATE_SUMMARY,
            DEFAULT_ALIAS_CANDIDATE_ROWS,
            DEFAULT_ALIAS_SYNTHETIC_DESCRIPTORS,
            DEFAULT_ALIAS_CANDIDATE_HTML,
        )
    )
    rows.append(alias_candidate_gate)
    alias_descriptor_gate, alias_descriptor_count = audit_cdcache_export(
        "cdcache_alias_candidate_descriptors",
        DEFAULT_ALIAS_TEXTURE_MANIFEST,
        DEFAULT_ALIAS_TEXTURE_VERIFICATION,
    )
    rows.append(alias_descriptor_gate)
    alias_tile_gate, alias_tile_count = audit_cdcache_export(
        "cdcache_alias_candidate_tiles",
        DEFAULT_ALIAS_TILE_MANIFEST,
        DEFAULT_ALIAS_TILE_VERIFICATION,
    )
    rows.append(alias_tile_gate)
    alias_pack_gate, alias_pack_assets = audit_alias_pack(
        DEFAULT_ALIAS_PACK_SUMMARY,
        DEFAULT_ALIAS_PACK_MANIFEST,
        DEFAULT_ALIAS_PACK_HTML,
    )
    rows.append(alias_pack_gate)
    tex_material_decode_gate, tex_material_decode_assets = audit_tex_material_decode_pack(
        DEFAULT_TEX_MATERIAL_DECODE_PACK_SUMMARY,
        DEFAULT_TEX_MATERIAL_DECODE_PACK_MANIFEST,
        DEFAULT_TEX_MATERIAL_DECODE_PACK_HTML,
    )
    rows.append(tex_material_decode_gate)
    tex_raw_same_archive_gate, tex_raw_same_archive_eligible = audit_tex_raw_same_archive_promoted_pack(
        DEFAULT_TEX_RAW_SAME_ARCHIVE_PROMOTED_PACK_SUMMARY,
        DEFAULT_TEX_RAW_SAME_ARCHIVE_PROMOTED_PACK_MANIFEST,
        DEFAULT_TEX_RAW_SAME_ARCHIVE_PROMOTED_PACK_HTML,
    )
    rows.append(tex_raw_same_archive_gate)
    (
        tex_augmented_gate,
        tex_augmented_exact_or_alias,
        tex_augmented_exact_alias_or_decoded,
        tex_augmented_exact_alias_decoded_or_raw,
        tex_augmented_unresolved,
    ) = (
        audit_tex_augmented_coverage(
            DEFAULT_TEX_AUGMENTED_SUMMARY,
            DEFAULT_TEX_AUGMENTED_REFERENCES,
            DEFAULT_TEX_AUGMENTED_ALIASES,
            DEFAULT_TEX_AUGMENTED_MATERIAL_DECODES,
            DEFAULT_TEX_AUGMENTED_RAW_SAME_ARCHIVE,
            DEFAULT_TEX_AUGMENTED_HTML,
        )
    )
    rows.append(tex_augmented_gate)
    tex_probe_gate, tex_probe_previews, tex_probe_unique_pcx = audit_tex_unresolved_material_probe(
        DEFAULT_TEX_UNRESOLVED_PROBE_SUMMARY,
        DEFAULT_TEX_UNRESOLVED_PROBE_MANIFEST,
        DEFAULT_TEX_UNRESOLVED_PROBE_HTML,
    )
    rows.append(tex_probe_gate)
    tex_probe_analysis_gate, tex_probe_analysis_best, tex_probe_analysis_segments = (
        audit_tex_probe_analysis(
            DEFAULT_TEX_PROBE_ANALYSIS_SUMMARY,
            DEFAULT_TEX_PROBE_ANALYSIS_ROWS,
            DEFAULT_TEX_PROBE_ANALYSIS_BEST,
            DEFAULT_TEX_PROBE_ANALYSIS_HTML,
        )
    )
    rows.append(tex_probe_analysis_gate)
    tex_decoder_queue_gate, tex_decoder_queue_rows, tex_decoder_queue_segments = (
        audit_tex_material_decoder_queue(
            DEFAULT_TEX_MATERIAL_DECODER_QUEUE_SUMMARY,
            DEFAULT_TEX_MATERIAL_DECODER_QUEUE_ROWS,
            DEFAULT_TEX_MATERIAL_DECODER_QUEUE_PREFIXES,
            DEFAULT_TEX_MATERIAL_DECODER_QUEUE_HTML,
        )
    )
    rows.append(tex_decoder_queue_gate)
    tex_remaining_profile_gate, tex_remaining_profile_unique = audit_tex_remaining_reference_profile(
        DEFAULT_TEX_REMAINING_PROFILE_SUMMARY,
        DEFAULT_TEX_REMAINING_PROFILE_ROWS,
        DEFAULT_TEX_REMAINING_PROFILE_ARCHIVES,
        DEFAULT_TEX_REMAINING_PROFILE_PREFIXES,
        DEFAULT_TEX_REMAINING_PROFILE_HTML,
    )
    rows.append(tex_remaining_profile_gate)
    tex_exact_compare_gate, tex_exact_compare_segments, tex_exact_compare_32b, tex_exact_compare_16b = (
        audit_tex_exact_cdcache_compare(
            DEFAULT_TEX_EXACT_CDCACHE_COMPARE_SUMMARY,
            DEFAULT_TEX_EXACT_CDCACHE_COMPARE_ROWS,
            DEFAULT_TEX_EXACT_CDCACHE_COMPARE_HTML,
        )
    )
    rows.append(tex_exact_compare_gate)
    tex_chunk_evidence_gate, tex_chunk_evidence_matches, tex_chunk_evidence_segments = (
        audit_tex_exact_chunk_evidence(
            DEFAULT_TEX_EXACT_CHUNK_EVIDENCE_SUMMARY,
            DEFAULT_TEX_EXACT_CHUNK_EVIDENCE_ROWS,
            DEFAULT_TEX_EXACT_CHUNK_EVIDENCE_HTML,
        )
    )
    rows.append(tex_chunk_evidence_gate)
    tex_match_overlay_gate, tex_match_overlay_fullhd, tex_match_overlay_pixels = (
        audit_tex_exact_match_overlays(
            DEFAULT_TEX_EXACT_MATCH_OVERLAY_SUMMARY,
            DEFAULT_TEX_EXACT_MATCH_OVERLAY_ROWS,
            DEFAULT_TEX_EXACT_MATCH_OVERLAY_HTML,
        )
    )
    rows.append(tex_match_overlay_gate)
    tex_decoder_seed_gate, tex_decoder_seed_strong, tex_decoder_seed_medium = (
        audit_tex_decoder_seed_report(
            DEFAULT_TEX_DECODER_SEED_SUMMARY,
            DEFAULT_TEX_DECODER_SEED_ROWS,
            DEFAULT_TEX_DECODER_SEED_HTML,
        )
    )
    rows.append(tex_decoder_seed_gate)
    tex_exact_chunk_scan_gate, tex_exact_chunk_scan_rows, tex_exact_chunk_scan_capped = (
        audit_tex_exact_chunk_scan(
            DEFAULT_TEX_EXACT_CHUNK_SCAN_SUMMARY,
            DEFAULT_TEX_EXACT_CHUNK_SCAN_ROWS,
            DEFAULT_TEX_EXACT_CHUNK_SCAN_HTML,
        )
    )
    rows.append(tex_exact_chunk_scan_gate)
    tex_exact_chunk_cluster_gate, tex_exact_chunk_clusters, tex_exact_chunk_cluster_strong, tex_exact_chunk_cluster_span = (
        audit_tex_exact_chunk_clusters(
            DEFAULT_TEX_EXACT_CHUNK_CLUSTER_SUMMARY,
            DEFAULT_TEX_EXACT_CHUNK_CLUSTER_ROWS,
            DEFAULT_TEX_EXACT_CHUNK_CLUSTER_HTML,
        )
    )
    rows.append(tex_exact_chunk_cluster_gate)
    tex_exact_cluster_overlay_gate, tex_exact_cluster_overlay_fullhd, tex_exact_cluster_overlay_pixels = (
        audit_tex_exact_cluster_overlays(
            DEFAULT_TEX_EXACT_CLUSTER_OVERLAY_SUMMARY,
            DEFAULT_TEX_EXACT_CLUSTER_OVERLAY_ROWS,
            DEFAULT_TEX_EXACT_CLUSTER_OVERLAY_HTML,
        )
    )
    rows.append(tex_exact_cluster_overlay_gate)
    tex_decoder_run_corpus_gate, tex_decoder_run_corpus_runs, tex_decoder_run_corpus_bytes = (
        audit_tex_decoder_run_corpus(
            DEFAULT_TEX_DECODER_RUN_CORPUS_SUMMARY,
            DEFAULT_TEX_DECODER_RUN_CORPUS_ROWS,
            DEFAULT_TEX_DECODER_RUN_CORPUS_HTML,
        )
    )
    rows.append(tex_decoder_run_corpus_gate)
    tex_partial_raw_decoder_gate, tex_partial_raw_decoder_fullhd, tex_partial_raw_decoder_bytes = (
        audit_tex_partial_raw_decoder(
            DEFAULT_TEX_PARTIAL_RAW_DECODER_SUMMARY,
            DEFAULT_TEX_PARTIAL_RAW_DECODER_MANIFEST,
            DEFAULT_TEX_PARTIAL_RAW_DECODER_HTML,
        )
    )
    rows.append(tex_partial_raw_decoder_gate)
    tex_partial_raw_coverage_gate, tex_partial_raw_coverage_pixels, tex_partial_raw_coverage_gaps = (
        audit_tex_partial_raw_coverage(
            DEFAULT_TEX_PARTIAL_RAW_COVERAGE_SUMMARY,
            DEFAULT_TEX_PARTIAL_RAW_COVERAGE_ROWS,
            DEFAULT_TEX_PARTIAL_RAW_COVERAGE_GAPS,
            DEFAULT_TEX_PARTIAL_RAW_COVERAGE_HTML,
        )
    )
    rows.append(tex_partial_raw_coverage_gate)
    tex_gap_frontier_gate, tex_gap_frontier_gaps, tex_gap_frontier_windows = (
        audit_tex_gap_frontier_report(
            DEFAULT_TEX_GAP_FRONTIER_SUMMARY,
            DEFAULT_TEX_GAP_FRONTIER_ROWS,
            DEFAULT_TEX_GAP_FRONTIER_HTML,
        )
    )
    rows.append(tex_gap_frontier_gate)
    tex_gap_opcode_gate, tex_gap_opcode_rows, tex_gap_opcode_best_prefix, tex_gap_opcode_exact_replays = (
        audit_tex_gap_opcode_probe(
            DEFAULT_TEX_GAP_OPCODE_PROBE_SUMMARY,
            DEFAULT_TEX_GAP_OPCODE_PROBE_ROWS,
            DEFAULT_TEX_GAP_OPCODE_PROBE_OPCODE_ROWS,
            DEFAULT_TEX_GAP_OPCODE_PROBE_HTML,
        )
    )
    rows.append(tex_gap_opcode_gate)
    tex_gap_rle_gate, tex_gap_rle_pairs, tex_gap_rle_full_matches, tex_gap_rle_best_prefix = (
        audit_tex_gap_rle_probe(
            DEFAULT_TEX_GAP_RLE_PROBE_SUMMARY,
            DEFAULT_TEX_GAP_RLE_PROBE_ROWS,
            DEFAULT_TEX_GAP_RLE_PROBE_BEST,
            DEFAULT_TEX_GAP_RLE_PROBE_HTML,
        )
    )
    rows.append(tex_gap_rle_gate)
    tex_gap_rule_gate, tex_gap_rule_rows, tex_gap_rule_types, tex_gap_rule_top_priority = (
        audit_tex_gap_rule_queue(
            DEFAULT_TEX_GAP_RULE_QUEUE_SUMMARY,
            DEFAULT_TEX_GAP_RULE_QUEUE_ROWS,
            DEFAULT_TEX_GAP_RULE_QUEUE_RULES,
            DEFAULT_TEX_GAP_RULE_QUEUE_HTML,
        )
    )
    rows.append(tex_gap_rule_gate)
    tex_gap_fixture_gate, tex_gap_fixture_rows, tex_gap_fixture_files, tex_gap_fixture_fragment_bytes = (
        audit_tex_gap_rule_fixtures(
            DEFAULT_TEX_GAP_RULE_FIXTURE_SUMMARY,
            DEFAULT_TEX_GAP_RULE_FIXTURE_ROWS,
            DEFAULT_TEX_GAP_RULE_FIXTURE_HTML,
        )
    )
    rows.append(tex_gap_fixture_gate)
    tex_gap_zero_gate, tex_gap_zero_fixtures, tex_gap_zero_runs, tex_gap_zero_max = (
        audit_tex_gap_zero_run_probe(
            DEFAULT_TEX_GAP_ZERO_RUN_SUMMARY,
            DEFAULT_TEX_GAP_ZERO_RUN_FIXTURES,
            DEFAULT_TEX_GAP_ZERO_RUN_RUNS,
            DEFAULT_TEX_GAP_ZERO_RUN_HTML,
        )
    )
    rows.append(tex_gap_zero_gate)
    tex_gap_geometry_gate, tex_gap_geometry_rows, tex_gap_geometry_prefix, tex_gap_geometry_exact = (
        audit_tex_gap_geometry_replay(
            DEFAULT_TEX_GAP_GEOMETRY_REPLAY_SUMMARY,
            DEFAULT_TEX_GAP_GEOMETRY_REPLAY_ROWS,
            DEFAULT_TEX_GAP_GEOMETRY_REPLAY_BEST,
            DEFAULT_TEX_GAP_GEOMETRY_REPLAY_HTML,
        )
    )
    rows.append(tex_gap_geometry_gate)
    tex_gap_nonzero_gate, tex_gap_nonzero_rows, tex_gap_nonzero_prefix, tex_gap_nonzero_exact = (
        audit_tex_gap_nonzero_stream_probe(
            DEFAULT_TEX_GAP_NONZERO_STREAM_SUMMARY,
            DEFAULT_TEX_GAP_NONZERO_STREAM_ROWS,
            DEFAULT_TEX_GAP_NONZERO_STREAM_BEST,
            DEFAULT_TEX_GAP_NONZERO_STREAM_HTML,
        )
    )
    rows.append(tex_gap_nonzero_gate)
    tex_gap_control_gate, tex_gap_control_hits, tex_gap_control_u16le, tex_gap_control_metrics = (
        audit_tex_gap_control_word_probe(
            DEFAULT_TEX_GAP_CONTROL_WORD_SUMMARY,
            DEFAULT_TEX_GAP_CONTROL_WORD_FIXTURES,
            DEFAULT_TEX_GAP_CONTROL_WORD_HITS,
            DEFAULT_TEX_GAP_CONTROL_WORD_METRICS,
            DEFAULT_TEX_GAP_CONTROL_WORD_HTML,
        )
    )
    rows.append(tex_gap_control_gate)
    (
        tex_gap_header_gate,
        tex_gap_header_blocks,
        tex_gap_header_candidates,
        tex_gap_header_dimension_blocks,
        tex_gap_header_best_prefix,
        tex_gap_header_best_exact,
    ) = audit_tex_gap_header_schema_probe(
        DEFAULT_TEX_GAP_HEADER_SCHEMA_SUMMARY,
        DEFAULT_TEX_GAP_HEADER_SCHEMA_FIXTURES,
        DEFAULT_TEX_GAP_HEADER_SCHEMA_BLOCKS,
        DEFAULT_TEX_GAP_HEADER_SCHEMA_PAYLOADS,
        DEFAULT_TEX_GAP_HEADER_SCHEMA_BEST,
        DEFAULT_TEX_GAP_HEADER_SCHEMA_HTML,
    )
    rows.append(tex_gap_header_gate)
    tex_gap_row_stride_gate, tex_gap_row_stride_rows, tex_gap_row_stride_prefix, tex_gap_row_stride_exact = (
        audit_tex_gap_row_stride_probe(
            DEFAULT_TEX_GAP_ROW_STRIDE_SUMMARY,
            DEFAULT_TEX_GAP_ROW_STRIDE_FIXTURES,
            DEFAULT_TEX_GAP_ROW_STRIDE_ROWS,
            DEFAULT_TEX_GAP_ROW_STRIDE_BEST,
            DEFAULT_TEX_GAP_ROW_STRIDE_HTML,
        )
    )
    rows.append(tex_gap_row_stride_gate)
    (
        tex_gap_row_stride_mismatch_gate,
        tex_gap_row_stride_mismatch_candidates,
        tex_gap_row_stride_mismatch_rows,
        tex_gap_row_stride_mismatch_full_rows,
    ) = audit_tex_gap_row_stride_mismatch_probe(
        DEFAULT_TEX_GAP_ROW_STRIDE_MISMATCH_SUMMARY,
        DEFAULT_TEX_GAP_ROW_STRIDE_MISMATCH_CANDIDATES,
        DEFAULT_TEX_GAP_ROW_STRIDE_MISMATCH_ROWS,
        DEFAULT_TEX_GAP_ROW_STRIDE_MISMATCH_HTML,
    )
    rows.append(tex_gap_row_stride_mismatch_gate)
    tex_gap_row_delta_gate, tex_gap_row_delta_rows, tex_gap_row_delta_adjusted, tex_gap_row_delta_gain = (
        audit_tex_gap_row_delta_probe(
            DEFAULT_TEX_GAP_ROW_DELTA_SUMMARY,
            DEFAULT_TEX_GAP_ROW_DELTA_CANDIDATES,
            DEFAULT_TEX_GAP_ROW_DELTA_ROWS,
            DEFAULT_TEX_GAP_ROW_DELTA_HTML,
        )
    )
    rows.append(tex_gap_row_delta_gate)
    (
        tex_gap_row_transform_gate,
        tex_gap_row_transform_rows,
        tex_gap_row_transform_best,
        tex_gap_row_transform_gain,
    ) = audit_tex_gap_row_transform_probe(
        DEFAULT_TEX_GAP_ROW_TRANSFORM_SUMMARY,
        DEFAULT_TEX_GAP_ROW_TRANSFORM_CANDIDATES,
        DEFAULT_TEX_GAP_ROW_TRANSFORM_ROWS,
        DEFAULT_TEX_GAP_ROW_TRANSFORM_HTML,
    )
    rows.append(tex_gap_row_transform_gate)
    (
        tex_gap_row_control_gate,
        tex_gap_row_control_rows,
        tex_gap_row_control_groups,
        tex_gap_row_control_best_metric_hits,
    ) = audit_tex_gap_row_control_probe(
        DEFAULT_TEX_GAP_ROW_CONTROL_SUMMARY,
        DEFAULT_TEX_GAP_ROW_CONTROL_CANDIDATES,
        DEFAULT_TEX_GAP_ROW_CONTROL_ROWS,
        DEFAULT_TEX_GAP_ROW_CONTROL_GROUPS,
        DEFAULT_TEX_GAP_ROW_CONTROL_METRICS,
        DEFAULT_TEX_GAP_ROW_CONTROL_HTML,
    )
    rows.append(tex_gap_row_control_gate)
    (
        tex_gap_row_sequence_gate,
        tex_gap_row_sequence_rows,
        tex_gap_row_sequence_step_groups,
        tex_gap_row_sequence_rewinds,
    ) = audit_tex_gap_row_sequence_probe(
        DEFAULT_TEX_GAP_ROW_SEQUENCE_SUMMARY,
        DEFAULT_TEX_GAP_ROW_SEQUENCE_CANDIDATES,
        DEFAULT_TEX_GAP_ROW_SEQUENCE_ROWS,
        DEFAULT_TEX_GAP_ROW_SEQUENCE_STEPS,
        DEFAULT_TEX_GAP_ROW_SEQUENCE_HTML,
    )
    rows.append(tex_gap_row_sequence_gate)
    (
        tex_gap_row_literal_scan_gate,
        tex_gap_row_literal_scan_rows,
        tex_gap_row_literal_scan_best,
        tex_gap_row_literal_scan_gain,
    ) = audit_tex_gap_row_literal_scan_probe(
        DEFAULT_TEX_GAP_ROW_LITERAL_SCAN_SUMMARY,
        DEFAULT_TEX_GAP_ROW_LITERAL_SCAN_CANDIDATES,
        DEFAULT_TEX_GAP_ROW_LITERAL_SCAN_ROWS,
        DEFAULT_TEX_GAP_ROW_LITERAL_SCAN_HTML,
    )
    rows.append(tex_gap_row_literal_scan_gate)
    (
        tex_gap_row_fill_run_gate,
        tex_gap_row_fill_run_rows,
        tex_gap_row_fill_run_best,
        tex_gap_row_fill_run_full_rows,
    ) = audit_tex_gap_row_fill_run_probe(
        DEFAULT_TEX_GAP_ROW_FILL_RUN_SUMMARY,
        DEFAULT_TEX_GAP_ROW_FILL_RUN_CANDIDATES,
        DEFAULT_TEX_GAP_ROW_FILL_RUN_ROWS,
        DEFAULT_TEX_GAP_ROW_FILL_RUN_MATCHES,
        DEFAULT_TEX_GAP_ROW_FILL_RUN_HTML,
    )
    rows.append(tex_gap_row_fill_run_gate)
    (
        tex_gap_control_grammar_gate,
        tex_gap_control_grammar_rows,
        tex_gap_control_grammar_best_prefix,
        tex_gap_control_grammar_best_exact,
    ) = audit_tex_gap_control_grammar_probe(
        DEFAULT_TEX_GAP_CONTROL_GRAMMAR_SUMMARY,
        DEFAULT_TEX_GAP_CONTROL_GRAMMAR_CANDIDATES,
        DEFAULT_TEX_GAP_CONTROL_GRAMMAR_BEST,
        DEFAULT_TEX_GAP_CONTROL_GRAMMAR_HTML,
    )
    rows.append(tex_gap_control_grammar_gate)
    (
        tex_gap_mismatch_trace_gate,
        tex_gap_mismatch_trace_rows,
        tex_gap_mismatch_trace_ops,
        tex_gap_mismatch_trace_control_prefix,
        tex_gap_mismatch_trace_replay_prefix,
    ) = audit_tex_gap_mismatch_trace_probe(
        DEFAULT_TEX_GAP_MISMATCH_TRACE_SUMMARY,
        DEFAULT_TEX_GAP_MISMATCH_TRACE_ROWS,
        DEFAULT_TEX_GAP_MISMATCH_TRACE_OPS,
        DEFAULT_TEX_GAP_MISMATCH_TRACE_HTML,
    )
    rows.append(tex_gap_mismatch_trace_gate)
    (
        tex_gap_zero_literal_switch_gate,
        tex_gap_zero_literal_switch_rows,
        tex_gap_zero_literal_switch_best_prefix,
        tex_gap_zero_literal_switch_best_exact,
    ) = audit_tex_gap_zero_literal_switch_probe(
        DEFAULT_TEX_GAP_ZERO_LITERAL_SWITCH_SUMMARY,
        DEFAULT_TEX_GAP_ZERO_LITERAL_SWITCH_CANDIDATES,
        DEFAULT_TEX_GAP_ZERO_LITERAL_SWITCH_BEST,
        DEFAULT_TEX_GAP_ZERO_LITERAL_SWITCH_HTML,
    )
    rows.append(tex_gap_zero_literal_switch_gate)
    (
        tex_gap_zero_literal_segmentation_gate,
        tex_gap_zero_literal_segmentation_covered,
        tex_gap_zero_literal_segmentation_gap,
        tex_gap_zero_literal_segmentation_literal,
        tex_gap_zero_literal_segmentation_full_fixtures,
    ) = audit_tex_gap_zero_literal_segmentation_probe(
        DEFAULT_TEX_GAP_ZERO_LITERAL_SEGMENTATION_SUMMARY,
        DEFAULT_TEX_GAP_ZERO_LITERAL_SEGMENTATION_STRATEGIES,
        DEFAULT_TEX_GAP_ZERO_LITERAL_SEGMENTATION_OPS,
        DEFAULT_TEX_GAP_ZERO_LITERAL_SEGMENTATION_BEST,
        DEFAULT_TEX_GAP_ZERO_LITERAL_SEGMENTATION_HTML,
    )
    rows.append(tex_gap_zero_literal_segmentation_gate)
    (
        tex_gap_segmentation_control_correlation_gate,
        tex_gap_segmentation_control_correlation_ops,
        tex_gap_segmentation_control_correlation_literal_ops,
        tex_gap_segmentation_control_correlation_forward_steps,
        tex_gap_segmentation_control_correlation_len_hits,
    ) = audit_tex_gap_segmentation_control_correlation_probe(
        DEFAULT_TEX_GAP_SEGMENTATION_CONTROL_CORRELATION_SUMMARY,
        DEFAULT_TEX_GAP_SEGMENTATION_CONTROL_CORRELATION_OPS,
        DEFAULT_TEX_GAP_SEGMENTATION_CONTROL_CORRELATION_CONTEXTS,
        DEFAULT_TEX_GAP_SEGMENTATION_CONTROL_CORRELATION_DELTAS,
        DEFAULT_TEX_GAP_SEGMENTATION_CONTROL_CORRELATION_HTML,
    )
    rows.append(tex_gap_segmentation_control_correlation_gate)
    (
        tex_gap_literal_token_gate,
        tex_gap_literal_token_match_ops,
        tex_gap_literal_token_match_bytes,
        tex_gap_literal_token_full_fixtures,
        tex_gap_literal_token_small_matches,
    ) = audit_tex_gap_literal_token_probe(
        DEFAULT_TEX_GAP_LITERAL_TOKEN_SUMMARY,
        DEFAULT_TEX_GAP_LITERAL_TOKEN_RULES,
        DEFAULT_TEX_GAP_LITERAL_TOKEN_LITERALS,
        DEFAULT_TEX_GAP_LITERAL_TOKEN_TOKENS,
        DEFAULT_TEX_GAP_LITERAL_TOKEN_FIXTURES,
        DEFAULT_TEX_GAP_LITERAL_TOKEN_HTML,
    )
    rows.append(tex_gap_literal_token_gate)
    (
        tex_gap_literal_token_classifier_gate,
        tex_gap_literal_token_classifier_small_fp,
        tex_gap_literal_token_classifier_high_recall_fp,
        tex_gap_literal_token_classifier_high_precision_fp,
        tex_gap_literal_token_classifier_rows,
    ) = audit_tex_gap_literal_token_classifier_probe(
        DEFAULT_TEX_GAP_LITERAL_TOKEN_CLASSIFIER_SUMMARY,
        DEFAULT_TEX_GAP_LITERAL_TOKEN_CLASSIFIER_ROWS,
        DEFAULT_TEX_GAP_LITERAL_TOKEN_CLASSIFIER_ERRORS,
        DEFAULT_TEX_GAP_LITERAL_TOKEN_CLASSIFIER_FIXTURES,
        DEFAULT_TEX_GAP_LITERAL_TOKEN_LITERALS,
        DEFAULT_TEX_GAP_LITERAL_TOKEN_CLASSIFIER_HTML,
    )
    rows.append(tex_gap_literal_token_classifier_gate)
    (
        tex_gap_literal_fp_rejection_gate,
        tex_gap_literal_fp_rejection_full_recall_fp,
        tex_gap_literal_fp_rejection_full_recall_false_bytes,
        tex_gap_literal_fp_rejection_low_false_fp,
        tex_gap_literal_fp_rejection_candidate_rows,
    ) = audit_tex_gap_literal_fp_rejection_probe(
        DEFAULT_TEX_GAP_LITERAL_FP_REJECTION_SUMMARY,
        DEFAULT_TEX_GAP_LITERAL_FP_REJECTION_ROWS,
        DEFAULT_TEX_GAP_LITERAL_FP_REJECTION_REJECTIONS,
        DEFAULT_TEX_GAP_LITERAL_FP_REJECTION_FIXTURES,
        DEFAULT_TEX_GAP_LITERAL_TOKEN_LITERALS,
        DEFAULT_TEX_GAP_SEGMENTATION_CONTROL_CORRELATION_OPS,
        DEFAULT_TEX_GAP_LITERAL_FP_REJECTION_HTML,
    )
    rows.append(tex_gap_literal_fp_rejection_gate)
    (
        tex_gap_zero_run_alignment_gate,
        tex_gap_zero_run_alignment_zero_ops,
        tex_gap_zero_run_alignment_zero_bytes,
        tex_gap_zero_run_alignment_len64_ops,
        tex_gap_zero_run_alignment_fill_mod64_ops,
    ) = audit_tex_gap_zero_run_alignment_probe(
        DEFAULT_TEX_GAP_ZERO_RUN_ALIGNMENT_SUMMARY,
        DEFAULT_TEX_GAP_ZERO_RUN_ALIGNMENT_ZERO_ROWS,
        DEFAULT_TEX_GAP_ZERO_RUN_ALIGNMENT_LENGTHS,
        DEFAULT_TEX_GAP_ZERO_RUN_ALIGNMENT_TRANSITIONS,
        DEFAULT_TEX_GAP_ZERO_RUN_ALIGNMENT_FIXTURES,
        DEFAULT_TEX_GAP_SEGMENTATION_CONTROL_CORRELATION_OPS,
        DEFAULT_TEX_GAP_ZERO_RUN_ALIGNMENT_HTML,
    )
    rows.append(tex_gap_zero_run_alignment_gate)
    (
        tex_gap_zero_control_risk_gate,
        tex_gap_zero_control_risk_current_false_bytes,
        tex_gap_zero_control_risk_false_free_bytes,
        tex_gap_zero_control_risk_low_false_bytes,
        tex_gap_zero_control_risk_classifier_rows,
    ) = audit_tex_gap_zero_control_risk_probe(
        DEFAULT_TEX_GAP_ZERO_CONTROL_RISK_SUMMARY,
        DEFAULT_TEX_GAP_ZERO_CONTROL_RISK_ROWS,
        DEFAULT_TEX_GAP_ZERO_CONTROL_RISK_FALSE_POSITIVES,
        DEFAULT_TEX_GAP_ZERO_CONTROL_RISK_KINDS,
        DEFAULT_TEX_GAP_ZERO_CONTROL_RISK_FIXTURES,
        DEFAULT_TEX_GAP_SEGMENTATION_CONTROL_CORRELATION_OPS,
        DEFAULT_TEX_GAP_ZERO_CONTROL_RISK_HTML,
    )
    rows.append(tex_gap_zero_control_risk_gate)
    (
        tex_gap_decoder_skeleton_candidate_gate,
        tex_gap_decoder_skeleton_best_nonoracle_bytes,
        tex_gap_decoder_skeleton_best_nonoracle_false,
        tex_gap_decoder_skeleton_best_oracle_bytes,
        tex_gap_decoder_skeleton_candidate_rows,
    ) = audit_tex_gap_decoder_skeleton_candidate_probe(
        DEFAULT_TEX_GAP_DECODER_SKELETON_CANDIDATE_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_SKELETON_CANDIDATE_ROWS,
        DEFAULT_TEX_GAP_DECODER_SKELETON_CANDIDATE_FIXTURES,
        DEFAULT_TEX_GAP_SEGMENTATION_CONTROL_CORRELATION_OPS,
        DEFAULT_TEX_GAP_DECODER_SKELETON_CANDIDATE_HTML,
    )
    rows.append(tex_gap_decoder_skeleton_candidate_gate)
    (
        tex_gap_decoder_risk_adjusted_gate,
        tex_gap_decoder_risk_adjusted_best_correct_bytes,
        tex_gap_decoder_risk_adjusted_best_false_bytes,
        tex_gap_decoder_risk_adjusted_best_net_bytes,
        tex_gap_decoder_risk_adjusted_best_low_false_bytes,
        tex_gap_decoder_risk_adjusted_candidate_rows,
    ) = audit_tex_gap_decoder_risk_adjusted_probe(
        DEFAULT_TEX_GAP_DECODER_RISK_ADJUSTED_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_RISK_ADJUSTED_ROWS,
        DEFAULT_TEX_GAP_DECODER_RISK_ADJUSTED_FIXTURES,
        DEFAULT_TEX_GAP_SEGMENTATION_CONTROL_CORRELATION_OPS,
        DEFAULT_TEX_GAP_LITERAL_TOKEN_LITERALS,
        DEFAULT_TEX_GAP_DECODER_RISK_ADJUSTED_HTML,
    )
    rows.append(tex_gap_decoder_risk_adjusted_gate)
    (
        tex_gap_decoder_seed_replay_gate,
        tex_gap_decoder_seed_replay_selected_bytes,
        tex_gap_decoder_seed_replay_trusted_bytes,
        tex_gap_decoder_seed_replay_false_bytes,
        tex_gap_decoder_seed_replay_fixture_rows,
        tex_gap_decoder_seed_replay_fullhd_previews,
    ) = audit_tex_gap_decoder_seed_replay(
        DEFAULT_TEX_GAP_DECODER_SEED_REPLAY_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_SEED_REPLAY_FIXTURES,
        DEFAULT_TEX_GAP_DECODER_SEED_REPLAY_DECISIONS,
        DEFAULT_TEX_GAP_DECODER_SEED_REPLAY_HTML,
    )
    rows.append(tex_gap_decoder_seed_replay_gate)
    (
        tex_gap_decoder_control_promotion_gate,
        tex_gap_decoder_control_promotion_bytes,
        tex_gap_decoder_control_promotion_literal_bytes,
        tex_gap_decoder_control_promotion_zero_bytes,
        tex_gap_decoder_control_promotion_ambiguous_groups,
    ) = audit_tex_gap_decoder_control_promotion_probe(
        DEFAULT_TEX_GAP_DECODER_CONTROL_PROMOTION_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_CONTROL_PROMOTION_SELECTORS,
        DEFAULT_TEX_GAP_DECODER_CONTROL_PROMOTION_SIGNATURES,
        DEFAULT_TEX_GAP_DECODER_CONTROL_PROMOTION_FIXTURES,
        DEFAULT_TEX_GAP_DECODER_CONTROL_PROMOTION_HTML,
    )
    rows.append(tex_gap_decoder_control_promotion_gate)
    (
        tex_gap_decoder_false_risk_queue_gate,
        tex_gap_decoder_false_risk_promoted_bytes,
        tex_gap_decoder_false_risk_rejected_bytes,
        tex_gap_decoder_false_risk_review_bytes,
        tex_gap_decoder_false_risk_safe_rejectors,
    ) = audit_tex_gap_decoder_false_risk_queue(
        DEFAULT_TEX_GAP_DECODER_FALSE_RISK_QUEUE_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_FALSE_RISK_QUEUE_ROWS,
        DEFAULT_TEX_GAP_DECODER_FALSE_RISK_QUEUE_REJECTORS,
        DEFAULT_TEX_GAP_DECODER_FALSE_RISK_QUEUE_FIXTURES,
        DEFAULT_TEX_GAP_DECODER_FALSE_RISK_QUEUE_HTML,
    )
    rows.append(tex_gap_decoder_false_risk_queue_gate)
    (
        tex_gap_decoder_clean_replay_gate,
        tex_gap_decoder_clean_replay_bytes,
        tex_gap_decoder_clean_replay_rejected_bytes,
        tex_gap_decoder_clean_replay_fullhd_previews,
    ) = audit_tex_gap_decoder_clean_replay(
        DEFAULT_TEX_GAP_DECODER_CLEAN_REPLAY_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_CLEAN_REPLAY_FIXTURES,
        DEFAULT_TEX_GAP_DECODER_CLEAN_REPLAY_DECISIONS,
        DEFAULT_TEX_GAP_DECODER_CLEAN_REPLAY_HTML,
    )
    rows.append(tex_gap_decoder_clean_replay_gate)
    (
        tex_gap_decoder_clean_gap_queue_gate,
        tex_gap_decoder_clean_gap_unresolved_bytes,
        tex_gap_decoder_clean_gap_span_rows,
        tex_gap_decoder_clean_gap_largest_span,
    ) = audit_tex_gap_decoder_clean_gap_queue(
        DEFAULT_TEX_GAP_DECODER_CLEAN_GAP_QUEUE_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_CLEAN_GAP_QUEUE_SPANS,
        DEFAULT_TEX_GAP_DECODER_CLEAN_GAP_QUEUE_FIXTURES,
        DEFAULT_TEX_GAP_DECODER_CLEAN_GAP_QUEUE_HTML,
    )
    rows.append(tex_gap_decoder_clean_gap_queue_gate)
    (
        tex_gap_decoder_unresolved_run_gate,
        tex_gap_decoder_unresolved_run_zero_bytes,
        tex_gap_decoder_unresolved_run_rows,
        tex_gap_decoder_unresolved_run_max_zero,
    ) = audit_tex_gap_decoder_unresolved_run_probe(
        DEFAULT_TEX_GAP_DECODER_UNRESOLVED_RUN_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_UNRESOLVED_RUN_SPANS,
        DEFAULT_TEX_GAP_DECODER_UNRESOLVED_RUN_RUNS,
        DEFAULT_TEX_GAP_DECODER_UNRESOLVED_RUN_FIXTURES,
        DEFAULT_TEX_GAP_DECODER_UNRESOLVED_RUN_HTML,
    )
    rows.append(tex_gap_decoder_unresolved_run_gate)
    (
        tex_gap_decoder_unresolved_zero_queue_gate,
        tex_gap_decoder_unresolved_zero_queue_bytes,
        tex_gap_decoder_unresolved_zero_queue_internal_bytes,
        tex_gap_decoder_unresolved_zero_queue_signatures,
    ) = audit_tex_gap_decoder_unresolved_zero_queue(
        DEFAULT_TEX_GAP_DECODER_UNRESOLVED_ZERO_QUEUE_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_UNRESOLVED_ZERO_QUEUE_ROWS,
        DEFAULT_TEX_GAP_DECODER_UNRESOLVED_ZERO_QUEUE_SIGNATURES,
        DEFAULT_TEX_GAP_DECODER_UNRESOLVED_ZERO_QUEUE_FIXTURES,
        DEFAULT_TEX_GAP_DECODER_UNRESOLVED_ZERO_QUEUE_HTML,
    )
    rows.append(tex_gap_decoder_unresolved_zero_queue_gate)
    (
        tex_gap_decoder_len64_internal_gate,
        tex_gap_decoder_len64_internal_rows,
        tex_gap_decoder_len64_internal_bytes,
        tex_gap_decoder_len64_internal_top_neighbor_rows,
    ) = audit_tex_gap_decoder_len64_internal_probe(
        DEFAULT_TEX_GAP_DECODER_LEN64_INTERNAL_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_LEN64_INTERNAL_TARGETS,
        DEFAULT_TEX_GAP_DECODER_LEN64_INTERNAL_NEIGHBORS,
        DEFAULT_TEX_GAP_DECODER_LEN64_INTERNAL_FIXTURES,
        DEFAULT_TEX_GAP_DECODER_LEN64_INTERNAL_HTML,
    )
    rows.append(tex_gap_decoder_len64_internal_gate)
    (
        tex_gap_decoder_len64_source_gate,
        tex_gap_decoder_len64_source_joined_rows,
        tex_gap_decoder_len64_source_control_refs,
        tex_gap_decoder_len64_source_top_ref_rows,
    ) = audit_tex_gap_decoder_len64_source_probe(
        DEFAULT_TEX_GAP_DECODER_LEN64_SOURCE_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_LEN64_SOURCE_TARGETS,
        DEFAULT_TEX_GAP_DECODER_LEN64_SOURCE_CONTROLS,
        DEFAULT_TEX_GAP_DECODER_LEN64_SOURCE_REFS,
        DEFAULT_TEX_GAP_DECODER_LEN64_SOURCE_HTML,
    )
    rows.append(tex_gap_decoder_len64_source_gate)
    (
        tex_gap_decoder_len64_selector_gate,
        tex_gap_decoder_len64_selector_best_bytes,
        tex_gap_decoder_len64_selector_greedy_bytes,
        tex_gap_decoder_len64_selector_greedy_selectors,
    ) = audit_tex_gap_decoder_len64_selector_probe(
        DEFAULT_TEX_GAP_DECODER_LEN64_SELECTOR_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_LEN64_SELECTOR_CANDIDATES,
        DEFAULT_TEX_GAP_DECODER_LEN64_SELECTOR_GREEDY,
        DEFAULT_TEX_GAP_DECODER_LEN64_SELECTOR_TARGETS,
        DEFAULT_TEX_GAP_DECODER_LEN64_SELECTOR_HTML,
    )
    rows.append(tex_gap_decoder_len64_selector_gate)
    (
        tex_gap_decoder_len64_promoted_gate,
        tex_gap_decoder_len64_promoted_added_bytes,
        tex_gap_decoder_len64_promoted_total_clean_bytes,
        tex_gap_decoder_len64_promoted_remaining_unresolved_bytes,
    ) = audit_tex_gap_decoder_len64_promoted_replay(
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_FIXTURES,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_PROMOTIONS,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_HTML,
    )
    rows.append(tex_gap_decoder_len64_promoted_gate)
    (
        tex_gap_decoder_len64_promoted_gap_gate,
        tex_gap_decoder_len64_promoted_gap_unresolved_bytes,
        tex_gap_decoder_len64_promoted_gap_span_rows,
        tex_gap_decoder_len64_promoted_gap_largest_span,
    ) = audit_tex_gap_decoder_len64_promoted_gap_queue(
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_GAP_QUEUE_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_GAP_QUEUE_SPANS,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_GAP_QUEUE_FIXTURES,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_GAP_QUEUE_HTML,
    )
    rows.append(tex_gap_decoder_len64_promoted_gap_gate)
    (
        tex_gap_decoder_len64_promoted_run_gate,
        tex_gap_decoder_len64_promoted_run_zero_bytes,
        tex_gap_decoder_len64_promoted_run_rows,
        tex_gap_decoder_len64_promoted_run_max_zero,
    ) = audit_tex_gap_decoder_len64_promoted_run_probe(
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_RUN_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_RUN_SPANS,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_RUN_RUNS,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_RUN_FIXTURES,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_RUN_HTML,
    )
    rows.append(tex_gap_decoder_len64_promoted_run_gate)
    (
        tex_gap_decoder_len64_promoted_zero_queue_gate,
        tex_gap_decoder_len64_promoted_zero_queue_bytes,
        tex_gap_decoder_len64_promoted_zero_queue_internal_bytes,
        tex_gap_decoder_len64_promoted_zero_queue_signatures,
    ) = audit_tex_gap_decoder_len64_promoted_zero_queue(
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_ZERO_QUEUE_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_ZERO_QUEUE_ROWS,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_ZERO_QUEUE_SIGNATURES,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_ZERO_QUEUE_FIXTURES,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_ZERO_QUEUE_HTML,
    )
    rows.append(tex_gap_decoder_len64_promoted_zero_queue_gate)
    (
        tex_gap_decoder_len64_promoted_zero_source_gate,
        tex_gap_decoder_len64_promoted_zero_source_joined_rows,
        tex_gap_decoder_len64_promoted_zero_source_joined_bytes,
        tex_gap_decoder_len64_promoted_zero_source_control_refs,
    ) = audit_tex_gap_decoder_len64_promoted_zero_source_probe(
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_ZERO_SOURCE_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_ZERO_SOURCE_TARGETS,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_ZERO_SOURCE_CONTROLS,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_ZERO_SOURCE_REFS,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_ZERO_SOURCE_HTML,
    )
    rows.append(tex_gap_decoder_len64_promoted_zero_source_gate)
    (
        tex_gap_decoder_len64_promoted_large32_selector_gate,
        tex_gap_decoder_len64_promoted_large32_selector_best_bytes,
        tex_gap_decoder_len64_promoted_large32_selector_greedy_bytes,
        tex_gap_decoder_len64_promoted_large32_selector_greedy_selectors,
    ) = audit_tex_gap_decoder_len64_promoted_large32_selector_probe(
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_SELECTOR_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_SELECTOR_CANDIDATES,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_SELECTOR_GREEDY,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_SELECTOR_TARGETS,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_SELECTOR_HTML,
    )
    rows.append(tex_gap_decoder_len64_promoted_large32_selector_gate)
    (
        tex_gap_decoder_len64_promoted_large32_replay_gate,
        tex_gap_decoder_len64_promoted_large32_replay_added_bytes,
        tex_gap_decoder_len64_promoted_large32_replay_total_clean_bytes,
        tex_gap_decoder_len64_promoted_large32_replay_remaining_unresolved_bytes,
    ) = audit_tex_gap_decoder_len64_promoted_large32_replay(
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_REPLAY_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_REPLAY_FIXTURES,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_REPLAY_PROMOTIONS,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_REPLAY_HTML,
    )
    rows.append(tex_gap_decoder_len64_promoted_large32_replay_gate)
    (
        tex_gap_decoder_len64_promoted_large32_gap_gate,
        tex_gap_decoder_len64_promoted_large32_gap_unresolved_bytes,
        tex_gap_decoder_len64_promoted_large32_gap_span_rows,
        tex_gap_decoder_len64_promoted_large32_gap_largest_span,
    ) = audit_tex_gap_decoder_len64_promoted_large32_gap_queue(
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_GAP_QUEUE_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_GAP_QUEUE_SPANS,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_GAP_QUEUE_FIXTURES,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_GAP_QUEUE_HTML,
    )
    rows.append(tex_gap_decoder_len64_promoted_large32_gap_gate)
    (
        tex_gap_decoder_len64_promoted_large32_run_gate,
        tex_gap_decoder_len64_promoted_large32_run_zero_bytes,
        tex_gap_decoder_len64_promoted_large32_run_rows,
        tex_gap_decoder_len64_promoted_large32_run_max_zero,
    ) = audit_tex_gap_decoder_len64_promoted_large32_run_probe(
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_RUN_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_RUN_SPANS,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_RUN_RUNS,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_RUN_FIXTURES,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_RUN_HTML,
    )
    rows.append(tex_gap_decoder_len64_promoted_large32_run_gate)
    (
        tex_gap_decoder_len64_promoted_large32_zero_queue_gate,
        tex_gap_decoder_len64_promoted_large32_zero_queue_bytes,
        tex_gap_decoder_len64_promoted_large32_zero_queue_internal_bytes,
        tex_gap_decoder_len64_promoted_large32_zero_queue_signatures,
    ) = audit_tex_gap_decoder_len64_promoted_large32_zero_queue(
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_ZERO_QUEUE_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_ZERO_QUEUE_ROWS,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_ZERO_QUEUE_SIGNATURES,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_ZERO_QUEUE_FIXTURES,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_ZERO_QUEUE_HTML,
    )
    rows.append(tex_gap_decoder_len64_promoted_large32_zero_queue_gate)
    (
        tex_gap_decoder_len64_promoted_large32_zero_source_gate,
        tex_gap_decoder_len64_promoted_large32_zero_source_joined_rows,
        tex_gap_decoder_len64_promoted_large32_zero_source_joined_bytes,
        tex_gap_decoder_len64_promoted_large32_zero_source_control_refs,
    ) = audit_tex_gap_decoder_len64_promoted_large32_zero_source_probe(
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_ZERO_SOURCE_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_ZERO_SOURCE_TARGETS,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_ZERO_SOURCE_CONTROLS,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_ZERO_SOURCE_REFS,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_ZERO_SOURCE_HTML,
    )
    rows.append(tex_gap_decoder_len64_promoted_large32_zero_source_gate)
    (
        tex_gap_decoder_len64_promoted_medium8_selector_gate,
        tex_gap_decoder_len64_promoted_medium8_selector_best_bytes,
        tex_gap_decoder_len64_promoted_medium8_selector_greedy_bytes,
        tex_gap_decoder_len64_promoted_medium8_selector_greedy_selectors,
    ) = audit_tex_gap_decoder_len64_promoted_medium8_selector_probe(
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_SELECTOR_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_SELECTOR_CANDIDATES,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_SELECTOR_GREEDY,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_SELECTOR_TARGETS,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_SELECTOR_HTML,
    )
    rows.append(tex_gap_decoder_len64_promoted_medium8_selector_gate)
    (
        tex_gap_decoder_len64_promoted_medium8_replay_gate,
        tex_gap_decoder_len64_promoted_medium8_replay_added_bytes,
        tex_gap_decoder_len64_promoted_medium8_replay_total_clean_bytes,
        tex_gap_decoder_len64_promoted_medium8_replay_remaining_unresolved_bytes,
    ) = audit_tex_gap_decoder_len64_promoted_medium8_replay(
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_REPLAY_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_REPLAY_FIXTURES,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_REPLAY_PROMOTIONS,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_REPLAY_HTML,
    )
    rows.append(tex_gap_decoder_len64_promoted_medium8_replay_gate)
    (
        tex_gap_decoder_len64_promoted_medium8_gap_gate,
        tex_gap_decoder_len64_promoted_medium8_gap_unresolved_bytes,
        tex_gap_decoder_len64_promoted_medium8_gap_span_rows,
        tex_gap_decoder_len64_promoted_medium8_gap_largest_span,
    ) = audit_tex_gap_decoder_len64_promoted_medium8_gap_queue(
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_GAP_QUEUE_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_GAP_QUEUE_SPANS,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_GAP_QUEUE_FIXTURES,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_GAP_QUEUE_HTML,
    )
    rows.append(tex_gap_decoder_len64_promoted_medium8_gap_gate)
    (
        tex_gap_decoder_len64_promoted_medium8_run_gate,
        tex_gap_decoder_len64_promoted_medium8_run_zero_bytes,
        tex_gap_decoder_len64_promoted_medium8_run_rows,
        tex_gap_decoder_len64_promoted_medium8_run_max_zero,
    ) = audit_tex_gap_decoder_len64_promoted_medium8_run_probe(
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_RUN_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_RUN_SPANS,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_RUN_RUNS,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_RUN_FIXTURES,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_RUN_HTML,
    )
    rows.append(tex_gap_decoder_len64_promoted_medium8_run_gate)
    (
        tex_gap_decoder_len64_promoted_medium8_zero_queue_gate,
        tex_gap_decoder_len64_promoted_medium8_zero_queue_bytes,
        tex_gap_decoder_len64_promoted_medium8_zero_queue_internal_bytes,
        tex_gap_decoder_len64_promoted_medium8_zero_queue_signatures,
    ) = audit_tex_gap_decoder_len64_promoted_medium8_zero_queue(
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_ZERO_QUEUE_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_ZERO_QUEUE_ROWS,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_ZERO_QUEUE_SIGNATURES,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_ZERO_QUEUE_FIXTURES,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_ZERO_QUEUE_HTML,
    )
    rows.append(tex_gap_decoder_len64_promoted_medium8_zero_queue_gate)
    (
        tex_gap_decoder_len64_promoted_medium8_zero_source_gate,
        tex_gap_decoder_len64_promoted_medium8_zero_source_joined_rows,
        tex_gap_decoder_len64_promoted_medium8_zero_source_joined_bytes,
        tex_gap_decoder_len64_promoted_medium8_zero_source_control_refs,
    ) = audit_tex_gap_decoder_len64_promoted_medium8_zero_source_probe(
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_ZERO_SOURCE_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_ZERO_SOURCE_TARGETS,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_ZERO_SOURCE_CONTROLS,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_ZERO_SOURCE_REFS,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_ZERO_SOURCE_HTML,
    )
    rows.append(tex_gap_decoder_len64_promoted_medium8_zero_source_gate)
    (
        tex_gap_decoder_len64_promoted_medium8_remaining_selector_gate,
        tex_gap_decoder_len64_promoted_medium8_remaining_selector_best_bytes,
        tex_gap_decoder_len64_promoted_medium8_remaining_selector_greedy_bytes,
        tex_gap_decoder_len64_promoted_medium8_remaining_selector_greedy_selectors,
    ) = audit_tex_gap_decoder_len64_promoted_medium8_remaining_selector_probe(
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_REMAINING_SELECTOR_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_REMAINING_SELECTOR_CANDIDATES,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_REMAINING_SELECTOR_GREEDY,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_REMAINING_SELECTOR_TARGETS,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_REMAINING_SELECTOR_HTML,
    )
    rows.append(tex_gap_decoder_len64_promoted_medium8_remaining_selector_gate)
    (
        tex_gap_decoder_len64_promoted_large32_remaining_selector_gate,
        tex_gap_decoder_len64_promoted_large32_remaining_selector_best_bytes,
        tex_gap_decoder_len64_promoted_large32_remaining_selector_greedy_bytes,
        tex_gap_decoder_len64_promoted_large32_remaining_selector_greedy_selectors,
    ) = audit_tex_gap_decoder_len64_promoted_large32_remaining_selector_probe(
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_REMAINING_SELECTOR_SUMMARY,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_REMAINING_SELECTOR_CANDIDATES,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_REMAINING_SELECTOR_GREEDY,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_REMAINING_SELECTOR_TARGETS,
        DEFAULT_TEX_GAP_DECODER_LEN64_PROMOTED_LARGE32_REMAINING_SELECTOR_HTML,
    )
    rows.append(tex_gap_decoder_len64_promoted_large32_remaining_selector_gate)

    def append_signature_selector_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "candidates.csv",
                    directory / "greedy.csv",
                    directory / "targets.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_signature",
                    "target_rows",
                    "target_bytes",
                    "best_selector_target_bytes",
                    "best_selector_false_bytes",
                    "greedy_target_bytes",
                    "greedy_false_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_SIGNATURE_SELECTOR_PROBE",
                zero_false_fields=["best_selector_false_bytes", "greedy_false_bytes"],
                positive_fields=["target_rows", "target_bytes"],
            )
        )

    def append_replay_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[directory / "fixtures.csv", directory / "promotions.csv"],
                html_report=directory / "index.html",
                expected_fields=[
                    "fixture_rows",
                    "target_rows",
                    "promoted_target_rows",
                    "selector_added_bytes",
                    "selector_false_bytes",
                    "remaining_unresolved_bytes",
                    "fullhd_previews",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_REMAINING_REPLAY",
                zero_false_fields=["selector_false_bytes"],
                positive_fields=["fixture_rows", "target_rows", "selector_added_bytes"],
                fullhd_previews_match_fixtures=True,
            )
        )

    def append_nonzero_fill_replay_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "fixtures.csv",
                    directory / "promotions.csv",
                    directory / "rules.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "fixture_rows",
                    "candidate_rule_rows",
                    "selected_rule_rows",
                    "target_rows",
                    "selected_target_rows",
                    "base_clean_bytes",
                    "fill_added_bytes",
                    "fill_exact_bytes",
                    "fill_false_bytes",
                    "total_clean_bytes",
                    "rejected_false_bytes",
                    "remaining_unresolved_bytes",
                    "fullhd_previews",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_TINY_NONZERO_FILL_REPLAY",
                zero_false_fields=["fill_false_bytes"],
                positive_fields=[
                    "fixture_rows",
                    "candidate_rule_rows",
                    "selected_rule_rows",
                    "target_rows",
                    "selected_target_rows",
                    "base_clean_bytes",
                    "fill_added_bytes",
                    "fill_exact_bytes",
                    "total_clean_bytes",
                    "remaining_unresolved_bytes",
                    "fullhd_previews",
                ],
                fullhd_previews_match_fixtures=True,
            )
        )

    def append_gap_queue_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[directory / "spans.csv", directory / "by_fixture.csv"],
                html_report=directory / "index.html",
                expected_fields=[
                    "fixture_rows",
                    "clean_bytes",
                    "selector_added_bytes",
                    "unresolved_bytes",
                    "span_rows",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_GAP_QUEUE",
                positive_fields=["fixture_rows", "clean_bytes", "unresolved_bytes", "span_rows"],
            )
        )

    def append_run_probe_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[directory / "by_span.csv", directory / "runs.csv", directory / "by_fixture.csv"],
                html_report=directory / "index.html",
                expected_fields=[
                    "fixture_rows",
                    "run_rows",
                    "zero_run_rows",
                    "zero_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_RUN_PROBE",
                positive_fields=["fixture_rows", "run_rows", "zero_run_rows", "zero_bytes"],
            )
        )

    def append_zero_queue_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[directory / "queue.csv", directory / "by_signature.csv", directory / "by_fixture.csv"],
                html_report=directory / "index.html",
                expected_fields=[
                    "zero_run_rows",
                    "zero_bytes",
                    "internal_zero_bytes",
                    "signature_rows",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_ZERO_QUEUE",
                positive_fields=["zero_run_rows", "zero_bytes", "signature_rows"],
            )
        )

    def append_zero_source_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_control_window.csv",
                    directory / "by_control_ref.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "joined_rows",
                    "target_bytes",
                    "joined_bytes",
                    "missing_rows",
                    "unique_control_refs",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_MEDIUM8_ZERO_SOURCE_PROBE",
                zero_issue_rows=False,
                positive_fields=["target_rows", "joined_rows", "target_bytes", "joined_bytes"],
            )
        )

    def append_nonzero_queue_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "queue.csv",
                    directory / "by_signature.csv",
                    directory / "by_fixture.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "nonzero_run_rows",
                    "nonzero_bytes",
                    "pure_nonzero_span_bytes",
                    "signature_rows",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_QUEUE",
                positive_fields=["nonzero_run_rows", "nonzero_bytes", "signature_rows"],
            )
        )

    def append_nonzero_source_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_control_window.csv",
                    directory / "by_control_ref.csv",
                    directory / "by_op_kind.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "joined_rows",
                    "target_bytes",
                    "joined_bytes",
                    "literal_bytes",
                    "gap_bytes",
                    "missing_rows",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_SOURCE_PROBE",
                zero_issue_rows=False,
                positive_fields=["target_rows", "joined_rows", "target_bytes", "joined_bytes"],
            )
        )

    def append_nonzero_gap_source_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "candidates.csv",
                    directory / "best_by_target.csv",
                    directory / "by_transform.csv",
                    directory / "by_offset_delta.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "candidate_rows_evaluated",
                    "best_rows",
                    "best_exact_bytes_total",
                    "full_match_rows",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_SOURCE_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "candidate_rows_evaluated",
                    "best_rows",
                    "best_exact_bytes_total",
                ],
            )
        )

    def append_nonzero_gap_pattern_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "patterns.csv",
                    directory / "by_pattern_class.csv",
                    directory / "by_dominant_byte.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "pattern_classes",
                    "small_palette_bytes",
                    "noisy_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_PATTERN_PROBE",
                positive_fields=["target_rows", "target_bytes", "pattern_classes"],
            )
        )

    def append_nonzero_gap_control_pattern_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "target_annotations.csv",
                    directory / "selector_candidates.csv",
                    directory / "by_pattern_control.csv",
                    directory / "by_best_transform.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "structured_bytes",
                    "selector_groups",
                    "pure_selector_groups",
                    "repeated_pure_selector_groups",
                    "strong_pure_selector_groups",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_CONTROL_PATTERN_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "structured_bytes",
                    "selector_groups",
                    "pure_selector_groups",
                ],
            )
        )

    def append_nonzero_gap_value_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "value_rows.csv",
                    directory / "by_best_value_source.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "control_identity_full_unique_bytes",
                    "control_fixed_full_unique_bytes",
                    "control_any_full_unique_bytes",
                    "best_full_unique_bytes",
                    "best_fixed_full_unique_bytes",
                    "best_fixed_exact_sequence_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_VALUE_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "control_identity_full_unique_bytes",
                    "best_fixed_full_unique_bytes",
                ],
            )
        )

    def append_nonzero_gap_exact_sequence_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "candidates.csv",
                    directory / "by_pool_transform.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "exact_rows",
                    "exact_bytes",
                    "candidate_rows",
                    "ambiguous_exact_rows",
                    "max_exact_length",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_EXACT_SEQUENCE_PROBE",
                positive_fields=["target_rows", "target_bytes", "exact_rows", "candidate_rows"],
            )
        )

    def append_nonzero_gap_fill_rule_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "candidates.csv",
                    directory / "by_pool_transform.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "candidate_rows",
                    "covered_rows",
                    "covered_bytes",
                    "control_identity_bytes",
                    "control_fixed_bytes",
                    "ambiguous_rows",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_FILL_RULE_PROBE",
                positive_fields=["target_rows", "target_bytes", "candidate_rows", "covered_rows", "covered_bytes"],
            )
        )

    def append_nonzero_gap_fill_selector_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "rule_candidates.csv",
                    directory / "by_rule_family.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "rule_rows",
                    "false_free_rule_rows",
                    "false_free_multirow_rule_rows",
                    "best_false_free_correct_bytes",
                    "best_any_correct_bytes",
                    "best_any_false_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_FILL_SELECTOR_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "rule_rows",
                    "false_free_rule_rows",
                    "best_false_free_correct_bytes",
                ],
            )
        )

    def append_nonzero_gap_palette_selector_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "rule_candidates.csv",
                    directory / "by_rule_family.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "small_palette_2_bytes",
                    "small_palette_4_bytes",
                    "rule_rows",
                    "false_free_rule_rows",
                    "false_free_multirow_rule_rows",
                    "best_false_free_correct_bytes",
                    "best_false_free_exact_bytes",
                    "best_any_correct_bytes",
                    "best_any_false_bytes",
                    "best_any_exact_bytes",
                    "exact_false_free_rule_rows",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_PALETTE_SELECTOR_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "small_palette_2_bytes",
                    "small_palette_4_bytes",
                    "rule_rows",
                    "false_free_rule_rows",
                    "best_false_free_correct_bytes",
                ],
            )
        )

    def append_nonzero_gap_palette_shape_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_first_use_shape.csv",
                    directory / "by_run_length_shape.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "small_palette_2_bytes",
                    "small_palette_4_bytes",
                    "first_use_shape_groups",
                    "first_use_repeated_groups",
                    "first_use_repeated_bytes",
                    "run_length_shape_groups",
                    "run_length_repeated_groups",
                    "run_length_repeated_bytes",
                    "best_first_use_shape_bytes",
                    "best_run_length_shape_bytes",
                    "alternating_bytes",
                    "dominant75_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_PALETTE_SHAPE_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "first_use_shape_groups",
                    "first_use_repeated_bytes",
                    "run_length_shape_groups",
                    "run_length_repeated_bytes",
                ],
            )
        )

    def append_nonzero_gap_palette_shape_control_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "selector_candidates.csv",
                    directory / "by_selector_family.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "selector_rows",
                    "pure_selector_rows",
                    "repeated_pure_selector_rows",
                    "repeated_pure_covered_rows",
                    "repeated_pure_covered_bytes",
                    "best_pure_rows",
                    "best_pure_bytes",
                    "best_repeated_pure_rows",
                    "best_repeated_pure_bytes",
                    "selector_families",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_PALETTE_SHAPE_CONTROL_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "selector_rows",
                    "pure_selector_rows",
                    "repeated_pure_selector_rows",
                    "repeated_pure_covered_bytes",
                ],
            )
        )

    def append_nonzero_gap_palette_shape_value_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "rule_candidates.csv",
                    directory / "by_rule_family.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "small_palette_2_bytes",
                    "small_palette_4_bytes",
                    "rule_rows",
                    "false_free_rule_rows",
                    "false_free_multirow_rule_rows",
                    "best_false_free_correct_bytes",
                    "best_false_free_exact_bytes",
                    "best_any_correct_bytes",
                    "best_any_false_bytes",
                    "best_any_exact_bytes",
                    "exact_false_free_rule_rows",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_PALETTE_SHAPE_VALUE_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "small_palette_2_bytes",
                    "small_palette_4_bytes",
                    "rule_rows",
                    "false_free_rule_rows",
                    "best_false_free_correct_bytes",
                ],
            )
        )

    def append_nonzero_gap_palette_pair_value_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "rule_candidates.csv",
                    directory / "by_rule_family.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "rule_rows",
                    "false_free_rule_rows",
                    "false_free_multirow_rule_rows",
                    "exact_false_free_rule_rows",
                    "best_false_free_correct_bytes",
                    "best_false_free_exact_bytes",
                    "best_exact_false_free_exact_bytes",
                    "best_any_correct_bytes",
                    "best_any_false_bytes",
                    "best_any_exact_bytes",
                    "max_offset",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_PALETTE_PAIR_VALUE_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "rule_rows",
                    "false_free_rule_rows",
                    "exact_false_free_rule_rows",
                    "best_false_free_correct_bytes",
                    "best_exact_false_free_exact_bytes",
                ],
            )
        )

    def append_nonzero_gap_dominant_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_exception_shape.csv",
                    directory / "rule_candidates.csv",
                    directory / "by_rule_family.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "dominant_bytes",
                    "exception_bytes",
                    "exception_shape_groups",
                    "rule_rows",
                    "false_free_rule_rows",
                    "best_false_free_dominant_bytes",
                    "best_any_dominant_bytes",
                    "best_any_false_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_DOMINANT_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "dominant_bytes",
                    "exception_bytes",
                    "exception_shape_groups",
                    "rule_rows",
                    "false_free_rule_rows",
                    "best_false_free_dominant_bytes",
                ],
            )
        )

    def append_nonzero_gap_noisy_shape_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_first_use_shape.csv",
                    directory / "by_delta_class_shape.csv",
                    directory / "by_run_length_shape.csv",
                    directory / "by_source.csv",
                    directory / "by_control_selector.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "first_use_shape_groups",
                    "delta_class_shape_groups",
                    "run_length_shape_groups",
                    "gradient_like_bytes",
                    "best_exact_bytes_total",
                    "control_selector_groups",
                    "repeated_control_selector_groups",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_NOISY_SHAPE_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "first_use_shape_groups",
                    "delta_class_shape_groups",
                    "run_length_shape_groups",
                    "gradient_like_bytes",
                    "best_exact_bytes_total",
                    "control_selector_groups",
                ],
            )
        )

    def append_nonzero_gap_gradient_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_gradient_class.csv",
                    directory / "by_dominant_delta.csv",
                    directory / "by_delta_histogram.csv",
                    directory / "by_delta_run_shape.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "total_delta_count",
                    "small_delta_count",
                    "small_delta_ratio",
                    "zero_delta_count",
                    "step_delta_count",
                    "dominant_delta_rows",
                    "linear_exact_bytes_total",
                    "small_delta_walk_bytes",
                    "banded_bytes",
                    "gradient_classes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_GRADIENT_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "total_delta_count",
                    "small_delta_count",
                    "zero_delta_count",
                    "step_delta_count",
                    "dominant_delta_rows",
                    "linear_exact_bytes_total",
                    "gradient_classes",
                ],
            )
        )

    def append_nonzero_gap_gradient_repeat_context_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_shape_context.csv",
                    directory / "by_payload.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "shape_context_groups",
                    "repeated_shape_context_groups",
                    "repeated_shape_context_bytes",
                    "payload_signature_groups",
                    "repeated_payload_groups",
                    "repeated_payload_bytes",
                    "copy_distance_320_groups",
                    "copy_distance_320_rows",
                    "copy_distance_320_bytes",
                    "copy_unlock_bytes",
                    "control_ref_distinct_groups",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_GRADIENT_REPEAT_CONTEXT_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "shape_context_groups",
                    "repeated_shape_context_groups",
                    "repeated_shape_context_bytes",
                    "payload_signature_groups",
                    "repeated_payload_groups",
                    "repeated_payload_bytes",
                    "copy_distance_320_groups",
                    "copy_distance_320_rows",
                    "copy_distance_320_bytes",
                    "copy_unlock_bytes",
                    "control_ref_distinct_groups",
                ],
            )
        )

    def append_nonzero_gap_gradient_seed_unlock_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_transform_set.csv",
                    directory / "by_payload_pair.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "seed_rows",
                    "seed_bytes",
                    "candidate_seed_rows",
                    "candidate_seed_bytes",
                    "control_seed_rows",
                    "control_seed_bytes",
                    "single_transform_seed_rows",
                    "single_transform_seed_bytes",
                    "mixed_transform_seed_rows",
                    "mixed_transform_seed_bytes",
                    "copy_unlock_rows",
                    "copy_unlock_bytes",
                    "total_seed_plus_unlock_bytes",
                    "payload_pair_groups",
                    "payload_pair_rows",
                    "payload_pair_bytes",
                    "copy_distance_320_pair_groups",
                    "copy_distance_320_pair_bytes",
                    "transform_set_groups",
                    "repeated_transform_set_groups",
                    "repeated_transform_set_bytes",
                    "blocked_seed_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_GRADIENT_SEED_UNLOCK_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "candidate_seed_rows",
                    "candidate_seed_bytes",
                    "control_seed_bytes",
                    "single_transform_seed_bytes",
                    "mixed_transform_seed_bytes",
                    "copy_unlock_bytes",
                    "total_seed_plus_unlock_bytes",
                    "payload_pair_bytes",
                    "copy_distance_320_pair_bytes",
                    "transform_set_groups",
                    "blocked_seed_bytes",
                ],
            )
        )

    def append_nonzero_gap_gradient_seed_shift_family_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_family.csv",
                    directory / "by_shift_set.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "candidate_rows",
                    "candidate_bytes",
                    "identity_shift_family_rows",
                    "identity_shift_family_bytes",
                    "repeated_family_groups",
                    "repeated_family_bytes",
                    "exact_shift_set_groups",
                    "repeated_exact_shift_set_groups",
                    "repeated_exact_shift_set_bytes",
                    "copy_unlock_rows",
                    "copy_unlock_bytes",
                    "total_potential_bytes",
                    "covered_palette_values",
                    "distinct_shift_deltas",
                    "shift_delta_min",
                    "shift_delta_max",
                    "max_source_offset",
                    "max_offset_span",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_GRADIENT_SEED_SHIFT_FAMILY_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "candidate_rows",
                    "candidate_bytes",
                    "identity_shift_family_bytes",
                    "repeated_family_bytes",
                    "copy_unlock_bytes",
                    "total_potential_bytes",
                    "covered_palette_values",
                    "distinct_shift_deltas",
                    "max_source_offset",
                    "max_offset_span",
                ],
            )
        )

    def append_nonzero_gap_gradient_seed_delta_selector_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "values.csv",
                    directory / "by_selector.csv",
                    directory / "by_selector_family.csv",
                    directory / "by_delta.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "seed_rows",
                    "seed_bytes",
                    "mapping_rows",
                    "mapping_value_bytes",
                    "source_only_selector_families",
                    "source_only_selector_groups",
                    "source_only_repeated_deterministic_groups",
                    "source_only_repeated_deterministic_bytes",
                    "source_only_conflicted_groups",
                    "source_only_conflicted_bytes",
                    "best_source_only_family",
                    "best_source_only_repeated_deterministic_bytes",
                    "row_local_repeated_deterministic_bytes",
                    "target_oracle_repeated_deterministic_bytes",
                    "delta_values",
                    "copy_unlock_rows",
                    "copy_unlock_bytes",
                    "total_potential_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_GRADIENT_SEED_DELTA_SELECTOR_PROBE",
                positive_fields=[
                    "seed_rows",
                    "seed_bytes",
                    "mapping_rows",
                    "mapping_value_bytes",
                    "source_only_selector_families",
                    "source_only_selector_groups",
                    "source_only_conflicted_bytes",
                    "target_oracle_repeated_deterministic_bytes",
                    "delta_values",
                    "copy_unlock_bytes",
                    "total_potential_bytes",
                ],
            )
        )

    def append_nonzero_gap_gradient_seed_delta_context_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "context_values.csv",
                    directory / "by_context_selector.csv",
                    directory / "by_context_family.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "mapping_rows",
                    "mapping_value_bytes",
                    "source_context_selector_families",
                    "source_context_selector_groups",
                    "source_context_deterministic_groups",
                    "source_context_deterministic_bytes",
                    "source_context_repeated_deterministic_groups",
                    "source_context_repeated_deterministic_bytes",
                    "source_context_singleton_deterministic_groups",
                    "source_context_singleton_deterministic_bytes",
                    "source_context_conflicted_groups",
                    "source_context_conflicted_bytes",
                    "best_source_context_family",
                    "best_source_context_repeated_deterministic_bytes",
                    "best_source_context_conflicted_bytes",
                    "delta_values",
                    "copy_unlock_rows",
                    "copy_unlock_bytes",
                    "total_potential_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_GRADIENT_SEED_DELTA_CONTEXT_PROBE",
                positive_fields=[
                    "mapping_rows",
                    "mapping_value_bytes",
                    "source_context_selector_families",
                    "source_context_selector_groups",
                    "source_context_deterministic_bytes",
                    "source_context_singleton_deterministic_bytes",
                    "source_context_conflicted_bytes",
                    "delta_values",
                    "copy_unlock_bytes",
                    "total_potential_bytes",
                ],
            )
        )

    def append_nonzero_gap_gradient_seed_delta_phase_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "phase_values.csv",
                    directory / "by_phase_selector.csv",
                    directory / "by_phase_family.csv",
                    directory / "by_phase_scope.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "mapping_rows",
                    "mapping_value_bytes",
                    "selector_scopes",
                    "selector_families",
                    "selector_groups",
                    "deterministic_groups",
                    "deterministic_bytes",
                    "repeated_deterministic_groups",
                    "repeated_deterministic_bytes",
                    "singleton_deterministic_groups",
                    "singleton_deterministic_bytes",
                    "conflicted_groups",
                    "conflicted_bytes",
                    "source_value_phase_repeated_bytes",
                    "broad_control_phase_repeated_bytes",
                    "wide_relative_repeated_bytes",
                    "best_phase_family",
                    "best_phase_repeated_deterministic_bytes",
                    "best_phase_conflicted_bytes",
                    "delta_values",
                    "copy_unlock_rows",
                    "copy_unlock_bytes",
                    "total_potential_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_GRADIENT_SEED_DELTA_PHASE_PROBE",
                positive_fields=[
                    "mapping_rows",
                    "mapping_value_bytes",
                    "selector_scopes",
                    "selector_families",
                    "selector_groups",
                    "deterministic_bytes",
                    "singleton_deterministic_bytes",
                    "conflicted_bytes",
                    "delta_values",
                    "copy_unlock_bytes",
                    "total_potential_bytes",
                ],
            )
        )

    def append_nonzero_gap_gradient_seed_delta_state_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "state_values.csv",
                    directory / "by_state_selector.csv",
                    directory / "by_state_family.csv",
                    directory / "by_state_scope.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "mapping_rows",
                    "mapping_value_bytes",
                    "state_scopes",
                    "state_families",
                    "state_groups",
                    "deterministic_groups",
                    "deterministic_bytes",
                    "repeated_deterministic_groups",
                    "repeated_deterministic_bytes",
                    "singleton_deterministic_groups",
                    "singleton_deterministic_bytes",
                    "conflicted_groups",
                    "conflicted_bytes",
                    "prefix_accumulator_repeated_bytes",
                    "fsm_repeated_bytes",
                    "nibble_counter_repeated_bytes",
                    "parser_counter_repeated_bytes",
                    "best_state_family",
                    "best_state_repeated_deterministic_bytes",
                    "best_state_conflicted_bytes",
                    "delta_values",
                    "copy_unlock_rows",
                    "copy_unlock_bytes",
                    "total_potential_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_GRADIENT_SEED_DELTA_STATE_PROBE",
                positive_fields=[
                    "mapping_rows",
                    "mapping_value_bytes",
                    "state_scopes",
                    "state_families",
                    "state_groups",
                    "deterministic_bytes",
                    "singleton_deterministic_bytes",
                    "conflicted_bytes",
                    "delta_values",
                    "copy_unlock_bytes",
                    "total_potential_bytes",
                ],
            )
        )

    def append_nonzero_gap_gradient_seed_delta_opcode_sequence_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "sequence_rows.csv",
                    directory / "transition_rows.csv",
                    directory / "by_transition_selector.csv",
                    directory / "by_transition_family.csv",
                    directory / "by_transition_scope.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "seed_rows",
                    "mapping_rows",
                    "mapping_value_bytes",
                    "control_window_bytes",
                    "sequence_signatures",
                    "constant_delta_seed_rows",
                    "mixed_delta_seed_rows",
                    "transition_rows",
                    "transition_value_bytes",
                    "transition_scopes",
                    "transition_families",
                    "transition_groups",
                    "deterministic_transition_groups",
                    "deterministic_transition_bytes",
                    "repeated_transition_groups",
                    "repeated_transition_bytes",
                    "singleton_transition_groups",
                    "singleton_transition_bytes",
                    "conflicted_transition_groups",
                    "conflicted_transition_bytes",
                    "offset_reuse_bytes",
                    "backward_offset_steps",
                    "zero_offset_steps",
                    "forward_offset_steps",
                    "plus1_delta_bytes",
                    "zero_delta_bytes",
                    "negative_delta_bytes",
                    "best_transition_family",
                    "best_transition_repeated_bytes",
                    "best_transition_conflicted_bytes",
                    "copy_unlock_rows",
                    "copy_unlock_bytes",
                    "total_potential_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker=(
                    "TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_GRADIENT_SEED_DELTA_"
                    "OPCODE_SEQUENCE_PROBE"
                ),
                positive_fields=[
                    "seed_rows",
                    "mapping_rows",
                    "mapping_value_bytes",
                    "control_window_bytes",
                    "sequence_signatures",
                    "transition_rows",
                    "transition_value_bytes",
                    "transition_groups",
                    "deterministic_transition_bytes",
                    "singleton_transition_bytes",
                    "conflicted_transition_bytes",
                    "offset_reuse_bytes",
                    "copy_unlock_bytes",
                    "total_potential_bytes",
                ],
            )
        )

    def append_nonzero_gap_gradient_seed_delta_semantic_opcode_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "seed_streams.csv",
                    directory / "semantic_values.csv",
                    directory / "by_semantic_selector.csv",
                    directory / "by_semantic_family.csv",
                    directory / "by_semantic_scope.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "seed_rows",
                    "mapping_rows",
                    "mapping_value_bytes",
                    "operation_context_rows",
                    "semantic_scopes",
                    "semantic_families",
                    "semantic_groups",
                    "deterministic_groups",
                    "deterministic_bytes",
                    "repeated_deterministic_groups",
                    "repeated_deterministic_bytes",
                    "singleton_deterministic_groups",
                    "singleton_deterministic_bytes",
                    "conflicted_groups",
                    "conflicted_bytes",
                    "op_context_repeated_bytes",
                    "op_neighborhood_repeated_bytes",
                    "source_role_repeated_bytes",
                    "control_token_repeated_bytes",
                    "semantic_combo_repeated_bytes",
                    "best_semantic_family",
                    "best_semantic_repeated_bytes",
                    "best_semantic_conflicted_bytes",
                    "kind_patterns",
                    "length_patterns",
                    "copy_unlock_rows",
                    "copy_unlock_bytes",
                    "total_potential_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker=(
                    "TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_GRADIENT_SEED_DELTA_"
                    "SEMANTIC_OPCODE_PROBE"
                ),
                positive_fields=[
                    "seed_rows",
                    "mapping_rows",
                    "mapping_value_bytes",
                    "operation_context_rows",
                    "semantic_scopes",
                    "semantic_families",
                    "semantic_groups",
                    "deterministic_bytes",
                    "singleton_deterministic_bytes",
                    "conflicted_bytes",
                    "kind_patterns",
                    "length_patterns",
                    "copy_unlock_bytes",
                    "total_potential_bytes",
                ],
            )
        )

    def append_nonzero_gap_flat_walk_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_run_length_shape.csv",
                    directory / "by_transition_shape.csv",
                    directory / "by_run_value_shape.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "value_run_count",
                    "plateau_bytes",
                    "plateau_ratio",
                    "transition_count",
                    "small_transition_count",
                    "small_transition_ratio",
                    "run_length_shape_groups",
                    "run_length_repeated_bytes",
                    "transition_shape_groups",
                    "transition_repeated_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_FLAT_WALK_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "value_run_count",
                    "plateau_bytes",
                    "transition_count",
                    "small_transition_count",
                    "run_length_shape_groups",
                    "transition_shape_groups",
                ],
            )
        )

    def append_nonzero_gap_flat_walk_source_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_length_source.csv",
                    directory / "by_transition_source.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "length_symbol_count",
                    "length_exact_total",
                    "length_best_single_exact",
                    "transition_symbol_count",
                    "transition_exact_total",
                    "transition_best_single_exact",
                    "both_ge50_rows",
                    "length_source_groups",
                    "transition_source_groups",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_FLAT_WALK_SOURCE_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "length_symbol_count",
                    "length_exact_total",
                    "transition_symbol_count",
                    "transition_exact_total",
                    "length_source_groups",
                    "transition_source_groups",
                ],
            )
        )

    def append_nonzero_gap_flat_walk_shape_control_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "selector_candidates.csv",
                    directory / "by_selector_family.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "selector_rows",
                    "pure_selector_rows",
                    "repeated_pure_selector_rows",
                    "repeated_pure_covered_rows",
                    "repeated_pure_covered_bytes",
                    "best_pure_rows",
                    "best_pure_bytes",
                    "best_repeated_pure_rows",
                    "best_repeated_pure_bytes",
                    "selector_families",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_FLAT_WALK_SHAPE_CONTROL_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "selector_rows",
                    "pure_selector_rows",
                    "repeated_pure_selector_rows",
                    "repeated_pure_covered_bytes",
                    "best_repeated_pure_bytes",
                ],
            )
        )

    def append_nonzero_gap_flat_walk_value_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "rule_candidates.csv",
                    directory / "by_rule_family.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "rule_rows",
                    "exact_rule_rows",
                    "false_free_rule_rows",
                    "false_free_multirow_rule_rows",
                    "best_false_free_exact_bytes",
                    "best_false_free_correct_bytes",
                    "best_any_exact_bytes",
                    "best_any_correct_bytes",
                    "best_any_false_bytes",
                    "best_target_exact_rows",
                    "best_target_exact_bytes",
                    "prefix_copy_exact_rows",
                    "prefix_copy_exact_bytes",
                    "prefix_copy_best_distance",
                    "max_offset",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_FLAT_WALK_VALUE_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "rule_rows",
                    "best_any_correct_bytes",
                    "prefix_copy_exact_bytes",
                    "max_offset",
                ],
            )
        )

    def append_nonzero_gap_flat_walk_backref_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_distance.csv",
                    directory / "rule_candidates.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "distance_rows",
                    "rule_rows",
                    "exact_copy_rows",
                    "exact_copy_bytes",
                    "exact_known_source_rows",
                    "exact_known_source_bytes",
                    "exact_unresolved_source_rows",
                    "exact_unresolved_source_bytes",
                    "best_distance",
                    "best_distance_correct_bytes",
                    "best_distance_false_bytes",
                    "best_distance_exact_rows",
                    "best_distance_exact_bytes",
                    "best_rule_correct_bytes",
                    "best_rule_false_bytes",
                    "best_rule_exact_bytes",
                    "max_distance",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_FLAT_WALK_BACKREF_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "distance_rows",
                    "rule_rows",
                    "exact_copy_bytes",
                    "exact_unresolved_source_bytes",
                    "best_distance",
                    "best_distance_correct_bytes",
                    "max_distance",
                ],
            )
        )

    def append_nonzero_gap_flat_walk_palette_seed_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_pool_transform.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "candidate_rows",
                    "candidate_bytes",
                    "control_candidate_rows",
                    "control_candidate_bytes",
                    "multirow_group_rows",
                    "best_group_rows",
                    "best_group_bytes",
                    "copy_unlock_rows",
                    "copy_unlock_bytes",
                    "total_candidate_plus_unlock_bytes",
                    "max_palette_size",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_FLAT_WALK_PALETTE_SEED_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "candidate_rows",
                    "candidate_bytes",
                    "control_candidate_bytes",
                    "copy_unlock_bytes",
                    "total_candidate_plus_unlock_bytes",
                    "max_palette_size",
                ],
            )
        )

    def append_nonzero_gap_flat_walk_palette_mix_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_pool_transform_set.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "candidate_rows",
                    "candidate_bytes",
                    "control_candidate_rows",
                    "control_candidate_bytes",
                    "mixed_candidate_rows",
                    "mixed_candidate_bytes",
                    "single_transform_rows",
                    "single_transform_bytes",
                    "multirow_group_rows",
                    "best_group_rows",
                    "best_group_bytes",
                    "copy_unlock_rows",
                    "copy_unlock_bytes",
                    "total_candidate_plus_unlock_bytes",
                    "max_palette_size",
                    "max_mix_transforms",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_FLAT_WALK_PALETTE_MIX_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "candidate_rows",
                    "candidate_bytes",
                    "control_candidate_bytes",
                    "mixed_candidate_bytes",
                    "copy_unlock_bytes",
                    "total_candidate_plus_unlock_bytes",
                    "max_mix_transforms",
                ],
            )
        )

    def append_nonzero_gap_flat_walk_backref_chain_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "chains.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "exact_copy_rows",
                    "exact_copy_bytes",
                    "seed_source_candidate_rows",
                    "seed_source_candidate_bytes",
                    "mix_source_candidate_rows",
                    "mix_source_candidate_bytes",
                    "any_source_candidate_rows",
                    "any_source_candidate_bytes",
                    "any_source_chain_bytes",
                    "repeated_group_rows",
                    "repeated_group_chain_bytes",
                    "promotion_ready_bytes",
                    "blocked_chain_rows",
                    "blocked_chain_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_FLAT_WALK_BACKREF_CHAIN_PROBE",
                positive_fields=[
                    "exact_copy_rows",
                    "exact_copy_bytes",
                    "seed_source_candidate_rows",
                    "seed_source_candidate_bytes",
                    "mix_source_candidate_rows",
                    "mix_source_candidate_bytes",
                    "any_source_candidate_rows",
                    "any_source_chain_bytes",
                    "blocked_chain_bytes",
                ],
            )
        )

    def append_nonzero_gap_flat_walk_palette_signature_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "by_signature.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "signature_groups",
                    "repeated_signature_groups",
                    "repeated_signature_rows",
                    "repeated_signature_bytes",
                    "copy_backed_signature_groups",
                    "copy_backed_signature_rows",
                    "copy_backed_signature_bytes",
                    "candidate_repeated_rows",
                    "candidate_repeated_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_FLAT_WALK_PALETTE_SIGNATURE_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "signature_groups",
                    "repeated_signature_groups",
                    "repeated_signature_rows",
                    "repeated_signature_bytes",
                    "copy_backed_signature_bytes",
                    "candidate_repeated_bytes",
                ],
            )
        )

    def append_nonzero_gap_flat_walk_palette_context_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "by_context.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "repeated_signature_groups",
                    "repeated_signature_rows",
                    "repeated_signature_bytes",
                    "context_rows",
                    "copy_distance_320_rows",
                    "same_candidate_pool_rows",
                    "same_transform_set_rows",
                    "same_control_ref_mod64_rows",
                    "shared_context_rows",
                    "best_aligned_control_equal_bytes",
                    "best_unique_control_overlap",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_FLAT_WALK_PALETTE_CONTEXT_PROBE",
                positive_fields=[
                    "repeated_signature_groups",
                    "repeated_signature_rows",
                    "repeated_signature_bytes",
                    "context_rows",
                    "copy_distance_320_rows",
                    "same_candidate_pool_rows",
                    "best_unique_control_overlap",
                ],
            )
        )

    def append_nonzero_gap_noisy_review_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "decisions.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "noisy_rows",
                    "noisy_bytes",
                    "gradient_rows",
                    "gradient_bytes",
                    "gradient_repeat_context_rows",
                    "gradient_repeat_context_bytes",
                    "gradient_repeat_context_repeated_payload_bytes",
                    "gradient_repeat_context_copy_distance_320_bytes",
                    "gradient_repeat_context_copy_unlock_bytes",
                    "gradient_repeat_context_control_ref_distinct_groups",
                    "gradient_seed_unlock_seed_bytes",
                    "gradient_seed_unlock_candidate_seed_bytes",
                    "gradient_seed_unlock_control_seed_bytes",
                    "gradient_seed_unlock_single_transform_seed_bytes",
                    "gradient_seed_unlock_mixed_transform_seed_bytes",
                    "gradient_seed_unlock_copy_unlock_bytes",
                    "gradient_seed_unlock_total_potential_bytes",
                    "gradient_seed_unlock_repeated_transform_set_bytes",
                    "gradient_seed_unlock_blocked_seed_bytes",
                    "gradient_seed_shift_family_candidate_bytes",
                    "gradient_seed_shift_family_identity_bytes",
                    "gradient_seed_shift_family_repeated_family_bytes",
                    "gradient_seed_shift_family_repeated_exact_shift_set_bytes",
                    "gradient_seed_shift_family_copy_unlock_bytes",
                    "gradient_seed_shift_family_total_potential_bytes",
                    "gradient_seed_shift_family_distinct_shift_deltas",
                    "gradient_seed_delta_selector_mapping_bytes",
                    "gradient_seed_delta_selector_source_only_repeated_bytes",
                    "gradient_seed_delta_selector_source_only_conflicted_bytes",
                    "gradient_seed_delta_selector_best_source_family",
                    "gradient_seed_delta_selector_row_local_repeated_bytes",
                    "gradient_seed_delta_selector_target_oracle_repeated_bytes",
                    "gradient_seed_delta_selector_delta_values",
                    "gradient_seed_delta_context_mapping_bytes",
                    "gradient_seed_delta_context_repeated_bytes",
                    "gradient_seed_delta_context_singleton_bytes",
                    "gradient_seed_delta_context_conflicted_bytes",
                    "gradient_seed_delta_context_best_family",
                    "gradient_seed_delta_context_delta_values",
                    "gradient_seed_delta_phase_mapping_bytes",
                    "gradient_seed_delta_phase_selector_groups",
                    "gradient_seed_delta_phase_repeated_bytes",
                    "gradient_seed_delta_phase_source_value_repeated_bytes",
                    "gradient_seed_delta_phase_broad_control_repeated_bytes",
                    "gradient_seed_delta_phase_wide_relative_repeated_bytes",
                    "gradient_seed_delta_phase_conflicted_bytes",
                    "gradient_seed_delta_phase_best_family",
                    "gradient_seed_delta_phase_delta_values",
                    "gradient_seed_delta_state_mapping_bytes",
                    "gradient_seed_delta_state_groups",
                    "gradient_seed_delta_state_repeated_bytes",
                    "gradient_seed_delta_state_prefix_repeated_bytes",
                    "gradient_seed_delta_state_fsm_repeated_bytes",
                    "gradient_seed_delta_state_nibble_repeated_bytes",
                    "gradient_seed_delta_state_parser_repeated_bytes",
                    "gradient_seed_delta_state_conflicted_bytes",
                    "gradient_seed_delta_state_best_family",
                    "gradient_seed_delta_state_delta_values",
                    "gradient_seed_delta_opcode_sequence_mapping_bytes",
                    "gradient_seed_delta_opcode_sequence_transition_groups",
                    "gradient_seed_delta_opcode_sequence_repeated_bytes",
                    "gradient_seed_delta_opcode_sequence_conflicted_bytes",
                    "gradient_seed_delta_opcode_sequence_offset_reuse_bytes",
                    "gradient_seed_delta_opcode_sequence_constant_seed_rows",
                    "gradient_seed_delta_opcode_sequence_best_family",
                    "gradient_seed_delta_semantic_opcode_mapping_bytes",
                    "gradient_seed_delta_semantic_opcode_groups",
                    "gradient_seed_delta_semantic_opcode_repeated_bytes",
                    "gradient_seed_delta_semantic_opcode_op_context_repeated_bytes",
                    "gradient_seed_delta_semantic_opcode_op_neighborhood_repeated_bytes",
                    "gradient_seed_delta_semantic_opcode_source_role_repeated_bytes",
                    "gradient_seed_delta_semantic_opcode_control_token_repeated_bytes",
                    "gradient_seed_delta_semantic_opcode_combo_repeated_bytes",
                    "gradient_seed_delta_semantic_opcode_conflicted_bytes",
                    "gradient_seed_delta_semantic_opcode_best_family",
                    "flat_walk_rows",
                    "flat_walk_bytes",
                    "flat_shape_control_selector_rows",
                    "flat_shape_control_repeated_pure_rows",
                    "flat_shape_control_repeated_pure_covered_bytes",
                    "flat_shape_control_best_repeated_pure_bytes",
                    "flat_value_rule_rows",
                    "flat_value_false_free_multirow_rules",
                    "flat_value_best_any_correct_bytes",
                    "flat_value_best_any_false_bytes",
                    "flat_value_prefix_copy_exact_bytes",
                    "flat_backref_exact_copy_bytes",
                    "flat_backref_exact_known_source_bytes",
                    "flat_backref_exact_unresolved_source_bytes",
                    "flat_backref_best_distance",
                    "flat_palette_seed_candidate_bytes",
                    "flat_palette_seed_control_candidate_bytes",
                    "flat_palette_seed_copy_unlock_bytes",
                    "flat_palette_seed_total_potential_bytes",
                    "flat_palette_seed_multirow_group_rows",
                    "flat_palette_mix_candidate_bytes",
                    "flat_palette_mix_control_candidate_bytes",
                    "flat_palette_mix_mixed_candidate_bytes",
                    "flat_palette_mix_copy_unlock_bytes",
                    "flat_palette_mix_total_potential_bytes",
                    "flat_palette_mix_multirow_group_rows",
                    "flat_backref_chain_any_source_chain_bytes",
                    "flat_backref_chain_repeated_group_chain_bytes",
                    "flat_backref_chain_blocked_chain_bytes",
                    "flat_palette_signature_repeated_bytes",
                    "flat_palette_signature_copy_backed_bytes",
                    "flat_palette_signature_candidate_repeated_bytes",
                    "flat_palette_context_shared_rows",
                    "flat_palette_context_best_overlap",
                    "micro_token_rows",
                    "micro_token_bytes",
                    "micro_small_delta_count",
                    "micro_jump_delta_count",
                    "micro_signed_repeated_bytes",
                    "micro_jump_mixed_bytes",
                    "mixed_token_rows",
                    "mixed_token_bytes",
                    "mixed_token_signed_repeated_bytes",
                    "mixed_token_dominant_top_nibble_bytes",
                    "mixed_token_band_low_repeated_bytes",
                    "mixed_token_band_dominant_low_repeated_bytes",
                    "mixed_token_backref_exact_copy_bytes",
                    "mixed_token_backref_best_false_bytes",
                    "mixed_token_control_candidate_windows",
                    "mixed_token_control_top_only_bytes",
                    "mixed_token_control_profile_like_bytes",
                    "mixed_token_control_best_ratio",
                    "mixed_token_control_context_repeated_signal_bytes",
                    "mixed_token_control_context_repeated_offset_bytes",
                    "mixed_token_control_context_repeated_payload_bytes",
                    "mixed_token_control_context_full_byte_ge50_bytes",
                    "jump_token_rows",
                    "jump_token_bytes",
                    "jump_delta_count",
                    "jump_delta_ratio",
                    "jump_long_island_bytes",
                    "jump_signed_repeated_bytes",
                    "jump_exact_repeated_bytes",
                    "jump_backref_exact_copy_bytes",
                    "jump_backref_best_distance",
                    "jump_backref_best_false_bytes",
                    "jump_token_context_repeated_groups",
                    "jump_token_context_candidate_bytes",
                    "jump_token_context_shared_context_bytes",
                    "jump_token_context_conflicted_context_bytes",
                    "jump_token_context_copy_backed_bytes",
                    "repeated_nibble_rows",
                    "repeated_nibble_bytes",
                    "repeated_nibble_pingpong_rows",
                    "repeated_nibble_band_repeated_bytes",
                    "repeated_nibble_best_ratio",
                    "repeated_nibble_context_repeated_band_bytes",
                    "repeated_nibble_context_repeated_phase_bytes",
                    "repeated_nibble_context_repeated_payload_bytes",
                    "repeated_nibble_context_source_ge50_bytes",
                    "mixed_jump_rows",
                    "mixed_jump_bytes",
                    "mixed_jump_dominant_band_rows",
                    "mixed_jump_zero_band_rows",
                    "mixed_jump_best_ratio",
                    "mixed_jump_context_repeated_band_bytes",
                    "mixed_jump_context_repeated_payload_bytes",
                    "mixed_jump_context_source_ge50_bytes",
                    "mixed_control_rows",
                    "mixed_control_bytes",
                    "mixed_control_candidate_windows",
                    "mixed_control_phase_ge75_rows",
                    "mixed_control_phase_ge75_long_rows",
                    "mixed_control_source_like_bytes",
                    "residual_jump_rows",
                    "residual_jump_bytes",
                    "residual_jump_sparse_rows",
                    "residual_jump_long_island_bytes",
                    "residual_jump_best_ratio",
                    "residual_control_rows",
                    "residual_control_bytes",
                    "residual_control_candidate_windows",
                    "residual_control_phase_ge75_rows",
                    "residual_control_phase_ge75_long_rows",
                    "residual_control_source_like_bytes",
                    "dense_jump_rows",
                    "dense_jump_bytes",
                    "dense_direction_switch_ratio",
                    "dense_single_byte_island_ratio",
                    "dense_phase_repeated_bytes",
                    "dense_control_rows",
                    "dense_control_bytes",
                    "dense_control_candidate_windows",
                    "dense_control_phase_ge75_rows",
                    "dense_control_phase_ge75_long_rows",
                    "dense_control_source_like_bytes",
                    "control_signal_gate_rows",
                    "control_signal_gate_bytes",
                    "control_signal_gate_candidate_windows",
                    "control_signal_gate_direction_only_bytes",
                    "control_signal_gate_short_phase_bytes",
                    "control_signal_gate_phase_ge75_long_bytes",
                    "weak_control_value_rows",
                    "weak_control_value_bytes",
                    "weak_control_value_magnitude_ge75_bytes",
                    "weak_control_value_repeated_signal_bytes",
                    "weak_control_value_repeated_payload_bytes",
                    "direction_value_rows",
                    "direction_value_bytes",
                    "direction_value_ge75_bytes",
                    "direction_value_exact_bytes",
                    "direction_value_conflicted_offset_bytes",
                    "direction_value_offset_rows",
                    "direction_value_offset_bytes",
                    "direction_value_offset_repeated_bytes",
                    "direction_value_offset_same_delta_bytes",
                    "direction_value_offset_conflicted_delta_bytes",
                    "direction_value_delta_context_rows",
                    "direction_value_delta_context_bytes",
                    "direction_value_delta_context_best_stable_bytes",
                    "direction_value_delta_context_best_repeated_stable_bytes",
                    "direction_value_delta_context_split_all_singleton_bytes",
                    "direction_value_delta_context_repeated_payload_bytes",
                    "direction_value_payload_grammar_rows",
                    "direction_value_payload_grammar_bytes",
                    "direction_value_payload_grammar_repeated_top_token_nibble_bytes",
                    "direction_value_payload_grammar_repeated_transition_profile_bytes",
                    "direction_value_payload_grammar_repeated_payload_bytes",
                    "direction_value_payload_grammar_exact_profile_unique_bytes",
                    "direction_value_source_profile_rows",
                    "direction_value_source_profile_bytes",
                    "direction_value_source_profile_best_segment_gap_bytes",
                    "direction_value_source_profile_overlap_ge75_bytes",
                    "direction_value_source_profile_exact_profile_match_bytes",
                    "direction_value_source_profile_positional_ge50_bytes",
                    "direction_value_source_profile_repeated_source_profile_bytes",
                    "direction_value_source_value_rows",
                    "direction_value_source_value_bytes",
                    "direction_value_source_value_best_exact_total",
                    "direction_value_source_value_best_exact_ratio_max",
                    "direction_value_source_value_rows_ge25",
                    "direction_value_source_value_exact_match_bytes",
                    "direction_value_source_value_repeated_transform_bytes",
                    "direction_value_source_window_rows",
                    "direction_value_source_window_bytes",
                    "direction_value_source_window_best_exact_total",
                    "direction_value_source_window_best_exact_ratio_max",
                    "direction_value_source_window_rows_ge25",
                    "direction_value_source_window_rows_ge50",
                    "direction_value_source_window_exact_match_bytes",
                    "direction_value_source_window_repeated_offset_delta_bytes",
                    "direction_value_source_window_repeated_transform_bytes",
                    "direction_value_control_context_rows",
                    "direction_value_control_context_bytes",
                    "direction_value_control_context_repeated_direction_signal_bytes",
                    "direction_value_control_context_repeated_direction_context_bytes",
                    "direction_value_control_context_repeated_combined_context_bytes",
                    "direction_value_control_context_repeated_op_phase_bytes",
                    "direction_value_control_context_repeated_payload_bytes",
                    "direction_value_control_context_best_repeated_context_bytes",
                    "direction_value_exact_context_rows",
                    "direction_value_exact_context_bytes",
                    "direction_value_exact_context_repeated_key_bytes",
                    "direction_value_exact_context_repeated_payload_bytes",
                    "direction_value_exact_context_conflicted_delta_bytes",
                    "direction_value_partial_context_rows",
                    "direction_value_partial_context_bytes",
                    "direction_value_partial_context_repeated_key_bytes",
                    "direction_value_partial_context_repeated_payload_bytes",
                    "direction_value_partial_context_conflicted_delta_bytes",
                    "promotion_ready_bytes",
                    "review_bytes",
                    "decision_rows",
                    "blocked_rows",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_NOISY_REVIEW",
                positive_fields=[
                    "noisy_rows",
                    "noisy_bytes",
                    "gradient_rows",
                    "gradient_bytes",
                    "gradient_repeat_context_rows",
                    "gradient_repeat_context_bytes",
                    "gradient_repeat_context_repeated_payload_bytes",
                    "gradient_repeat_context_copy_distance_320_bytes",
                    "gradient_repeat_context_copy_unlock_bytes",
                    "gradient_repeat_context_control_ref_distinct_groups",
                    "gradient_seed_unlock_seed_bytes",
                    "gradient_seed_unlock_candidate_seed_bytes",
                    "gradient_seed_unlock_control_seed_bytes",
                    "gradient_seed_unlock_single_transform_seed_bytes",
                    "gradient_seed_unlock_mixed_transform_seed_bytes",
                    "gradient_seed_unlock_copy_unlock_bytes",
                    "gradient_seed_unlock_total_potential_bytes",
                    "gradient_seed_unlock_blocked_seed_bytes",
                    "gradient_seed_shift_family_candidate_bytes",
                    "gradient_seed_shift_family_identity_bytes",
                    "gradient_seed_shift_family_repeated_family_bytes",
                    "gradient_seed_shift_family_copy_unlock_bytes",
                    "gradient_seed_shift_family_total_potential_bytes",
                    "gradient_seed_shift_family_distinct_shift_deltas",
                    "gradient_seed_delta_selector_mapping_bytes",
                    "gradient_seed_delta_selector_source_only_conflicted_bytes",
                    "gradient_seed_delta_selector_target_oracle_repeated_bytes",
                    "gradient_seed_delta_selector_delta_values",
                    "gradient_seed_delta_context_mapping_bytes",
                    "gradient_seed_delta_context_singleton_bytes",
                    "gradient_seed_delta_context_conflicted_bytes",
                    "gradient_seed_delta_context_delta_values",
                    "gradient_seed_delta_phase_mapping_bytes",
                    "gradient_seed_delta_phase_selector_groups",
                    "gradient_seed_delta_phase_conflicted_bytes",
                    "gradient_seed_delta_phase_delta_values",
                    "gradient_seed_delta_state_mapping_bytes",
                    "gradient_seed_delta_state_groups",
                    "gradient_seed_delta_state_conflicted_bytes",
                    "gradient_seed_delta_state_delta_values",
                    "gradient_seed_delta_opcode_sequence_mapping_bytes",
                    "gradient_seed_delta_opcode_sequence_transition_groups",
                    "gradient_seed_delta_opcode_sequence_conflicted_bytes",
                    "gradient_seed_delta_opcode_sequence_offset_reuse_bytes",
                    "gradient_seed_delta_semantic_opcode_mapping_bytes",
                    "gradient_seed_delta_semantic_opcode_groups",
                    "gradient_seed_delta_semantic_opcode_conflicted_bytes",
                    "flat_walk_rows",
                    "flat_walk_bytes",
                    "flat_shape_control_selector_rows",
                    "flat_shape_control_repeated_pure_rows",
                    "flat_shape_control_repeated_pure_covered_bytes",
                    "flat_shape_control_best_repeated_pure_bytes",
                    "flat_value_rule_rows",
                    "flat_value_best_any_correct_bytes",
                    "flat_value_prefix_copy_exact_bytes",
                    "flat_backref_exact_copy_bytes",
                    "flat_backref_exact_unresolved_source_bytes",
                    "flat_backref_best_distance",
                    "flat_palette_seed_candidate_bytes",
                    "flat_palette_seed_control_candidate_bytes",
                    "flat_palette_seed_copy_unlock_bytes",
                    "flat_palette_seed_total_potential_bytes",
                    "flat_palette_mix_candidate_bytes",
                    "flat_palette_mix_control_candidate_bytes",
                    "flat_palette_mix_mixed_candidate_bytes",
                    "flat_palette_mix_copy_unlock_bytes",
                    "flat_palette_mix_total_potential_bytes",
                    "flat_backref_chain_any_source_chain_bytes",
                    "flat_backref_chain_blocked_chain_bytes",
                    "flat_palette_signature_repeated_bytes",
                    "flat_palette_signature_copy_backed_bytes",
                    "flat_palette_signature_candidate_repeated_bytes",
                    "flat_palette_context_best_overlap",
                    "micro_token_rows",
                    "micro_token_bytes",
                    "micro_small_delta_count",
                    "micro_jump_delta_count",
                    "micro_jump_mixed_bytes",
                    "mixed_token_rows",
                    "mixed_token_bytes",
                    "mixed_token_dominant_top_nibble_bytes",
                    "mixed_token_band_low_repeated_bytes",
                    "mixed_token_backref_best_false_bytes",
                    "mixed_token_control_candidate_windows",
                    "mixed_token_control_top_only_bytes",
                    "mixed_token_control_context_repeated_signal_bytes",
                    "mixed_token_control_context_repeated_offset_bytes",
                    "jump_token_rows",
                    "jump_token_bytes",
                    "jump_delta_count",
                    "jump_long_island_bytes",
                    "jump_backref_best_distance",
                    "jump_backref_best_false_bytes",
                    "jump_token_context_repeated_groups",
                    "jump_token_context_candidate_bytes",
                    "jump_token_context_conflicted_context_bytes",
                    "jump_token_context_copy_backed_bytes",
                    "repeated_nibble_rows",
                    "repeated_nibble_bytes",
                    "repeated_nibble_pingpong_rows",
                    "repeated_nibble_band_repeated_bytes",
                    "repeated_nibble_context_repeated_band_bytes",
                    "repeated_nibble_context_repeated_phase_bytes",
                    "repeated_nibble_context_source_ge50_bytes",
                    "mixed_jump_rows",
                    "mixed_jump_bytes",
                    "mixed_jump_dominant_band_rows",
                    "mixed_jump_zero_band_rows",
                    "mixed_jump_context_repeated_band_bytes",
                    "mixed_control_rows",
                    "mixed_control_bytes",
                    "mixed_control_candidate_windows",
                    "mixed_control_phase_ge75_rows",
                    "mixed_control_source_like_bytes",
                    "residual_jump_rows",
                    "residual_jump_bytes",
                    "residual_jump_sparse_rows",
                    "residual_jump_long_island_bytes",
                    "residual_control_rows",
                    "residual_control_bytes",
                    "residual_control_candidate_windows",
                    "residual_control_phase_ge75_rows",
                    "residual_control_source_like_bytes",
                    "dense_jump_rows",
                    "dense_jump_bytes",
                    "dense_control_rows",
                    "dense_control_bytes",
                    "dense_control_candidate_windows",
                    "dense_control_phase_ge75_rows",
                    "dense_control_source_like_bytes",
                    "control_signal_gate_rows",
                    "control_signal_gate_bytes",
                    "control_signal_gate_candidate_windows",
                    "control_signal_gate_direction_only_bytes",
                    "control_signal_gate_short_phase_bytes",
                    "weak_control_value_rows",
                    "weak_control_value_bytes",
                    "weak_control_value_magnitude_ge75_bytes",
                    "weak_control_value_repeated_signal_bytes",
                    "direction_value_rows",
                    "direction_value_bytes",
                    "direction_value_ge75_bytes",
                    "direction_value_exact_bytes",
                    "direction_value_conflicted_offset_bytes",
                    "direction_value_offset_rows",
                    "direction_value_offset_bytes",
                    "direction_value_offset_repeated_bytes",
                    "direction_value_offset_conflicted_delta_bytes",
                    "direction_value_delta_context_rows",
                    "direction_value_delta_context_bytes",
                    "direction_value_delta_context_best_stable_bytes",
                    "direction_value_delta_context_split_all_singleton_bytes",
                    "direction_value_payload_grammar_rows",
                    "direction_value_payload_grammar_bytes",
                    "direction_value_payload_grammar_repeated_top_token_nibble_bytes",
                    "direction_value_payload_grammar_exact_profile_unique_bytes",
                    "direction_value_source_profile_rows",
                    "direction_value_source_profile_bytes",
                    "direction_value_source_profile_best_segment_gap_bytes",
                    "direction_value_source_profile_overlap_ge75_bytes",
                    "direction_value_source_profile_exact_profile_match_bytes",
                    "direction_value_source_profile_positional_ge50_bytes",
                    "direction_value_source_value_rows",
                    "direction_value_source_value_bytes",
                    "direction_value_source_value_best_exact_total",
                    "direction_value_source_value_repeated_transform_bytes",
                    "direction_value_source_window_rows",
                    "direction_value_source_window_bytes",
                    "direction_value_source_window_best_exact_total",
                    "direction_value_source_window_rows_ge25",
                    "direction_value_source_window_repeated_offset_delta_bytes",
                    "direction_value_source_window_repeated_transform_bytes",
                    "direction_value_control_context_rows",
                    "direction_value_control_context_bytes",
                    "direction_value_control_context_repeated_direction_signal_bytes",
                    "direction_value_control_context_repeated_direction_context_bytes",
                    "direction_value_control_context_best_repeated_context_bytes",
                    "direction_value_exact_context_rows",
                    "direction_value_exact_context_bytes",
                    "direction_value_exact_context_repeated_key_bytes",
                    "direction_value_exact_context_conflicted_delta_bytes",
                    "direction_value_partial_context_rows",
                    "direction_value_partial_context_bytes",
                    "direction_value_partial_context_repeated_key_bytes",
                    "direction_value_partial_context_conflicted_delta_bytes",
                    "review_bytes",
                    "decision_rows",
                    "blocked_rows",
                ],
            )
        )

    def append_nonzero_gap_micro_token_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_micro_class.csv",
                    directory / "by_coarse_shape.csv",
                    directory / "by_signed_shape.csv",
                    directory / "by_transition_profile.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "delta_count",
                    "zero_delta_count",
                    "step_delta_count",
                    "small_delta_count",
                    "jump_delta_count",
                    "small_delta_ratio",
                    "jump_delta_ratio",
                    "token_runs",
                    "coarse_shape_groups",
                    "coarse_repeated_bytes",
                    "signed_shape_groups",
                    "signed_repeated_bytes",
                    "transition_profile_groups",
                    "transition_profile_repeated_bytes",
                    "plateau_walk_rows",
                    "plateau_walk_bytes",
                    "small_signed_walk_rows",
                    "small_signed_walk_bytes",
                    "banded_walk_rows",
                    "banded_walk_bytes",
                    "jump_mixed_rows",
                    "jump_mixed_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_MICRO_TOKEN_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "delta_count",
                    "zero_delta_count",
                    "step_delta_count",
                    "small_delta_count",
                    "jump_delta_count",
                    "token_runs",
                    "coarse_shape_groups",
                    "signed_shape_groups",
                    "transition_profile_groups",
                    "plateau_walk_rows",
                    "plateau_walk_bytes",
                    "jump_mixed_rows",
                    "jump_mixed_bytes",
                ],
            )
        )

    def append_nonzero_gap_mixed_token_uniqueness_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_group.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "coarse_shape_groups",
                    "coarse_repeated_groups",
                    "coarse_repeated_rows",
                    "coarse_repeated_bytes",
                    "signed_shape_groups",
                    "signed_repeated_groups",
                    "signed_repeated_rows",
                    "signed_repeated_bytes",
                    "transition_profile_groups",
                    "transition_profile_repeated_groups",
                    "transition_profile_repeated_rows",
                    "transition_profile_repeated_bytes",
                    "top_nibble_groups",
                    "dominant_top_nibble",
                    "dominant_top_nibble_rows",
                    "dominant_top_nibble_bytes",
                    "control_ref_groups",
                    "control_ref_repeated_rows",
                    "control_ref_repeated_bytes",
                    "missing_control_ref_rows",
                    "missing_control_ref_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_MIXED_TOKEN_UNIQUENESS_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "coarse_shape_groups",
                    "signed_shape_groups",
                    "transition_profile_groups",
                    "top_nibble_groups",
                    "dominant_top_nibble_rows",
                    "dominant_top_nibble_bytes",
                    "control_ref_groups",
                    "control_ref_repeated_bytes",
                ],
            )
        )

    def append_nonzero_gap_mixed_token_band_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_group.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "top_nibble_groups",
                    "dominant_top_nibble",
                    "dominant_top_nibble_rows",
                    "dominant_top_nibble_bytes",
                    "low_profile_groups",
                    "low_profile_repeated_groups",
                    "low_profile_repeated_rows",
                    "low_profile_repeated_bytes",
                    "dominant_top_low_profile_groups",
                    "dominant_top_low_profile_repeated_groups",
                    "dominant_top_low_profile_repeated_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_MIXED_TOKEN_BAND_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "top_nibble_groups",
                    "dominant_top_nibble_rows",
                    "dominant_top_nibble_bytes",
                    "low_profile_groups",
                    "low_profile_repeated_bytes",
                    "dominant_top_low_profile_groups",
                ],
            )
        )

    def append_nonzero_gap_mixed_token_backref_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_distance.csv",
                    directory / "rule_candidates.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "distance_rows",
                    "rule_rows",
                    "exact_copy_rows",
                    "exact_copy_bytes",
                    "exact_known_source_rows",
                    "exact_known_source_bytes",
                    "exact_unresolved_source_rows",
                    "exact_unresolved_source_bytes",
                    "best_distance",
                    "best_distance_correct_bytes",
                    "best_distance_false_bytes",
                    "best_distance_exact_rows",
                    "best_distance_exact_bytes",
                    "best_rule_correct_bytes",
                    "best_rule_false_bytes",
                    "best_rule_exact_bytes",
                    "max_distance",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_MIXED_TOKEN_BACKREF_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "distance_rows",
                    "rule_rows",
                    "best_distance",
                    "best_distance_correct_bytes",
                    "best_distance_false_bytes",
                    "max_distance",
                ],
            )
        )

    def append_nonzero_gap_mixed_token_control_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_best_signal.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "operation_rows",
                    "missing_operation_rows",
                    "candidate_windows",
                    "top_nibble_exact_total",
                    "top_nibble_best_single",
                    "top_nibble_ge50_rows",
                    "top_nibble_ge75_rows",
                    "low_nibble_exact_total",
                    "low_nibble_best_single",
                    "low_nibble_ge50_rows",
                    "low_nibble_ge75_rows",
                    "signed_delta_exact_total",
                    "signed_delta_best_single",
                    "signed_delta_ge50_rows",
                    "signed_delta_ge75_rows",
                    "byte_exact_total",
                    "byte_best_single",
                    "byte_ge50_rows",
                    "byte_ge75_rows",
                    "best_overall_exact",
                    "best_overall_ratio",
                    "dominant_top_nibble",
                    "dominant_top_nibble_rows",
                    "dominant_top_nibble_bytes",
                    "top_nibble_only_rows",
                    "top_nibble_only_bytes",
                    "profile_like_rows",
                    "profile_like_bytes",
                    "profile_like_long_rows",
                    "profile_like_long_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_MIXED_TOKEN_CONTROL_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "operation_rows",
                    "candidate_windows",
                    "top_nibble_exact_total",
                    "top_nibble_best_single",
                    "top_nibble_ge50_rows",
                    "top_nibble_ge75_rows",
                    "low_nibble_exact_total",
                    "low_nibble_best_single",
                    "low_nibble_ge50_rows",
                    "signed_delta_exact_total",
                    "signed_delta_best_single",
                    "signed_delta_ge50_rows",
                    "byte_exact_total",
                    "byte_best_single",
                    "best_overall_exact",
                    "dominant_top_nibble_rows",
                    "dominant_top_nibble_bytes",
                    "top_nibble_only_rows",
                    "top_nibble_only_bytes",
                ],
            )
        )

    def append_nonzero_gap_mixed_token_control_context_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_signal_context.csv",
                    directory / "by_offset_context.csv",
                    directory / "by_payload.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "signal_groups",
                    "repeated_signal_groups",
                    "repeated_signal_bytes",
                    "signal_top_groups",
                    "repeated_signal_top_groups",
                    "repeated_signal_top_bytes",
                    "offset_context_groups",
                    "repeated_offset_context_groups",
                    "repeated_offset_context_bytes",
                    "payload_signature_groups",
                    "repeated_payload_groups",
                    "repeated_payload_bytes",
                    "full_byte_ge50_rows",
                    "full_byte_ge50_bytes",
                    "profile_like_rows",
                    "profile_like_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_MIXED_TOKEN_CONTROL_CONTEXT_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "signal_groups",
                    "repeated_signal_groups",
                    "repeated_signal_bytes",
                    "signal_top_groups",
                    "repeated_signal_top_groups",
                    "repeated_signal_top_bytes",
                    "offset_context_groups",
                    "repeated_offset_context_groups",
                    "repeated_offset_context_bytes",
                    "payload_signature_groups",
                ],
            )
        )

    def append_nonzero_gap_jump_token_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_jump_structure_class.csv",
                    directory / "by_island_length_shape.csv",
                    directory / "by_jump_signed_shape.csv",
                    directory / "by_jump_nibble_pair.csv",
                    directory / "by_jump_exact_pair.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "delta_count",
                    "jump_delta_count",
                    "jump_delta_ratio",
                    "positive_jump_count",
                    "negative_jump_count",
                    "jump_rows_ge4",
                    "jump_rows_ge8",
                    "island_count",
                    "single_byte_islands",
                    "long_island_count",
                    "long_island_bytes",
                    "island_length_shape_groups",
                    "island_length_repeated_bytes",
                    "jump_signed_shape_groups",
                    "jump_signed_repeated_bytes",
                    "jump_nibble_pair_groups",
                    "jump_nibble_pair_repeated_bytes",
                    "jump_exact_pair_groups",
                    "jump_exact_pair_repeated_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_JUMP_TOKEN_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "delta_count",
                    "jump_delta_count",
                    "positive_jump_count",
                    "negative_jump_count",
                    "jump_rows_ge4",
                    "jump_rows_ge8",
                    "island_count",
                    "single_byte_islands",
                    "long_island_count",
                    "long_island_bytes",
                    "island_length_shape_groups",
                    "jump_signed_shape_groups",
                    "jump_nibble_pair_groups",
                    "jump_exact_pair_groups",
                ],
            )
        )

    def append_nonzero_gap_dense_jump_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_dense_class.csv",
                    directory / "by_direction_shape.csv",
                    directory / "by_magnitude_shape.csv",
                    directory / "by_nibble_pair_shape.csv",
                    directory / "by_island_bucket_shape.csv",
                    directory / "by_phase_shape.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "delta_count",
                    "jump_delta_count",
                    "jump_delta_ratio",
                    "positive_jump_count",
                    "negative_jump_count",
                    "direction_switch_count",
                    "direction_switch_ratio",
                    "alternating_rows",
                    "alternating_bytes",
                    "island_count",
                    "single_byte_islands",
                    "single_byte_island_ratio",
                    "dominant_nibble_rows",
                    "dominant_nibble_bytes",
                    "direction_shape_groups",
                    "direction_repeated_bytes",
                    "magnitude_shape_groups",
                    "magnitude_repeated_bytes",
                    "nibble_pair_shape_groups",
                    "nibble_pair_repeated_bytes",
                    "island_bucket_shape_groups",
                    "island_bucket_repeated_bytes",
                    "phase_shape_groups",
                    "phase_repeated_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_DENSE_JUMP_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "delta_count",
                    "jump_delta_count",
                    "positive_jump_count",
                    "negative_jump_count",
                    "direction_switch_count",
                    "alternating_rows",
                    "alternating_bytes",
                    "island_count",
                    "single_byte_islands",
                    "dominant_nibble_rows",
                    "dominant_nibble_bytes",
                    "direction_shape_groups",
                    "magnitude_shape_groups",
                    "nibble_pair_shape_groups",
                    "island_bucket_shape_groups",
                    "phase_shape_groups",
                ],
            )
        )

    def append_nonzero_gap_dense_control_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_best_signal.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "operation_rows",
                    "missing_operation_rows",
                    "jump_delta_count",
                    "candidate_windows",
                    "direction_exact_total",
                    "direction_ge75_rows",
                    "magnitude_exact_total",
                    "magnitude_ge75_rows",
                    "nibble_pair_exact_total",
                    "nibble_pair_ge75_rows",
                    "phase_exact_total",
                    "phase_ge75_rows",
                    "phase_ge75_long_rows",
                    "phase_ge75_long_bytes",
                    "best_overall_exact",
                    "best_overall_ratio",
                    "source_like_rows",
                    "source_like_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_DENSE_CONTROL_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "operation_rows",
                    "jump_delta_count",
                    "candidate_windows",
                    "direction_exact_total",
                    "direction_ge75_rows",
                    "magnitude_exact_total",
                    "magnitude_ge75_rows",
                    "nibble_pair_exact_total",
                    "phase_exact_total",
                    "phase_ge75_rows",
                    "best_overall_exact",
                    "source_like_rows",
                    "source_like_bytes",
                ],
            )
        )

    def append_nonzero_gap_jump_token_backref_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_distance.csv",
                    directory / "rule_candidates.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "distance_rows",
                    "rule_rows",
                    "exact_copy_rows",
                    "exact_copy_bytes",
                    "exact_known_source_rows",
                    "exact_known_source_bytes",
                    "exact_unresolved_source_rows",
                    "exact_unresolved_source_bytes",
                    "best_distance",
                    "best_distance_correct_bytes",
                    "best_distance_false_bytes",
                    "best_distance_exact_rows",
                    "best_distance_exact_bytes",
                    "best_rule_correct_bytes",
                    "best_rule_false_bytes",
                    "best_rule_exact_bytes",
                    "max_distance",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_JUMP_TOKEN_BACKREF_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "distance_rows",
                    "rule_rows",
                    "best_distance",
                    "best_distance_correct_bytes",
                    "best_distance_false_bytes",
                    "max_distance",
                ],
            )
        )

    def append_nonzero_gap_jump_token_context_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_context.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "shape_kinds",
                    "repeated_group_rows",
                    "repeated_group_bytes",
                    "repeated_candidate_rows",
                    "repeated_candidate_bytes",
                    "same_length_groups",
                    "same_structure_groups",
                    "same_control_ref_groups",
                    "same_start_mod64_groups",
                    "same_top_pair_groups",
                    "shared_context_groups",
                    "shared_context_bytes",
                    "conflicted_context_groups",
                    "conflicted_context_bytes",
                    "copy_backed_group_rows",
                    "copy_backed_group_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_JUMP_TOKEN_CONTEXT_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "shape_kinds",
                    "repeated_group_rows",
                    "repeated_group_bytes",
                    "repeated_candidate_rows",
                    "repeated_candidate_bytes",
                    "same_length_groups",
                    "same_structure_groups",
                    "same_top_pair_groups",
                    "conflicted_context_groups",
                    "conflicted_context_bytes",
                    "copy_backed_group_rows",
                    "copy_backed_group_bytes",
                ],
            )
        )

    def append_nonzero_gap_repeated_nibble_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_band_pair.csv",
                    directory / "by_best_signal.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "operation_rows",
                    "missing_operation_rows",
                    "jump_delta_count",
                    "positive_jump_count",
                    "negative_jump_count",
                    "two_band_rows",
                    "two_band_bytes",
                    "pingpong_rows",
                    "pingpong_bytes",
                    "dominant_band_rows",
                    "dominant_band_bytes",
                    "band_pair_groups",
                    "repeated_band_pair_bytes",
                    "band_phase_shape_groups",
                    "band_phase_repeated_bytes",
                    "exact_pair_shape_groups",
                    "exact_pair_repeated_bytes",
                    "candidate_windows",
                    "nibble_source_exact_total",
                    "nibble_source_ge50_rows",
                    "exact_source_exact_total",
                    "best_overall_exact",
                    "best_overall_ratio",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_REPEATED_NIBBLE_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "operation_rows",
                    "jump_delta_count",
                    "positive_jump_count",
                    "negative_jump_count",
                    "two_band_rows",
                    "two_band_bytes",
                    "pingpong_rows",
                    "pingpong_bytes",
                    "dominant_band_rows",
                    "dominant_band_bytes",
                    "band_pair_groups",
                    "repeated_band_pair_bytes",
                    "band_phase_shape_groups",
                    "band_phase_repeated_bytes",
                    "exact_pair_shape_groups",
                    "candidate_windows",
                    "nibble_source_exact_total",
                    "nibble_source_ge50_rows",
                    "exact_source_exact_total",
                    "best_overall_exact",
                ],
            )
        )

    def append_nonzero_gap_repeated_nibble_context_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_band_context.csv",
                    directory / "by_phase_context.csv",
                    directory / "by_payload.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "band_pair_groups",
                    "repeated_band_pair_groups",
                    "repeated_band_pair_bytes",
                    "phase_context_groups",
                    "repeated_phase_context_groups",
                    "repeated_phase_context_bytes",
                    "payload_signature_groups",
                    "repeated_payload_groups",
                    "repeated_payload_bytes",
                    "pingpong_rows",
                    "pingpong_bytes",
                    "source_ge50_rows",
                    "source_ge50_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_REPEATED_NIBBLE_CONTEXT_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "band_pair_groups",
                    "repeated_band_pair_groups",
                    "repeated_band_pair_bytes",
                    "phase_context_groups",
                    "repeated_phase_context_groups",
                    "repeated_phase_context_bytes",
                    "payload_signature_groups",
                    "pingpong_rows",
                    "pingpong_bytes",
                    "source_ge50_rows",
                    "source_ge50_bytes",
                ],
            )
        )

    def append_nonzero_gap_mixed_jump_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_dominant_band.csv",
                    directory / "by_best_signal.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "operation_rows",
                    "missing_operation_rows",
                    "jump_delta_count",
                    "positive_jump_count",
                    "negative_jump_count",
                    "island_count",
                    "single_byte_islands",
                    "long_island_count",
                    "long_island_bytes",
                    "dominant_band_rows",
                    "dominant_band_bytes",
                    "zero_band_rows",
                    "zero_band_bytes",
                    "multi_band_rows",
                    "multi_band_bytes",
                    "band_pair_groups",
                    "repeated_band_pair_bytes",
                    "nibble_shape_groups",
                    "nibble_repeated_bytes",
                    "exact_shape_groups",
                    "exact_repeated_bytes",
                    "candidate_windows",
                    "nibble_source_exact_total",
                    "nibble_source_ge50_rows",
                    "exact_source_exact_total",
                    "best_overall_exact",
                    "best_overall_ratio",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_MIXED_JUMP_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "operation_rows",
                    "jump_delta_count",
                    "positive_jump_count",
                    "negative_jump_count",
                    "island_count",
                    "single_byte_islands",
                    "long_island_count",
                    "long_island_bytes",
                    "dominant_band_rows",
                    "dominant_band_bytes",
                    "zero_band_rows",
                    "zero_band_bytes",
                    "multi_band_rows",
                    "multi_band_bytes",
                    "band_pair_groups",
                    "repeated_band_pair_bytes",
                    "nibble_shape_groups",
                    "exact_shape_groups",
                    "candidate_windows",
                    "nibble_source_exact_total",
                    "exact_source_exact_total",
                    "best_overall_exact",
                ],
            )
        )

    def append_nonzero_gap_mixed_control_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_dominant_band.csv",
                    directory / "by_best_signal.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "operation_rows",
                    "missing_operation_rows",
                    "jump_delta_count",
                    "long_island_bytes",
                    "dominant_band_rows",
                    "dominant_band_bytes",
                    "zero_band_rows",
                    "zero_band_bytes",
                    "multi_band_rows",
                    "multi_band_bytes",
                    "candidate_windows",
                    "direction_exact_total",
                    "direction_best_single",
                    "direction_ge50_rows",
                    "direction_ge75_rows",
                    "magnitude_exact_total",
                    "magnitude_best_single",
                    "magnitude_ge50_rows",
                    "magnitude_ge75_rows",
                    "nibble_pair_exact_total",
                    "nibble_pair_best_single",
                    "nibble_pair_ge50_rows",
                    "nibble_pair_ge75_rows",
                    "phase_exact_total",
                    "phase_best_single",
                    "phase_ge50_rows",
                    "phase_ge75_rows",
                    "phase_ge75_long_rows",
                    "phase_ge75_long_bytes",
                    "best_overall_exact",
                    "best_overall_ratio",
                    "source_like_rows",
                    "source_like_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_MIXED_CONTROL_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "operation_rows",
                    "jump_delta_count",
                    "long_island_bytes",
                    "dominant_band_rows",
                    "dominant_band_bytes",
                    "zero_band_rows",
                    "zero_band_bytes",
                    "multi_band_rows",
                    "multi_band_bytes",
                    "candidate_windows",
                    "direction_exact_total",
                    "direction_best_single",
                    "direction_ge50_rows",
                    "direction_ge75_rows",
                    "magnitude_exact_total",
                    "magnitude_best_single",
                    "magnitude_ge50_rows",
                    "magnitude_ge75_rows",
                    "nibble_pair_exact_total",
                    "nibble_pair_best_single",
                    "nibble_pair_ge50_rows",
                    "nibble_pair_ge75_rows",
                    "phase_exact_total",
                    "phase_best_single",
                    "phase_ge50_rows",
                    "phase_ge75_rows",
                    "best_overall_exact",
                    "source_like_rows",
                    "source_like_bytes",
                ],
            )
        )

    def append_nonzero_gap_residual_jump_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_jump_class.csv",
                    directory / "by_dominant_band.csv",
                    directory / "by_best_signal.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "operation_rows",
                    "missing_operation_rows",
                    "sparse_rows",
                    "sparse_bytes",
                    "long_island_rows",
                    "long_island_bytes_total",
                    "jump_delta_count",
                    "positive_jump_count",
                    "negative_jump_count",
                    "island_count",
                    "single_byte_islands",
                    "long_island_count",
                    "long_island_bytes",
                    "dominant_band_rows",
                    "dominant_band_bytes",
                    "zero_band_rows",
                    "zero_band_bytes",
                    "band_pair_groups",
                    "repeated_band_pair_bytes",
                    "nibble_shape_groups",
                    "nibble_repeated_bytes",
                    "exact_shape_groups",
                    "exact_repeated_bytes",
                    "candidate_windows",
                    "nibble_source_exact_total",
                    "nibble_source_ge50_rows",
                    "exact_source_exact_total",
                    "best_overall_exact",
                    "best_overall_ratio",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_RESIDUAL_JUMP_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "operation_rows",
                    "sparse_rows",
                    "sparse_bytes",
                    "long_island_rows",
                    "long_island_bytes_total",
                    "jump_delta_count",
                    "positive_jump_count",
                    "negative_jump_count",
                    "island_count",
                    "single_byte_islands",
                    "long_island_count",
                    "long_island_bytes",
                    "dominant_band_rows",
                    "dominant_band_bytes",
                    "zero_band_rows",
                    "zero_band_bytes",
                    "band_pair_groups",
                    "repeated_band_pair_bytes",
                    "nibble_shape_groups",
                    "nibble_repeated_bytes",
                    "exact_shape_groups",
                    "candidate_windows",
                    "nibble_source_exact_total",
                    "exact_source_exact_total",
                    "best_overall_exact",
                ],
            )
        )

    def append_nonzero_gap_residual_control_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_jump_class.csv",
                    directory / "by_best_signal.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "operation_rows",
                    "missing_operation_rows",
                    "sparse_rows",
                    "sparse_bytes",
                    "long_island_rows",
                    "long_island_bytes_total",
                    "jump_delta_count",
                    "candidate_windows",
                    "direction_exact_total",
                    "direction_best_single",
                    "direction_ge50_rows",
                    "direction_ge75_rows",
                    "magnitude_exact_total",
                    "magnitude_best_single",
                    "magnitude_ge50_rows",
                    "magnitude_ge75_rows",
                    "nibble_pair_exact_total",
                    "nibble_pair_best_single",
                    "nibble_pair_ge50_rows",
                    "nibble_pair_ge75_rows",
                    "phase_exact_total",
                    "phase_best_single",
                    "phase_ge50_rows",
                    "phase_ge75_rows",
                    "phase_ge75_long_rows",
                    "phase_ge75_long_bytes",
                    "best_overall_exact",
                    "best_overall_ratio",
                    "source_like_rows",
                    "source_like_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_RESIDUAL_CONTROL_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "operation_rows",
                    "sparse_rows",
                    "sparse_bytes",
                    "long_island_rows",
                    "long_island_bytes_total",
                    "jump_delta_count",
                    "candidate_windows",
                    "direction_exact_total",
                    "direction_best_single",
                    "direction_ge50_rows",
                    "direction_ge75_rows",
                    "magnitude_exact_total",
                    "magnitude_best_single",
                    "magnitude_ge50_rows",
                    "magnitude_ge75_rows",
                    "nibble_pair_exact_total",
                    "nibble_pair_best_single",
                    "nibble_pair_ge50_rows",
                    "nibble_pair_ge75_rows",
                    "phase_exact_total",
                    "phase_best_single",
                    "phase_ge50_rows",
                    "phase_ge75_rows",
                    "best_overall_exact",
                    "source_like_rows",
                    "source_like_bytes",
                ],
            )
        )

    def append_nonzero_gap_control_signal_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_surface.csv",
                    directory / "by_signal.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "surface_count",
                    "surface_rows",
                    "surface_bytes",
                    "jump_delta_count",
                    "candidate_windows",
                    "direction_ge75_rows",
                    "direction_ge75_bytes",
                    "phase_ge75_rows",
                    "phase_ge75_bytes",
                    "phase_ge75_long_rows",
                    "phase_ge75_long_bytes",
                    "direction_only_rows",
                    "direction_only_bytes",
                    "short_phase_rows",
                    "short_phase_bytes",
                    "long_phase_rows",
                    "long_phase_bytes",
                    "weak_control_rows",
                    "weak_control_bytes",
                    "shared_direction_signal_groups",
                    "shared_phase_signal_groups",
                    "best_direction_signal_rows",
                    "best_direction_signal_bytes",
                    "best_phase_signal_rows",
                    "best_phase_signal_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_CONTROL_SIGNAL_GATE_PROBE",
                positive_fields=[
                    "surface_count",
                    "surface_rows",
                    "surface_bytes",
                    "jump_delta_count",
                    "candidate_windows",
                    "direction_ge75_rows",
                    "direction_ge75_bytes",
                    "phase_ge75_rows",
                    "phase_ge75_bytes",
                    "direction_only_rows",
                    "direction_only_bytes",
                    "short_phase_rows",
                    "short_phase_bytes",
                    "weak_control_rows",
                    "weak_control_bytes",
                    "shared_direction_signal_groups",
                    "shared_phase_signal_groups",
                    "best_direction_signal_rows",
                    "best_direction_signal_bytes",
                    "best_phase_signal_rows",
                    "best_phase_signal_bytes",
                ],
            )
        )

    def append_nonzero_gap_weak_control_value_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_signal.csv",
                    directory / "by_payload.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "surface_count",
                    "candidate_windows",
                    "best_signal_groups",
                    "best_signal_repeated_groups",
                    "best_signal_repeated_bytes",
                    "magnitude_rows",
                    "magnitude_bytes",
                    "magnitude_ge75_rows",
                    "magnitude_ge75_bytes",
                    "direction_near75_rows",
                    "direction_near75_bytes",
                    "phase_nonzero_rows",
                    "phase_nonzero_bytes",
                    "payload_signature_groups",
                    "repeated_payload_groups",
                    "repeated_payload_bytes",
                    "source_join_missing_rows",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_WEAK_CONTROL_VALUE_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "surface_count",
                    "candidate_windows",
                    "best_signal_groups",
                    "best_signal_repeated_groups",
                    "best_signal_repeated_bytes",
                    "magnitude_rows",
                    "magnitude_bytes",
                    "magnitude_ge75_rows",
                    "magnitude_ge75_bytes",
                    "direction_near75_rows",
                    "direction_near75_bytes",
                    "phase_nonzero_rows",
                    "phase_nonzero_bytes",
                    "payload_signature_groups",
                ],
            )
        )

    def append_nonzero_gap_direction_value_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_direction_value.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "surface_count",
                    "direction_signal_groups",
                    "value_signal_groups",
                    "direction_value_groups",
                    "value_ge75_rows",
                    "value_ge75_bytes",
                    "value_exact_rows",
                    "value_exact_bytes",
                    "magnitude_ge75_rows",
                    "magnitude_ge75_bytes",
                    "nibble_ge75_rows",
                    "nibble_ge75_bytes",
                    "byte_bucket_rows",
                    "byte_bucket_bytes",
                    "high_nibble_bucket_rows",
                    "high_nibble_bucket_bytes",
                    "low_nibble_bucket_rows",
                    "low_nibble_bucket_bytes",
                    "adjacent_delta_bucket_rows",
                    "adjacent_delta_bucket_bytes",
                    "repeated_direction_value_groups",
                    "repeated_direction_value_bytes",
                    "same_offset_groups",
                    "same_offset_bytes",
                    "conflicted_offset_groups",
                    "conflicted_offset_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_DIRECTION_VALUE_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "surface_count",
                    "direction_signal_groups",
                    "value_signal_groups",
                    "direction_value_groups",
                    "value_ge75_rows",
                    "value_ge75_bytes",
                    "value_exact_rows",
                    "value_exact_bytes",
                    "magnitude_ge75_rows",
                    "magnitude_ge75_bytes",
                    "byte_bucket_rows",
                    "byte_bucket_bytes",
                    "high_nibble_bucket_rows",
                    "high_nibble_bucket_bytes",
                    "low_nibble_bucket_rows",
                    "low_nibble_bucket_bytes",
                    "adjacent_delta_bucket_rows",
                    "adjacent_delta_bucket_bytes",
                    "repeated_direction_value_groups",
                    "repeated_direction_value_bytes",
                    "conflicted_offset_groups",
                    "conflicted_offset_bytes",
                ],
            )
        )

    def append_nonzero_gap_direction_value_offset_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_offset.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "value_exact_rows",
                    "value_exact_bytes",
                    "direction_value_groups",
                    "repeated_key_groups",
                    "repeated_key_bytes",
                    "same_delta_groups",
                    "same_delta_bytes",
                    "surface_stable_delta_groups",
                    "surface_stable_delta_bytes",
                    "conflicted_delta_groups",
                    "conflicted_delta_bytes",
                    "singleton_rows",
                    "singleton_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_DIRECTION_VALUE_OFFSET_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "value_exact_rows",
                    "value_exact_bytes",
                    "direction_value_groups",
                    "repeated_key_groups",
                    "repeated_key_bytes",
                    "surface_stable_delta_groups",
                    "surface_stable_delta_bytes",
                    "conflicted_delta_groups",
                    "conflicted_delta_bytes",
                    "singleton_rows",
                    "singleton_bytes",
                ],
            )
        )

    def append_nonzero_gap_direction_value_delta_context_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "contexts.csv",
                    directory / "by_payload.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "context_profiles",
                    "best_context_name",
                    "best_stable_bytes",
                    "best_repeated_stable_bytes",
                    "best_conflict_bytes",
                    "singleton_stable_bytes",
                    "split_all_singleton_bytes",
                    "payload_signature_groups",
                    "repeated_payload_groups",
                    "repeated_payload_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_DIRECTION_VALUE_DELTA_CONTEXT_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "context_profiles",
                    "best_stable_bytes",
                    "singleton_stable_bytes",
                    "split_all_singleton_bytes",
                    "payload_signature_groups",
                ],
            )
        )

    def append_nonzero_gap_direction_value_payload_grammar_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "shared_signals.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "fixture_keys",
                    "payload_signature_groups",
                    "repeated_payload_groups",
                    "repeated_payload_bytes",
                    "coarse_shape_groups",
                    "repeated_coarse_shape_groups",
                    "repeated_coarse_shape_bytes",
                    "signed_shape_groups",
                    "repeated_signed_shape_groups",
                    "repeated_signed_shape_bytes",
                    "transition_profile_groups",
                    "repeated_transition_profile_groups",
                    "repeated_transition_profile_bytes",
                    "top_token_groups",
                    "repeated_top_token_groups",
                    "repeated_top_token_bytes",
                    "top_nibble_groups",
                    "repeated_top_nibble_groups",
                    "repeated_top_nibble_bytes",
                    "top_token_nibble_groups",
                    "repeated_top_token_nibble_groups",
                    "repeated_top_token_nibble_bytes",
                    "dominant_jump_rows",
                    "dominant_jump_bytes",
                    "dominant_top_nibble_rows",
                    "dominant_top_nibble_bytes",
                    "exact_profile_unique_bytes",
                    "broad_signal_only_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_DIRECTION_VALUE_PAYLOAD_GRAMMAR_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "fixture_keys",
                    "payload_signature_groups",
                    "coarse_shape_groups",
                    "signed_shape_groups",
                    "transition_profile_groups",
                    "top_token_groups",
                    "repeated_top_token_bytes",
                    "top_nibble_groups",
                    "repeated_top_nibble_bytes",
                    "top_token_nibble_groups",
                    "repeated_top_token_nibble_bytes",
                    "dominant_jump_bytes",
                    "exact_profile_unique_bytes",
                    "broad_signal_only_bytes",
                ],
            )
        )

    def append_nonzero_gap_direction_value_source_profile_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_source_profile.csv",
                    directory / "by_best_offset.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "fixture_keys",
                    "source_pools",
                    "best_segment_gap_rows",
                    "best_segment_gap_bytes",
                    "profile_overlap_ge50_rows",
                    "profile_overlap_ge50_bytes",
                    "profile_overlap_ge75_rows",
                    "profile_overlap_ge75_bytes",
                    "profile_overlap_ge90_rows",
                    "profile_overlap_ge90_bytes",
                    "exact_profile_match_rows",
                    "exact_profile_match_bytes",
                    "positional_ge50_rows",
                    "positional_ge50_bytes",
                    "positional_ge75_rows",
                    "positional_ge75_bytes",
                    "source_profile_groups",
                    "repeated_source_profile_groups",
                    "repeated_source_profile_bytes",
                    "best_offset_groups",
                    "repeated_best_offset_groups",
                    "repeated_best_offset_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_DIRECTION_VALUE_SOURCE_PROFILE_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "fixture_keys",
                    "source_pools",
                    "best_segment_gap_rows",
                    "best_segment_gap_bytes",
                    "profile_overlap_ge50_bytes",
                    "profile_overlap_ge75_bytes",
                    "profile_overlap_ge90_bytes",
                    "exact_profile_match_bytes",
                    "positional_ge50_bytes",
                    "positional_ge75_bytes",
                    "source_profile_groups",
                    "best_offset_groups",
                    "repeated_best_offset_bytes",
                ],
            )
        )

    def append_nonzero_gap_direction_value_source_value_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_transform.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "fixture_keys",
                    "transform_count",
                    "best_exact_total",
                    "best_exact_ratio_max",
                    "best_exact_ratio_avg",
                    "rows_ge25",
                    "bytes_ge25",
                    "rows_ge50",
                    "bytes_ge50",
                    "rows_ge75",
                    "bytes_ge75",
                    "exact_match_rows",
                    "exact_match_bytes",
                    "best_transform_groups",
                    "repeated_best_transform_groups",
                    "repeated_best_transform_bytes",
                    "top_best_transform",
                    "top_best_transform_rows",
                    "top_best_transform_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_DIRECTION_VALUE_SOURCE_VALUE_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "fixture_keys",
                    "transform_count",
                    "best_exact_total",
                    "best_transform_groups",
                    "repeated_best_transform_groups",
                    "repeated_best_transform_bytes",
                    "top_best_transform_rows",
                    "top_best_transform_bytes",
                ],
            )
        )

    def append_nonzero_gap_direction_value_source_window_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_offset_delta.csv",
                    directory / "by_transform.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "fixture_keys",
                    "scan_radius",
                    "transform_count",
                    "offset_candidate_total",
                    "best_exact_total",
                    "best_exact_ratio_max",
                    "best_exact_ratio_avg",
                    "rows_ge25",
                    "bytes_ge25",
                    "rows_ge50",
                    "bytes_ge50",
                    "rows_ge75",
                    "bytes_ge75",
                    "exact_match_rows",
                    "exact_match_bytes",
                    "zero_delta_rows",
                    "zero_delta_bytes",
                    "nonzero_delta_rows",
                    "nonzero_delta_bytes",
                    "best_offset_delta_groups",
                    "repeated_best_offset_delta_groups",
                    "repeated_best_offset_delta_bytes",
                    "best_transform_groups",
                    "repeated_best_transform_groups",
                    "repeated_best_transform_bytes",
                    "top_best_offset_delta",
                    "top_best_offset_delta_rows",
                    "top_best_offset_delta_bytes",
                    "top_best_transform",
                    "top_best_transform_rows",
                    "top_best_transform_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_DIRECTION_VALUE_SOURCE_WINDOW_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "fixture_keys",
                    "scan_radius",
                    "transform_count",
                    "offset_candidate_total",
                    "best_exact_total",
                    "rows_ge25",
                    "bytes_ge25",
                    "zero_delta_rows",
                    "zero_delta_bytes",
                    "nonzero_delta_rows",
                    "nonzero_delta_bytes",
                    "best_offset_delta_groups",
                    "repeated_best_offset_delta_groups",
                    "repeated_best_offset_delta_bytes",
                    "best_transform_groups",
                    "repeated_best_transform_groups",
                    "repeated_best_transform_bytes",
                    "top_best_offset_delta_rows",
                    "top_best_offset_delta_bytes",
                    "top_best_transform_rows",
                    "top_best_transform_bytes",
                ],
            )
        )

    def append_nonzero_gap_direction_value_control_context_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_direction_signal.csv",
                    directory / "by_direction_context.csv",
                    directory / "by_value_context.csv",
                    directory / "by_combined_context.csv",
                    directory / "by_op_phase.csv",
                    directory / "by_payload.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "fixture_keys",
                    "context_radius",
                    "direction_signal_groups",
                    "repeated_direction_signal_groups",
                    "repeated_direction_signal_bytes",
                    "direction_context_groups",
                    "repeated_direction_context_groups",
                    "repeated_direction_context_bytes",
                    "value_context_groups",
                    "repeated_value_context_groups",
                    "repeated_value_context_bytes",
                    "combined_context_groups",
                    "repeated_combined_context_groups",
                    "repeated_combined_context_bytes",
                    "op_phase_groups",
                    "repeated_op_phase_groups",
                    "repeated_op_phase_bytes",
                    "stable_delta_groups",
                    "stable_delta_bytes",
                    "conflicted_delta_groups",
                    "conflicted_delta_bytes",
                    "payload_signature_groups",
                    "repeated_payload_groups",
                    "repeated_payload_bytes",
                    "best_repeated_context",
                    "best_repeated_context_rows",
                    "best_repeated_context_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_DIRECTION_VALUE_CONTROL_CONTEXT_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "fixture_keys",
                    "context_radius",
                    "direction_signal_groups",
                    "repeated_direction_signal_groups",
                    "repeated_direction_signal_bytes",
                    "direction_context_groups",
                    "repeated_direction_context_groups",
                    "repeated_direction_context_bytes",
                    "value_context_groups",
                    "repeated_value_context_groups",
                    "repeated_value_context_bytes",
                    "combined_context_groups",
                    "op_phase_groups",
                    "payload_signature_groups",
                    "best_repeated_context_rows",
                    "best_repeated_context_bytes",
                ],
            )
        )

    def append_nonzero_gap_direction_value_exact_context_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_exact_context.csv",
                    directory / "by_payload.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "direction_value_groups",
                    "repeated_key_groups",
                    "repeated_key_bytes",
                    "same_delta_groups",
                    "same_delta_bytes",
                    "conflicted_delta_groups",
                    "conflicted_delta_bytes",
                    "payload_signature_groups",
                    "repeated_payload_groups",
                    "repeated_payload_bytes",
                    "singleton_rows",
                    "singleton_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_DIRECTION_VALUE_EXACT_CONTEXT_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "direction_value_groups",
                    "repeated_key_groups",
                    "repeated_key_bytes",
                    "conflicted_delta_groups",
                    "conflicted_delta_bytes",
                    "payload_signature_groups",
                    "singleton_rows",
                    "singleton_bytes",
                ],
            )
        )

    def append_nonzero_gap_direction_value_partial_context_gate(name: str, directory: Path) -> None:
        rows.append(
            audit_generated_report(
                name,
                summary_path=directory / "summary.csv",
                required_paths=[
                    directory / "targets.csv",
                    directory / "by_partial_context.csv",
                    directory / "by_payload.csv",
                ],
                html_report=directory / "index.html",
                expected_fields=[
                    "target_rows",
                    "target_bytes",
                    "direction_value_groups",
                    "repeated_key_groups",
                    "repeated_key_bytes",
                    "ratio_ge90_rows",
                    "ratio_ge90_bytes",
                    "ratio_ge80_rows",
                    "ratio_ge80_bytes",
                    "best_value_exact_total",
                    "same_delta_groups",
                    "same_delta_bytes",
                    "conflicted_delta_groups",
                    "conflicted_delta_bytes",
                    "payload_signature_groups",
                    "repeated_payload_groups",
                    "repeated_payload_bytes",
                    "singleton_rows",
                    "singleton_bytes",
                    "promotion_ready_bytes",
                    "issue_rows",
                ],
                html_marker="TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_DIRECTION_VALUE_PARTIAL_CONTEXT_PROBE",
                positive_fields=[
                    "target_rows",
                    "target_bytes",
                    "direction_value_groups",
                    "repeated_key_groups",
                    "repeated_key_bytes",
                    "ratio_ge90_rows",
                    "ratio_ge90_bytes",
                    "ratio_ge80_rows",
                    "ratio_ge80_bytes",
                    "best_value_exact_total",
                    "conflicted_delta_groups",
                    "conflicted_delta_bytes",
                    "payload_signature_groups",
                    "singleton_rows",
                    "singleton_bytes",
                ],
            )
        )

    append_signature_selector_gate(
        "tex_gap_decoder_len64_promoted_trailing_large32_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_trailing_large32_selector_probe"),
    )
    append_signature_selector_gate(
        "tex_gap_decoder_len64_promoted_leading_len64_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_leading_len64_selector_probe"),
    )
    append_signature_selector_gate(
        "tex_gap_decoder_len64_promoted_internal_small_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_internal_small_selector_probe"),
    )
    append_signature_selector_gate(
        "tex_gap_decoder_len64_promoted_leading_large32_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_leading_large32_selector_probe"),
    )
    append_signature_selector_gate(
        "tex_gap_decoder_len64_promoted_trailing_medium8_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_trailing_medium8_selector_probe"),
    )
    append_replay_gate(
        "tex_gap_decoder_len64_promoted_remaining_replay",
        Path("output/tex_gap_decoder_len64_promoted_remaining_replay"),
    )
    append_gap_queue_gate(
        "tex_gap_decoder_len64_promoted_remaining_gap_queue",
        Path("output/tex_gap_decoder_len64_promoted_remaining_gap_queue"),
    )
    append_run_probe_gate(
        "tex_gap_decoder_len64_promoted_remaining_run_probe",
        Path("output/tex_gap_decoder_len64_promoted_remaining_run_probe"),
    )
    append_zero_queue_gate(
        "tex_gap_decoder_len64_promoted_remaining_zero_queue",
        Path("output/tex_gap_decoder_len64_promoted_remaining_zero_queue"),
    )
    append_zero_source_gate(
        "tex_gap_decoder_len64_promoted_remaining_zero_source_probe",
        Path("output/tex_gap_decoder_len64_promoted_remaining_zero_source_probe"),
    )
    append_signature_selector_gate(
        "tex_gap_decoder_len64_promoted_micro_internal_medium8_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_micro_internal_medium8_selector_probe"),
    )
    append_signature_selector_gate(
        "tex_gap_decoder_len64_promoted_micro_internal_large32_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_micro_internal_large32_selector_probe"),
    )
    append_signature_selector_gate(
        "tex_gap_decoder_len64_promoted_micro_internal_small_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_micro_internal_small_selector_probe"),
    )
    append_signature_selector_gate(
        "tex_gap_decoder_len64_promoted_micro_leading_large32_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_micro_leading_large32_selector_probe"),
    )
    append_signature_selector_gate(
        "tex_gap_decoder_len64_promoted_micro_trailing_medium8_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_micro_trailing_medium8_selector_probe"),
    )
    append_signature_selector_gate(
        "tex_gap_decoder_len64_promoted_micro_trailing_large32_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_micro_trailing_large32_selector_probe"),
    )
    append_replay_gate(
        "tex_gap_decoder_len64_promoted_micro_replay",
        Path("output/tex_gap_decoder_len64_promoted_micro_replay"),
    )
    append_gap_queue_gate(
        "tex_gap_decoder_len64_promoted_micro_gap_queue",
        Path("output/tex_gap_decoder_len64_promoted_micro_gap_queue"),
    )
    append_run_probe_gate(
        "tex_gap_decoder_len64_promoted_micro_run_probe",
        Path("output/tex_gap_decoder_len64_promoted_micro_run_probe"),
    )
    append_zero_queue_gate(
        "tex_gap_decoder_len64_promoted_micro_zero_queue",
        Path("output/tex_gap_decoder_len64_promoted_micro_zero_queue"),
    )
    append_zero_source_gate(
        "tex_gap_decoder_len64_promoted_micro_zero_source_probe",
        Path("output/tex_gap_decoder_len64_promoted_micro_zero_source_probe"),
    )
    append_signature_selector_gate(
        "tex_gap_decoder_len64_promoted_postmicro_internal_medium8_triple_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_postmicro_internal_medium8_triple_selector_probe"),
    )
    append_signature_selector_gate(
        "tex_gap_decoder_len64_promoted_postmicro_internal_small_triple_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_postmicro_internal_small_triple_selector_probe"),
    )
    append_signature_selector_gate(
        "tex_gap_decoder_len64_promoted_postmicro_internal_large32_triple_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_postmicro_internal_large32_triple_selector_probe"),
    )
    append_signature_selector_gate(
        "tex_gap_decoder_len64_promoted_postmicro_trailing_medium8_triple_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_postmicro_trailing_medium8_triple_selector_probe"),
    )
    append_replay_gate(
        "tex_gap_decoder_len64_promoted_triple_replay",
        Path("output/tex_gap_decoder_len64_promoted_triple_replay"),
    )
    append_gap_queue_gate(
        "tex_gap_decoder_len64_promoted_triple_gap_queue",
        Path("output/tex_gap_decoder_len64_promoted_triple_gap_queue"),
    )
    append_run_probe_gate(
        "tex_gap_decoder_len64_promoted_triple_run_probe",
        Path("output/tex_gap_decoder_len64_promoted_triple_run_probe"),
    )
    append_zero_queue_gate(
        "tex_gap_decoder_len64_promoted_triple_zero_queue",
        Path("output/tex_gap_decoder_len64_promoted_triple_zero_queue"),
    )
    append_zero_source_gate(
        "tex_gap_decoder_len64_promoted_triple_zero_source_probe",
        Path("output/tex_gap_decoder_len64_promoted_triple_zero_source_probe"),
    )
    append_signature_selector_gate(
        "tex_gap_decoder_len64_promoted_posttriple_micro_internal_medium8_triple_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_posttriple_micro_internal_medium8_triple_selector_probe"),
    )
    append_signature_selector_gate(
        "tex_gap_decoder_len64_promoted_posttriple_micro_internal_large32_triple_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_posttriple_micro_internal_large32_triple_selector_probe"),
    )
    append_signature_selector_gate(
        "tex_gap_decoder_len64_promoted_posttriple_micro_leading_edge_large32_triple_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_posttriple_micro_leading_edge_large32_triple_selector_probe"),
    )
    append_signature_selector_gate(
        "tex_gap_decoder_len64_promoted_posttriple_micro_internal_small_triple_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_posttriple_micro_internal_small_triple_selector_probe"),
    )
    append_signature_selector_gate(
        "tex_gap_decoder_len64_promoted_posttriple_micro_trailing_medium8_triple_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_posttriple_micro_trailing_medium8_triple_selector_probe"),
    )
    append_replay_gate(
        "tex_gap_decoder_len64_promoted_posttriple_micro_replay",
        Path("output/tex_gap_decoder_len64_promoted_posttriple_micro_replay"),
    )
    append_gap_queue_gate(
        "tex_gap_decoder_len64_promoted_posttriple_micro_gap_queue",
        Path("output/tex_gap_decoder_len64_promoted_posttriple_micro_gap_queue"),
    )
    append_run_probe_gate(
        "tex_gap_decoder_len64_promoted_posttriple_micro_run_probe",
        Path("output/tex_gap_decoder_len64_promoted_posttriple_micro_run_probe"),
    )
    append_zero_queue_gate(
        "tex_gap_decoder_len64_promoted_posttriple_micro_zero_queue",
        Path("output/tex_gap_decoder_len64_promoted_posttriple_micro_zero_queue"),
    )
    append_zero_source_gate(
        "tex_gap_decoder_len64_promoted_posttriple_micro_zero_source_probe",
        Path("output/tex_gap_decoder_len64_promoted_posttriple_micro_zero_source_probe"),
    )
    append_signature_selector_gate(
        "tex_gap_decoder_len64_promoted_residual_trailing_large96_edge_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_residual_trailing_large96_edge_selector_probe"),
    )
    append_signature_selector_gate(
        "tex_gap_decoder_len64_promoted_residual_trailing_large32_edge_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_residual_trailing_large32_edge_selector_probe"),
    )
    append_signature_selector_gate(
        "tex_gap_decoder_len64_promoted_residual_span_full_large32_edge_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_residual_span_full_large32_edge_selector_probe"),
    )
    append_signature_selector_gate(
        "tex_gap_decoder_len64_promoted_residual_span_full_large32_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_residual_span_full_large32_selector_probe"),
    )
    append_signature_selector_gate(
        "tex_gap_decoder_len64_promoted_residual_trailing_medium8_edge_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_residual_trailing_medium8_edge_selector_probe"),
    )
    append_signature_selector_gate(
        "tex_gap_decoder_len64_promoted_residual_trailing_large32_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_residual_trailing_large32_selector_probe"),
    )
    append_signature_selector_gate(
        "tex_gap_decoder_len64_promoted_residual_trailing_small_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_residual_trailing_small_selector_probe"),
    )
    append_signature_selector_gate(
        "tex_gap_decoder_len64_promoted_residual_trailing_small_edge_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_residual_trailing_small_edge_selector_probe"),
    )
    append_replay_gate(
        "tex_gap_decoder_len64_promoted_residual_replay",
        Path("output/tex_gap_decoder_len64_promoted_residual_replay"),
    )
    append_gap_queue_gate(
        "tex_gap_decoder_len64_promoted_residual_gap_queue",
        Path("output/tex_gap_decoder_len64_promoted_residual_gap_queue"),
    )
    append_run_probe_gate(
        "tex_gap_decoder_len64_promoted_residual_run_probe",
        Path("output/tex_gap_decoder_len64_promoted_residual_run_probe"),
    )
    append_zero_queue_gate(
        "tex_gap_decoder_len64_promoted_residual_zero_queue",
        Path("output/tex_gap_decoder_len64_promoted_residual_zero_queue"),
    )
    append_zero_source_gate(
        "tex_gap_decoder_len64_promoted_residual_zero_source_probe",
        Path("output/tex_gap_decoder_len64_promoted_residual_zero_source_probe"),
    )
    append_signature_selector_gate(
        "tex_gap_decoder_len64_promoted_residual_span_full_small_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_residual_span_full_small_selector_probe"),
    )
    append_replay_gate(
        "tex_gap_decoder_len64_promoted_tiny_replay",
        Path("output/tex_gap_decoder_len64_promoted_tiny_replay"),
    )
    append_nonzero_fill_replay_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_fill_replay",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_fill_replay"),
    )
    append_gap_queue_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_fill_gap_queue",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_fill_gap_queue"),
    )
    append_run_probe_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_fill_run_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_fill_run_probe"),
    )
    append_nonzero_queue_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_fill_nonzero_queue",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_fill_nonzero_queue"),
    )
    append_nonzero_source_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_fill_nonzero_source_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_fill_nonzero_source_probe"),
    )
    append_nonzero_gap_source_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_fill_nonzero_gap_source_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_fill_nonzero_gap_source_probe"),
    )
    append_nonzero_gap_pattern_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_fill_nonzero_gap_pattern_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_fill_nonzero_gap_pattern_probe"),
    )
    append_nonzero_gap_fill_rule_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_fill_nonzero_gap_fill_rule_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_fill_nonzero_gap_fill_rule_probe"),
    )
    append_nonzero_gap_fill_selector_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_fill_nonzero_gap_fill_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_fill_nonzero_gap_fill_selector_probe"),
    )
    append_gap_queue_gate(
        "tex_gap_decoder_len64_promoted_tiny_gap_queue",
        Path("output/tex_gap_decoder_len64_promoted_tiny_gap_queue"),
    )
    append_run_probe_gate(
        "tex_gap_decoder_len64_promoted_tiny_run_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_run_probe"),
    )
    append_zero_queue_gate(
        "tex_gap_decoder_len64_promoted_tiny_zero_queue",
        Path("output/tex_gap_decoder_len64_promoted_tiny_zero_queue"),
    )
    append_zero_source_gate(
        "tex_gap_decoder_len64_promoted_tiny_zero_source_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_zero_source_probe"),
    )
    append_nonzero_queue_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_queue",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_queue"),
    )
    append_nonzero_source_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_source_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_source_probe"),
    )
    append_nonzero_gap_source_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_source_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_source_probe"),
    )
    append_nonzero_gap_pattern_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_pattern_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_pattern_probe"),
    )
    append_nonzero_gap_control_pattern_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_control_pattern_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_control_pattern_probe"),
    )
    append_nonzero_gap_value_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_value_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_value_probe"),
    )
    append_nonzero_gap_exact_sequence_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_exact_sequence_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_exact_sequence_probe"),
    )
    append_nonzero_gap_fill_rule_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_fill_rule_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_fill_rule_probe"),
    )
    append_nonzero_gap_fill_selector_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_fill_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_fill_selector_probe"),
    )
    append_nonzero_gap_palette_selector_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_palette_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_palette_selector_probe"),
    )
    append_nonzero_gap_palette_shape_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_palette_shape_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_palette_shape_probe"),
    )
    append_nonzero_gap_palette_shape_control_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_palette_shape_control_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_palette_shape_control_probe"),
    )
    append_nonzero_gap_palette_shape_value_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_palette_shape_value_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_palette_shape_value_probe"),
    )
    append_nonzero_gap_palette_pair_value_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_palette_pair_value_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_palette_pair_value_probe"),
    )
    append_nonzero_gap_dominant_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_dominant_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_dominant_probe"),
    )
    append_nonzero_gap_noisy_shape_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_noisy_shape_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_noisy_shape_probe"),
    )
    append_nonzero_gap_gradient_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_probe"),
    )
    append_nonzero_gap_gradient_repeat_context_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_repeat_context_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_repeat_context_probe"),
    )
    append_nonzero_gap_gradient_seed_unlock_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_unlock_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_unlock_probe"),
    )
    append_nonzero_gap_gradient_seed_shift_family_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_shift_family_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_shift_family_probe"),
    )
    append_nonzero_gap_gradient_seed_delta_selector_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_selector_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_selector_probe"),
    )
    append_nonzero_gap_gradient_seed_delta_context_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_context_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_context_probe"),
    )
    append_nonzero_gap_gradient_seed_delta_phase_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_phase_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_phase_probe"),
    )
    append_nonzero_gap_gradient_seed_delta_state_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_state_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_state_probe"),
    )
    append_nonzero_gap_gradient_seed_delta_opcode_sequence_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_opcode_sequence_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_opcode_sequence_probe"),
    )
    append_nonzero_gap_gradient_seed_delta_semantic_opcode_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_semantic_opcode_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_semantic_opcode_probe"),
    )
    append_nonzero_gap_flat_walk_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_probe"),
    )
    append_nonzero_gap_flat_walk_source_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_source_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_source_probe"),
    )
    append_nonzero_gap_flat_walk_shape_control_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_shape_control_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_shape_control_probe"),
    )
    append_nonzero_gap_flat_walk_value_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_value_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_value_probe"),
    )
    append_nonzero_gap_flat_walk_backref_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_backref_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_backref_probe"),
    )
    append_nonzero_gap_flat_walk_palette_seed_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_seed_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_seed_probe"),
    )
    append_nonzero_gap_flat_walk_palette_mix_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_mix_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_mix_probe"),
    )
    append_nonzero_gap_flat_walk_backref_chain_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_backref_chain_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_backref_chain_probe"),
    )
    append_nonzero_gap_flat_walk_palette_signature_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_signature_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_signature_probe"),
    )
    append_nonzero_gap_flat_walk_palette_context_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_context_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_context_probe"),
    )
    append_nonzero_gap_micro_token_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_micro_token_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_micro_token_probe"),
    )
    append_nonzero_gap_mixed_token_uniqueness_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_token_uniqueness_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_token_uniqueness_probe"),
    )
    append_nonzero_gap_mixed_token_band_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_token_band_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_token_band_probe"),
    )
    append_nonzero_gap_mixed_token_backref_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_token_backref_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_token_backref_probe"),
    )
    append_nonzero_gap_mixed_token_control_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_token_control_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_token_control_probe"),
    )
    append_nonzero_gap_mixed_token_control_context_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_token_control_context_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_token_control_context_probe"),
    )
    append_nonzero_gap_jump_token_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_jump_token_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_jump_token_probe"),
    )
    append_nonzero_gap_jump_token_backref_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_jump_token_backref_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_jump_token_backref_probe"),
    )
    append_nonzero_gap_jump_token_context_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_jump_token_context_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_jump_token_context_probe"),
    )
    append_nonzero_gap_repeated_nibble_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_repeated_nibble_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_repeated_nibble_probe"),
    )
    append_nonzero_gap_repeated_nibble_context_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_repeated_nibble_context_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_repeated_nibble_context_probe"),
    )
    append_nonzero_gap_mixed_jump_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_jump_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_jump_probe"),
    )
    append_nonzero_gap_mixed_control_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_control_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_control_probe"),
    )
    append_nonzero_gap_residual_jump_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_residual_jump_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_residual_jump_probe"),
    )
    append_nonzero_gap_residual_control_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_residual_control_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_residual_control_probe"),
    )
    append_nonzero_gap_dense_jump_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_dense_jump_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_dense_jump_probe"),
    )
    append_nonzero_gap_dense_control_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_dense_control_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_dense_control_probe"),
    )
    append_nonzero_gap_control_signal_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_control_signal_gate_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_control_signal_gate_probe"),
    )
    append_nonzero_gap_weak_control_value_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_weak_control_value_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_weak_control_value_probe"),
    )
    append_nonzero_gap_direction_value_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_probe"),
    )
    append_nonzero_gap_direction_value_offset_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_offset_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_offset_probe"),
    )
    append_nonzero_gap_direction_value_delta_context_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_delta_context_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_delta_context_probe"),
    )
    append_nonzero_gap_direction_value_payload_grammar_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_payload_grammar_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_payload_grammar_probe"),
    )
    append_nonzero_gap_direction_value_source_profile_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_source_profile_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_source_profile_probe"),
    )
    append_nonzero_gap_direction_value_source_value_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_source_value_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_source_value_probe"),
    )
    append_nonzero_gap_direction_value_source_window_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_source_window_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_source_window_probe"),
    )
    append_nonzero_gap_direction_value_control_context_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_control_context_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_control_context_probe"),
    )
    append_nonzero_gap_direction_value_exact_context_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_exact_context_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_exact_context_probe"),
    )
    append_nonzero_gap_direction_value_partial_context_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_partial_context_probe",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_partial_context_probe"),
    )
    append_nonzero_gap_noisy_review_gate(
        "tex_gap_decoder_len64_promoted_tiny_nonzero_gap_noisy_review",
        Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_noisy_review"),
    )
    tex_gap_replay_gate, tex_gap_replay_rows, tex_gap_replay_exact, tex_gap_replay_best_prefix = (
        audit_tex_gap_fixture_replay(
            DEFAULT_TEX_GAP_FIXTURE_REPLAY_SUMMARY,
            DEFAULT_TEX_GAP_FIXTURE_REPLAY_ROWS,
            DEFAULT_TEX_GAP_FIXTURE_REPLAY_BEST,
            DEFAULT_TEX_GAP_FIXTURE_REPLAY_HTML,
        )
    )
    rows.append(tex_gap_replay_gate)
    gallery_gate, gallery_count = audit_gallery(DEFAULT_PACK_GALLERY, DEFAULT_PACK_MANIFEST)
    rows.append(gallery_gate)
    dashboard_gate, dashboard_cards = audit_dashboard(DEFAULT_DASHBOARD)
    rows.append(dashboard_gate)
    rows.append(audit_run_hd(DEFAULT_RUN_HD, DEFAULT_DOSBOX_CONF))

    failed = [row for row in rows if row["status"] != "pass"]
    summary_row = {
        "status": "pass" if not failed else "fail",
        "gates": str(len(rows)),
        "passed": str(len(rows) - len(failed)),
        "failed": str(len(failed)),
        "total_fullhd_pngs": str(total_fullhd),
        "vqa_fullhd_frames": str(vqa_count),
        "vqa_gallery_entries": str(vqa_gallery_count),
        "vqa_status_archives": str(vqa_status_archives),
        "archive_coverage_visual_entries": str(archive_coverage_visual),
        "still_fullhd_images": str(still_count),
        "still_gallery_entries": str(still_gallery_count),
        "cdcache_fullhd_outputs": str(cdcache_descriptor_count + cdcache_tile_count),
        "cdcache_pack_assets": str(pack_count),
        "cdcache_pack_linked_assets": str(pack_linked),
        "tex_hd_linked_assets": str(tex_assets),
        "tex_hd_material_links": str(tex_material_links),
        "tex_reference_unique_pcx": str(tex_reference_unique),
        "tex_reference_covered_unique_pcx": str(tex_reference_covered),
        "tex_reference_missing_unique_pcx": str(tex_reference_missing),
        "tex_missing_reference_raw_unique_pcx": str(tex_missing_raw_unique),
        "tex_missing_reference_material_unique_pcx": str(tex_missing_material_unique),
        "cdcache_raw_probe_candidate_rows": str(raw_probe_candidates),
        "cdcache_alias_candidate_assets": str(alias_candidate_count),
        "cdcache_alias_synthetic_descriptors": str(alias_synthetic_descriptors),
        "cdcache_alias_fullhd_outputs": str(alias_descriptor_count + alias_tile_count),
        "cdcache_tex_alias_pack_assets": str(alias_pack_assets),
        "tex_material_decode_pack_assets": str(tex_material_decode_assets),
        "tex_raw_same_archive_promoted_pack_eligible": str(tex_raw_same_archive_eligible),
        "tex_augmented_exact_or_alias_unique_pcx": str(tex_augmented_exact_or_alias),
        "tex_augmented_exact_alias_or_decoded_unique_pcx": str(tex_augmented_exact_alias_or_decoded),
        "tex_augmented_exact_alias_decoded_or_raw_unique_pcx": str(
            tex_augmented_exact_alias_decoded_or_raw
        ),
        "tex_augmented_unresolved_unique_pcx": str(tex_augmented_unresolved),
        "tex_unresolved_material_probe_fullhd_previews": str(tex_probe_previews),
        "tex_unresolved_material_probe_unique_pcx": str(tex_probe_unique_pcx),
        "tex_probe_analysis_best_candidates": str(tex_probe_analysis_best),
        "tex_probe_analysis_segments": str(tex_probe_analysis_segments),
        "tex_material_decoder_queue_rows": str(tex_decoder_queue_rows),
        "tex_material_decoder_queue_segments": str(tex_decoder_queue_segments),
        "tex_remaining_reference_profile_unique": str(tex_remaining_profile_unique),
        "tex_exact_cdcache_compare_segments": str(tex_exact_compare_segments),
        "tex_exact_cdcache_compare_32b_matches": str(tex_exact_compare_32b),
        "tex_exact_cdcache_compare_16b_matches": str(tex_exact_compare_16b),
        "tex_exact_chunk_evidence_matches": str(tex_chunk_evidence_matches),
        "tex_exact_chunk_evidence_matched_segments": str(tex_chunk_evidence_segments),
        "tex_exact_match_overlays_fullhd": str(tex_match_overlay_fullhd),
        "tex_exact_match_overlays_pixels": str(tex_match_overlay_pixels),
        "tex_decoder_seed_strong": str(tex_decoder_seed_strong),
        "tex_decoder_seed_medium": str(tex_decoder_seed_medium),
        "tex_exact_chunk_scan_rows": str(tex_exact_chunk_scan_rows),
        "tex_exact_chunk_scan_capped_groups": str(tex_exact_chunk_scan_capped),
        "tex_exact_chunk_clusters": str(tex_exact_chunk_clusters),
        "tex_exact_chunk_cluster_strong": str(tex_exact_chunk_cluster_strong),
        "tex_exact_chunk_cluster_longest_span": str(tex_exact_chunk_cluster_span),
        "tex_exact_cluster_overlays_fullhd": str(tex_exact_cluster_overlay_fullhd),
        "tex_exact_cluster_overlays_pixels": str(tex_exact_cluster_overlay_pixels),
        "tex_decoder_run_corpus_runs": str(tex_decoder_run_corpus_runs),
        "tex_decoder_run_corpus_bytes": str(tex_decoder_run_corpus_bytes),
        "tex_partial_raw_decoder_fullhd": str(tex_partial_raw_decoder_fullhd),
        "tex_partial_raw_decoder_bytes": str(tex_partial_raw_decoder_bytes),
        "tex_partial_raw_coverage_pixels": str(tex_partial_raw_coverage_pixels),
        "tex_partial_raw_coverage_gaps": str(tex_partial_raw_coverage_gaps),
        "tex_gap_frontier_gaps": str(tex_gap_frontier_gaps),
        "tex_gap_frontier_segment_windows": str(tex_gap_frontier_windows),
        "tex_gap_opcode_probe_rows": str(tex_gap_opcode_rows),
        "tex_gap_opcode_probe_best_prefix": str(tex_gap_opcode_best_prefix),
        "tex_gap_opcode_probe_exact_replays": str(tex_gap_opcode_exact_replays),
        "tex_gap_rle_probe_pairs": str(tex_gap_rle_pairs),
        "tex_gap_rle_probe_full_matches": str(tex_gap_rle_full_matches),
        "tex_gap_rle_probe_best_prefix": str(tex_gap_rle_best_prefix),
        "tex_gap_rule_queue_rows": str(tex_gap_rule_rows),
        "tex_gap_rule_queue_rule_types": str(tex_gap_rule_types),
        "tex_gap_rule_queue_top_priority": str(tex_gap_rule_top_priority),
        "tex_gap_rule_fixture_rows": str(tex_gap_fixture_rows),
        "tex_gap_rule_fixture_files": str(tex_gap_fixture_files),
        "tex_gap_rule_fixture_fragment_bytes": str(tex_gap_fixture_fragment_bytes),
        "tex_gap_zero_run_fixtures": str(tex_gap_zero_fixtures),
        "tex_gap_zero_run_rows": str(tex_gap_zero_runs),
        "tex_gap_zero_run_max_zero": str(tex_gap_zero_max),
        "tex_gap_geometry_replay_rows": str(tex_gap_geometry_rows),
        "tex_gap_geometry_replay_best_prefix": str(tex_gap_geometry_prefix),
        "tex_gap_geometry_replay_best_exact": str(tex_gap_geometry_exact),
        "tex_gap_nonzero_stream_rows": str(tex_gap_nonzero_rows),
        "tex_gap_nonzero_stream_best_prefix": str(tex_gap_nonzero_prefix),
        "tex_gap_nonzero_stream_best_exact": str(tex_gap_nonzero_exact),
        "tex_gap_control_word_hits": str(tex_gap_control_hits),
        "tex_gap_control_word_u16le_hits": str(tex_gap_control_u16le),
        "tex_gap_control_word_metrics": str(tex_gap_control_metrics),
        "tex_gap_header_schema_blocks": str(tex_gap_header_blocks),
        "tex_gap_header_schema_candidates": str(tex_gap_header_candidates),
        "tex_gap_header_schema_dimension_blocks": str(tex_gap_header_dimension_blocks),
        "tex_gap_header_schema_best_prefix": str(tex_gap_header_best_prefix),
        "tex_gap_header_schema_best_exact": str(tex_gap_header_best_exact),
        "tex_gap_row_stride_rows": str(tex_gap_row_stride_rows),
        "tex_gap_row_stride_best_prefix": str(tex_gap_row_stride_prefix),
        "tex_gap_row_stride_best_exact": str(tex_gap_row_stride_exact),
        "tex_gap_row_stride_mismatch_candidates": str(tex_gap_row_stride_mismatch_candidates),
        "tex_gap_row_stride_mismatch_rows": str(tex_gap_row_stride_mismatch_rows),
        "tex_gap_row_stride_mismatch_full_rows": str(tex_gap_row_stride_mismatch_full_rows),
        "tex_gap_row_delta_rows": str(tex_gap_row_delta_rows),
        "tex_gap_row_delta_best_adjusted": str(tex_gap_row_delta_adjusted),
        "tex_gap_row_delta_best_gain": str(tex_gap_row_delta_gain),
        "tex_gap_row_transform_rows": str(tex_gap_row_transform_rows),
        "tex_gap_row_transform_best": str(tex_gap_row_transform_best),
        "tex_gap_row_transform_gain": str(tex_gap_row_transform_gain),
        "tex_gap_row_control_rows": str(tex_gap_row_control_rows),
        "tex_gap_row_control_groups": str(tex_gap_row_control_groups),
        "tex_gap_row_control_best_metric_hits": str(tex_gap_row_control_best_metric_hits),
        "tex_gap_row_sequence_rows": str(tex_gap_row_sequence_rows),
        "tex_gap_row_sequence_step_groups": str(tex_gap_row_sequence_step_groups),
        "tex_gap_row_sequence_rewinds": str(tex_gap_row_sequence_rewinds),
        "tex_gap_row_literal_scan_rows": str(tex_gap_row_literal_scan_rows),
        "tex_gap_row_literal_scan_best": str(tex_gap_row_literal_scan_best),
        "tex_gap_row_literal_scan_gain": str(tex_gap_row_literal_scan_gain),
        "tex_gap_row_fill_run_rows": str(tex_gap_row_fill_run_rows),
        "tex_gap_row_fill_run_best": str(tex_gap_row_fill_run_best),
        "tex_gap_row_fill_run_full_rows": str(tex_gap_row_fill_run_full_rows),
        "tex_gap_control_grammar_rows": str(tex_gap_control_grammar_rows),
        "tex_gap_control_grammar_best_prefix": str(tex_gap_control_grammar_best_prefix),
        "tex_gap_control_grammar_best_exact": str(tex_gap_control_grammar_best_exact),
        "tex_gap_mismatch_trace_rows": str(tex_gap_mismatch_trace_rows),
        "tex_gap_mismatch_trace_ops": str(tex_gap_mismatch_trace_ops),
        "tex_gap_mismatch_trace_control_prefix": str(tex_gap_mismatch_trace_control_prefix),
        "tex_gap_mismatch_trace_replay_prefix": str(tex_gap_mismatch_trace_replay_prefix),
        "tex_gap_zero_literal_switch_rows": str(tex_gap_zero_literal_switch_rows),
        "tex_gap_zero_literal_switch_best_prefix": str(tex_gap_zero_literal_switch_best_prefix),
        "tex_gap_zero_literal_switch_best_exact": str(tex_gap_zero_literal_switch_best_exact),
        "tex_gap_zero_literal_segmentation_covered": str(tex_gap_zero_literal_segmentation_covered),
        "tex_gap_zero_literal_segmentation_gap": str(tex_gap_zero_literal_segmentation_gap),
        "tex_gap_zero_literal_segmentation_literal": str(tex_gap_zero_literal_segmentation_literal),
        "tex_gap_zero_literal_segmentation_full_fixtures": str(
            tex_gap_zero_literal_segmentation_full_fixtures
        ),
        "tex_gap_segmentation_control_correlation_ops": str(
            tex_gap_segmentation_control_correlation_ops
        ),
        "tex_gap_segmentation_control_correlation_literal_ops": str(
            tex_gap_segmentation_control_correlation_literal_ops
        ),
        "tex_gap_segmentation_control_correlation_forward_steps": str(
            tex_gap_segmentation_control_correlation_forward_steps
        ),
        "tex_gap_segmentation_control_correlation_len_hits": str(
            tex_gap_segmentation_control_correlation_len_hits
        ),
        "tex_gap_literal_token_match_ops": str(tex_gap_literal_token_match_ops),
        "tex_gap_literal_token_match_bytes": str(tex_gap_literal_token_match_bytes),
        "tex_gap_literal_token_full_fixtures": str(tex_gap_literal_token_full_fixtures),
        "tex_gap_literal_token_small_matches": str(tex_gap_literal_token_small_matches),
        "tex_gap_literal_token_classifier_small_fp": str(tex_gap_literal_token_classifier_small_fp),
        "tex_gap_literal_token_classifier_high_recall_fp": str(
            tex_gap_literal_token_classifier_high_recall_fp
        ),
        "tex_gap_literal_token_classifier_high_precision_fp": str(
            tex_gap_literal_token_classifier_high_precision_fp
        ),
        "tex_gap_literal_token_classifier_rows": str(tex_gap_literal_token_classifier_rows),
        "tex_gap_literal_fp_rejection_full_recall_fp": str(tex_gap_literal_fp_rejection_full_recall_fp),
        "tex_gap_literal_fp_rejection_full_recall_false_bytes": str(
            tex_gap_literal_fp_rejection_full_recall_false_bytes
        ),
        "tex_gap_literal_fp_rejection_low_false_fp": str(tex_gap_literal_fp_rejection_low_false_fp),
        "tex_gap_literal_fp_rejection_candidate_rows": str(tex_gap_literal_fp_rejection_candidate_rows),
        "tex_gap_zero_run_alignment_zero_ops": str(tex_gap_zero_run_alignment_zero_ops),
        "tex_gap_zero_run_alignment_zero_bytes": str(tex_gap_zero_run_alignment_zero_bytes),
        "tex_gap_zero_run_alignment_len64_ops": str(tex_gap_zero_run_alignment_len64_ops),
        "tex_gap_zero_run_alignment_fill_mod64_ops": str(tex_gap_zero_run_alignment_fill_mod64_ops),
        "tex_gap_zero_control_risk_current_false_bytes": str(
            tex_gap_zero_control_risk_current_false_bytes
        ),
        "tex_gap_zero_control_risk_false_free_bytes": str(
            tex_gap_zero_control_risk_false_free_bytes
        ),
        "tex_gap_zero_control_risk_low_false_bytes": str(tex_gap_zero_control_risk_low_false_bytes),
        "tex_gap_zero_control_risk_classifier_rows": str(tex_gap_zero_control_risk_classifier_rows),
        "tex_gap_decoder_skeleton_best_nonoracle_bytes": str(
            tex_gap_decoder_skeleton_best_nonoracle_bytes
        ),
        "tex_gap_decoder_skeleton_best_nonoracle_false": str(
            tex_gap_decoder_skeleton_best_nonoracle_false
        ),
        "tex_gap_decoder_skeleton_best_oracle_bytes": str(tex_gap_decoder_skeleton_best_oracle_bytes),
        "tex_gap_decoder_skeleton_candidate_rows": str(tex_gap_decoder_skeleton_candidate_rows),
        "tex_gap_decoder_risk_adjusted_best_correct_bytes": str(
            tex_gap_decoder_risk_adjusted_best_correct_bytes
        ),
        "tex_gap_decoder_risk_adjusted_best_false_bytes": str(
            tex_gap_decoder_risk_adjusted_best_false_bytes
        ),
        "tex_gap_decoder_risk_adjusted_best_net_bytes": str(
            tex_gap_decoder_risk_adjusted_best_net_bytes
        ),
        "tex_gap_decoder_risk_adjusted_best_low_false_bytes": str(
            tex_gap_decoder_risk_adjusted_best_low_false_bytes
        ),
        "tex_gap_decoder_risk_adjusted_candidate_rows": str(
            tex_gap_decoder_risk_adjusted_candidate_rows
        ),
        "tex_gap_decoder_seed_replay_selected_bytes": str(
            tex_gap_decoder_seed_replay_selected_bytes
        ),
        "tex_gap_decoder_seed_replay_trusted_bytes": str(
            tex_gap_decoder_seed_replay_trusted_bytes
        ),
        "tex_gap_decoder_seed_replay_false_bytes": str(tex_gap_decoder_seed_replay_false_bytes),
        "tex_gap_decoder_seed_replay_fixture_rows": str(tex_gap_decoder_seed_replay_fixture_rows),
        "tex_gap_decoder_seed_replay_fullhd_previews": str(
            tex_gap_decoder_seed_replay_fullhd_previews
        ),
        "tex_gap_decoder_control_promotion_bytes": str(tex_gap_decoder_control_promotion_bytes),
        "tex_gap_decoder_control_promotion_literal_bytes": str(
            tex_gap_decoder_control_promotion_literal_bytes
        ),
        "tex_gap_decoder_control_promotion_zero_bytes": str(
            tex_gap_decoder_control_promotion_zero_bytes
        ),
        "tex_gap_decoder_control_promotion_ambiguous_groups": str(
            tex_gap_decoder_control_promotion_ambiguous_groups
        ),
        "tex_gap_decoder_false_risk_promoted_bytes": str(
            tex_gap_decoder_false_risk_promoted_bytes
        ),
        "tex_gap_decoder_false_risk_rejected_bytes": str(
            tex_gap_decoder_false_risk_rejected_bytes
        ),
        "tex_gap_decoder_false_risk_review_bytes": str(
            tex_gap_decoder_false_risk_review_bytes
        ),
        "tex_gap_decoder_false_risk_safe_rejectors": str(
            tex_gap_decoder_false_risk_safe_rejectors
        ),
        "tex_gap_decoder_clean_replay_bytes": str(tex_gap_decoder_clean_replay_bytes),
        "tex_gap_decoder_clean_replay_rejected_bytes": str(
            tex_gap_decoder_clean_replay_rejected_bytes
        ),
        "tex_gap_decoder_clean_replay_fullhd_previews": str(
            tex_gap_decoder_clean_replay_fullhd_previews
        ),
        "tex_gap_decoder_clean_gap_unresolved_bytes": str(
            tex_gap_decoder_clean_gap_unresolved_bytes
        ),
        "tex_gap_decoder_clean_gap_span_rows": str(tex_gap_decoder_clean_gap_span_rows),
        "tex_gap_decoder_clean_gap_largest_span": str(
            tex_gap_decoder_clean_gap_largest_span
        ),
        "tex_gap_decoder_unresolved_run_zero_bytes": str(
            tex_gap_decoder_unresolved_run_zero_bytes
        ),
        "tex_gap_decoder_unresolved_run_rows": str(tex_gap_decoder_unresolved_run_rows),
        "tex_gap_decoder_unresolved_run_max_zero": str(
            tex_gap_decoder_unresolved_run_max_zero
        ),
        "tex_gap_decoder_unresolved_zero_queue_bytes": str(
            tex_gap_decoder_unresolved_zero_queue_bytes
        ),
        "tex_gap_decoder_unresolved_zero_queue_internal_bytes": str(
            tex_gap_decoder_unresolved_zero_queue_internal_bytes
        ),
        "tex_gap_decoder_unresolved_zero_queue_signatures": str(
            tex_gap_decoder_unresolved_zero_queue_signatures
        ),
        "tex_gap_decoder_len64_internal_rows": str(tex_gap_decoder_len64_internal_rows),
        "tex_gap_decoder_len64_internal_bytes": str(tex_gap_decoder_len64_internal_bytes),
        "tex_gap_decoder_len64_internal_top_neighbor_rows": str(
            tex_gap_decoder_len64_internal_top_neighbor_rows
        ),
        "tex_gap_decoder_len64_source_joined_rows": str(
            tex_gap_decoder_len64_source_joined_rows
        ),
        "tex_gap_decoder_len64_source_control_refs": str(
            tex_gap_decoder_len64_source_control_refs
        ),
        "tex_gap_decoder_len64_source_top_ref_rows": str(
            tex_gap_decoder_len64_source_top_ref_rows
        ),
        "tex_gap_decoder_len64_selector_best_bytes": str(
            tex_gap_decoder_len64_selector_best_bytes
        ),
        "tex_gap_decoder_len64_selector_greedy_bytes": str(
            tex_gap_decoder_len64_selector_greedy_bytes
        ),
        "tex_gap_decoder_len64_selector_greedy_selectors": str(
            tex_gap_decoder_len64_selector_greedy_selectors
        ),
        "tex_gap_decoder_len64_promoted_added_bytes": str(
            tex_gap_decoder_len64_promoted_added_bytes
        ),
        "tex_gap_decoder_len64_promoted_total_clean_bytes": str(
            tex_gap_decoder_len64_promoted_total_clean_bytes
        ),
        "tex_gap_decoder_len64_promoted_remaining_unresolved_bytes": str(
            tex_gap_decoder_len64_promoted_remaining_unresolved_bytes
        ),
        "tex_gap_decoder_len64_promoted_gap_unresolved_bytes": str(
            tex_gap_decoder_len64_promoted_gap_unresolved_bytes
        ),
        "tex_gap_decoder_len64_promoted_gap_span_rows": str(
            tex_gap_decoder_len64_promoted_gap_span_rows
        ),
        "tex_gap_decoder_len64_promoted_gap_largest_span": str(
            tex_gap_decoder_len64_promoted_gap_largest_span
        ),
        "tex_gap_decoder_len64_promoted_run_zero_bytes": str(
            tex_gap_decoder_len64_promoted_run_zero_bytes
        ),
        "tex_gap_decoder_len64_promoted_run_rows": str(
            tex_gap_decoder_len64_promoted_run_rows
        ),
        "tex_gap_decoder_len64_promoted_run_max_zero": str(
            tex_gap_decoder_len64_promoted_run_max_zero
        ),
        "tex_gap_decoder_len64_promoted_zero_queue_bytes": str(
            tex_gap_decoder_len64_promoted_zero_queue_bytes
        ),
        "tex_gap_decoder_len64_promoted_zero_queue_internal_bytes": str(
            tex_gap_decoder_len64_promoted_zero_queue_internal_bytes
        ),
        "tex_gap_decoder_len64_promoted_zero_queue_signatures": str(
            tex_gap_decoder_len64_promoted_zero_queue_signatures
        ),
        "tex_gap_decoder_len64_promoted_zero_source_joined_rows": str(
            tex_gap_decoder_len64_promoted_zero_source_joined_rows
        ),
        "tex_gap_decoder_len64_promoted_zero_source_joined_bytes": str(
            tex_gap_decoder_len64_promoted_zero_source_joined_bytes
        ),
        "tex_gap_decoder_len64_promoted_zero_source_control_refs": str(
            tex_gap_decoder_len64_promoted_zero_source_control_refs
        ),
        "tex_gap_decoder_len64_promoted_large32_selector_best_bytes": str(
            tex_gap_decoder_len64_promoted_large32_selector_best_bytes
        ),
        "tex_gap_decoder_len64_promoted_large32_selector_greedy_bytes": str(
            tex_gap_decoder_len64_promoted_large32_selector_greedy_bytes
        ),
        "tex_gap_decoder_len64_promoted_large32_selector_greedy_selectors": str(
            tex_gap_decoder_len64_promoted_large32_selector_greedy_selectors
        ),
        "tex_gap_decoder_len64_promoted_large32_replay_added_bytes": str(
            tex_gap_decoder_len64_promoted_large32_replay_added_bytes
        ),
        "tex_gap_decoder_len64_promoted_large32_replay_total_clean_bytes": str(
            tex_gap_decoder_len64_promoted_large32_replay_total_clean_bytes
        ),
        "tex_gap_decoder_len64_promoted_large32_replay_remaining_unresolved_bytes": str(
            tex_gap_decoder_len64_promoted_large32_replay_remaining_unresolved_bytes
        ),
        "tex_gap_decoder_len64_promoted_large32_gap_unresolved_bytes": str(
            tex_gap_decoder_len64_promoted_large32_gap_unresolved_bytes
        ),
        "tex_gap_decoder_len64_promoted_large32_gap_span_rows": str(
            tex_gap_decoder_len64_promoted_large32_gap_span_rows
        ),
        "tex_gap_decoder_len64_promoted_large32_gap_largest_span": str(
            tex_gap_decoder_len64_promoted_large32_gap_largest_span
        ),
        "tex_gap_decoder_len64_promoted_large32_run_zero_bytes": str(
            tex_gap_decoder_len64_promoted_large32_run_zero_bytes
        ),
        "tex_gap_decoder_len64_promoted_large32_run_rows": str(
            tex_gap_decoder_len64_promoted_large32_run_rows
        ),
        "tex_gap_decoder_len64_promoted_large32_run_max_zero": str(
            tex_gap_decoder_len64_promoted_large32_run_max_zero
        ),
        "tex_gap_decoder_len64_promoted_large32_zero_queue_bytes": str(
            tex_gap_decoder_len64_promoted_large32_zero_queue_bytes
        ),
        "tex_gap_decoder_len64_promoted_large32_zero_queue_internal_bytes": str(
            tex_gap_decoder_len64_promoted_large32_zero_queue_internal_bytes
        ),
        "tex_gap_decoder_len64_promoted_large32_zero_queue_signatures": str(
            tex_gap_decoder_len64_promoted_large32_zero_queue_signatures
        ),
        "tex_gap_decoder_len64_promoted_large32_zero_source_joined_rows": str(
            tex_gap_decoder_len64_promoted_large32_zero_source_joined_rows
        ),
        "tex_gap_decoder_len64_promoted_large32_zero_source_joined_bytes": str(
            tex_gap_decoder_len64_promoted_large32_zero_source_joined_bytes
        ),
        "tex_gap_decoder_len64_promoted_large32_zero_source_control_refs": str(
            tex_gap_decoder_len64_promoted_large32_zero_source_control_refs
        ),
        "tex_gap_decoder_len64_promoted_medium8_selector_best_bytes": str(
            tex_gap_decoder_len64_promoted_medium8_selector_best_bytes
        ),
        "tex_gap_decoder_len64_promoted_medium8_selector_greedy_bytes": str(
            tex_gap_decoder_len64_promoted_medium8_selector_greedy_bytes
        ),
        "tex_gap_decoder_len64_promoted_medium8_selector_greedy_selectors": str(
            tex_gap_decoder_len64_promoted_medium8_selector_greedy_selectors
        ),
        "tex_gap_decoder_len64_promoted_medium8_replay_added_bytes": str(
            tex_gap_decoder_len64_promoted_medium8_replay_added_bytes
        ),
        "tex_gap_decoder_len64_promoted_medium8_replay_total_clean_bytes": str(
            tex_gap_decoder_len64_promoted_medium8_replay_total_clean_bytes
        ),
        "tex_gap_decoder_len64_promoted_medium8_replay_remaining_unresolved_bytes": str(
            tex_gap_decoder_len64_promoted_medium8_replay_remaining_unresolved_bytes
        ),
        "tex_gap_decoder_len64_promoted_medium8_gap_unresolved_bytes": str(
            tex_gap_decoder_len64_promoted_medium8_gap_unresolved_bytes
        ),
        "tex_gap_decoder_len64_promoted_medium8_gap_span_rows": str(
            tex_gap_decoder_len64_promoted_medium8_gap_span_rows
        ),
        "tex_gap_decoder_len64_promoted_medium8_gap_largest_span": str(
            tex_gap_decoder_len64_promoted_medium8_gap_largest_span
        ),
        "tex_gap_decoder_len64_promoted_medium8_run_zero_bytes": str(
            tex_gap_decoder_len64_promoted_medium8_run_zero_bytes
        ),
        "tex_gap_decoder_len64_promoted_medium8_run_rows": str(
            tex_gap_decoder_len64_promoted_medium8_run_rows
        ),
        "tex_gap_decoder_len64_promoted_medium8_run_max_zero": str(
            tex_gap_decoder_len64_promoted_medium8_run_max_zero
        ),
        "tex_gap_decoder_len64_promoted_medium8_zero_queue_bytes": str(
            tex_gap_decoder_len64_promoted_medium8_zero_queue_bytes
        ),
        "tex_gap_decoder_len64_promoted_medium8_zero_queue_internal_bytes": str(
            tex_gap_decoder_len64_promoted_medium8_zero_queue_internal_bytes
        ),
        "tex_gap_decoder_len64_promoted_medium8_zero_queue_signatures": str(
            tex_gap_decoder_len64_promoted_medium8_zero_queue_signatures
        ),
        "tex_gap_decoder_len64_promoted_medium8_zero_source_joined_rows": str(
            tex_gap_decoder_len64_promoted_medium8_zero_source_joined_rows
        ),
        "tex_gap_decoder_len64_promoted_medium8_zero_source_joined_bytes": str(
            tex_gap_decoder_len64_promoted_medium8_zero_source_joined_bytes
        ),
        "tex_gap_decoder_len64_promoted_medium8_zero_source_control_refs": str(
            tex_gap_decoder_len64_promoted_medium8_zero_source_control_refs
        ),
        "tex_gap_decoder_len64_promoted_medium8_remaining_selector_best_bytes": str(
            tex_gap_decoder_len64_promoted_medium8_remaining_selector_best_bytes
        ),
        "tex_gap_decoder_len64_promoted_medium8_remaining_selector_greedy_bytes": str(
            tex_gap_decoder_len64_promoted_medium8_remaining_selector_greedy_bytes
        ),
        "tex_gap_decoder_len64_promoted_medium8_remaining_selector_greedy_selectors": str(
            tex_gap_decoder_len64_promoted_medium8_remaining_selector_greedy_selectors
        ),
        "tex_gap_decoder_len64_promoted_large32_remaining_selector_best_bytes": str(
            tex_gap_decoder_len64_promoted_large32_remaining_selector_best_bytes
        ),
        "tex_gap_decoder_len64_promoted_large32_remaining_selector_greedy_bytes": str(
            tex_gap_decoder_len64_promoted_large32_remaining_selector_greedy_bytes
        ),
        "tex_gap_decoder_len64_promoted_large32_remaining_selector_greedy_selectors": str(
            tex_gap_decoder_len64_promoted_large32_remaining_selector_greedy_selectors
        ),
        "tex_gap_fixture_replay_rows": str(tex_gap_replay_rows),
        "tex_gap_fixture_replay_exact_matches": str(tex_gap_replay_exact),
        "tex_gap_fixture_replay_best_prefix": str(tex_gap_replay_best_prefix),
        "cdcache_gallery_assets": str(gallery_count),
        "dashboard_cards": str(dashboard_cards),
    }
    audit_path, summary_path = write_outputs(args.output, rows, summary_row)

    print(
        f"Full HD audit: {summary_row['status']} "
        f"({summary_row['passed']}/{summary_row['gates']} gates passed)"
    )
    print(f"Audit: {audit_path}")
    print(f"Summary: {summary_path}")
    if failed:
        print("Failed gates:")
        for row in failed:
            print(f"  {row['gate']}: {row['issues']}")
    if args.fail_on_issues and failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
