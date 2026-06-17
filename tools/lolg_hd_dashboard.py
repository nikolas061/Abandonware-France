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
DEFAULT_INVENTORY_SUMMARY = Path("output/fullhd_inventory/summary.csv")
DEFAULT_PROJECT_LEGACY_INVENTORY = Path("output/project_legacy_inventory/index.html")
DEFAULT_PROJECT_LEGACY_MANIFEST = Path("output/project_legacy_inventory/manifest.csv")
DEFAULT_VQA_GALLERY = Path("output/vqa_batch_window_lcw_transparent0_allframes/index.html")
DEFAULT_VQA_GALLERY_MANIFEST = Path(
    "output/vqa_batch_window_lcw_transparent0_allframes/gallery_manifest.csv"
)
DEFAULT_VQA_STATUS = Path("output/vqa_batch_window_lcw_transparent0_allframes/status.html")
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
DEFAULT_TEX_MATERIAL_DECODER_QUEUE = Path("output/tex_material_decoder_queue/index.html")
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


def dashboard_payload(output: Path) -> dict[str, object]:
    base_dir = output.parent
    audit_summary = first_row(DEFAULT_AUDIT_SUMMARY)
    audit_rows = read_csv(DEFAULT_AUDIT) if DEFAULT_AUDIT.exists() else []
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
    ]

    links = [
        ("Audit CSV", DEFAULT_AUDIT),
        ("Audit summary", DEFAULT_AUDIT_SUMMARY),
        ("Inventaire Full HD", DEFAULT_INVENTORY_SUMMARY),
        ("Inventaire fichiers projet", DEFAULT_PROJECT_LEGACY_INVENTORY),
        ("Manifest fichiers projet", DEFAULT_PROJECT_LEGACY_MANIFEST),
        ("Galerie images fixes", DEFAULT_STILL_GALLERY),
        ("Manifest images fixes", DEFAULT_STILL_MANIFEST),
        ("Galerie VQA", DEFAULT_VQA_GALLERY),
        ("Rapport VQA", DEFAULT_VQA_STATUS),
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
        ("File décodeur .tex", DEFAULT_TEX_MATERIAL_DECODER_QUEUE),
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
