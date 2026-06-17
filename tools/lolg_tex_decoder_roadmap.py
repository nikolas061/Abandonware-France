#!/usr/bin/env python3
"""Build a prioritized roadmap from .tex decoder review decisions."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter
from pathlib import Path


DEFAULT_OUTPUT = Path("output/tex_decoder_roadmap")
DEFAULT_DECISIONS = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_noisy_review/decisions.csv")
DEFAULT_REVIEW_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_noisy_review/summary.csv"
)
DEFAULT_STABLE_WALKS_SUMMARY = Path("output/tex_micro_stable_walks/summary.csv")
DEFAULT_STABLE_WALKS_GROUPS = Path("output/tex_micro_stable_walks/groups.csv")
DEFAULT_STABLE_BACKREFS_SUMMARY = Path("output/tex_micro_stable_backrefs/summary.csv")
DEFAULT_STABLE_SOURCES_SUMMARY = Path("output/tex_micro_stable_sources/summary.csv")
DEFAULT_STABLE_SOURCE_GRAMMAR_SUMMARY = Path("output/tex_micro_stable_source_grammar/summary.csv")
DEFAULT_STABLE_VALUE_CONTEXT_SUMMARY = Path("output/tex_micro_stable_value_context/summary.csv")
DEFAULT_STABLE_CONTEXT_RULES_SUMMARY = Path("output/tex_micro_stable_context_rules/summary.csv")
DEFAULT_STABLE_SEQUENCES_SUMMARY = Path("output/tex_micro_stable_sequences/summary.csv")
DEFAULT_STABLE_ALTERNATION_SUMMARY = Path("output/tex_micro_stable_alternation/summary.csv")
DEFAULT_STABLE_ALTERNATION_REPLAY_SUMMARY = Path("output/tex_micro_stable_alternation_replay/summary.csv")
DEFAULT_STABLE_LENGTH_SEQUENCE_SUMMARY = Path("output/tex_micro_stable_length_sequences/summary.csv")
DEFAULT_STABLE_LENGTH_CONTROL_SUMMARY = Path("output/tex_micro_stable_length_control/summary.csv")
DEFAULT_STABLE_LENGTH_OPCODE_SUMMARY = Path("output/tex_micro_stable_length_opcode/summary.csv")
DEFAULT_STABLE_LENGTH_INTERVAL_SUMMARY = Path("output/tex_micro_stable_length_interval/summary.csv")
DEFAULT_FLAT_WALK_BACKREF_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_backref_probe/summary.csv"
)
DEFAULT_FLAT_WALK_BACKREF_CHAIN_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_backref_chain_probe/summary.csv"
)
DEFAULT_FLAT_WALK_PALETTE_CONTEXT_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_context_probe/summary.csv"
)
DEFAULT_FLAT_WALK_PALETTE_NORMALIZED_CONTEXT_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_normalized_context_probe/summary.csv"
)
DEFAULT_FLAT_WALK_PALETTE_VALUE_SPLIT_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_value_split_probe/summary.csv"
)
DEFAULT_FLAT_WALK_PALETTE_VALUE_TABLE_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_value_table_probe/summary.csv"
)
DEFAULT_FLAT_WALK_PALETTE_COMPRESSED_SELECTOR_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_compressed_selector_probe/summary.csv"
)
DEFAULT_FLAT_WALK_PALETTE_COMPRESSED_COMBO_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_compressed_combo_probe/summary.csv"
)
DEFAULT_FLAT_WALK_PALETTE_COMPRESSED_FORMULA_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_compressed_formula_probe/summary.csv"
)
DEFAULT_FLAT_WALK_PALETTE_CORPUS_FORMULA_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_corpus_formula_probe/summary.csv"
)
DEFAULT_FLAT_WALK_PALETTE_PROMOTION_CANDIDATE_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_promotion_candidate_probe/summary.csv"
)
DEFAULT_FLAT_WALK_PALETTE_FORMULA_REPLAY_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_formula_replay/summary.csv"
)
DEFAULT_FLAT_WALK_PALETTE_POST_FORMULA_VERTICAL_COPY_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_post_formula_vertical_copy_probe/summary.csv"
)
DEFAULT_GRADIENT_SHAPE_PEER_COPY_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_shape_peer_copy_probe/summary.csv"
)
DEFAULT_GRADIENT_SOURCE_PROFILE_HIGH_LOW_SUMMARY = Path(
    "output/tex_gradient_source_profile_high_low/summary.csv"
)
DEFAULT_GRADIENT_SOURCE_PROFILE_HIGH_SAFE_LOW_SUMMARY = Path(
    "output/tex_gradient_source_profile_high_safe_low/summary.csv"
)
DEFAULT_GRADIENT_PAYLOAD_PROFILE_SUMMARY = Path("output/tex_gradient_payload_profile/summary.csv")
DEFAULT_GRADIENT_PAYLOAD_STATE_OPCODE_SUMMARY = Path(
    "output/tex_gradient_payload_state_opcode/summary.csv"
)
DEFAULT_GRADIENT_MACRO_OPCODE_SUMMARY = Path("output/tex_gradient_macro_opcode/summary.csv")
DEFAULT_GRADIENT_MACRO_CONFLICT_SPLIT_SUMMARY = Path(
    "output/tex_gradient_macro_conflict_split/summary.csv"
)
DEFAULT_GRADIENT_MACRO_RESIDUAL_STATE_SUMMARY = Path(
    "output/tex_gradient_macro_residual_state/summary.csv"
)
DEFAULT_GRADIENT_MACRO_PHASE_SUMMARY = Path("output/tex_gradient_macro_phase/summary.csv")
DEFAULT_GRADIENT_MACRO_PHASE_CONFLICT_SPLIT_SUMMARY = Path(
    "output/tex_gradient_macro_phase_conflict_split/summary.csv"
)
DEFAULT_GRADIENT_MACRO_PHASE_SEQUENCE_SUMMARY = Path(
    "output/tex_gradient_macro_phase_sequence/summary.csv"
)
DEFAULT_GRADIENT_MACRO_FIXTURE_TRANSITION_SUMMARY = Path(
    "output/tex_gradient_macro_fixture_transition/summary.csv"
)
DEFAULT_GRADIENT_MACRO_STATE_CLUSTER_SUMMARY = Path(
    "output/tex_gradient_macro_state_cluster/summary.csv"
)
DEFAULT_GRADIENT_MACRO_SOURCE_PROFILE_STATE_SUMMARY = Path(
    "output/tex_gradient_macro_source_profile_state/summary.csv"
)
DEFAULT_GRADIENT_SEED_DELTA_PAYLOAD_OPCODE_SUMMARY = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_payload_opcode_probe/summary.csv"
)
DEFAULT_GRADIENT_NONLOCAL_KNOWN_SPATIAL_SUMMARY = Path(
    "output/tex_gradient_nonlocal_known_spatial/summary.csv"
)
DEFAULT_GRADIENT_SEQUENCE_KNOWN_STATE_SUMMARY = Path(
    "output/tex_gradient_sequence_known_state/summary.csv"
)
DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low/summary.csv"
)
DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_SOURCE_PROFILE_LOW_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_source_profile_low/summary.csv"
)
DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_ROW_CORPUS_LOW_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_row_corpus_low/summary.csv"
)
DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_TRANSFORM_LOW_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_transform_low/summary.csv"
)
DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_SOURCE_WINDOW_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_source_window/summary.csv"
)
DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_CONTROL_OPCODE_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_control_opcode/summary.csv"
)
DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_ROW_TRANSITION_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_row_transition/summary.csv"
)
DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_ROW_MARKOV_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_row_markov/summary.csv"
)
DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_ROW_TEMPLATE_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_row_template/summary.csv"
)
DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_BUCKET_SPLIT_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_bucket_split/summary.csv"
)
DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception/summary.csv"
)
DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_ALIGNMENT_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_alignment/summary.csv"
)
DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_ALIGNMENT_REVIEW_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_alignment_review/summary.csv"
)
DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_ROW_FAMILY_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_row_family/summary.csv"
)
DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_EXTERNAL_STATE_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_state/summary.csv"
)
DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_PREREQUISITE_STATE_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_prerequisite_state/summary.csv"
)
DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_SOURCE_DEPENDENCY_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_dependency/summary.csv"
)
DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_SOURCE_CHAIN_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_chain/summary.csv"
)
DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_SOURCE_TERMINAL_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_terminal/summary.csv"
)
DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_SOURCE_TERMINAL_REVIEW_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_review/summary.csv"
)
DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_SOURCE_TERMINAL_DELTA_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_delta/summary.csv"
)
DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_SOURCE_TERMINAL_CHAIN_CONTEXT_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_chain_context/summary.csv"
)
DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_SOURCE_TERMINAL_REPLAY_SUPPORT_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_support/summary.csv"
)
DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_SOURCE_TERMINAL_REPLAY_UNION_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union/summary.csv"
)
DEFAULT_GRADIENT_MACRO_STATE_CLUSTER_PAYLOAD_SUMMARY = Path(
    "output/tex_gradient_macro_state_cluster_payload/summary.csv"
)
DEFAULT_GRADIENT_MACRO_STATE_CLUSTER_SOURCE_SUMMARY = Path(
    "output/tex_gradient_macro_state_cluster_source/summary.csv"
)
DEFAULT_GRADIENT_MACRO_STATE_CLUSTER_LITERAL_SUMMARY = Path(
    "output/tex_gradient_macro_state_cluster_literal/summary.csv"
)
DEFAULT_GRADIENT_MACRO_STATE_CLUSTER_BACKREF_SUMMARY = Path(
    "output/tex_gradient_macro_state_cluster_backref/summary.csv"
)
DEFAULT_MICRO_JUMP_MIXED_PAYLOAD_SUMMARY = Path("output/tex_micro_jump_mixed_payload/summary.csv")
DEFAULT_JUMP_TOKEN_PAYLOAD_PROFILE_SUMMARY = Path("output/tex_jump_token_payload_profile/summary.csv")
DEFAULT_JUMP_TOKEN_PAYLOAD_STATE_OPCODE_SUMMARY = Path(
    "output/tex_jump_token_payload_state_opcode/summary.csv"
)
DEFAULT_MICRO_TOKEN_FAMILY_SPLIT_SUMMARY = Path("output/tex_micro_token_family_split/summary.csv")
DEFAULT_MICRO_MIXED_VALUE_SUBFAMILY_SUMMARY = Path("output/tex_micro_mixed_value_subfamily/summary.csv")
DEFAULT_MICRO_MIXED_VALUE_DOMINANT_CONTROL_SUMMARY = Path(
    "output/tex_micro_mixed_value_dominant_control/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_LOCAL_GRAMMAR_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_local_grammar/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_PREDICTOR_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_predictor/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_COMBO_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_combo/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_HIGH_LOW_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_high_low/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SOURCE_PROFILE_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_source_profile/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_EXTERNAL_SOURCE_COMBO_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_external_source_combo/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_EXTERNAL_HIGH_LOW_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_external_high_low/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_STATE_EXTERNAL_COMBO_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_state_external_combo/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_STATE_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_state/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_CANDIDATE_REVIEW_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_candidate_review/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_PREFIX_BOOTSTRAP_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_prefix_bootstrap/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_PREFIX_SEQUENCE_REPLAY_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_prefix_sequence_replay/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_PREFIX_SEQUENCE_PROMOTED_REPLAY_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_prefix_sequence_promoted_replay/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PROMOTED_GENERALIZATION_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_promoted_generalization/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_LOW_SPLIT_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_low_split/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_LOW_SPLIT_PROMOTED_REPLAY_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_low_split_promoted_replay/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_EXPANSION_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_expansion/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_EXPANSION_PROMOTED_REPLAY_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_LOW_SPLIT_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_low_split/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_LOW_SPLIT_PROMOTED_REPLAY_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_LOW_SPLIT_GENERALIZATION_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_low_split_generalization/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_SECOND_LOW_SPLIT_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_second_low_split_max3/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_SECOND_EXPANSION_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_second_expansion_max3/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_CORPUS_EXPANSION_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_expansion/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_CORPUS_EXPANSION_PROMOTED_REPLAY_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_promoted_replay/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_CORPUS_LOW_SPLIT_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_low_split/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_CORPUS_LOW_SPLIT_PROMOTED_REPLAY_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_promoted_replay/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_CORPUS_SECOND_LOW_SPLIT_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_CORPUS_SECOND_LOW_SPLIT_PROMOTED_REPLAY_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_promoted_replay/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_THIRD_PROMOTED_REPLAY_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_GENERALIZATION_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_generalization/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_LOW_SPLIT_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_low_split/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_CORPUS_EXPANSION_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_corpus_expansion/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_FOURTH_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_fourth/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_TRANSFORM_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_TRANSFORM_PROMOTED_REPLAY_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_TRANSFORM_GENERALIZATION_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_generalization/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_TRANSFORM_SECOND_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_second/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_TRANSFORM_LOW_SPLIT_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_low_split/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_TRANSFORM_CORPUS_EXPANSION_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_expansion/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_TRANSFORM_ADJACENT_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_adjacent/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_TRANSFORM_CORPUS_THIRD_PROMOTED_REPLAY_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_TRANSFORM_CORPUS_THIRD_GENERALIZATION_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_generalization/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_TRANSFORM_CORPUS_FOURTH_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_fourth/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_TRANSFORM_CORPUS_THIRD_LOW_SPLIT_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_low_split/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_TRANSFORM_CORPUS_THIRD_CORPUS_EXPANSION_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_corpus_expansion/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_TRANSFORM_CORPUS_THIRD_ADJACENT_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_adjacent/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_LOW_COPY_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_low_copy/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_LOW_COPY_PROMOTED_REPLAY_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_low_copy_promoted_replay/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_LOW_COPY_GENERALIZATION_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_low_copy_generalization/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_LOW_COPY_SECOND_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_low_copy_second/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_LOW_COPY_LOW_SPLIT_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_low_copy_low_split/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_LOW_COPY_CORPUS_EXPANSION_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_low_copy_corpus_expansion/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_LOW_COPY_ADJACENT_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_low_copy_adjacent/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_BLOCKED_PREREQUISITE_ROLE_TRANSFORM_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_sequence_blocked_prerequisite_role_transform/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SPATIAL_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_spatial/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_STATE_OPCODE_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_state_opcode/summary.csv"
)

QUEUE_FIELDNAMES = [
    "priority",
    "track",
    "surface",
    "rows",
    "bytes",
    "promotion_ready_bytes",
    "signal_score",
    "status",
    "next_action",
    "positive_evidence",
    "blocking_evidence",
]

SUMMARY_FIELDNAMES = [
    "scope",
    "decision_rows",
    "total_bytes",
    "promotion_ready_bytes",
    "blocked_rows",
    "blocked_bytes",
    "tracks",
    "top_track",
    "top_surface",
    "top_action",
    "issue_rows",
]


TRACK_RULES = [
    ("gradient", ("gradient", "seed", "delta")),
    ("flat_walk", ("flat", "plateau", "palette")),
    ("jump", ("jump", "nibble", "dense", "residual")),
    ("mixed_token", ("mixed_token", "mixed-token", "band")),
    ("control", ("control", "signal", "phase", "payload")),
    ("direction_value", ("direction_value", "direction-value", "value")),
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def int_value(row: dict[str, str], field: str) -> int:
    raw = row.get(field, "")
    try:
        return int(raw) if raw else 0
    except ValueError:
        return 0


def classify_track(row: dict[str, str]) -> str:
    surface = row.get("surface", "").lower()
    if surface.startswith("mixed_token"):
        return "mixed_token"
    if surface.startswith("jump") or surface.startswith("dense") or surface.startswith("residual"):
        return "jump"
    if surface.startswith("direction_value"):
        return "direction_value"
    if surface.startswith("flat_walk"):
        return "flat_walk"
    if surface.startswith("gradient"):
        return "gradient"
    if "control" in surface or "signal" in surface:
        return "control"

    text = " ".join(
        [
            surface,
            row.get("next_action", ""),
            row.get("positive_evidence", ""),
            row.get("blocking_evidence", ""),
        ]
    ).lower()
    for track, needles in TRACK_RULES:
        if any(needle in text for needle in needles):
            return track
    return "general"


def signal_score(row: dict[str, str]) -> int:
    positive = row.get("positive_evidence", "").lower()
    blocking = row.get("blocking_evidence", "").lower()
    score = 0
    for word, weight in [
        ("repeated", 8),
        ("copy_unlock", 7),
        ("copy_distance", 6),
        ("candidate", 5),
        ("exact", 4),
        ("ge75", 3),
        ("dominant", 2),
    ]:
        score += positive.count(word) * weight
    for word, weight in [
        ("promotion_ready=0", 8),
        ("conflicted", 5),
        ("false", 5),
        ("singleton", 3),
        ("reject", 3),
    ]:
        score -= blocking.count(word) * weight
    return score


def append_evidence(existing: str, extra: list[str]) -> str:
    values = [existing] if existing else []
    values.extend(value for value in extra if value)
    return "; ".join(values)


def flat_walk_compressed_selector_action(summary: dict[str, str]) -> str:
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote compressed-stream selectors for flat-walk palette values"
    if int_value(summary, "best_pair_selector_rows") > 0 or int_value(summary, "best_transform_selector_rows") > 0:
        return "combine compressed selector features for conflicted flat-walk palette values"
    return "probe combined compressed selectors for conflicted flat-walk palette values"


def flat_walk_compressed_combo_action(summary: dict[str, str]) -> str:
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote combined compressed selectors for flat-walk palette values"
    if int_value(summary, "best_pair_singleton_conflicted_rows") > 0:
        return "generalize singleton-heavy raw-pair selectors for flat-walk palette values"
    if int_value(summary, "best_transform_exact_conflicted_rows") > 0:
        return "derive offset selectors after raw-delta transform coverage"
    return "expand combined compressed selectors for flat-walk palette values"


def flat_walk_compressed_formula_action(summary: dict[str, str]) -> str:
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote raw-delta compressed formulas for flat-walk palette values"
    if int_value(summary, "pair_formula_mismatch_rows") == 0 and int_value(summary, "pair_formula_exact_rows") > 0:
        return "validate raw-delta compressed formulas on broader flat-walk palette corpus"
    return "split raw-delta formula mismatches for flat-walk palette values"


def flat_walk_corpus_formula_action(summary: dict[str, str]) -> str:
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote corpus-validated flat-walk palette formula"
    if int_value(summary, "shift_formula_mismatch_rows") == 0 and int_value(summary, "shift_formula_exact_rows") > 0:
        return "prepare promotion candidate from corpus-validated flat-walk palette formula"
    return "split corpus flat-walk palette formula mismatches"


def flat_walk_palette_promotion_candidate_action(summary: dict[str, str]) -> str:
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote replayed flat-walk palette formula candidates"
    if int_value(summary, "candidate_ready_bytes") > 0 and int_value(summary, "issue_rows") == 0:
        return "replay guarded flat-walk palette formula promotion candidates"
    return "fix flat-walk palette promotion candidate issues"


def flat_walk_palette_formula_replay_action(
    summary: dict[str, str],
    candidate_summary: dict[str, str] | None = None,
) -> str:
    if int_value(summary, "formula_false_bytes") > 0 or int_value(summary, "issue_rows") > 0:
        return "fix guarded flat-walk palette formula replay issues"
    if int_value(summary, "formula_added_bytes") > 0:
        if candidate_summary and int_value(candidate_summary, "unique_backref_unlock_bytes") == 0:
            return "continue unresolved decoder probes after deduped flat-walk palette replay"
        return "replay flat-walk palette backref unlocks after formula promotion"
    if int_value(summary, "target_rows") > 0:
        return "replay guarded flat-walk palette formula promotion candidates"
    return "prepare flat-walk palette formula replay inputs"


def flat_walk_palette_post_formula_vertical_copy_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix post-formula vertical copy probe issues"
    if int_value(summary, "promotion_candidate_bytes") > 0:
        return "replay post-formula source-known vertical copy candidates"
    if int_value(summary, "copy_false_bytes") > 0:
        return "reject post-formula vertical-copy shortcuts and seek a stronger gradient producer"
    return "inspect post-formula vertical copy residuals"


def gradient_shape_peer_copy_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient shape-peer copy probe issues"
    if int_value(summary, "promotion_candidate_bytes") > 0:
        return "replay gradient shape-peer copy candidates"
    if int_value(summary, "copy_false_bytes") > 0:
        return "reject shape-peer gradient copies and mine source-profile gradients"
    return "inspect gradient shape-peer residuals"


def gradient_source_profile_high_low_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient source-profile high/low probe issues"
    if int_value(summary, "promotion_candidate_bytes") > 0:
        return "replay gradient source-profile full-byte candidates"
    if (
        int_value(summary, "high_best_false_free_slots") > 0
        and int_value(summary, "full_false_free_feature_sets") == 0
        and int_value(summary, "low_false_free_feature_sets") == 0
    ):
        return "keep source-profile high nibble as partial signal and seek low/full gradient resolver"
    if int_value(summary, "full_best_false_slots") > 0:
        return "reject source-profile full-byte transforms and seek richer gradient state"
    return "inspect gradient source-profile high/low residuals"


def gradient_source_profile_high_safe_low_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient high-safe low probe issues"
    if int_value(summary, "promotion_candidate_bytes") > 0:
        return "replay high-safe gradient low/full candidates"
    if (
        int_value(summary, "high_safe_slots") > 0
        and int_value(summary, "target_low_false_free_sets") == 0
        and int_value(summary, "delta_low_false_free_sets") == 0
    ):
        return "reject high-safe low shortcuts and seek richer gradient state"
    return "inspect high-safe gradient low residuals"


def gradient_macro_source_profile_state_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient macro/source-profile state probe issues"
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote gradient macro/source-profile state candidates"
    if (
        int_value(summary, "full_best_false_free_slots") <= 2
        and int_value(summary, "target_low_best_false_free_slots") <= 2
        and int_value(summary, "low_delta_best_false_free_slots") <= 2
        and int_value(summary, "full_best_false_slots") > 0
        and int_value(summary, "low_delta_best_false_slots") > 0
    ):
        return "reject overfit macro/source-profile gradient state and search nonlocal payload state"
    return "inspect macro/source-profile gradient state residuals"


def gradient_seed_delta_payload_opcode_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient seed payload-opcode probe issues"
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote gradient seed payload-opcode candidates"
    if (
        int_value(summary, "best_token_repeated_bytes") > 0
        and int_value(summary, "best_token_conflicted_bytes")
        >= int_value(summary, "best_token_repeated_bytes")
    ):
        return "reject seed payload-opcode shortcuts and search broader nonlocal gradient state"
    return "inspect gradient seed payload-opcode residuals"


def gradient_nonlocal_known_spatial_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient nonlocal known-spatial probe issues"
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote gradient nonlocal known-spatial candidates"
    if (
        int_value(summary, "false_free_rules") == 0
        and int_value(summary, "best_false_slots") > int_value(summary, "best_exact_slots")
    ):
        return "reject known-spatial nonlocal gradient copies and search sequence-level state"
    return "inspect gradient known-spatial residuals"


def gradient_sequence_known_state_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient sequence known-state probe issues"
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote gradient sequence known-state candidates"
    if (
        int_value(summary, "high_best_false_free_slots") > 0
        and int_value(summary, "full_false_free_feature_sets") == 0
        and int_value(summary, "low_false_free_feature_sets") == 0
    ):
        return "keep sequence high nibble as partial signal and seek low/full gradient resolver"
    return "inspect gradient sequence known-state residuals"


def gradient_sequence_high_safe_low_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient sequence high-safe low probe issues"
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote gradient sequence high-safe low candidates"
    if (
        int_value(summary, "high_safe_slots") > 0
        and int_value(summary, "target_low_best_false_free_slots") <= 5
        and int_value(summary, "target_low_best_false_slots") > 0
    ):
        return "reject sparse sequence high-safe low shortcuts and search richer gradient low state"
    return "inspect sequence high-safe low residuals"


def gradient_sequence_high_safe_source_profile_low_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient sequence/source-profile low probe issues"
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote gradient sequence/source-profile low candidates"
    if (
        int_value(summary, "joined_slots") > 0
        and int_value(summary, "target_low_best_false_free_slots") <= 6
        and int_value(summary, "target_low_best_false_slots")
        > int_value(summary, "target_low_best_false_free_slots")
    ):
        return "reject sequence/source-profile high-safe low shortcuts and seek row-corpus gradient low state"
    return "inspect sequence/source-profile high-safe low residuals"


def gradient_sequence_high_safe_row_corpus_low_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient sequence row/corpus low probe issues"
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote gradient sequence row/corpus low candidates"
    if (
        int_value(summary, "row_corpus_slots") > 0
        and int_value(summary, "target_low_best_false_free_slots") <= 10
        and int_value(summary, "target_low_low_false_false_slots") > 0
    ):
        return "reject row-corpus gradient low shortcuts and seek transform/low-split gradient resolver"
    return "inspect sequence row/corpus low residuals"


def gradient_sequence_high_safe_transform_low_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient sequence transform-low probe issues"
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote gradient sequence transform-low candidates"
    if (
        int_value(summary, "row_corpus_slots") > 0
        and int_value(summary, "best_false_free_correct_slots") <= 10
        and int_value(summary, "best_false_slots") > int_value(summary, "best_false_free_correct_slots")
    ):
        return "reject transform/low-split gradient shortcuts and seek residual source-window grammar"
    return "inspect sequence transform-low residuals"


def gradient_sequence_high_safe_source_window_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient sequence source-window probe issues"
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote gradient sequence source-window candidates"
    if (
        int_value(summary, "slots") > 0
        and int_value(summary, "fixed_low_best_false_slots") > int_value(summary, "fixed_low_best_exact_slots")
        and int_value(summary, "gate_best_false_slots") >= int_value(summary, "gate_best_exact_slots")
        and int_value(summary, "gate_best_false_free_slots") <= 5
    ):
        return "reject residual source-window grammar and seek control/opcode gradient residual state"
    return "inspect sequence source-window residuals"


def gradient_sequence_high_safe_control_opcode_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient sequence control/opcode probe issues"
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote gradient sequence control/opcode candidates"
    if (
        int_value(summary, "slots") > 0
        and int_value(summary, "best_low_false_free_slots") == 0
        and int_value(summary, "best_low_false_slots") >= int_value(summary, "best_low_correct_slots")
    ):
        return "reject high-safe control/opcode contexts and seek cross-row low transition grammar"
    return "inspect sequence control/opcode residuals"


def gradient_sequence_high_safe_row_transition_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient sequence row-transition probe issues"
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote gradient sequence row-transition candidates"
    if (
        int_value(summary, "slots") > 0
        and int_value(summary, "fixed_best_false_slots") > int_value(summary, "fixed_best_exact_slots")
        and int_value(summary, "gate_best_false_slots") >= int_value(summary, "gate_best_exact_slots")
        and int_value(summary, "gate_best_false_free_slots") <= 8
    ):
        return "reject cross-row low transitions and seek row-local low Markov grammar"
    return "inspect sequence row-transition residuals"


def gradient_sequence_high_safe_row_markov_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient sequence row-Markov probe issues"
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote gradient sequence row-Markov candidates"
    if (
        int_value(summary, "slots") > 0
        and int_value(summary, "best_low_false_slots") > int_value(summary, "best_low_correct_slots")
        and int_value(summary, "best_delta_false_slots") >= int_value(summary, "best_delta_correct_slots")
        and int_value(summary, "best_delta_false_free_slots") <= 9
    ):
        return "reject row-local low Markov grammar and seek row-template low model"
    return "inspect sequence row-Markov residuals"


def gradient_sequence_high_safe_row_template_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient sequence row-template probe issues"
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote gradient sequence row-template candidates"
    if (
        int_value(summary, "slots") > 0
        and int_value(summary, "best_low_false_slots") > int_value(summary, "best_low_correct_slots")
        and int_value(summary, "best_low_bucket_correct_slots") > int_value(summary, "best_low_correct_slots")
        and int_value(summary, "best_low_false_free_slots") <= 9
    ):
        return "reject exact row-template low model and seek low-bucket split resolver"
    return "inspect sequence row-template residuals"


def gradient_sequence_high_safe_low_bucket_split_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient sequence low-bucket split probe issues"
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote gradient sequence low-bucket split candidates"
    if (
        int_value(summary, "slots") > 0
        and int_value(summary, "combined_baseline_correct_slots")
        > int_value(summary, "combined_best_correct_slots")
        and int_value(summary, "combined_false_free_slots") <= 30
    ):
        return "reject bucket-local exact resolver and seek minority low exception model"
    return "inspect gradient sequence low-bucket split conflicts"


def gradient_sequence_high_safe_low_exception_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient sequence low-exception probe issues"
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote gradient sequence low-exception candidates"
    if (
        int_value(summary, "slots") > 0
        and int_value(summary, "combined_false_free_slots") == 0
        and int_value(summary, "combined_best_false_slots")
        >= int_value(summary, "combined_best_correct_slots")
    ):
        return "reject local minority low selectors and seek cross-row exception alignment"
    return "inspect gradient sequence low-exception residuals"


def gradient_sequence_high_safe_low_exception_alignment_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient sequence low-exception alignment probe issues"
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote gradient sequence low-exception alignment candidates"
    if int_value(summary, "best_false_free_slots") > 0:
        return "review false-free same-bucket peer exception alignments"
    return "reject direct peer exception alignment and seek row-family rule"


def gradient_sequence_high_safe_low_exception_alignment_review_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient sequence low-exception alignment review issues"
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote gradient sequence low-exception alignment review candidates"
    if (
        int_value(summary, "broad_false_free_selector_rows") == 0
        and int_value(summary, "best_nonrow_false_free_correct_slots") <= 6
    ):
        return "reject broad peer exception selectors and seek row-family support"
    if int_value(summary, "best_nonrow_false_free_correct_slots") > 0:
        return "review narrow non-row peer exception selectors"
    return "reject peer exception selector families and seek corpus support"


def gradient_sequence_high_safe_low_exception_row_family_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient sequence low-exception row-family probe issues"
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote gradient sequence low-exception row-family candidates"
    if int_value(summary, "robust_family_rows") > 0:
        return "review robust low-exception row-family candidates"
    if (
        int_value(summary, "best_false_free_correct_slots") <= 6
        and int_value(summary, "robust_family_rows") == 0
    ):
        return "reject row-family exception support and seek external corpus state"
    return "inspect low-exception row-family support"


def gradient_sequence_high_safe_low_exception_external_state_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient sequence low-exception external-state probe issues"
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote gradient sequence low-exception external-state candidates"
    if (
        int_value(summary, "combined_false_free_slots") == 0
        and int_value(summary, "combined_best_false_slots")
        >= int_value(summary, "combined_best_correct_slots")
    ):
        return "reject external corpus state selectors and seek payload/corpus prerequisite"
    return "inspect low-exception external-state residuals"


def gradient_sequence_high_safe_low_exception_prerequisite_state_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient sequence low-exception prerequisite-state probe issues"
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote gradient sequence low-exception prerequisite-state candidates"
    if (
        int_value(summary, "target_known_slots") == 0
        and int_value(summary, "combined_false_free_slots") == 0
    ):
        return "reject replay prerequisite state and seek upstream gradient payload unlock"
    if (
        int_value(summary, "combined_false_free_slots") == 0
        and int_value(summary, "combined_best_false_slots")
        >= int_value(summary, "combined_best_correct_slots")
    ):
        return "reject replay prerequisite selectors and seek upstream corpus unlock"
    return "inspect low-exception prerequisite-state residuals"


def gradient_sequence_high_safe_low_exception_source_dependency_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient sequence low-exception source-dependency probe issues"
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote gradient sequence low-exception source-dependency candidates"
    if int_value(summary, "source_unknown_in_highsafe_slots") > 0:
        return "resolve high-safe source dependency graph for upstream gradient payload unlock"
    if int_value(summary, "source_unknown_outside_highsafe_slots") > 0:
        return "seek external source unlock for gradient high-safe dependencies"
    return "inspect low-exception source-dependency residuals"


def gradient_sequence_high_safe_low_exception_source_chain_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient sequence low-exception source-chain probe issues"
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote gradient sequence low-exception source-chain candidates"
    if int_value(summary, "cycle_chains") > 0:
        return "break cyclic high-safe source dependencies before terminal replay"
    if int_value(summary, "best_false_free_slots") == 0:
        return "reject terminal source-low propagation and seek external terminal unlock"
    return "inspect low-exception source-chain terminal candidates"


def gradient_sequence_high_safe_low_exception_source_terminal_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient sequence low-exception source-terminal probe issues"
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote gradient sequence low-exception source-terminal candidates"
    if int_value(summary, "best_false_free_slots") > 0:
        return "review false-free terminal context candidates for source-chain unlock"
    return "reject terminal context unlock and seek external terminal source"


def gradient_sequence_high_safe_low_exception_source_terminal_review_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient sequence low-exception source-terminal review issues"
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote gradient sequence low-exception source-terminal replay candidates"
    if (
        int_value(summary, "oracle_delta_root_exact") > 0
        and int_value(summary, "oracle_delta_root_false") == 0
    ):
        return "derive non-oracle delta rule for terminal source-chain replay"
    return "reject terminal source-chain replay and seek another terminal source"


def gradient_sequence_high_safe_low_exception_source_terminal_delta_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient sequence low-exception source-terminal delta probe issues"
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote gradient sequence low-exception source-terminal delta candidates"
    if int_value(summary, "best_false_free_review_exact") > 0:
        return "review narrow terminal delta candidates and seek stronger chain-delta features"
    return "reject current terminal delta contexts and seek stronger chain-delta features"


def gradient_sequence_high_safe_low_exception_source_terminal_chain_context_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient sequence low-exception source-terminal chain-context probe issues"
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote gradient sequence low-exception source-terminal chain-context candidates"
    if int_value(summary, "best_false_free_chains") > 0:
        return "review direct chain-context candidates and seek broader terminal replay support"
    return "reject direct chain-context replay and seek broader terminal replay support"


def gradient_sequence_high_safe_low_exception_source_terminal_replay_support_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient sequence low-exception source-terminal replay-support probe issues"
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote gradient sequence low-exception source-terminal replay-support candidates"
    if int_value(summary, "best_no_bucket_false_free_chains") > 0:
        return "review no-bucket terminal replay candidates and seek broader non-bucket support"
    return "reject broadened terminal replay and seek another terminal support signal"


def gradient_sequence_high_safe_low_exception_source_terminal_replay_union_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix gradient sequence low-exception source-terminal replay-union issues"
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote gradient sequence low-exception source-terminal replay-union candidates"
    if int_value(summary, "covered_roots") > 0:
        return "review replay-union candidates and derive a broader guard before promotion"
    return "reject replay-union candidates and seek another terminal support signal"


def mixed_value_payload_combo_action(summary: dict[str, str]) -> str:
    if int_value(summary, "false_free_byte_slots") > 0:
        return "replay false-free mixed-value payload byte combos"
    if int_value(summary, "best_false_free_high_slots") > 0:
        return "seek low-nibble resolver for sparse false-free mixed-value high contexts"
    return "leave local mixed-value payload combos blocked and search external state"


def mixed_value_payload_high_low_action(summary: dict[str, str]) -> str:
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote mixed-value high/low payload resolver"
    if int_value(summary, "selected_high_slots") > 0 and int_value(summary, "best_low_correct_slots") == 0:
        return "discard sparse mixed-value high contexts and search external byte source"
    return "expand mixed-value low-nibble resolver candidates"


def mixed_value_external_source_combo_action(summary: dict[str, str]) -> str:
    if int_value(summary, "best_false_free_byte_slots") >= 8:
        return "replay false-free mixed-value external source byte slots"
    if int_value(summary, "best_false_free_high_slots") > int_value(summary, "best_false_free_byte_slots"):
        return "inspect low-nibble resolver for external mixed-value high contexts"
    return "discard simple external mixed-value source combos and search richer state"


def mixed_value_external_high_low_action(summary: dict[str, str]) -> str:
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote external mixed-value high/low payload resolver"
    if int_value(summary, "selected_high_slots") > 0 and int_value(summary, "best_low_correct_slots") == 0:
        return "discard external mixed-value high contexts and search richer byte state"
    return "expand external mixed-value low-nibble resolver candidates"


def mixed_value_state_external_combo_action(summary: dict[str, str]) -> str:
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote mixed-value state/external byte resolver"
    if int_value(summary, "best_false_free_byte_slots") > 0:
        return "review false-free mixed-value state/external byte slots"
    if int_value(summary, "best_byte_false_slots") >= int_value(summary, "best_byte_correct_slots"):
        return "discard crossed mixed-value state/external byte combos and search sequence state"
    return "expand crossed mixed-value state/external combo features"


def mixed_value_sequence_state_action(summary: dict[str, str]) -> str:
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote mixed-value sequence high/low resolver"
    if int_value(summary, "promotion_candidate_bytes") > 0:
        return "review tiny mixed-value sequence high/low candidates before promotion"
    if int_value(summary, "best_byte_false_slots") >= int_value(summary, "best_byte_correct_slots"):
        return "discard mixed-value sequence byte contexts and search broader decoder state"
    return "expand mixed-value sequence-state candidates"


def mixed_value_sequence_candidate_review_action(summary: dict[str, str]) -> str:
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote reviewed mixed-value sequence candidates"
    if int_value(summary, "replay_ready_bytes") > 0:
        return "replay reviewed mixed-value sequence candidates with guards"
    if int_value(summary, "oracle_dependency_bytes") > 0:
        return "discard oracle-only mixed-value sequence candidates and search non-oracle state"
    return "expand mixed-value sequence candidate review"


def mixed_value_prefix_bootstrap_action(summary: dict[str, str]) -> str:
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote mixed-value prefix bootstrap candidates"
    if (
        int_value(summary, "union_candidate_slots") > 0
        and int_value(summary, "union_conflict_slots") == 0
        and int_value(summary, "sequence_candidate_unlocked_bytes") > 0
    ):
        return "review mixed-value prefix bootstrap union before guarded replay"
    if int_value(summary, "union_candidate_slots") > 0:
        return "inspect conflicted mixed-value prefix bootstrap candidates"
    return "expand non-oracle mixed-value prefix bootstrap search"


def mixed_value_prefix_sequence_replay_action(summary: dict[str, str]) -> str:
    if int_value(summary, "promotion_ready_bytes") > 0:
        return "promote mixed-value prefix/sequence replay candidates"
    if int_value(summary, "total_false_bytes") == 0 and int_value(summary, "guarded_replay_bytes") > 0:
        return "promote guarded mixed-value prefix/sequence replay bytes"
    if int_value(summary, "total_false_bytes") > 0:
        return "fix mixed-value prefix/sequence replay false positives"
    return "expand mixed-value prefix/sequence replay coverage"


def mixed_value_prefix_sequence_promoted_replay_action(summary: dict[str, str]) -> str:
    if int_value(summary, "mixed_value_false_bytes") > 0 or int_value(summary, "issue_rows") > 0:
        return "fix promoted mixed-value prefix/sequence replay issues"
    if int_value(summary, "mixed_value_added_bytes") > 0:
        return "generalize mixed-value prefix/sequence replay beyond guarded rows"
    return "expand mixed-value prefix/sequence promoted replay coverage"


def mixed_value_sequence_promoted_generalization_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix mixed-value sequence promoted generalization issues"
    if int_value(summary, "false_free_feature_sets") > 0:
        return "review false-free mixed-value sequence generalization candidates"
    if int_value(summary, "replayable_unknown_slots") > 0 and int_value(summary, "best_false_slots") > 0:
        return "split replayable mixed-value sequence low conflicts"
    if int_value(summary, "blocked_prerequisite_slots") > 0:
        return "expand mixed-value prefix prerequisites for sequence generalization"
    return "expand mixed-value sequence promoted generalization search"


def mixed_value_sequence_low_split_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix mixed-value sequence low split probe issues"
    if int_value(summary, "false_free_split_sets") > 0 and int_value(summary, "promotion_candidate_bytes") > 0:
        return "replay guarded mixed-value sequence low split candidates"
    if int_value(summary, "replayable_unknown_slots") > 0:
        return "expand source-enriched mixed-value sequence low split search"
    return "expand mixed-value prefix prerequisites for low split search"


def mixed_value_sequence_low_split_promoted_replay_action(summary: dict[str, str]) -> str:
    if int_value(summary, "low_split_false_bytes") > 0 or int_value(summary, "issue_rows") > 0:
        return "fix promoted mixed-value sequence low split replay issues"
    if int_value(summary, "low_split_added_bytes") > 0:
        return "expand mixed-value prefix prerequisites after low split promotion"
    return "expand mixed-value sequence low split promoted replay coverage"


def mixed_value_sequence_prerequisite_expansion_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix mixed-value sequence prerequisite expansion issues"
    if int_value(summary, "union_conflict_slots") > 0:
        return "split conflicted mixed-value sequence prerequisite candidates"
    if int_value(summary, "promotion_candidate_bytes") > 0:
        return "replay guarded mixed-value sequence prerequisite candidates"
    if int_value(summary, "unknown_prerequisite_slots") > 0:
        return "expand mixed-value sequence prerequisite search"
    return "re-evaluate mixed-value sequence after prerequisite expansion"


def mixed_value_sequence_prerequisite_expansion_promoted_action(summary: dict[str, str]) -> str:
    if int_value(summary, "prerequisite_false_bytes") > 0 or int_value(summary, "issue_rows") > 0:
        return "fix promoted mixed-value sequence prerequisite replay issues"
    if int_value(summary, "prerequisite_added_bytes") > 0:
        return "re-evaluate mixed-value sequence after prerequisite expansion"
    return "expand mixed-value sequence prerequisite promoted replay coverage"


def mixed_value_sequence_prerequisite_low_split_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix mixed-value sequence prerequisite low split issues"
    if int_value(summary, "false_free_split_sets") > 0 and int_value(summary, "promotion_candidate_bytes") > 0:
        return "replay guarded mixed-value sequence prerequisite low-split candidates"
    if int_value(summary, "replayable_unknown_slots") > 0:
        return "expand mixed-value sequence prerequisite low-split search"
    if int_value(summary, "blocked_prerequisite_slots") > 0:
        return "expand mixed-value sequence prerequisites after prerequisite low split"
    return "re-evaluate mixed-value sequence after prerequisite low split"


def mixed_value_sequence_prerequisite_low_split_promoted_action(summary: dict[str, str]) -> str:
    if int_value(summary, "low_split_false_bytes") > 0 or int_value(summary, "issue_rows") > 0:
        return "fix promoted mixed-value sequence prerequisite low-split replay issues"
    if int_value(summary, "low_split_added_bytes") > 0:
        return "re-evaluate mixed-value sequence after prerequisite low-split promotion"
    return "expand mixed-value sequence prerequisite low-split promoted replay coverage"


def mixed_value_sequence_prerequisite_low_split_generalization_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix mixed-value sequence prerequisite low-split generalization issues"
    if int_value(summary, "false_free_feature_sets") > 0:
        return "review residual mixed-value sequence generalization candidates"
    if int_value(summary, "replayable_unknown_slots") > 0 and int_value(summary, "best_false_slots") > 0:
        return "probe residual mixed-value sequence low splits beyond prerequisite low-split promotion"
    if int_value(summary, "blocked_prerequisite_slots") > 0:
        return "probe residual mixed-value sequence prerequisite expansion"
    return "expand mixed-value sequence prerequisite low-split generalization search"


def mixed_value_sequence_prerequisite_second_low_split_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix residual mixed-value sequence low split issues"
    if int_value(summary, "false_free_split_sets") > 0 and int_value(summary, "promotion_candidate_bytes") > 0:
        return "replay residual mixed-value sequence low-split candidates"
    if int_value(summary, "replayable_unknown_slots") > 0:
        return "inspect residual mixed-value sequence 6d lows beyond current low-split features"
    if int_value(summary, "blocked_prerequisite_slots") > 0:
        return "probe residual mixed-value sequence prerequisites beyond current low-split features"
    return "expand residual mixed-value sequence low-split search"


def mixed_value_sequence_prerequisite_second_expansion_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix residual mixed-value sequence prerequisite expansion issues"
    if int_value(summary, "union_conflict_slots") > 0:
        return "split residual mixed-value sequence prerequisite conflicts"
    if int_value(summary, "promotion_candidate_bytes") > 0:
        return "replay residual mixed-value sequence prerequisite candidates"
    if int_value(summary, "unknown_prerequisite_slots") > 0:
        return "add new mixed-value sequence prerequisite feature family"
    return "inspect residual mixed-value sequence 6d lows"


def mixed_value_sequence_prerequisite_corpus_expansion_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix mixed-value sequence prerequisite corpus expansion issues"
    if int_value(summary, "union_conflict_slots") > 0:
        return "split mixed-value sequence prerequisite corpus conflicts"
    if int_value(summary, "promotion_candidate_bytes") > 0:
        return "replay mixed-value sequence prerequisite corpus candidates"
    if int_value(summary, "unknown_prerequisite_slots") > 0:
        return "extend mixed-value sequence prerequisite corpus feature family"
    return "re-evaluate mixed-value sequence after corpus prerequisite expansion"


def mixed_value_sequence_prerequisite_corpus_expansion_promoted_action(summary: dict[str, str]) -> str:
    if int_value(summary, "prerequisite_false_bytes") > 0 or int_value(summary, "issue_rows") > 0:
        return "fix promoted mixed-value sequence prerequisite corpus replay issues"
    if int_value(summary, "prerequisite_added_bytes") > 0:
        return "re-evaluate mixed-value sequence after corpus prerequisite expansion"
    return "expand mixed-value sequence prerequisite corpus promoted replay coverage"


def mixed_value_sequence_prerequisite_corpus_low_split_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix mixed-value sequence corpus low split issues"
    if int_value(summary, "false_free_split_sets") > 0 and int_value(summary, "promotion_candidate_bytes") > 0:
        return "replay mixed-value sequence corpus low-split candidates"
    if int_value(summary, "replayable_unknown_slots") > 0:
        return "expand mixed-value sequence corpus low-split search"
    if int_value(summary, "blocked_prerequisite_slots") > 0:
        return "expand mixed-value sequence corpus prerequisites after low split"
    return "re-evaluate mixed-value sequence after corpus low split"


def mixed_value_sequence_prerequisite_corpus_low_split_promoted_action(summary: dict[str, str]) -> str:
    if int_value(summary, "low_split_false_bytes") > 0 or int_value(summary, "issue_rows") > 0:
        return "fix promoted mixed-value sequence corpus low-split replay issues"
    if int_value(summary, "low_split_added_bytes") > 0:
        return "re-evaluate mixed-value sequence after corpus low-split promotion"
    return "expand mixed-value sequence corpus low-split promoted replay coverage"


def mixed_value_sequence_prerequisite_corpus_second_low_split_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix second mixed-value sequence corpus low split issues"
    if int_value(summary, "false_free_split_sets") > 0 and int_value(summary, "promotion_candidate_bytes") > 0:
        return "replay second mixed-value sequence corpus low-split candidates"
    if int_value(summary, "replayable_unknown_slots") > 0:
        return "expand second mixed-value sequence corpus low-split search"
    return "expand mixed-value sequence corpus prerequisites after second low split"


def mixed_value_sequence_prerequisite_corpus_second_low_split_promoted_action(summary: dict[str, str]) -> str:
    if int_value(summary, "low_split_false_bytes") > 0 or int_value(summary, "issue_rows") > 0:
        return "fix promoted second mixed-value sequence corpus low-split replay issues"
    if int_value(summary, "low_split_added_bytes") > 0:
        return "re-evaluate mixed-value sequence after second corpus low-split promotion"
    return "expand second mixed-value sequence corpus low-split promoted replay coverage"


def mixed_value_sequence_prerequisite_adjacent_known_promoted_action(summary: dict[str, str]) -> str:
    if int_value(summary, "prerequisite_false_bytes") > 0 or int_value(summary, "issue_rows") > 0:
        return "fix promoted mixed-value sequence adjacent-known prerequisite replay issues"
    if int_value(summary, "prerequisite_added_bytes") > 0:
        return "re-evaluate mixed-value sequence after adjacent-known prerequisite promotion"
    return "expand mixed-value sequence adjacent-known prerequisite replay coverage"


def mixed_value_sequence_prerequisite_adjacent_known_generalization_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix mixed-value sequence adjacent-known generalization issues"
    if int_value(summary, "false_free_feature_sets") > 0:
        return "review residual mixed-value sequence adjacent-known generalization candidates"
    if int_value(summary, "replayable_unknown_slots") > 0 and int_value(summary, "best_false_slots") > 0:
        return "probe residual mixed-value sequence adjacent-known low splits"
    if int_value(summary, "blocked_prerequisite_slots") > 0:
        return "probe residual mixed-value sequence adjacent-known prerequisites"
    return "expand mixed-value sequence adjacent-known generalization search"


def mixed_value_sequence_prerequisite_adjacent_known_low_split_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix residual mixed-value sequence adjacent-known low split issues"
    if int_value(summary, "false_free_split_sets") > 0 and int_value(summary, "promotion_candidate_bytes") > 0:
        return "replay residual mixed-value sequence adjacent-known low-split candidates"
    if int_value(summary, "replayable_unknown_slots") > 0:
        return "inspect residual mixed-value sequence lows after adjacent-known"
    return "probe residual mixed-value sequence prerequisites after adjacent-known"


def mixed_value_sequence_prerequisite_adjacent_known_corpus_expansion_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix residual mixed-value sequence adjacent-known corpus expansion issues"
    if int_value(summary, "union_conflict_slots") > 0:
        return "split residual mixed-value sequence adjacent-known corpus conflicts"
    if int_value(summary, "promotion_candidate_bytes") > 0:
        return "replay residual mixed-value sequence adjacent-known corpus candidates"
    if int_value(summary, "unknown_prerequisite_slots") > 0:
        return "add new mixed-value sequence feature family beyond corpus and adjacent-known"
    return "inspect residual mixed-value sequence lows after adjacent-known"


def mixed_value_sequence_prerequisite_adjacent_known_fourth_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix fourth mixed-value sequence adjacent-known probe issues"
    if int_value(summary, "promotion_candidate_bytes") > 0:
        return "replay fourth mixed-value sequence adjacent-known prerequisite candidates"
    return "add new mixed-value sequence feature family beyond corpus and adjacent-known"


def mixed_value_sequence_prerequisite_adjacent_known_transform_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix residual mixed-value sequence transform issues"
    if int_value(summary, "false_free_transform_sets") > 0 and int_value(summary, "promotion_candidate_bytes") > 0:
        return "replay residual mixed-value sequence transform candidates"
    if int_value(summary, "replayable_unknown_slots") > 0:
        return "expand residual mixed-value sequence transform family"
    return "probe residual mixed-value sequence prerequisites after transform"


def mixed_value_sequence_prerequisite_adjacent_known_transform_promoted_action(summary: dict[str, str]) -> str:
    if int_value(summary, "low_split_false_bytes") > 0 or int_value(summary, "issue_rows") > 0:
        return "fix promoted mixed-value sequence transform replay issues"
    if int_value(summary, "low_split_added_bytes") > 0:
        return "re-evaluate mixed-value sequence after transform promotion"
    return "expand residual mixed-value sequence transform promoted replay coverage"


def mixed_value_sequence_prerequisite_adjacent_known_transform_generalization_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix mixed-value sequence transform generalization issues"
    if int_value(summary, "false_free_feature_sets") > 0:
        return "review residual mixed-value sequence transform generalization candidates"
    if int_value(summary, "replayable_unknown_slots") > 0:
        return "probe second residual mixed-value sequence transform"
    return "probe residual mixed-value sequence prerequisites after transform"


def mixed_value_sequence_prerequisite_adjacent_known_transform_second_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix second residual mixed-value sequence transform issues"
    if int_value(summary, "false_free_transform_sets") > 0 and int_value(summary, "promotion_candidate_bytes") > 0:
        return "replay second residual mixed-value sequence transform candidates"
    if int_value(summary, "replayable_unknown_slots") > 0:
        return "probe residual mixed-value sequence low-split after transform"
    return "probe residual mixed-value sequence prerequisites after transform"


def mixed_value_sequence_prerequisite_adjacent_known_transform_low_split_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix residual mixed-value sequence low-split after transform issues"
    if int_value(summary, "false_free_split_sets") > 0 and int_value(summary, "promotion_candidate_bytes") > 0:
        return "replay residual mixed-value sequence low-split after transform candidates"
    if int_value(summary, "replayable_unknown_slots") > 0:
        return "probe residual mixed-value sequence corpus prerequisites after transform"
    return "probe residual mixed-value sequence prerequisites after transform"


def mixed_value_sequence_prerequisite_adjacent_known_transform_corpus_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix residual mixed-value sequence corpus after transform issues"
    if int_value(summary, "union_conflict_slots") > 0:
        return "split residual mixed-value sequence corpus after transform conflicts"
    if int_value(summary, "promotion_candidate_bytes") > 0:
        return "replay residual mixed-value sequence corpus after transform candidates"
    if int_value(summary, "unknown_prerequisite_slots") > 0:
        return "probe adjacent-known prerequisites after transform"
    return "inspect residual mixed-value sequence lows after transform"


def mixed_value_sequence_prerequisite_adjacent_known_transform_adjacent_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix residual adjacent-known after transform issues"
    if int_value(summary, "promotion_candidate_bytes") > 0:
        return "replay residual adjacent-known prerequisite candidates after transform"
    return "add next mixed-value sequence feature family beyond transform/corpus-transform/corpus/adjacent-known"


def mixed_value_sequence_low_copy_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix residual mixed-value sequence low-copy issues"
    if int_value(summary, "false_free_copy_sets") > 0 and int_value(summary, "promotion_candidate_bytes") > 0:
        return "replay residual mixed-value sequence low-copy candidates"
    if int_value(summary, "replayable_unknown_slots") > 0:
        return "expand residual mixed-value sequence low-copy feature family"
    return "probe blocked mixed-value sequence prerequisites after low-copy"


def mixed_value_sequence_low_copy_promoted_action(summary: dict[str, str]) -> str:
    if int_value(summary, "low_split_false_bytes") > 0 or int_value(summary, "issue_rows") > 0:
        return "fix promoted mixed-value sequence low-copy replay issues"
    if int_value(summary, "low_split_added_bytes") > 0:
        return "re-evaluate mixed-value sequence after low-copy promotion"
    return "expand residual mixed-value sequence low-copy promoted replay coverage"


def mixed_value_sequence_low_copy_generalization_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix mixed-value sequence low-copy generalization issues"
    if int_value(summary, "false_free_feature_sets") > 0:
        return "review residual mixed-value sequence low-copy generalization candidates"
    if int_value(summary, "replayable_unknown_slots") > 0:
        return "probe second residual mixed-value sequence low-copy"
    if int_value(summary, "blocked_prerequisite_slots") > 0:
        return "probe blocked mixed-value sequence prerequisites after low-copy"
    return "inspect residual mixed-value sequence after low-copy"


def mixed_value_sequence_low_copy_second_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix second residual mixed-value sequence low-copy issues"
    if int_value(summary, "false_free_copy_sets") > 0 and int_value(summary, "promotion_candidate_bytes") > 0:
        return "replay second residual mixed-value sequence low-copy candidates"
    if int_value(summary, "replayable_unknown_slots") > 0:
        return "probe residual mixed-value sequence low-split after low-copy"
    return "probe blocked mixed-value sequence prerequisites after low-copy"


def mixed_value_sequence_low_copy_low_split_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix residual mixed-value sequence low-split after low-copy issues"
    if int_value(summary, "false_free_split_sets") > 0 and int_value(summary, "promotion_candidate_bytes") > 0:
        return "replay residual mixed-value sequence low-split after low-copy candidates"
    return "probe blocked mixed-value sequence prerequisites after low-copy"


def mixed_value_sequence_low_copy_corpus_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix residual mixed-value sequence corpus after low-copy issues"
    if int_value(summary, "union_conflict_slots") > 0:
        return "split residual mixed-value sequence corpus after low-copy conflicts"
    if int_value(summary, "promotion_candidate_bytes") > 0:
        return "replay residual mixed-value sequence corpus after low-copy candidates"
    if int_value(summary, "unknown_prerequisite_slots") > 0:
        return "add blocked-prerequisite feature family beyond low-copy/corpus/adjacent-known"
    return "inspect residual mixed-value sequence after low-copy"


def mixed_value_sequence_low_copy_adjacent_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix residual adjacent-known after low-copy issues"
    if int_value(summary, "promotion_candidate_bytes") > 0:
        return "replay residual adjacent-known prerequisite candidates after low-copy"
    return "add blocked-prerequisite feature family beyond low-copy/corpus/adjacent-known"


def mixed_value_sequence_blocked_prerequisite_role_transform_action(summary: dict[str, str]) -> str:
    if int_value(summary, "issue_rows") > 0:
        return "fix blocked-prerequisite role-transform report issues"
    if int_value(summary, "promotion_candidate_bytes") > 0:
        return "replay full-byte blocked-prerequisite role-transform candidates"
    if int_value(summary, "partial_high_slots") > 0 or int_value(summary, "partial_low_slots") > 0:
        return "leave mixed-value blocked prerequisites until a non-oracle full-byte producer emerges"
    return "move mixed-value sequence residuals behind broader gradient/flat-walk probes"


def flat_walk_palette_formula_replay_consumed(
    summary: dict[str, str],
    candidate_summary: dict[str, str] | None = None,
) -> bool:
    return bool(
        candidate_summary
        and int_value(candidate_summary, "unique_backref_unlock_bytes") == 0
        and int_value(summary, "formula_false_bytes") == 0
        and int_value(summary, "issue_rows") == 0
    )


def build_queue(
    decisions: list[dict[str, str]],
    gradient_payload_profile_summary: dict[str, str] | None = None,
    gradient_payload_state_opcode_summary: dict[str, str] | None = None,
    gradient_macro_opcode_summary: dict[str, str] | None = None,
    gradient_macro_conflict_split_summary: dict[str, str] | None = None,
    gradient_macro_residual_state_summary: dict[str, str] | None = None,
    gradient_macro_phase_summary: dict[str, str] | None = None,
    gradient_macro_phase_conflict_split_summary: dict[str, str] | None = None,
    gradient_macro_phase_sequence_summary: dict[str, str] | None = None,
    gradient_macro_fixture_transition_summary: dict[str, str] | None = None,
    gradient_macro_state_cluster_summary: dict[str, str] | None = None,
    gradient_macro_source_profile_state_summary: dict[str, str] | None = None,
    gradient_seed_delta_payload_opcode_summary: dict[str, str] | None = None,
    gradient_nonlocal_known_spatial_summary: dict[str, str] | None = None,
    gradient_sequence_known_state_summary: dict[str, str] | None = None,
    gradient_sequence_high_safe_low_summary: dict[str, str] | None = None,
    gradient_sequence_high_safe_source_profile_low_summary: dict[str, str] | None = None,
    gradient_sequence_high_safe_row_corpus_low_summary: dict[str, str] | None = None,
    gradient_sequence_high_safe_transform_low_summary: dict[str, str] | None = None,
    gradient_sequence_high_safe_source_window_summary: dict[str, str] | None = None,
    gradient_sequence_high_safe_control_opcode_summary: dict[str, str] | None = None,
    gradient_sequence_high_safe_row_transition_summary: dict[str, str] | None = None,
    gradient_sequence_high_safe_row_markov_summary: dict[str, str] | None = None,
    gradient_sequence_high_safe_row_template_summary: dict[str, str] | None = None,
    gradient_sequence_high_safe_low_bucket_split_summary: dict[str, str] | None = None,
    gradient_sequence_high_safe_low_exception_summary: dict[str, str] | None = None,
    gradient_sequence_high_safe_low_exception_alignment_summary: dict[str, str] | None = None,
    gradient_sequence_high_safe_low_exception_alignment_review_summary: dict[str, str] | None = None,
    gradient_sequence_high_safe_low_exception_row_family_summary: dict[str, str] | None = None,
    gradient_sequence_high_safe_low_exception_external_state_summary: dict[str, str] | None = None,
    gradient_sequence_high_safe_low_exception_prerequisite_state_summary: dict[str, str] | None = None,
    gradient_sequence_high_safe_low_exception_source_dependency_summary: dict[str, str] | None = None,
    gradient_sequence_high_safe_low_exception_source_chain_summary: dict[str, str] | None = None,
    gradient_sequence_high_safe_low_exception_source_terminal_summary: dict[str, str] | None = None,
    gradient_sequence_high_safe_low_exception_source_terminal_review_summary: dict[str, str] | None = None,
    gradient_sequence_high_safe_low_exception_source_terminal_delta_summary: dict[str, str] | None = None,
    gradient_sequence_high_safe_low_exception_source_terminal_chain_context_summary: dict[str, str] | None = None,
    gradient_sequence_high_safe_low_exception_source_terminal_replay_support_summary: dict[str, str] | None = None,
    gradient_sequence_high_safe_low_exception_source_terminal_replay_union_summary: dict[str, str] | None = None,
    gradient_macro_state_cluster_payload_summary: dict[str, str] | None = None,
    gradient_macro_state_cluster_source_summary: dict[str, str] | None = None,
    gradient_macro_state_cluster_literal_summary: dict[str, str] | None = None,
    gradient_macro_state_cluster_backref_summary: dict[str, str] | None = None,
    flat_walk_backref_summary: dict[str, str] | None = None,
    flat_walk_backref_chain_summary: dict[str, str] | None = None,
    flat_walk_palette_context_summary: dict[str, str] | None = None,
    flat_walk_palette_normalized_context_summary: dict[str, str] | None = None,
    flat_walk_palette_value_split_summary: dict[str, str] | None = None,
    flat_walk_palette_value_table_summary: dict[str, str] | None = None,
    flat_walk_palette_compressed_selector_summary: dict[str, str] | None = None,
    flat_walk_palette_compressed_combo_summary: dict[str, str] | None = None,
    flat_walk_palette_compressed_formula_summary: dict[str, str] | None = None,
    flat_walk_palette_corpus_formula_summary: dict[str, str] | None = None,
    flat_walk_palette_promotion_candidate_summary: dict[str, str] | None = None,
    flat_walk_palette_formula_replay_summary: dict[str, str] | None = None,
    flat_walk_palette_post_formula_vertical_copy_summary: dict[str, str] | None = None,
    gradient_shape_peer_copy_summary: dict[str, str] | None = None,
    gradient_source_profile_high_low_summary: dict[str, str] | None = None,
    gradient_source_profile_high_safe_low_summary: dict[str, str] | None = None,
    micro_jump_mixed_payload_summary: dict[str, str] | None = None,
    jump_token_payload_profile_summary: dict[str, str] | None = None,
    jump_token_payload_state_opcode_summary: dict[str, str] | None = None,
    micro_token_family_split_summary: dict[str, str] | None = None,
    micro_mixed_value_subfamily_summary: dict[str, str] | None = None,
    micro_mixed_value_dominant_control_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_local_grammar_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_predictor_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_combo_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_high_low_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_source_profile_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_external_source_combo_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_external_high_low_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_state_external_combo_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_state_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_candidate_review_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_prefix_bootstrap_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_prefix_sequence_replay_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_prefix_sequence_promoted_replay_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_promoted_generalization_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_low_split_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_low_split_promoted_replay_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_expansion_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_low_split_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_low_split_generalization_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_second_low_split_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_second_expansion_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_promoted_replay_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_promoted_replay_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_promoted_replay_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_generalization_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_low_split_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_corpus_expansion_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_fourth_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_generalization_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_second_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_low_split_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_expansion_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_adjacent_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_generalization_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_fourth_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_low_split_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_corpus_expansion_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_adjacent_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_low_copy_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_low_copy_promoted_replay_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_low_copy_generalization_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_low_copy_second_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_low_copy_low_split_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_low_copy_corpus_expansion_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_low_copy_adjacent_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_sequence_blocked_prerequisite_role_transform_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_spatial_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_state_opcode_summary: dict[str, str] | None = None,
) -> list[dict[str, object]]:
    enriched: list[dict[str, object]] = []
    for row in decisions:
        ready = int_value(row, "promotion_ready_bytes")
        bytes_ = int_value(row, "bytes")
        status = "promotion_ready" if ready > 0 else "blocked_review"
        positive_evidence = row.get("positive_evidence", "")
        blocking_evidence = row.get("blocking_evidence", "")
        if row.get("surface", "") == "micro_token" and micro_token_family_split_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"family_split_clean_bytes={micro_token_family_split_summary.get('clean_family_bytes', '0')}",
                    f"family_split_top={micro_token_family_split_summary.get('top_family', '')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"family_split_ambiguous_bytes={micro_token_family_split_summary.get('ambiguous_bytes', '0')}",
                    f"family_split_disagreement_bytes="
                    f"{micro_token_family_split_summary.get('existing_disagreement_bytes', '0')}",
                ],
            )
            row = {**row, "positive_evidence": positive_evidence, "blocking_evidence": blocking_evidence}
        if row.get("surface", "") == "gradient_like" and gradient_payload_profile_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_payload_repeated_signature_bytes="
                    f"{gradient_payload_profile_summary.get('repeated_payload_signature_bytes', '0')}",
                    f"gradient_payload_class_pair_ge50="
                    f"{gradient_payload_profile_summary.get('class_pair_ge50_bytes', '0')}",
                    f"gradient_payload_source_profile_ge75="
                    f"{gradient_payload_profile_summary.get('source_profile_ge75_bytes', '0')}",
                    f"gradient_payload_spatial_exact="
                    f"{gradient_payload_profile_summary.get('spatial_exact_copy_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_payload_external_exact="
                    f"{gradient_payload_profile_summary.get('external_best_exact_bytes', '0')}",
                    f"gradient_payload_spatial_best_false="
                    f"{gradient_payload_profile_summary.get('spatial_best_false_bytes', '0')}",
                    f"gradient_payload_promotion_ready="
                    f"{gradient_payload_profile_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {**row, "positive_evidence": positive_evidence, "blocking_evidence": blocking_evidence}
        if row.get("surface", "") == "gradient_like" and gradient_payload_state_opcode_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_state_control_anchors="
                    f"{gradient_payload_state_opcode_summary.get('control_anchor_rows', '0')}",
                    f"gradient_state_best_band="
                    f"{gradient_payload_state_opcode_summary.get('best_band_correct_slots', '0')}/"
                    f"{gradient_payload_state_opcode_summary.get('best_band_false_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_state_raw_exact="
                    f"{gradient_payload_state_opcode_summary.get('control_raw_exact_bytes', '0')}/"
                    f"{gradient_payload_state_opcode_summary.get('start_raw_exact_bytes', '0')}",
                    f"gradient_state_best_byte="
                    f"{gradient_payload_state_opcode_summary.get('best_byte_correct_slots', '0')}/"
                    f"{gradient_payload_state_opcode_summary.get('best_byte_false_slots', '0')}",
                    f"gradient_state_best_step="
                    f"{gradient_payload_state_opcode_summary.get('best_step_correct_slots', '0')}/"
                    f"{gradient_payload_state_opcode_summary.get('best_step_false_slots', '0')}",
                    f"gradient_state_rejected="
                    f"{gradient_payload_state_opcode_summary.get('source_state_rejected', '0')}",
                    f"gradient_state_promotion_ready="
                    f"{gradient_payload_state_opcode_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": "derive higher-order gradient opcode grammar after local source-state rejection",
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "") == "gradient_like" and gradient_macro_opcode_summary:
            best_target = gradient_macro_opcode_summary.get("best_target_kind", "")
            best_selector = gradient_macro_opcode_summary.get("best_selector_family", "")
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_macro_best={best_target}/{best_selector}",
                    f"gradient_macro_deterministic="
                    f"{gradient_macro_opcode_summary.get('best_repeated_deterministic_bytes', '0')}",
                    f"gradient_macro_top_nibble="
                    f"{gradient_macro_opcode_summary.get('top_nibble_repeated_evidence_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_macro_conflicted="
                    f"{gradient_macro_opcode_summary.get('best_conflicted_bytes', '0')}",
                    f"gradient_macro_exact_payload="
                    f"{gradient_macro_opcode_summary.get('exact_payload_repeated_evidence_bytes', '0')}",
                    f"gradient_macro_band_shape="
                    f"{gradient_macro_opcode_summary.get('band_shape_repeated_evidence_bytes', '0')}",
                    f"gradient_macro_step_shape="
                    f"{gradient_macro_opcode_summary.get('step_shape_repeated_evidence_bytes', '0')}",
                    f"gradient_macro_promotion_ready="
                    f"{gradient_macro_opcode_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": "split macro selectors by dominant-delta conflicts before opcode promotion",
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "") == "gradient_like" and gradient_macro_conflict_split_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_macro_split_best="
                    f"{gradient_macro_conflict_split_summary.get('best_split_family', '')}",
                    f"gradient_macro_split_deterministic="
                    f"{gradient_macro_conflict_split_summary.get('best_split_deterministic_bytes', '0')}",
                    f"gradient_macro_split_reduction="
                    f"{gradient_macro_conflict_split_summary.get('best_split_conflict_reduction_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_macro_split_remaining="
                    f"{gradient_macro_conflict_split_summary.get('best_split_conflicted_bytes', '0')}",
                    f"gradient_macro_split_singleton="
                    f"{gradient_macro_conflict_split_summary.get('best_split_singleton_bytes', '0')}",
                    f"gradient_macro_split_low_conflict_singleton="
                    f"{gradient_macro_conflict_split_summary.get('low_conflict_singleton_bytes', '0')}",
                    f"gradient_macro_split_promotion_ready="
                    f"{gradient_macro_conflict_split_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": "resolve residual control-anchor macro conflict before gradient opcode promotion",
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "") == "gradient_like" and gradient_macro_residual_state_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_residual_state_best="
                    f"{gradient_macro_residual_state_summary.get('best_state_selector_family', '')}",
                    f"gradient_residual_state_deterministic="
                    f"{gradient_macro_residual_state_summary.get('best_state_deterministic_bytes', '0')}",
                    f"gradient_residual_source_best="
                    f"{gradient_macro_residual_state_summary.get('best_source_selector_family', '')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_residual_source_conflicted="
                    f"{gradient_macro_residual_state_summary.get('best_source_conflicted_bytes', '0')}",
                    f"gradient_residual_state_singleton="
                    f"{gradient_macro_residual_state_summary.get('best_state_singleton_bytes', '0')}",
                    f"gradient_residual_promotion_ready="
                    f"{gradient_macro_residual_state_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": "expand residual op-index phase bins across gradient macro rows before promotion",
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "") == "gradient_like" and gradient_macro_phase_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_phase_best="
                    f"{gradient_macro_phase_summary.get('best_coarse_target_kind', '')}/"
                    f"{gradient_macro_phase_summary.get('best_coarse_selector_family', '')}",
                    f"gradient_phase_deterministic="
                    f"{gradient_macro_phase_summary.get('best_coarse_deterministic_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_phase_conflicted="
                    f"{gradient_macro_phase_summary.get('best_coarse_conflicted_bytes', '0')}",
                    f"gradient_phase_payload_deterministic="
                    f"{gradient_macro_phase_summary.get('best_payload_deterministic_bytes', '0')}",
                    f"gradient_phase_payload_conflicted="
                    f"{gradient_macro_phase_summary.get('best_payload_conflicted_bytes', '0')}",
                    f"gradient_phase_promotion_ready="
                    f"{gradient_macro_phase_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": "split op-index phase conflicts before gradient macro opcode promotion",
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "") == "gradient_like" and gradient_macro_phase_conflict_split_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_phase_split_best="
                    f"{gradient_macro_phase_conflict_split_summary.get('best_split_family', '')}",
                    f"gradient_phase_split_deterministic="
                    f"{gradient_macro_phase_conflict_split_summary.get('best_split_deterministic_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_phase_split_conflicted="
                    f"{gradient_macro_phase_conflict_split_summary.get('best_split_conflicted_bytes', '0')}",
                    f"gradient_phase_split_singleton="
                    f"{gradient_macro_phase_conflict_split_summary.get('best_split_singleton_bytes', '0')}",
                    f"gradient_phase_split_promotion_ready="
                    f"{gradient_macro_phase_conflict_split_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": "broaden gradient phase grammar; op-index conflict split leaves mostly singletons",
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "") == "gradient_like" and gradient_macro_phase_sequence_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_phase_sequence_best="
                    f"{gradient_macro_phase_sequence_summary.get('best_sequence_target_kind', '')}/"
                    f"{gradient_macro_phase_sequence_summary.get('best_sequence_selector_family', '')}",
                    f"gradient_phase_sequence_deterministic="
                    f"{gradient_macro_phase_sequence_summary.get('best_sequence_deterministic_bytes', '0')}",
                    f"gradient_phase_sequence_low_conflict="
                    f"{gradient_macro_phase_sequence_summary.get('low_conflict_sequence_selector_family', '')}",
                    f"gradient_phase_sequence_low_conflict_deterministic="
                    f"{gradient_macro_phase_sequence_summary.get('low_conflict_sequence_deterministic_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_phase_sequence_conflicted="
                    f"{gradient_macro_phase_sequence_summary.get('best_sequence_conflicted_bytes', '0')}",
                    f"gradient_phase_sequence_singleton="
                    f"{gradient_macro_phase_sequence_summary.get('best_sequence_singleton_bytes', '0')}",
                    f"gradient_phase_sequence_low_conflict_singleton="
                    f"{gradient_macro_phase_sequence_summary.get('low_conflict_sequence_singleton_bytes', '0')}",
                    f"gradient_phase_sequence_payload_deterministic="
                    f"{gradient_macro_phase_sequence_summary.get('best_payload_deterministic_bytes', '0')}",
                    f"gradient_phase_sequence_promotion_ready="
                    f"{gradient_macro_phase_sequence_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": "probe fixture/op transition grammar; local sequence stays conflicted or singleton-heavy",
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "") == "gradient_like" and gradient_macro_fixture_transition_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_fixture_transition_best="
                    f"{gradient_macro_fixture_transition_summary.get('best_transition_target_kind', '')}/"
                    f"{gradient_macro_fixture_transition_summary.get('best_transition_selector_family', '')}",
                    f"gradient_fixture_transition_deterministic="
                    f"{gradient_macro_fixture_transition_summary.get('best_transition_deterministic_bytes', '0')}",
                    f"gradient_fixture_transition_low_conflict="
                    f"{gradient_macro_fixture_transition_summary.get('low_conflict_transition_selector_family', '')}",
                    f"gradient_fixture_transition_low_conflict_deterministic="
                    f"{gradient_macro_fixture_transition_summary.get('low_conflict_transition_deterministic_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_fixture_transition_conflicted="
                    f"{gradient_macro_fixture_transition_summary.get('best_transition_conflicted_bytes', '0')}",
                    f"gradient_fixture_transition_singleton="
                    f"{gradient_macro_fixture_transition_summary.get('best_transition_singleton_bytes', '0')}",
                    f"gradient_fixture_transition_low_conflict_singleton="
                    f"{gradient_macro_fixture_transition_summary.get('low_conflict_transition_singleton_bytes', '0')}",
                    f"gradient_fixture_transition_payload_deterministic="
                    f"{gradient_macro_fixture_transition_summary.get('best_payload_deterministic_bytes', '0')}",
                    f"gradient_fixture_transition_promotion_ready="
                    f"{gradient_macro_fixture_transition_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": (
                    "probe cross-frontier macro state clusters; fixture/op transition stays conflicted or singleton-heavy"
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "") == "gradient_like" and gradient_macro_state_cluster_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_macro_state_cluster_best="
                    f"{gradient_macro_state_cluster_summary.get('best_cluster_target_kind', '')}/"
                    f"{gradient_macro_state_cluster_summary.get('best_cluster_selector_family', '')}",
                    f"gradient_macro_state_cluster_deterministic="
                    f"{gradient_macro_state_cluster_summary.get('best_cluster_deterministic_bytes', '0')}",
                    f"gradient_macro_state_cluster_low_conflict="
                    f"{gradient_macro_state_cluster_summary.get('low_conflict_cluster_selector_family', '')}",
                    f"gradient_macro_state_cluster_low_conflict_deterministic="
                    f"{gradient_macro_state_cluster_summary.get('low_conflict_cluster_deterministic_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_macro_state_cluster_conflicted="
                    f"{gradient_macro_state_cluster_summary.get('best_cluster_conflicted_bytes', '0')}",
                    f"gradient_macro_state_cluster_singleton="
                    f"{gradient_macro_state_cluster_summary.get('best_cluster_singleton_bytes', '0')}",
                    f"gradient_macro_state_cluster_low_conflict_singleton="
                    f"{gradient_macro_state_cluster_summary.get('low_conflict_cluster_singleton_bytes', '0')}",
                    f"gradient_macro_state_cluster_payload_deterministic="
                    f"{gradient_macro_state_cluster_summary.get('best_payload_deterministic_bytes', '0')}",
                    f"gradient_macro_state_cluster_payload_conflicted="
                    f"{gradient_macro_state_cluster_summary.get('best_payload_conflicted_bytes', '0')}",
                    f"gradient_macro_state_cluster_promotion_ready="
                    f"{gradient_macro_state_cluster_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": "probe payload inside skip/op8 macro-state clusters before promotion",
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "") == "gradient_like" and gradient_macro_source_profile_state_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_macro_source_profile_joined="
                    f"{gradient_macro_source_profile_state_summary.get('joined_slots', '0')}",
                    f"gradient_macro_source_profile_full_ff_slots="
                    f"{gradient_macro_source_profile_state_summary.get('full_best_false_free_slots', '0')}",
                    f"gradient_macro_source_profile_low_ff_slots="
                    f"{gradient_macro_source_profile_state_summary.get('low_delta_best_false_free_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_macro_source_profile_full_best_false="
                    f"{gradient_macro_source_profile_state_summary.get('full_best_false_slots', '0')}",
                    f"gradient_macro_source_profile_target_low_false="
                    f"{gradient_macro_source_profile_state_summary.get('target_low_best_false_slots', '0')}",
                    f"gradient_macro_source_profile_low_delta_false="
                    f"{gradient_macro_source_profile_state_summary.get('low_delta_best_false_slots', '0')}",
                    f"gradient_macro_source_profile_promotion_ready="
                    f"{gradient_macro_source_profile_state_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_macro_source_profile_state_action(
                    gradient_macro_source_profile_state_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "") == "gradient_like" and gradient_seed_delta_payload_opcode_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_seed_payload_opcode_mapping="
                    f"{gradient_seed_delta_payload_opcode_summary.get('mapping_value_bytes', '0')}",
                    f"gradient_seed_payload_opcode_best="
                    f"{gradient_seed_delta_payload_opcode_summary.get('best_token_family', '')}/"
                    f"{gradient_seed_delta_payload_opcode_summary.get('best_token_repeated_bytes', '0')}",
                    f"gradient_seed_payload_opcode_copy_unlock="
                    f"{gradient_seed_delta_payload_opcode_summary.get('copy_unlock_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_seed_payload_opcode_conflicted="
                    f"{gradient_seed_delta_payload_opcode_summary.get('best_token_conflicted_bytes', '0')}",
                    f"gradient_seed_payload_opcode_singleton="
                    f"{gradient_seed_delta_payload_opcode_summary.get('singleton_deterministic_bytes', '0')}",
                    f"gradient_seed_payload_opcode_promotion_ready="
                    f"{gradient_seed_delta_payload_opcode_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_seed_delta_payload_opcode_action(
                    gradient_seed_delta_payload_opcode_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "") == "gradient_like" and gradient_nonlocal_known_spatial_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_known_spatial_sources="
                    f"{gradient_nonlocal_known_spatial_summary.get('known_source_samples', '0')}",
                    f"gradient_known_spatial_exact_candidates="
                    f"{gradient_nonlocal_known_spatial_summary.get('slots_with_exact_candidate', '0')}",
                    f"gradient_known_spatial_best="
                    f"{gradient_nonlocal_known_spatial_summary.get('best_distance', '')}/"
                    f"{gradient_nonlocal_known_spatial_summary.get('best_transform', '')}/"
                    f"{gradient_nonlocal_known_spatial_summary.get('best_exact_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_known_spatial_false_free="
                    f"{gradient_nonlocal_known_spatial_summary.get('false_free_rules', '0')}",
                    f"gradient_known_spatial_best_false="
                    f"{gradient_nonlocal_known_spatial_summary.get('best_false_slots', '0')}",
                    f"gradient_known_spatial_promotion_ready="
                    f"{gradient_nonlocal_known_spatial_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_nonlocal_known_spatial_action(
                    gradient_nonlocal_known_spatial_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "") == "gradient_like" and gradient_sequence_known_state_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_sequence_high_false_free="
                    f"{gradient_sequence_known_state_summary.get('high_best_false_free_slots', '0')}",
                    f"gradient_sequence_high_sets="
                    f"{gradient_sequence_known_state_summary.get('high_false_free_feature_sets', '0')}",
                    f"gradient_sequence_high_best="
                    f"{gradient_sequence_known_state_summary.get('high_best_exact_slots', '0')}/"
                    f"{gradient_sequence_known_state_summary.get('high_best_false_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_sequence_full_false_free="
                    f"{gradient_sequence_known_state_summary.get('full_false_free_feature_sets', '0')}",
                    f"gradient_sequence_low_false_free="
                    f"{gradient_sequence_known_state_summary.get('low_false_free_feature_sets', '0')}",
                    f"gradient_sequence_full_best_false="
                    f"{gradient_sequence_known_state_summary.get('full_best_false_slots', '0')}",
                    f"gradient_sequence_low_best_false="
                    f"{gradient_sequence_known_state_summary.get('low_best_false_slots', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_sequence_known_state_action(
                    gradient_sequence_known_state_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "") == "gradient_like" and gradient_sequence_high_safe_low_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_sequence_high_safe_slots="
                    f"{gradient_sequence_high_safe_low_summary.get('high_safe_slots', '0')}",
                    f"gradient_sequence_high_safe_rows="
                    f"{gradient_sequence_high_safe_low_summary.get('high_safe_rows', '0')}",
                    f"gradient_sequence_low_false_free_slots="
                    f"{gradient_sequence_high_safe_low_summary.get('target_low_best_false_free_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_sequence_low_best_false="
                    f"{gradient_sequence_high_safe_low_summary.get('target_low_best_false_slots', '0')}",
                    f"gradient_sequence_full_best_false="
                    f"{gradient_sequence_high_safe_low_summary.get('full_best_false_slots', '0')}",
                    f"gradient_sequence_high_safe_promotion_ready="
                    f"{gradient_sequence_high_safe_low_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_sequence_high_safe_low_action(
                    gradient_sequence_high_safe_low_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "") == "gradient_like"
            and gradient_sequence_high_safe_source_profile_low_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_sequence_source_profile_joined="
                    f"{gradient_sequence_high_safe_source_profile_low_summary.get('joined_slots', '0')}",
                    f"gradient_sequence_source_profile_low_ff_slots="
                    f"{gradient_sequence_high_safe_source_profile_low_summary.get('target_low_best_false_free_slots', '0')}",
                    f"gradient_sequence_source_profile_low_false_near="
                    f"{gradient_sequence_high_safe_source_profile_low_summary.get('target_low_low_false_exact_slots', '0')}/"
                    f"{gradient_sequence_high_safe_source_profile_low_summary.get('target_low_low_false_false_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_sequence_source_profile_low_best_false="
                    f"{gradient_sequence_high_safe_source_profile_low_summary.get('target_low_best_false_slots', '0')}",
                    f"gradient_sequence_source_profile_full_best_false="
                    f"{gradient_sequence_high_safe_source_profile_low_summary.get('full_best_false_slots', '0')}",
                    f"gradient_sequence_source_profile_promotion_ready="
                    f"{gradient_sequence_high_safe_source_profile_low_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_sequence_high_safe_source_profile_low_action(
                    gradient_sequence_high_safe_source_profile_low_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "") == "gradient_like" and gradient_macro_state_cluster_payload_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_cluster_payload_best="
                    f"{gradient_macro_state_cluster_payload_summary.get('best_payload_target_kind', '')}/"
                    f"{gradient_macro_state_cluster_payload_summary.get('best_payload_selector_family', '')}",
                    f"gradient_cluster_payload_deterministic="
                    f"{gradient_macro_state_cluster_payload_summary.get('best_payload_deterministic_bytes', '0')}",
                    f"gradient_cluster_payload_coarse="
                    f"{gradient_macro_state_cluster_payload_summary.get('best_coarse_target_kind', '')}/"
                    f"{gradient_macro_state_cluster_payload_summary.get('best_coarse_selector_family', '')}",
                    f"gradient_cluster_payload_coarse_deterministic="
                    f"{gradient_macro_state_cluster_payload_summary.get('best_coarse_deterministic_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_cluster_payload_exact_deterministic="
                    f"{gradient_macro_state_cluster_payload_summary.get('exact_payload_deterministic_bytes', '0')}",
                    f"gradient_cluster_payload_conflicted="
                    f"{gradient_macro_state_cluster_payload_summary.get('best_payload_conflicted_bytes', '0')}",
                    f"gradient_cluster_payload_singleton="
                    f"{gradient_macro_state_cluster_payload_summary.get('best_payload_singleton_bytes', '0')}",
                    f"gradient_cluster_payload_promotion_ready="
                    f"{gradient_macro_state_cluster_payload_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": (
                    "probe source-window transforms inside skip/op8 clusters; payload exact does not repeat"
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "") == "gradient_like" and gradient_macro_state_cluster_source_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_cluster_source_linear="
                    f"{gradient_macro_state_cluster_source_summary.get('linear_exact_bytes', '0')}",
                    f"gradient_cluster_source_control_high="
                    f"{gradient_macro_state_cluster_source_summary.get('control_high_exact_bytes', '0')}",
                    f"gradient_cluster_source_start_high="
                    f"{gradient_macro_state_cluster_source_summary.get('start_high_exact_bytes', '0')}",
                    f"gradient_cluster_source_best="
                    f"{gradient_macro_state_cluster_source_summary.get('best_source_target_kind', '')}/"
                    f"{gradient_macro_state_cluster_source_summary.get('best_source_selector_family', '')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_cluster_source_control_raw="
                    f"{gradient_macro_state_cluster_source_summary.get('control_raw_exact_bytes', '0')}",
                    f"gradient_cluster_source_start_raw="
                    f"{gradient_macro_state_cluster_source_summary.get('start_raw_exact_bytes', '0')}",
                    f"gradient_cluster_source_promotion_ready="
                    f"{gradient_macro_state_cluster_source_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": (
                    "probe literal/geometric transforms inside skip/op8 clusters; source-window replay is weak"
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "") == "gradient_like" and gradient_macro_state_cluster_literal_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_cluster_literal_spatial_best="
                    f"{gradient_macro_state_cluster_literal_summary.get('spatial_best_direction', '')}"
                    f"{gradient_macro_state_cluster_literal_summary.get('spatial_best_distance', '')}/"
                    f"{gradient_macro_state_cluster_literal_summary.get('spatial_best_transform', '')}",
                    f"gradient_cluster_literal_spatial_correct="
                    f"{gradient_macro_state_cluster_literal_summary.get('spatial_best_correct_bytes', '0')}",
                    f"gradient_cluster_literal_source_best="
                    f"{gradient_macro_state_cluster_literal_summary.get('source_best_pool', '')}/"
                    f"{gradient_macro_state_cluster_literal_summary.get('source_best_transform', '')}",
                    f"gradient_cluster_literal_source_correct="
                    f"{gradient_macro_state_cluster_literal_summary.get('source_best_correct_bytes', '0')}",
                    f"gradient_cluster_literal_back320_exact="
                    f"{gradient_macro_state_cluster_literal_summary.get('spatial_back_distance320_exact_rows', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_cluster_literal_spatial_false="
                    f"{gradient_macro_state_cluster_literal_summary.get('spatial_best_false_bytes', '0')}",
                    f"gradient_cluster_literal_spatial_exact="
                    f"{gradient_macro_state_cluster_literal_summary.get('spatial_best_exact_rows', '0')}",
                    f"gradient_cluster_literal_source_exact="
                    f"{gradient_macro_state_cluster_literal_summary.get('source_exact_rows', '0')}",
                    f"gradient_cluster_literal_promotion_ready="
                    f"{gradient_macro_state_cluster_literal_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": (
                    "isolate the lone -320 exact spatial row; broad literal/geometric transforms remain non-promotable"
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "") == "gradient_like" and gradient_macro_state_cluster_backref_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_cluster_backref_best="
                    f"{gradient_macro_state_cluster_backref_summary.get('best_rule', '')}",
                    f"gradient_cluster_backref_exact="
                    f"{gradient_macro_state_cluster_backref_summary.get('exact_back320_bytes', '0')}",
                    f"gradient_cluster_backref_candidate="
                    f"{gradient_macro_state_cluster_backref_summary.get('candidate_review_bytes', '0')}",
                    f"gradient_cluster_backref_literal_exact="
                    f"{gradient_macro_state_cluster_backref_summary.get('literal_target_exact_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_cluster_backref_false="
                    f"{gradient_macro_state_cluster_backref_summary.get('false_back320_bytes', '0')}",
                    f"gradient_cluster_backref_promotion_ready="
                    f"{gradient_macro_state_cluster_backref_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": "broaden flat-walk -320 backref probe outside macro clusters before promotion",
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "") == "gradient_like"
            and gradient_macro_state_cluster_backref_summary
            and flat_walk_backref_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"flat_walk_backref_broad_exact={flat_walk_backref_summary.get('exact_copy_bytes', '0')}",
                    f"flat_walk_backref_broad_distance={flat_walk_backref_summary.get('best_distance', '0')}",
                    f"flat_walk_backref_broad_best_rule={flat_walk_backref_summary.get('best_rule', '')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"flat_walk_backref_broad_known_source="
                    f"{flat_walk_backref_summary.get('exact_known_source_bytes', '0')}",
                    f"flat_walk_backref_broad_unresolved="
                    f"{flat_walk_backref_summary.get('exact_unresolved_source_bytes', '0')}",
                    f"flat_walk_backref_broad_rule_false="
                    f"{flat_walk_backref_summary.get('best_rule_false_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": "decode flat-walk first occurrences/source coverage before -320 replay promotion",
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "") == "gradient_like"
            and flat_walk_backref_summary
            and flat_walk_backref_chain_summary
            and flat_walk_palette_context_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"flat_walk_chain_source_candidate="
                    f"{flat_walk_backref_chain_summary.get('any_source_candidate_bytes', '0')}",
                    f"flat_walk_context_copy320="
                    f"{flat_walk_palette_context_summary.get('copy_distance_320_rows', '0')}",
                    f"flat_walk_context_overlap="
                    f"{flat_walk_palette_context_summary.get('best_unique_control_overlap', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"flat_walk_chain_repeated="
                    f"{flat_walk_backref_chain_summary.get('repeated_group_chain_bytes', '0')}",
                    f"flat_walk_chain_blocked="
                    f"{flat_walk_backref_chain_summary.get('blocked_chain_bytes', '0')}",
                    f"flat_walk_context_shared="
                    f"{flat_walk_palette_context_summary.get('shared_context_rows', '0')}",
                    f"flat_walk_context_same_transform="
                    f"{flat_walk_palette_context_summary.get('same_transform_set_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": "probe context-normalized palette producers for flat-walk first occurrences",
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "") == "gradient_like"
            and flat_walk_palette_context_summary
            and flat_walk_palette_normalized_context_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"flat_walk_palette_norm_groups="
                    f"{flat_walk_palette_normalized_context_summary.get('repeated_signature_groups', '0')}",
                    f"flat_walk_palette_norm_values="
                    f"{flat_walk_palette_normalized_context_summary.get('palette_value_count', '0')}",
                    f"flat_walk_palette_norm_best_delta_hits="
                    f"{flat_walk_palette_normalized_context_summary.get('best_transform_delta_value_hits', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"flat_walk_palette_norm_uniform_transform="
                    f"{flat_walk_palette_normalized_context_summary.get('uniform_transform_delta_groups', '0')}",
                    f"flat_walk_palette_norm_uniform_offset="
                    f"{flat_walk_palette_normalized_context_summary.get('uniform_offset_delta_groups', '0')}",
                    f"flat_walk_palette_norm_full="
                    f"{flat_walk_palette_normalized_context_summary.get('full_normalized_groups', '0')}",
                    f"flat_walk_palette_norm_promotion_ready="
                    f"{flat_walk_palette_normalized_context_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": (
                    "split palette values inside repeated flat-walk signatures; group-level normalization fails"
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "") == "gradient_like"
            and flat_walk_palette_normalized_context_summary
            and flat_walk_palette_value_split_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"flat_walk_palette_value_rows="
                    f"{flat_walk_palette_value_split_summary.get('value_rows', '0')}",
                    f"flat_walk_palette_value_best_transform="
                    f"{flat_walk_palette_value_split_summary.get('best_transform_delta', '')}/"
                    f"{flat_walk_palette_value_split_summary.get('best_transform_delta_values', '0')}",
                    f"flat_walk_palette_value_best_pair="
                    f"{flat_walk_palette_value_split_summary.get('best_delta_pair', '')}/"
                    f"{flat_walk_palette_value_split_summary.get('best_delta_pair_values', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"flat_walk_palette_value_transform_groups="
                    f"{flat_walk_palette_value_split_summary.get('transform_delta_groups', '0')}",
                    f"flat_walk_palette_value_pair_groups="
                    f"{flat_walk_palette_value_split_summary.get('delta_pair_groups', '0')}",
                    f"flat_walk_palette_value_promotion_ready="
                    f"{flat_walk_palette_value_split_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": (
                    "derive a compact palette-value delta table; best transform delta covers only 8/14 values"
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "") == "gradient_like"
            and flat_walk_palette_value_split_summary
            and flat_walk_palette_value_table_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"flat_walk_value_table_multi="
                    f"{flat_walk_palette_value_table_summary.get('multi_signature_values', '0')}",
                    f"flat_walk_value_table_stable_transform="
                    f"{flat_walk_palette_value_table_summary.get('stable_transform_multi_values', '0')}",
                    f"flat_walk_value_table_best_transform="
                    f"{flat_walk_palette_value_table_summary.get('best_value_transform', '')}/"
                    f"{flat_walk_palette_value_table_summary.get('best_value_transform_rows', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"flat_walk_value_table_conflicted_transform="
                    f"{flat_walk_palette_value_table_summary.get('conflicted_transform_multi_values', '0')}",
                    f"flat_walk_value_table_stable_pair="
                    f"{flat_walk_palette_value_table_summary.get('stable_pair_multi_values', '0')}",
                    f"flat_walk_value_table_promotion_ready="
                    f"{flat_walk_palette_value_table_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": "seek compressed-stream selectors for conflicted flat-walk palette values",
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "") == "gradient_like" and flat_walk_palette_compressed_selector_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"flat_walk_compressed_conflicted="
                    f"{flat_walk_palette_compressed_selector_summary.get('conflicted_value_rows', '0')}",
                    f"flat_walk_compressed_best_transform="
                    f"{flat_walk_palette_compressed_selector_summary.get('best_transform_selector', '')}/"
                    f"{flat_walk_palette_compressed_selector_summary.get('best_transform_selector_rows', '0')}->"
                    f"{flat_walk_palette_compressed_selector_summary.get('best_transform_selector_delta', '')}",
                    f"flat_walk_compressed_best_pair="
                    f"{flat_walk_palette_compressed_selector_summary.get('best_pair_selector', '')}/"
                    f"{flat_walk_palette_compressed_selector_summary.get('best_pair_selector_rows', '0')}",
                    f"flat_walk_compressed_exact_transform_groups="
                    f"{flat_walk_palette_compressed_selector_summary.get('exact_transform_compressed_groups', '0')}",
                    f"flat_walk_compressed_exact_pair_groups="
                    f"{flat_walk_palette_compressed_selector_summary.get('exact_pair_compressed_groups', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"flat_walk_compressed_best_transform_rows="
                    f"{flat_walk_palette_compressed_selector_summary.get('best_transform_selector_rows', '0')}/"
                    f"{flat_walk_palette_compressed_selector_summary.get('conflicted_value_rows', '0')}",
                    f"flat_walk_compressed_best_pair_rows="
                    f"{flat_walk_palette_compressed_selector_summary.get('best_pair_selector_rows', '0')}/"
                    f"{flat_walk_palette_compressed_selector_summary.get('conflicted_value_rows', '0')}",
                    f"flat_walk_compressed_promotion_ready="
                    f"{flat_walk_palette_compressed_selector_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": flat_walk_compressed_selector_action(flat_walk_palette_compressed_selector_summary),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "") == "gradient_like" and flat_walk_palette_compressed_combo_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"flat_walk_combo_best_transform="
                    f"{flat_walk_palette_compressed_combo_summary.get('best_transform_feature_set', '')}/"
                    f"{flat_walk_palette_compressed_combo_summary.get('best_transform_exact_conflicted_rows', '0')}"
                    f"_multirow={flat_walk_palette_compressed_combo_summary.get('best_transform_multirow_conflicted_rows', '0')}",
                    f"flat_walk_combo_best_pair="
                    f"{flat_walk_palette_compressed_combo_summary.get('best_pair_feature_set', '')}/"
                    f"{flat_walk_palette_compressed_combo_summary.get('best_pair_exact_conflicted_rows', '0')}",
                    f"flat_walk_combo_full_transform_sets="
                    f"{flat_walk_palette_compressed_combo_summary.get('full_transform_cover_sets', '0')}",
                    f"flat_walk_combo_full_pair_sets="
                    f"{flat_walk_palette_compressed_combo_summary.get('full_pair_cover_sets', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"flat_walk_combo_pair_singletons="
                    f"{flat_walk_palette_compressed_combo_summary.get('best_pair_singleton_conflicted_rows', '0')}",
                    f"flat_walk_combo_pair_multirow="
                    f"{flat_walk_palette_compressed_combo_summary.get('best_pair_multirow_conflicted_rows', '0')}",
                    f"flat_walk_combo_promotion_ready="
                    f"{flat_walk_palette_compressed_combo_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": flat_walk_compressed_combo_action(flat_walk_palette_compressed_combo_summary),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "") == "gradient_like" and flat_walk_palette_compressed_formula_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"flat_walk_formula_transform_exact="
                    f"{flat_walk_palette_compressed_formula_summary.get('transform_formula_exact_rows', '0')}/"
                    f"{flat_walk_palette_compressed_formula_summary.get('value_rows', '0')}",
                    f"flat_walk_formula_pair_exact="
                    f"{flat_walk_palette_compressed_formula_summary.get('pair_formula_exact_rows', '0')}/"
                    f"{flat_walk_palette_compressed_formula_summary.get('value_rows', '0')}",
                    f"flat_walk_formula_conflicted_pair_exact="
                    f"{flat_walk_palette_compressed_formula_summary.get('pair_formula_exact_conflicted_rows', '0')}/"
                    f"{flat_walk_palette_compressed_formula_summary.get('conflicted_value_rows', '0')}",
                    f"flat_walk_formula_raw_delta_groups="
                    f"{flat_walk_palette_compressed_formula_summary.get('raw_delta_groups', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"flat_walk_formula_scope_rows="
                    f"{flat_walk_palette_compressed_formula_summary.get('value_rows', '0')}",
                    f"flat_walk_formula_mismatches="
                    f"{flat_walk_palette_compressed_formula_summary.get('pair_formula_mismatch_rows', '0')}",
                    f"flat_walk_formula_promotion_ready="
                    f"{flat_walk_palette_compressed_formula_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": flat_walk_compressed_formula_action(flat_walk_palette_compressed_formula_summary),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "") == "gradient_like" and flat_walk_palette_corpus_formula_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"flat_walk_corpus_formula_exact="
                    f"{flat_walk_palette_corpus_formula_summary.get('shift_formula_exact_rows', '0')}/"
                    f"{flat_walk_palette_corpus_formula_summary.get('value_rows', '0')}",
                    f"flat_walk_corpus_formula_conflicted_exact="
                    f"{flat_walk_palette_corpus_formula_summary.get('shift_formula_exact_conflicted_rows', '0')}/"
                    f"{flat_walk_palette_corpus_formula_summary.get('known_conflicted_value_rows', '0')}",
                    f"flat_walk_corpus_formula_multi_exact="
                    f"{flat_walk_palette_corpus_formula_summary.get('shift_formula_exact_known_multi_rows', '0')}/"
                    f"{flat_walk_palette_corpus_formula_summary.get('known_multi_signature_value_rows', '0')}",
                    f"flat_walk_corpus_formula_pools="
                    f"{flat_walk_palette_corpus_formula_summary.get('candidate_pools', '0')}",
                    f"flat_walk_corpus_formula_transform_sets="
                    f"{flat_walk_palette_corpus_formula_summary.get('transform_sets', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"flat_walk_corpus_formula_candidate_scope="
                    f"{flat_walk_palette_corpus_formula_summary.get('candidate_target_rows', '0')}/"
                    f"{flat_walk_palette_corpus_formula_summary.get('target_rows', '0')}",
                    f"flat_walk_corpus_formula_mismatches="
                    f"{flat_walk_palette_corpus_formula_summary.get('shift_formula_mismatch_rows', '0')}",
                    f"flat_walk_corpus_formula_promotion_ready="
                    f"{flat_walk_palette_corpus_formula_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": flat_walk_corpus_formula_action(flat_walk_palette_corpus_formula_summary),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "") == "gradient_like" and flat_walk_palette_promotion_candidate_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"flat_walk_palette_candidate_targets="
                    f"{flat_walk_palette_promotion_candidate_summary.get('candidate_ready_target_rows', '0')}",
                    f"flat_walk_palette_candidate_bytes="
                    f"{flat_walk_palette_promotion_candidate_summary.get('candidate_ready_bytes', '0')}",
                    f"flat_walk_palette_candidate_plus_unlock="
                    f"{flat_walk_palette_promotion_candidate_summary.get('total_candidate_plus_unlock_bytes', '0')}",
                    f"flat_walk_palette_candidate_raw_plus_unlock="
                    f"{flat_walk_palette_promotion_candidate_summary.get('raw_candidate_plus_unlock_bytes', '0')}",
                    f"flat_walk_palette_candidate_overlap="
                    f"{flat_walk_palette_promotion_candidate_summary.get('backref_candidate_overlap_bytes', '0')}",
                    f"flat_walk_palette_candidate_unique_unlock="
                    f"{flat_walk_palette_promotion_candidate_summary.get('unique_backref_unlock_bytes', '0')}",
                    f"flat_walk_palette_candidate_values="
                    f"{flat_walk_palette_promotion_candidate_summary.get('formula_exact_value_rows', '0')}/"
                    f"{flat_walk_palette_promotion_candidate_summary.get('formula_value_rows', '0')}",
                ],
            )
            candidate_blocking = [
                f"flat_walk_palette_candidate_promotion_ready="
                f"{flat_walk_palette_promotion_candidate_summary.get('promotion_ready_bytes', '0')}",
                f"flat_walk_palette_candidate_issues="
                f"{flat_walk_palette_promotion_candidate_summary.get('issue_rows', '0')}",
            ]
            if flat_walk_palette_formula_replay_summary:
                candidate_blocking.insert(
                    0,
                    f"flat_walk_palette_candidate_replayed="
                    f"{flat_walk_palette_formula_replay_summary.get('replayed_target_rows', '0')}/"
                    f"{flat_walk_palette_promotion_candidate_summary.get('candidate_ready_target_rows', '0')}",
                )
            else:
                candidate_blocking.insert(
                    0,
                    f"flat_walk_palette_candidate_replay_needed="
                    f"{flat_walk_palette_promotion_candidate_summary.get('candidate_ready_target_rows', '0')}",
                )
            blocking_evidence = append_evidence(blocking_evidence, candidate_blocking)
            row_updates = {
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
            if not flat_walk_palette_formula_replay_summary:
                row_updates["next_action"] = flat_walk_palette_promotion_candidate_action(
                    flat_walk_palette_promotion_candidate_summary
                )
            row = {**row, **row_updates}
        if row.get("surface", "") == "gradient_like" and flat_walk_palette_formula_replay_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"flat_walk_palette_replay_targets="
                    f"{flat_walk_palette_formula_replay_summary.get('replayed_target_rows', '0')}/"
                    f"{flat_walk_palette_formula_replay_summary.get('target_rows', '0')}",
                    f"flat_walk_palette_replay_added="
                    f"{flat_walk_palette_formula_replay_summary.get('formula_added_bytes', '0')}",
                    f"flat_walk_palette_replay_exact="
                    f"{flat_walk_palette_formula_replay_summary.get('formula_exact_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"flat_walk_palette_replay_false="
                    f"{flat_walk_palette_formula_replay_summary.get('formula_false_bytes', '0')}",
                    f"flat_walk_palette_replay_skipped="
                    f"{flat_walk_palette_formula_replay_summary.get('skipped_known_bytes', '0')}/"
                    f"{flat_walk_palette_formula_replay_summary.get('skipped_rejected_bytes', '0')}",
                    f"flat_walk_palette_replay_issues="
                    f"{flat_walk_palette_formula_replay_summary.get('issue_rows', '0')}",
                ],
            )
            row_updates = {
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
            if not flat_walk_palette_formula_replay_consumed(
                flat_walk_palette_formula_replay_summary,
                flat_walk_palette_promotion_candidate_summary,
            ):
                row_updates["next_action"] = flat_walk_palette_formula_replay_action(
                    flat_walk_palette_formula_replay_summary,
                    flat_walk_palette_promotion_candidate_summary,
                )
            else:
                row_updates["next_action"] = "continue unresolved decoder probes after deduped flat-walk palette replay"
            row = {**row, **row_updates}
        if row.get("surface", "") == "gradient_like" and flat_walk_palette_post_formula_vertical_copy_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"post_formula_vertical_copy_exact="
                    f"{flat_walk_palette_post_formula_vertical_copy_summary.get('copy_exact_bytes', '0')}",
                    f"post_formula_vertical_copy_best_false_free="
                    f"{flat_walk_palette_post_formula_vertical_copy_summary.get('best_false_free_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"post_formula_vertical_copy_false="
                    f"{flat_walk_palette_post_formula_vertical_copy_summary.get('copy_false_bytes', '0')}",
                    f"post_formula_vertical_copy_candidates="
                    f"{flat_walk_palette_post_formula_vertical_copy_summary.get('promotion_candidate_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": flat_walk_palette_post_formula_vertical_copy_action(
                    flat_walk_palette_post_formula_vertical_copy_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "") == "gradient_like" and gradient_shape_peer_copy_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_shape_peer_exact="
                    f"{gradient_shape_peer_copy_summary.get('copy_exact_bytes', '0')}",
                    f"gradient_shape_peer_best_false_free="
                    f"{gradient_shape_peer_copy_summary.get('best_false_free_bytes', '0')}",
                    f"gradient_shape_peer_unknown="
                    f"{gradient_shape_peer_copy_summary.get('unknown_gradient_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_shape_peer_false="
                    f"{gradient_shape_peer_copy_summary.get('copy_false_bytes', '0')}",
                    f"gradient_shape_peer_candidates="
                    f"{gradient_shape_peer_copy_summary.get('candidate_slots', '0')}",
                    f"gradient_shape_peer_promotions="
                    f"{gradient_shape_peer_copy_summary.get('promotion_candidate_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_shape_peer_copy_action(gradient_shape_peer_copy_summary),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "") == "gradient_like" and gradient_source_profile_high_low_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_source_profile_high_false_free="
                    f"{gradient_source_profile_high_low_summary.get('high_best_false_free_slots', '0')}",
                    f"gradient_source_profile_high_sets="
                    f"{gradient_source_profile_high_low_summary.get('high_false_free_feature_sets', '0')}",
                    f"gradient_source_profile_slots="
                    f"{gradient_source_profile_high_low_summary.get('slot_rows', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_source_profile_full_false_free="
                    f"{gradient_source_profile_high_low_summary.get('full_false_free_feature_sets', '0')}",
                    f"gradient_source_profile_low_false_free="
                    f"{gradient_source_profile_high_low_summary.get('low_false_free_feature_sets', '0')}",
                    f"gradient_source_profile_full_best_false="
                    f"{gradient_source_profile_high_low_summary.get('full_best_false_slots', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_source_profile_high_low_action(
                    gradient_source_profile_high_low_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "") == "gradient_like" and gradient_source_profile_high_safe_low_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_high_safe_slots="
                    f"{gradient_source_profile_high_safe_low_summary.get('high_safe_slots', '0')}",
                    f"gradient_high_safe_rows="
                    f"{gradient_source_profile_high_safe_low_summary.get('high_safe_rows', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_high_safe_target_low_ff="
                    f"{gradient_source_profile_high_safe_low_summary.get('target_low_false_free_sets', '0')}",
                    f"gradient_high_safe_delta_low_ff="
                    f"{gradient_source_profile_high_safe_low_summary.get('delta_low_false_free_sets', '0')}",
                    f"gradient_high_safe_target_low_false="
                    f"{gradient_source_profile_high_safe_low_summary.get('target_low_best_false_slots', '0')}",
                    f"gradient_high_safe_delta_low_false="
                    f"{gradient_source_profile_high_safe_low_summary.get('delta_low_best_false_slots', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_source_profile_high_safe_low_action(
                    gradient_source_profile_high_safe_low_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "") == "gradient_like"
            and gradient_sequence_high_safe_row_corpus_low_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_sequence_row_corpus_slots="
                    f"{gradient_sequence_high_safe_row_corpus_low_summary.get('row_corpus_slots', '0')}",
                    f"gradient_sequence_row_corpus_low_ff_slots="
                    f"{gradient_sequence_high_safe_row_corpus_low_summary.get('target_low_best_false_free_slots', '0')}",
                    f"gradient_sequence_row_corpus_low_false_near="
                    f"{gradient_sequence_high_safe_row_corpus_low_summary.get('target_low_low_false_exact_slots', '0')}/"
                    f"{gradient_sequence_high_safe_row_corpus_low_summary.get('target_low_low_false_false_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_sequence_row_corpus_low_best_false="
                    f"{gradient_sequence_high_safe_row_corpus_low_summary.get('target_low_best_false_slots', '0')}",
                    f"gradient_sequence_row_corpus_full_best_false="
                    f"{gradient_sequence_high_safe_row_corpus_low_summary.get('full_best_false_slots', '0')}",
                    f"gradient_sequence_row_corpus_promotion_ready="
                    f"{gradient_sequence_high_safe_row_corpus_low_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_sequence_high_safe_row_corpus_low_action(
                    gradient_sequence_high_safe_row_corpus_low_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "") == "gradient_like"
            and gradient_sequence_high_safe_transform_low_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_sequence_transform_low_rules="
                    f"{gradient_sequence_high_safe_transform_low_summary.get('candidate_rules', '0')}",
                    f"gradient_sequence_transform_low_ff_slots="
                    f"{gradient_sequence_high_safe_transform_low_summary.get('best_false_free_correct_slots', '0')}",
                    f"gradient_sequence_transform_low_near="
                    f"{gradient_sequence_high_safe_transform_low_summary.get('best_low_false_exact_slots', '0')}/"
                    f"{gradient_sequence_high_safe_transform_low_summary.get('best_low_false_false_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_sequence_transform_low_best_false="
                    f"{gradient_sequence_high_safe_transform_low_summary.get('best_false_slots', '0')}",
                    f"gradient_sequence_transform_low_best="
                    f"{gradient_sequence_high_safe_transform_low_summary.get('best_transform_target', '')}/"
                    f"{gradient_sequence_high_safe_transform_low_summary.get('best_feature_set', '')}",
                    f"gradient_sequence_transform_low_promotion_ready="
                    f"{gradient_sequence_high_safe_transform_low_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_sequence_high_safe_transform_low_action(
                    gradient_sequence_high_safe_transform_low_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "") == "gradient_like"
            and gradient_sequence_high_safe_source_window_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_sequence_source_window_fixed="
                    f"{gradient_sequence_high_safe_source_window_summary.get('fixed_low_best_exact_slots', '0')}/"
                    f"{gradient_sequence_high_safe_source_window_summary.get('fixed_low_best_false_slots', '0')}",
                    f"gradient_sequence_source_window_gate="
                    f"{gradient_sequence_high_safe_source_window_summary.get('gate_best_exact_slots', '0')}/"
                    f"{gradient_sequence_high_safe_source_window_summary.get('gate_best_false_slots', '0')}",
                    f"gradient_sequence_source_window_ff_slots="
                    f"{gradient_sequence_high_safe_source_window_summary.get('gate_best_false_free_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_sequence_source_window_fixed_candidate="
                    f"{gradient_sequence_high_safe_source_window_summary.get('fixed_low_best_candidate', '')}",
                    f"gradient_sequence_source_window_gate_candidate="
                    f"{gradient_sequence_high_safe_source_window_summary.get('gate_best_candidate', '')}/"
                    f"{gradient_sequence_high_safe_source_window_summary.get('gate_best_feature_set', '')}",
                    f"gradient_sequence_source_window_promotion_ready="
                    f"{gradient_sequence_high_safe_source_window_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_sequence_high_safe_source_window_action(
                    gradient_sequence_high_safe_source_window_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "") == "gradient_like"
            and gradient_sequence_high_safe_control_opcode_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_sequence_control_opcode_raw_low="
                    f"{gradient_sequence_high_safe_control_opcode_summary.get('control_low_exact_slots', '0')}/"
                    f"{gradient_sequence_high_safe_control_opcode_summary.get('start_low_exact_slots', '0')}",
                    f"gradient_sequence_control_opcode_low="
                    f"{gradient_sequence_high_safe_control_opcode_summary.get('best_low_correct_slots', '0')}/"
                    f"{gradient_sequence_high_safe_control_opcode_summary.get('best_low_false_slots', '0')}",
                    f"gradient_sequence_control_opcode_byte="
                    f"{gradient_sequence_high_safe_control_opcode_summary.get('best_byte_correct_slots', '0')}/"
                    f"{gradient_sequence_high_safe_control_opcode_summary.get('best_byte_false_slots', '0')}",
                    f"gradient_sequence_control_opcode_ff_low="
                    f"{gradient_sequence_high_safe_control_opcode_summary.get('best_low_false_free_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_sequence_control_opcode_low_context="
                    f"{gradient_sequence_high_safe_control_opcode_summary.get('best_low_context', '')}",
                    f"gradient_sequence_control_opcode_byte_context="
                    f"{gradient_sequence_high_safe_control_opcode_summary.get('best_byte_context', '')}",
                    f"gradient_sequence_control_opcode_promotion_ready="
                    f"{gradient_sequence_high_safe_control_opcode_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_sequence_high_safe_control_opcode_action(
                    gradient_sequence_high_safe_control_opcode_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "") == "gradient_like"
            and gradient_sequence_high_safe_row_transition_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_sequence_row_transition_fixed="
                    f"{gradient_sequence_high_safe_row_transition_summary.get('fixed_best_exact_slots', '0')}/"
                    f"{gradient_sequence_high_safe_row_transition_summary.get('fixed_best_false_slots', '0')}",
                    f"gradient_sequence_row_transition_gate="
                    f"{gradient_sequence_high_safe_row_transition_summary.get('gate_best_exact_slots', '0')}/"
                    f"{gradient_sequence_high_safe_row_transition_summary.get('gate_best_false_slots', '0')}",
                    f"gradient_sequence_row_transition_ff_slots="
                    f"{gradient_sequence_high_safe_row_transition_summary.get('gate_best_false_free_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_sequence_row_transition_fixed_candidate="
                    f"{gradient_sequence_high_safe_row_transition_summary.get('fixed_best_candidate', '')}",
                    f"gradient_sequence_row_transition_gate_candidate="
                    f"{gradient_sequence_high_safe_row_transition_summary.get('gate_best_candidate', '')}/"
                    f"{gradient_sequence_high_safe_row_transition_summary.get('gate_best_feature_set', '')}",
                    f"gradient_sequence_row_transition_promotion_ready="
                    f"{gradient_sequence_high_safe_row_transition_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_sequence_high_safe_row_transition_action(
                    gradient_sequence_high_safe_row_transition_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "") == "gradient_like"
            and gradient_sequence_high_safe_row_markov_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_sequence_row_markov_low="
                    f"{gradient_sequence_high_safe_row_markov_summary.get('best_low_correct_slots', '0')}/"
                    f"{gradient_sequence_high_safe_row_markov_summary.get('best_low_false_slots', '0')}",
                    f"gradient_sequence_row_markov_delta="
                    f"{gradient_sequence_high_safe_row_markov_summary.get('best_delta_correct_slots', '0')}/"
                    f"{gradient_sequence_high_safe_row_markov_summary.get('best_delta_false_slots', '0')}",
                    f"gradient_sequence_row_markov_ff_delta="
                    f"{gradient_sequence_high_safe_row_markov_summary.get('best_delta_false_free_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_sequence_row_markov_low_context="
                    f"{gradient_sequence_high_safe_row_markov_summary.get('best_low_context', '')}",
                    f"gradient_sequence_row_markov_delta_context="
                    f"{gradient_sequence_high_safe_row_markov_summary.get('best_delta_context', '')}",
                    f"gradient_sequence_row_markov_promotion_ready="
                    f"{gradient_sequence_high_safe_row_markov_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_sequence_high_safe_row_markov_action(
                    gradient_sequence_high_safe_row_markov_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "") == "gradient_like"
            and gradient_sequence_high_safe_row_template_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_sequence_row_template_low="
                    f"{gradient_sequence_high_safe_row_template_summary.get('best_low_correct_slots', '0')}/"
                    f"{gradient_sequence_high_safe_row_template_summary.get('best_low_false_slots', '0')}",
                    f"gradient_sequence_row_template_bucket="
                    f"{gradient_sequence_high_safe_row_template_summary.get('best_low_bucket_correct_slots', '0')}/"
                    f"{gradient_sequence_high_safe_row_template_summary.get('best_low_bucket_false_slots', '0')}",
                    f"gradient_sequence_row_template_ff_low="
                    f"{gradient_sequence_high_safe_row_template_summary.get('best_low_false_free_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_sequence_row_template_low_context="
                    f"{gradient_sequence_high_safe_row_template_summary.get('best_low_context', '')}",
                    f"gradient_sequence_row_template_bucket_context="
                    f"{gradient_sequence_high_safe_row_template_summary.get('best_low_bucket_context', '')}",
                    f"gradient_sequence_row_template_promotion_ready="
                    f"{gradient_sequence_high_safe_row_template_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_sequence_high_safe_row_template_action(
                    gradient_sequence_high_safe_row_template_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "") == "gradient_like"
            and gradient_sequence_high_safe_low_bucket_split_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_sequence_low_bucket_split="
                    f"{gradient_sequence_high_safe_low_bucket_split_summary.get('combined_best_correct_slots', '0')}/"
                    f"{gradient_sequence_high_safe_low_bucket_split_summary.get('combined_best_false_slots', '0')}",
                    f"gradient_sequence_low_bucket_baseline="
                    f"{gradient_sequence_high_safe_low_bucket_split_summary.get('combined_baseline_correct_slots', '0')}/"
                    f"{gradient_sequence_high_safe_low_bucket_split_summary.get('entry_slots', '0')}",
                    f"gradient_sequence_low_bucket_ff="
                    f"{gradient_sequence_high_safe_low_bucket_split_summary.get('combined_false_free_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_sequence_low_bucket_best="
                    f"{gradient_sequence_high_safe_low_bucket_split_summary.get('best_bucket', '')}:"
                    f"{gradient_sequence_high_safe_low_bucket_split_summary.get('best_context', '')}",
                    f"gradient_sequence_low_bucket_promotion_ready="
                    f"{gradient_sequence_high_safe_low_bucket_split_summary.get('promotion_ready_bytes', '0')}",
                    f"gradient_sequence_low_bucket_issues="
                    f"{gradient_sequence_high_safe_low_bucket_split_summary.get('issue_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_sequence_high_safe_low_bucket_split_action(
                    gradient_sequence_high_safe_low_bucket_split_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "") == "gradient_like"
            and gradient_sequence_high_safe_low_exception_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_sequence_low_exception="
                    f"{gradient_sequence_high_safe_low_exception_summary.get('combined_best_correct_slots', '0')}/"
                    f"{gradient_sequence_high_safe_low_exception_summary.get('combined_best_false_slots', '0')}",
                    f"gradient_sequence_low_exception_targets="
                    f"{gradient_sequence_high_safe_low_exception_summary.get('exception_targets', '')}",
                    f"gradient_sequence_low_exception_ff="
                    f"{gradient_sequence_high_safe_low_exception_summary.get('combined_false_free_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_sequence_low_exception_best="
                    f"{gradient_sequence_high_safe_low_exception_summary.get('best_target', '')}:"
                    f"{gradient_sequence_high_safe_low_exception_summary.get('best_context', '')}",
                    f"gradient_sequence_low_exception_promotion_ready="
                    f"{gradient_sequence_high_safe_low_exception_summary.get('promotion_ready_bytes', '0')}",
                    f"gradient_sequence_low_exception_issues="
                    f"{gradient_sequence_high_safe_low_exception_summary.get('issue_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_sequence_high_safe_low_exception_action(
                    gradient_sequence_high_safe_low_exception_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "") == "gradient_like"
            and gradient_sequence_high_safe_low_exception_alignment_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_sequence_low_exception_alignment="
                    f"{gradient_sequence_high_safe_low_exception_alignment_summary.get('best_correct_slots', '0')}/"
                    f"{gradient_sequence_high_safe_low_exception_alignment_summary.get('best_false_slots', '0')}",
                    f"gradient_sequence_low_exception_alignment_ff="
                    f"{gradient_sequence_high_safe_low_exception_alignment_summary.get('best_false_free_slots', '0')}",
                    f"gradient_sequence_low_exception_alignment_same_bucket_ff="
                    f"{gradient_sequence_high_safe_low_exception_alignment_summary.get('same_bucket_false_free_alignments', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_sequence_low_exception_alignment_best="
                    f"{gradient_sequence_high_safe_low_exception_alignment_summary.get('best_mode', '')}:"
                    f"{gradient_sequence_high_safe_low_exception_alignment_summary.get('best_shift', '')}",
                    f"gradient_sequence_low_exception_alignment_promotion_ready="
                    f"{gradient_sequence_high_safe_low_exception_alignment_summary.get('promotion_ready_bytes', '0')}",
                    f"gradient_sequence_low_exception_alignment_issues="
                    f"{gradient_sequence_high_safe_low_exception_alignment_summary.get('issue_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_sequence_high_safe_low_exception_alignment_action(
                    gradient_sequence_high_safe_low_exception_alignment_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "") == "gradient_like"
            and gradient_sequence_high_safe_low_exception_alignment_review_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_sequence_low_exception_alignment_review_ff="
                    f"{gradient_sequence_high_safe_low_exception_alignment_review_summary.get('same_bucket_false_free_alignments', '0')}/"
                    f"{gradient_sequence_high_safe_low_exception_alignment_review_summary.get('same_bucket_false_free_slots', '0')}",
                    f"gradient_sequence_low_exception_alignment_review_nonrow="
                    f"{gradient_sequence_high_safe_low_exception_alignment_review_summary.get('best_nonrow_false_free_correct_slots', '0')}/"
                    f"{gradient_sequence_high_safe_low_exception_alignment_review_summary.get('best_nonrow_false_free_alignments', '0')}",
                    f"gradient_sequence_low_exception_alignment_review_broad="
                    f"{gradient_sequence_high_safe_low_exception_alignment_review_summary.get('broad_false_free_selector_rows', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_sequence_low_exception_alignment_review_best="
                    f"{gradient_sequence_high_safe_low_exception_alignment_review_summary.get('best_nonrow_false_free_family', '')}:"
                    f"{gradient_sequence_high_safe_low_exception_alignment_review_summary.get('best_nonrow_false_free_key', '')}",
                    f"gradient_sequence_low_exception_alignment_review_promotion_ready="
                    f"{gradient_sequence_high_safe_low_exception_alignment_review_summary.get('promotion_ready_bytes', '0')}",
                    f"gradient_sequence_low_exception_alignment_review_issues="
                    f"{gradient_sequence_high_safe_low_exception_alignment_review_summary.get('issue_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_sequence_high_safe_low_exception_alignment_review_action(
                    gradient_sequence_high_safe_low_exception_alignment_review_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "") == "gradient_like"
            and gradient_sequence_high_safe_low_exception_row_family_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_sequence_low_exception_row_family_ff="
                    f"{gradient_sequence_high_safe_low_exception_row_family_summary.get('best_false_free_correct_slots', '0')}/"
                    f"{gradient_sequence_high_safe_low_exception_row_family_summary.get('best_false_free_alignments', '0')}",
                    f"gradient_sequence_low_exception_row_family_robust="
                    f"{gradient_sequence_high_safe_low_exception_row_family_summary.get('robust_family_rows', '0')}",
                    f"gradient_sequence_low_exception_row_family_narrow="
                    f"{gradient_sequence_high_safe_low_exception_row_family_summary.get('narrow_family_rows', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_sequence_low_exception_row_family_best="
                    f"{gradient_sequence_high_safe_low_exception_row_family_summary.get('best_false_free_family_kind', '')}:"
                    f"{gradient_sequence_high_safe_low_exception_row_family_summary.get('best_false_free_family_key', '')}",
                    f"gradient_sequence_low_exception_row_family_promotion_ready="
                    f"{gradient_sequence_high_safe_low_exception_row_family_summary.get('promotion_ready_bytes', '0')}",
                    f"gradient_sequence_low_exception_row_family_issues="
                    f"{gradient_sequence_high_safe_low_exception_row_family_summary.get('issue_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_sequence_high_safe_low_exception_row_family_action(
                    gradient_sequence_high_safe_low_exception_row_family_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "") == "gradient_like"
            and gradient_sequence_high_safe_low_exception_external_state_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_sequence_low_exception_external="
                    f"{gradient_sequence_high_safe_low_exception_external_state_summary.get('combined_best_correct_slots', '0')}/"
                    f"{gradient_sequence_high_safe_low_exception_external_state_summary.get('combined_best_false_slots', '0')}",
                    f"gradient_sequence_low_exception_external_ff="
                    f"{gradient_sequence_high_safe_low_exception_external_state_summary.get('combined_false_free_slots', '0')}",
                    f"gradient_sequence_low_exception_external_families="
                    f"{gradient_sequence_high_safe_low_exception_external_state_summary.get('context_families', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_sequence_low_exception_external_best="
                    f"{gradient_sequence_high_safe_low_exception_external_state_summary.get('best_target', '')}:"
                    f"{gradient_sequence_high_safe_low_exception_external_state_summary.get('best_context', '')}",
                    f"gradient_sequence_low_exception_external_promotion_ready="
                    f"{gradient_sequence_high_safe_low_exception_external_state_summary.get('promotion_ready_bytes', '0')}",
                    f"gradient_sequence_low_exception_external_issues="
                    f"{gradient_sequence_high_safe_low_exception_external_state_summary.get('issue_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_sequence_high_safe_low_exception_external_state_action(
                    gradient_sequence_high_safe_low_exception_external_state_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "") == "gradient_like"
            and gradient_sequence_high_safe_low_exception_prerequisite_state_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_sequence_low_exception_prereq="
                    f"{gradient_sequence_high_safe_low_exception_prerequisite_state_summary.get('combined_best_correct_slots', '0')}/"
                    f"{gradient_sequence_high_safe_low_exception_prerequisite_state_summary.get('combined_best_false_slots', '0')}",
                    f"gradient_sequence_low_exception_prereq_known="
                    f"{gradient_sequence_high_safe_low_exception_prerequisite_state_summary.get('target_known_slots', '0')}/"
                    f"{gradient_sequence_high_safe_low_exception_prerequisite_state_summary.get('slots', '0')}",
                    f"gradient_sequence_low_exception_prereq_ff="
                    f"{gradient_sequence_high_safe_low_exception_prerequisite_state_summary.get('combined_false_free_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_sequence_low_exception_prereq_best="
                    f"{gradient_sequence_high_safe_low_exception_prerequisite_state_summary.get('best_target', '')}:"
                    f"{gradient_sequence_high_safe_low_exception_prerequisite_state_summary.get('best_context', '')}",
                    f"gradient_sequence_low_exception_prereq_exact="
                    f"{gradient_sequence_high_safe_low_exception_prerequisite_state_summary.get('target_exact_slots', '0')}",
                    f"gradient_sequence_low_exception_prereq_promotion_ready="
                    f"{gradient_sequence_high_safe_low_exception_prerequisite_state_summary.get('promotion_ready_bytes', '0')}",
                    f"gradient_sequence_low_exception_prereq_issues="
                    f"{gradient_sequence_high_safe_low_exception_prerequisite_state_summary.get('issue_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_sequence_high_safe_low_exception_prerequisite_state_action(
                    gradient_sequence_high_safe_low_exception_prerequisite_state_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "") == "gradient_like"
            and gradient_sequence_high_safe_low_exception_source_dependency_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_sequence_low_exception_source_available="
                    f"{gradient_sequence_high_safe_low_exception_source_dependency_summary.get('source_available_slots', '0')}/"
                    f"{gradient_sequence_high_safe_low_exception_source_dependency_summary.get('slots', '0')}",
                    f"gradient_sequence_low_exception_source_highsafe_unknown="
                    f"{gradient_sequence_high_safe_low_exception_source_dependency_summary.get('source_unknown_in_highsafe_slots', '0')}",
                    f"gradient_sequence_low_exception_source_edges="
                    f"{gradient_sequence_high_safe_low_exception_source_dependency_summary.get('dependency_edges', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_sequence_low_exception_source_top_unknown="
                    f"{gradient_sequence_high_safe_low_exception_source_dependency_summary.get('top_unknown_dependency_edge', '')}:"
                    f"{gradient_sequence_high_safe_low_exception_source_dependency_summary.get('top_unknown_dependency_edge_slots', '0')}",
                    f"gradient_sequence_low_exception_source_exception_unknown="
                    f"{gradient_sequence_high_safe_low_exception_source_dependency_summary.get('exception_source_unknown_slots', '0')}/"
                    f"{gradient_sequence_high_safe_low_exception_source_dependency_summary.get('exception_source_unknown_in_highsafe_slots', '0')}",
                    f"gradient_sequence_low_exception_source_promotion_ready="
                    f"{gradient_sequence_high_safe_low_exception_source_dependency_summary.get('promotion_ready_bytes', '0')}",
                    f"gradient_sequence_low_exception_source_issues="
                    f"{gradient_sequence_high_safe_low_exception_source_dependency_summary.get('issue_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_sequence_high_safe_low_exception_source_dependency_action(
                    gradient_sequence_high_safe_low_exception_source_dependency_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "") == "gradient_like"
            and gradient_sequence_high_safe_low_exception_source_chain_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_sequence_low_exception_source_chains="
                    f"{gradient_sequence_high_safe_low_exception_source_chain_summary.get('unknown_highsafe_source_chains', '0')}",
                    f"gradient_sequence_low_exception_source_terminals="
                    f"{gradient_sequence_high_safe_low_exception_source_chain_summary.get('unique_terminal_slots', '0')}",
                    f"gradient_sequence_low_exception_source_cycles="
                    f"{gradient_sequence_high_safe_low_exception_source_chain_summary.get('cycle_chains', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_sequence_low_exception_source_terminal_best="
                    f"{gradient_sequence_high_safe_low_exception_source_chain_summary.get('best_context', '')}:"
                    f"{gradient_sequence_high_safe_low_exception_source_chain_summary.get('best_correct_slots', '0')}/"
                    f"{gradient_sequence_high_safe_low_exception_source_chain_summary.get('best_false_slots', '0')}",
                    f"gradient_sequence_low_exception_source_terminal_ff="
                    f"{gradient_sequence_high_safe_low_exception_source_chain_summary.get('best_false_free_slots', '0')}",
                    f"gradient_sequence_low_exception_source_chain_promotion_ready="
                    f"{gradient_sequence_high_safe_low_exception_source_chain_summary.get('promotion_ready_bytes', '0')}",
                    f"gradient_sequence_low_exception_source_chain_issues="
                    f"{gradient_sequence_high_safe_low_exception_source_chain_summary.get('issue_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_sequence_high_safe_low_exception_source_chain_action(
                    gradient_sequence_high_safe_low_exception_source_chain_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "") == "gradient_like"
            and gradient_sequence_high_safe_low_exception_source_terminal_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_sequence_low_exception_source_terminal_context="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_summary.get('best_correct_slots', '0')}/"
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_summary.get('best_false_slots', '0')}",
                    f"gradient_sequence_low_exception_source_terminal_context_ff="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_summary.get('best_false_free_slots', '0')}",
                    f"gradient_sequence_low_exception_source_terminal_context_features="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_summary.get('feature_sets', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_sequence_low_exception_source_terminal_context_best="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_summary.get('best_context', '')}",
                    f"gradient_sequence_low_exception_source_terminal_context_ff_key="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_summary.get('best_false_free_context', '')}",
                    f"gradient_sequence_low_exception_source_terminal_context_promotion_ready="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_summary.get('promotion_ready_bytes', '0')}",
                    f"gradient_sequence_low_exception_source_terminal_context_issues="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_summary.get('issue_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_sequence_high_safe_low_exception_source_terminal_action(
                    gradient_sequence_high_safe_low_exception_source_terminal_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "") == "gradient_like"
            and gradient_sequence_high_safe_low_exception_source_terminal_review_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_sequence_low_exception_source_terminal_review="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_review_summary.get('oracle_delta_root_exact', '0')}/"
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_review_summary.get('oracle_delta_root_false', '0')}",
                    f"gradient_sequence_low_exception_source_terminal_review_covered="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_review_summary.get('predicted_terminal_slots', '0')}/"
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_review_summary.get('covered_chains', '0')}",
                    f"gradient_sequence_low_exception_source_terminal_review_contexts="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_review_summary.get('covered_contexts', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_sequence_low_exception_source_terminal_review_lengths="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_review_summary.get('covered_chain_length2', '0')}/"
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_review_summary.get('covered_chain_length3', '0')}",
                    f"gradient_sequence_low_exception_source_terminal_review_promotion_ready="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_review_summary.get('promotion_ready_bytes', '0')}",
                    f"gradient_sequence_low_exception_source_terminal_review_issues="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_review_summary.get('issue_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_sequence_high_safe_low_exception_source_terminal_review_action(
                    gradient_sequence_high_safe_low_exception_source_terminal_review_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "") == "gradient_like"
            and gradient_sequence_high_safe_low_exception_source_terminal_delta_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_sequence_low_exception_source_terminal_delta="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_delta_summary.get('best_review_exact', '0')}/"
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_delta_summary.get('best_review_false', '0')}",
                    f"gradient_sequence_low_exception_source_terminal_delta_ff="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_delta_summary.get('best_false_free_review_exact', '0')}",
                    f"gradient_sequence_low_exception_source_terminal_delta_features="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_delta_summary.get('feature_sets', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_sequence_low_exception_source_terminal_delta_best="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_delta_summary.get('best_context', '')}",
                    f"gradient_sequence_low_exception_source_terminal_delta_ff_context="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_delta_summary.get('best_false_free_context', '')}",
                    f"gradient_sequence_low_exception_source_terminal_delta_promotion_ready="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_delta_summary.get('promotion_ready_bytes', '0')}",
                    f"gradient_sequence_low_exception_source_terminal_delta_issues="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_delta_summary.get('issue_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_sequence_high_safe_low_exception_source_terminal_delta_action(
                    gradient_sequence_high_safe_low_exception_source_terminal_delta_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "") == "gradient_like"
            and gradient_sequence_high_safe_low_exception_source_terminal_chain_context_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_sequence_low_exception_source_terminal_chain_context="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_chain_context_summary.get('best_correct_chains', '0')}/"
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_chain_context_summary.get('best_false_chains', '0')}",
                    f"gradient_sequence_low_exception_source_terminal_chain_context_ff="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_chain_context_summary.get('best_false_free_chains', '0')}",
                    f"gradient_sequence_low_exception_source_terminal_chain_context_features="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_chain_context_summary.get('feature_sets', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_sequence_low_exception_source_terminal_chain_context_best="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_chain_context_summary.get('best_context', '')}",
                    f"gradient_sequence_low_exception_source_terminal_chain_context_ff_context="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_chain_context_summary.get('best_false_free_context', '')}",
                    f"gradient_sequence_low_exception_source_terminal_chain_context_promotion_ready="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_chain_context_summary.get('promotion_ready_bytes', '0')}",
                    f"gradient_sequence_low_exception_source_terminal_chain_context_issues="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_chain_context_summary.get('issue_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_sequence_high_safe_low_exception_source_terminal_chain_context_action(
                    gradient_sequence_high_safe_low_exception_source_terminal_chain_context_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "") == "gradient_like"
            and gradient_sequence_high_safe_low_exception_source_terminal_replay_support_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_sequence_low_exception_source_terminal_replay_support="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_replay_support_summary.get('best_exact_chains', '0')}/"
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_replay_support_summary.get('best_false_chains', '0')}",
                    f"gradient_sequence_low_exception_source_terminal_replay_support_no_bucket="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_replay_support_summary.get('best_no_bucket_exact_chains', '0')}/"
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_replay_support_summary.get('best_no_bucket_false_chains', '0')}",
                    f"gradient_sequence_low_exception_source_terminal_replay_support_no_bucket_ff="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_replay_support_summary.get('best_no_bucket_false_free_chains', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_sequence_low_exception_source_terminal_replay_support_best="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_replay_support_summary.get('best_context', '')}",
                    f"gradient_sequence_low_exception_source_terminal_replay_support_no_bucket_best="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_replay_support_summary.get('best_no_bucket_context', '')}",
                    f"gradient_sequence_low_exception_source_terminal_replay_support_no_bucket_ff_context="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_replay_support_summary.get('best_no_bucket_false_free_context', '')}",
                    f"gradient_sequence_low_exception_source_terminal_replay_support_promotion_ready="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_replay_support_summary.get('promotion_ready_bytes', '0')}",
                    f"gradient_sequence_low_exception_source_terminal_replay_support_issues="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_replay_support_summary.get('issue_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_sequence_high_safe_low_exception_source_terminal_replay_support_action(
                    gradient_sequence_high_safe_low_exception_source_terminal_replay_support_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "") == "gradient_like"
            and gradient_sequence_high_safe_low_exception_source_terminal_replay_union_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"gradient_sequence_low_exception_source_terminal_replay_union="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_replay_union_summary.get('covered_roots', '0')}",
                    f"gradient_sequence_low_exception_source_terminal_replay_union_selected="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_replay_union_summary.get('selected_candidates', '0')}",
                    f"gradient_sequence_low_exception_source_terminal_replay_union_sources="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_replay_union_summary.get('chain_context_candidates', '0')}/"
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_replay_union_summary.get('terminal_replay_candidates', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"gradient_sequence_low_exception_source_terminal_replay_union_candidates="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_replay_union_summary.get('candidate_rows', '0')}",
                    f"gradient_sequence_low_exception_source_terminal_replay_union_conflicts="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_replay_union_summary.get('conflict_roots', '0')}",
                    f"gradient_sequence_low_exception_source_terminal_replay_union_promotion_ready="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_replay_union_summary.get('promotion_ready_bytes', '0')}",
                    f"gradient_sequence_low_exception_source_terminal_replay_union_issues="
                    f"{gradient_sequence_high_safe_low_exception_source_terminal_replay_union_summary.get('issue_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": gradient_sequence_high_safe_low_exception_source_terminal_replay_union_action(
                    gradient_sequence_high_safe_low_exception_source_terminal_replay_union_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "") == "micro_token" and micro_jump_mixed_payload_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"jump_payload_repeated_bucket_bytes="
                    f"{micro_jump_mixed_payload_summary.get('repeated_bucket_bytes', '0')}",
                    f"jump_payload_source_profile_ge75="
                    f"{micro_jump_mixed_payload_summary.get('source_profile_ge75_bytes', '0')}",
                    f"jump_payload_spatial_best="
                    f"{micro_jump_mixed_payload_summary.get('spatial_best_correct_bytes', '0')}/"
                    f"{micro_jump_mixed_payload_summary.get('spatial_best_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"jump_payload_repeated_signature_bytes="
                    f"{micro_jump_mixed_payload_summary.get('repeated_payload_signature_bytes', '0')}",
                    f"jump_payload_pair_ge50={micro_jump_mixed_payload_summary.get('pair_overlap_ge50_bytes', '0')}",
                    f"jump_payload_external_exact="
                    f"{micro_jump_mixed_payload_summary.get('external_best_exact_bytes', '0')}",
                    f"jump_payload_spatial_exact="
                    f"{micro_jump_mixed_payload_summary.get('spatial_exact_copy_bytes', '0')}",
                    f"jump_payload_promotion_ready="
                    f"{micro_jump_mixed_payload_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {**row, "positive_evidence": positive_evidence, "blocking_evidence": blocking_evidence}
        if row.get("surface", "").startswith("jump_token") and jump_token_payload_profile_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"jump_token_payload_source_profile_ge75="
                    f"{jump_token_payload_profile_summary.get('source_profile_ge75_bytes', '0')}",
                    f"jump_token_payload_class_pair_ge50="
                    f"{jump_token_payload_profile_summary.get('class_pair_ge50_bytes', '0')}",
                    f"jump_token_payload_spatial_best="
                    f"{jump_token_payload_profile_summary.get('spatial_best_correct_bytes', '0')}/"
                    f"{jump_token_payload_profile_summary.get('spatial_best_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"jump_token_payload_repeated_signature_bytes="
                    f"{jump_token_payload_profile_summary.get('repeated_payload_signature_bytes', '0')}",
                    f"jump_token_payload_external_exact="
                    f"{jump_token_payload_profile_summary.get('external_best_exact_bytes', '0')}",
                    f"jump_token_payload_spatial_exact="
                    f"{jump_token_payload_profile_summary.get('spatial_exact_copy_bytes', '0')}",
                    f"jump_token_payload_promotion_ready="
                    f"{jump_token_payload_profile_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {**row, "positive_evidence": positive_evidence, "blocking_evidence": blocking_evidence}
        if row.get("surface", "").startswith("jump_token") and jump_token_payload_state_opcode_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"jump_token_state_control_anchors="
                    f"{jump_token_payload_state_opcode_summary.get('control_anchor_rows', '0')}",
                    f"jump_token_state_control_slots="
                    f"{jump_token_payload_state_opcode_summary.get('control_slot_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"jump_token_state_raw_exact="
                    f"{jump_token_payload_state_opcode_summary.get('control_raw_exact_bytes', '0')}/"
                    f"{jump_token_payload_state_opcode_summary.get('start_raw_exact_bytes', '0')}",
                    f"jump_token_state_best_byte="
                    f"{jump_token_payload_state_opcode_summary.get('best_byte_correct_slots', '0')}/"
                    f"{jump_token_payload_state_opcode_summary.get('best_byte_false_slots', '0')}",
                    f"jump_token_state_best_high="
                    f"{jump_token_payload_state_opcode_summary.get('best_high_correct_slots', '0')}/"
                    f"{jump_token_payload_state_opcode_summary.get('best_high_false_slots', '0')}",
                    f"jump_token_state_rejected="
                    f"{jump_token_payload_state_opcode_summary.get('source_state_rejected', '0')}",
                    f"jump_token_state_promotion_ready="
                    f"{jump_token_payload_state_opcode_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {**row, "positive_evidence": positive_evidence, "blocking_evidence": blocking_evidence}
        if row.get("surface", "").startswith("mixed_token") and micro_mixed_value_subfamily_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_clean_bytes={micro_mixed_value_subfamily_summary.get('clean_bytes', '0')}",
                    f"mixed_value_repeated_subfamily_bytes="
                    f"{micro_mixed_value_subfamily_summary.get('repeated_subfamily_bytes', '0')}",
                    f"mixed_value_dominant={micro_mixed_value_subfamily_summary.get('dominant_subfamily', '')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_ambiguous_bytes={micro_mixed_value_subfamily_summary.get('ambiguous_bytes', '0')}",
                    f"mixed_value_promotion_ready="
                    f"{micro_mixed_value_subfamily_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {**row, "positive_evidence": positive_evidence, "blocking_evidence": blocking_evidence}
        if row.get("surface", "").startswith("mixed_token") and micro_mixed_value_dominant_control_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_dominant_signal_bytes="
                    f"{micro_mixed_value_dominant_control_summary.get('repeated_signal_bytes', '0')}",
                    f"mixed_value_dominant_control_signal_bytes="
                    f"{micro_mixed_value_dominant_control_summary.get('repeated_control_signal_bytes', '0')}",
                    f"mixed_value_dominant_control="
                    f"{micro_mixed_value_dominant_control_summary.get('dominant_control_signal', '')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_dominant_offset_context_bytes="
                    f"{micro_mixed_value_dominant_control_summary.get('repeated_offset_context_bytes', '0')}",
                    f"mixed_value_dominant_payload_bytes="
                    f"{micro_mixed_value_dominant_control_summary.get('repeated_payload_bytes', '0')}",
                    f"mixed_value_dominant_promotion_ready="
                    f"{micro_mixed_value_dominant_control_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {**row, "positive_evidence": positive_evidence, "blocking_evidence": blocking_evidence}
        if row.get("surface", "").startswith("mixed_token") and micro_mixed_value_payload_local_grammar_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_payload_repeated_byte_values="
                    f"{micro_mixed_value_payload_local_grammar_summary.get('repeated_byte_value_bytes', '0')}",
                    f"mixed_value_payload_byte_trigram_slots="
                    f"{micro_mixed_value_payload_local_grammar_summary.get('byte_trigram_repeated_slots', '0')}",
                    f"mixed_value_payload_high_ngram8_slots="
                    f"{micro_mixed_value_payload_local_grammar_summary.get('high_ngram8_repeated_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_payload_shape_bytes="
                    f"{micro_mixed_value_payload_local_grammar_summary.get('repeated_byte_shape_bytes', '0')}",
                    f"mixed_value_payload_byte_ngram8_slots="
                    f"{micro_mixed_value_payload_local_grammar_summary.get('byte_ngram8_repeated_slots', '0')}",
                    f"mixed_value_payload_promotion_ready="
                    f"{micro_mixed_value_payload_local_grammar_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {**row, "positive_evidence": positive_evidence, "blocking_evidence": blocking_evidence}
        if row.get("surface", "").startswith("mixed_token") and micro_mixed_value_payload_predictor_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_predictor_high_correct="
                    f"{micro_mixed_value_payload_predictor_summary.get('best_high_correct_slots', '0')}",
                    f"mixed_value_predictor_high_precision="
                    f"{micro_mixed_value_payload_predictor_summary.get('best_high_precision', '0')}",
                    f"mixed_value_predictor_high6_baseline="
                    f"{micro_mixed_value_payload_predictor_summary.get('high6_baseline_precision', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_predictor_byte_correct="
                    f"{micro_mixed_value_payload_predictor_summary.get('best_byte_correct_slots', '0')}",
                    f"mixed_value_predictor_byte_false="
                    f"{micro_mixed_value_payload_predictor_summary.get('best_byte_false_slots', '0')}",
                    f"mixed_value_predictor_promotion_ready="
                    f"{micro_mixed_value_payload_predictor_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {**row, "positive_evidence": positive_evidence, "blocking_evidence": blocking_evidence}
        if row.get("surface", "").startswith("mixed_token") and micro_mixed_value_payload_combo_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_combo_best_byte="
                    f"{micro_mixed_value_payload_combo_summary.get('best_byte_feature_set', '')}/"
                    f"{micro_mixed_value_payload_combo_summary.get('best_byte_correct_slots', '0')}"
                    f"_{micro_mixed_value_payload_combo_summary.get('best_byte_false_slots', '0')}",
                    f"mixed_value_combo_best_high="
                    f"{micro_mixed_value_payload_combo_summary.get('best_high_feature_set', '')}/"
                    f"{micro_mixed_value_payload_combo_summary.get('best_high_correct_slots', '0')}"
                    f"_{micro_mixed_value_payload_combo_summary.get('best_high_false_slots', '0')}",
                    f"mixed_value_combo_false_free_high="
                    f"{micro_mixed_value_payload_combo_summary.get('best_false_free_high_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_combo_false_free_byte="
                    f"{micro_mixed_value_payload_combo_summary.get('false_free_byte_slots', '0')}",
                    f"mixed_value_combo_feature_sets="
                    f"{micro_mixed_value_payload_combo_summary.get('feature_sets', '0')}",
                    f"mixed_value_combo_promotion_ready="
                    f"{micro_mixed_value_payload_combo_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_payload_combo_action(micro_mixed_value_payload_combo_summary),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "").startswith("mixed_token") and micro_mixed_value_payload_high_low_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_high_low_slots="
                    f"{micro_mixed_value_payload_high_low_summary.get('selected_high_slots', '0')}",
                    f"mixed_value_high_low_values="
                    f"{micro_mixed_value_payload_high_low_summary.get('selected_low_values', '')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_high_low_best="
                    f"{micro_mixed_value_payload_high_low_summary.get('best_low_feature_set', '')}/"
                    f"{micro_mixed_value_payload_high_low_summary.get('best_low_correct_slots', '0')}"
                    f"_{micro_mixed_value_payload_high_low_summary.get('best_low_false_slots', '0')}",
                    f"mixed_value_high_low_unknown="
                    f"{micro_mixed_value_payload_high_low_summary.get('best_low_unknown_slots', '0')}",
                    f"mixed_value_high_low_promotion_ready="
                    f"{micro_mixed_value_payload_high_low_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_payload_high_low_action(micro_mixed_value_payload_high_low_summary),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "").startswith("mixed_token") and micro_mixed_value_payload_source_profile_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_source_profile_ge50="
                    f"{micro_mixed_value_payload_source_profile_summary.get('profile_overlap_ge50_bytes', '0')}",
                    f"mixed_value_source_compressed_exact="
                    f"{micro_mixed_value_payload_source_profile_summary.get('compressed_best_exact_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_source_profile_ge75="
                    f"{micro_mixed_value_payload_source_profile_summary.get('profile_overlap_ge75_bytes', '0')}",
                    f"mixed_value_source_decoded_zero_bias="
                    f"{micro_mixed_value_payload_source_profile_summary.get('decoded_zero_bias_bytes', '0')}",
                    f"mixed_value_source_promotion_ready="
                    f"{micro_mixed_value_payload_source_profile_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {**row, "positive_evidence": positive_evidence, "blocking_evidence": blocking_evidence}
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_external_source_combo_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_external_best_byte="
                    f"{micro_mixed_value_payload_external_source_combo_summary.get('best_byte_feature_set', '')}/"
                    f"{micro_mixed_value_payload_external_source_combo_summary.get('best_byte_correct_slots', '0')}"
                    f"_{micro_mixed_value_payload_external_source_combo_summary.get('best_byte_false_slots', '0')}",
                    f"mixed_value_external_false_free_byte="
                    f"{micro_mixed_value_payload_external_source_combo_summary.get('best_false_free_byte_slots', '0')}",
                    f"mixed_value_external_false_free_high="
                    f"{micro_mixed_value_payload_external_source_combo_summary.get('best_false_free_high_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_external_byte_unknown="
                    f"{micro_mixed_value_payload_external_source_combo_summary.get('best_false_free_byte_unknown_slots', '0')}",
                    f"mixed_value_external_high_unknown="
                    f"{micro_mixed_value_payload_external_source_combo_summary.get('best_false_free_high_unknown_slots', '0')}",
                    f"mixed_value_external_promotion_ready="
                    f"{micro_mixed_value_payload_external_source_combo_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_external_source_combo_action(
                    micro_mixed_value_payload_external_source_combo_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "").startswith("mixed_token") and micro_mixed_value_payload_external_high_low_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_external_high_low_slots="
                    f"{micro_mixed_value_payload_external_high_low_summary.get('selected_high_slots', '0')}",
                    f"mixed_value_external_high_low_values="
                    f"{micro_mixed_value_payload_external_high_low_summary.get('selected_low_values', '')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_external_high_low_best="
                    f"{micro_mixed_value_payload_external_high_low_summary.get('best_low_feature_set', '')}/"
                    f"{micro_mixed_value_payload_external_high_low_summary.get('best_low_correct_slots', '0')}"
                    f"_{micro_mixed_value_payload_external_high_low_summary.get('best_low_false_slots', '0')}",
                    f"mixed_value_external_high_low_false_free="
                    f"{micro_mixed_value_payload_external_high_low_summary.get('false_free_low_slots', '0')}",
                    f"mixed_value_external_high_low_promotion_ready="
                    f"{micro_mixed_value_payload_external_high_low_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_external_high_low_action(
                    micro_mixed_value_payload_external_high_low_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "").startswith("mixed_token") and micro_mixed_value_payload_state_external_combo_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_state_external_best_byte="
                    f"{micro_mixed_value_payload_state_external_combo_summary.get('best_byte_feature_set', '')}/"
                    f"{micro_mixed_value_payload_state_external_combo_summary.get('best_byte_correct_slots', '0')}"
                    f"_{micro_mixed_value_payload_state_external_combo_summary.get('best_byte_false_slots', '0')}",
                    f"mixed_value_state_external_best_high="
                    f"{micro_mixed_value_payload_state_external_combo_summary.get('best_high_feature_set', '')}/"
                    f"{micro_mixed_value_payload_state_external_combo_summary.get('best_high_correct_slots', '0')}"
                    f"_{micro_mixed_value_payload_state_external_combo_summary.get('best_high_false_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_state_external_false_free_byte="
                    f"{micro_mixed_value_payload_state_external_combo_summary.get('best_false_free_byte_slots', '0')}",
                    f"mixed_value_state_external_promotion_ready="
                    f"{micro_mixed_value_payload_state_external_combo_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_state_external_combo_action(
                    micro_mixed_value_payload_state_external_combo_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "").startswith("mixed_token") and micro_mixed_value_payload_sequence_state_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_sequence_high="
                    f"{micro_mixed_value_payload_sequence_state_summary.get('best_false_free_high_slots', '0')}",
                    f"mixed_value_sequence_low_candidates="
                    f"{micro_mixed_value_payload_sequence_state_summary.get('promotion_candidate_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_sequence_best_byte="
                    f"{micro_mixed_value_payload_sequence_state_summary.get('best_byte_feature_set', '')}/"
                    f"{micro_mixed_value_payload_sequence_state_summary.get('best_byte_correct_slots', '0')}"
                    f"_{micro_mixed_value_payload_sequence_state_summary.get('best_byte_false_slots', '0')}",
                    f"mixed_value_sequence_promotion_ready="
                    f"{micro_mixed_value_payload_sequence_state_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_state_action(micro_mixed_value_payload_sequence_state_summary),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_sequence_candidate_review_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_sequence_review_candidates="
                    f"{micro_mixed_value_payload_sequence_candidate_review_summary.get('candidate_bytes', '0')}",
                    f"mixed_value_sequence_review_oracle_correct="
                    f"{micro_mixed_value_payload_sequence_candidate_review_summary.get('correct_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_sequence_review_known_prereq="
                    f"{micro_mixed_value_payload_sequence_candidate_review_summary.get('known_prerequisite_bytes', '0')}/"
                    f"{micro_mixed_value_payload_sequence_candidate_review_summary.get('prerequisite_bytes', '0')}",
                    f"mixed_value_sequence_review_oracle_dependency="
                    f"{micro_mixed_value_payload_sequence_candidate_review_summary.get('oracle_dependency_bytes', '0')}",
                    f"mixed_value_sequence_review_promotion_ready="
                    f"{micro_mixed_value_payload_sequence_candidate_review_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_candidate_review_action(
                    micro_mixed_value_payload_sequence_candidate_review_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "").startswith("mixed_token") and micro_mixed_value_payload_prefix_bootstrap_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prefix_union="
                    f"{micro_mixed_value_payload_prefix_bootstrap_summary.get('union_candidate_slots', '0')}",
                    f"mixed_value_prefix_sequence_unlock="
                    f"{micro_mixed_value_payload_prefix_bootstrap_summary.get('sequence_candidate_unlocked_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prefix_conflicts="
                    f"{micro_mixed_value_payload_prefix_bootstrap_summary.get('union_conflict_slots', '0')}",
                    f"mixed_value_prefix_promotion_ready="
                    f"{micro_mixed_value_payload_prefix_bootstrap_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_prefix_bootstrap_action(
                    micro_mixed_value_payload_prefix_bootstrap_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "").startswith("mixed_token") and micro_mixed_value_payload_prefix_sequence_replay_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prefix_sequence_added="
                    f"{micro_mixed_value_payload_prefix_sequence_replay_summary.get('total_added_bytes', '0')}",
                    f"mixed_value_prefix_sequence_guarded="
                    f"{micro_mixed_value_payload_prefix_sequence_replay_summary.get('guarded_replay_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prefix_sequence_false="
                    f"{micro_mixed_value_payload_prefix_sequence_replay_summary.get('total_false_bytes', '0')}",
                    f"mixed_value_prefix_sequence_promotion_ready="
                    f"{micro_mixed_value_payload_prefix_sequence_replay_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_prefix_sequence_replay_action(
                    micro_mixed_value_payload_prefix_sequence_replay_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_prefix_sequence_promoted_replay_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prefix_sequence_promoted="
                    f"{micro_mixed_value_payload_prefix_sequence_promoted_replay_summary.get('mixed_value_added_bytes', '0')}",
                    f"mixed_value_prefix_sequence_clean_total="
                    f"{micro_mixed_value_payload_prefix_sequence_promoted_replay_summary.get('total_clean_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prefix_sequence_promoted_false="
                    f"{micro_mixed_value_payload_prefix_sequence_promoted_replay_summary.get('mixed_value_false_bytes', '0')}",
                    f"mixed_value_prefix_sequence_promoted_issues="
                    f"{micro_mixed_value_payload_prefix_sequence_promoted_replay_summary.get('issue_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_prefix_sequence_promoted_replay_action(
                    micro_mixed_value_payload_prefix_sequence_promoted_replay_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_sequence_promoted_generalization_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_sequence_replayable_unknown="
                    f"{micro_mixed_value_payload_sequence_promoted_generalization_summary.get('replayable_unknown_slots', '0')}",
                    f"mixed_value_sequence_target_known="
                    f"{micro_mixed_value_payload_sequence_promoted_generalization_summary.get('target_known_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_sequence_generalization_false_free="
                    f"{micro_mixed_value_payload_sequence_promoted_generalization_summary.get('false_free_feature_sets', '0')}",
                    f"mixed_value_sequence_generalization_best="
                    f"{micro_mixed_value_payload_sequence_promoted_generalization_summary.get('best_correct_slots', '0')}/"
                    f"{micro_mixed_value_payload_sequence_promoted_generalization_summary.get('best_false_slots', '0')}",
                    f"mixed_value_sequence_blocked="
                    f"{micro_mixed_value_payload_sequence_promoted_generalization_summary.get('blocked_prerequisite_slots', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_promoted_generalization_action(
                    micro_mixed_value_payload_sequence_promoted_generalization_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "").startswith("mixed_token") and micro_mixed_value_payload_sequence_low_split_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_low_split_false_free="
                    f"{micro_mixed_value_payload_sequence_low_split_summary.get('false_free_split_sets', '0')}",
                    f"mixed_value_low_split_candidates="
                    f"{micro_mixed_value_payload_sequence_low_split_summary.get('promotion_candidate_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_low_split_best_unknown="
                    f"{micro_mixed_value_payload_sequence_low_split_summary.get('best_false_free_split_unknown_slots', '0')}",
                    f"mixed_value_low_split_conflicted="
                    f"{micro_mixed_value_payload_sequence_low_split_summary.get('best_conflicted_correct_slots', '0')}/"
                    f"{micro_mixed_value_payload_sequence_low_split_summary.get('best_conflicted_false_slots', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_low_split_action(
                    micro_mixed_value_payload_sequence_low_split_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_sequence_low_split_promoted_replay_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_low_split_promoted="
                    f"{micro_mixed_value_payload_sequence_low_split_promoted_replay_summary.get('low_split_added_bytes', '0')}",
                    f"mixed_value_low_split_clean_total="
                    f"{micro_mixed_value_payload_sequence_low_split_promoted_replay_summary.get('total_clean_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_low_split_false="
                    f"{micro_mixed_value_payload_sequence_low_split_promoted_replay_summary.get('low_split_false_bytes', '0')}",
                    f"mixed_value_low_split_issues="
                    f"{micro_mixed_value_payload_sequence_low_split_promoted_replay_summary.get('issue_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_low_split_promoted_replay_action(
                    micro_mixed_value_payload_sequence_low_split_promoted_replay_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_sequence_prerequisite_expansion_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prereq_candidates="
                    f"{micro_mixed_value_payload_sequence_prerequisite_expansion_summary.get('union_candidate_slots', '0')}",
                    f"mixed_value_prereq_unlocks="
                    f"{micro_mixed_value_payload_sequence_prerequisite_expansion_summary.get('unlocked_sequence_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_unknown="
                    f"{micro_mixed_value_payload_sequence_prerequisite_expansion_summary.get('unknown_prerequisite_slots', '0')}",
                    f"mixed_value_prereq_conflicts="
                    f"{micro_mixed_value_payload_sequence_prerequisite_expansion_summary.get('union_conflict_slots', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_expansion_action(
                    micro_mixed_value_payload_sequence_prerequisite_expansion_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prereq_promoted="
                    f"{micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay_summary.get('prerequisite_added_bytes', '0')}",
                    f"mixed_value_prereq_clean_total="
                    f"{micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay_summary.get('total_clean_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_false="
                    f"{micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay_summary.get('prerequisite_false_bytes', '0')}",
                    f"mixed_value_prereq_issues="
                    f"{micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay_summary.get('issue_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_expansion_promoted_action(
                    micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "").startswith("mixed_token") and micro_mixed_value_payload_sequence_prerequisite_low_split_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prereq_low_split_false_free="
                    f"{micro_mixed_value_payload_sequence_prerequisite_low_split_summary.get('false_free_split_sets', '0')}",
                    f"mixed_value_prereq_low_split_candidates="
                    f"{micro_mixed_value_payload_sequence_prerequisite_low_split_summary.get('promotion_candidate_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_low_split_unknown="
                    f"{micro_mixed_value_payload_sequence_prerequisite_low_split_summary.get('best_false_free_split_unknown_slots', '0')}",
                    f"mixed_value_prereq_low_split_conflicted="
                    f"{micro_mixed_value_payload_sequence_prerequisite_low_split_summary.get('best_conflicted_correct_slots', '0')}/"
                    f"{micro_mixed_value_payload_sequence_prerequisite_low_split_summary.get('best_conflicted_false_slots', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_low_split_action(
                    micro_mixed_value_payload_sequence_prerequisite_low_split_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prereq_low_split_promoted="
                    f"{micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay_summary.get('low_split_added_bytes', '0')}",
                    f"mixed_value_prereq_low_split_clean_total="
                    f"{micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay_summary.get('total_clean_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_low_split_false="
                    f"{micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay_summary.get('low_split_false_bytes', '0')}",
                    f"mixed_value_prereq_low_split_issues="
                    f"{micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay_summary.get('issue_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_low_split_promoted_action(
                    micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_sequence_prerequisite_low_split_generalization_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prereq_low_split_gen_known="
                    f"{micro_mixed_value_payload_sequence_prerequisite_low_split_generalization_summary.get('target_known_slots', '0')}",
                    f"mixed_value_prereq_low_split_gen_replayable="
                    f"{micro_mixed_value_payload_sequence_prerequisite_low_split_generalization_summary.get('replayable_unknown_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_low_split_gen_false_free="
                    f"{micro_mixed_value_payload_sequence_prerequisite_low_split_generalization_summary.get('false_free_feature_sets', '0')}",
                    f"mixed_value_prereq_low_split_gen_best="
                    f"{micro_mixed_value_payload_sequence_prerequisite_low_split_generalization_summary.get('best_correct_slots', '0')}/"
                    f"{micro_mixed_value_payload_sequence_prerequisite_low_split_generalization_summary.get('best_false_slots', '0')}",
                    f"mixed_value_prereq_low_split_gen_blocked="
                    f"{micro_mixed_value_payload_sequence_prerequisite_low_split_generalization_summary.get('blocked_prerequisite_slots', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_low_split_generalization_action(
                    micro_mixed_value_payload_sequence_prerequisite_low_split_generalization_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "").startswith("mixed_token") and micro_mixed_value_payload_sequence_prerequisite_second_low_split_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prereq_second_low_split_features="
                    f"{micro_mixed_value_payload_sequence_prerequisite_second_low_split_summary.get('feature_sets', '0')}",
                    f"mixed_value_prereq_second_low_split_replayable="
                    f"{micro_mixed_value_payload_sequence_prerequisite_second_low_split_summary.get('replayable_unknown_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_second_low_split_false_free="
                    f"{micro_mixed_value_payload_sequence_prerequisite_second_low_split_summary.get('false_free_split_sets', '0')}",
                    f"mixed_value_prereq_second_low_split_candidates="
                    f"{micro_mixed_value_payload_sequence_prerequisite_second_low_split_summary.get('promotion_candidate_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_second_low_split_action(
                    micro_mixed_value_payload_sequence_prerequisite_second_low_split_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "").startswith("mixed_token") and micro_mixed_value_payload_sequence_prerequisite_second_expansion_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prereq_second_expansion_features="
                    f"{micro_mixed_value_payload_sequence_prerequisite_second_expansion_summary.get('feature_sets', '0')}",
                    f"mixed_value_prereq_second_expansion_blocked="
                    f"{micro_mixed_value_payload_sequence_prerequisite_second_expansion_summary.get('blocked_sequence_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_second_expansion_unknown="
                    f"{micro_mixed_value_payload_sequence_prerequisite_second_expansion_summary.get('unknown_prerequisite_slots', '0')}",
                    f"mixed_value_prereq_second_expansion_candidates="
                    f"{micro_mixed_value_payload_sequence_prerequisite_second_expansion_summary.get('promotion_candidate_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_second_expansion_action(
                    micro_mixed_value_payload_sequence_prerequisite_second_expansion_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "").startswith("mixed_token") and micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prereq_corpus_candidates="
                    f"{micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_summary.get('union_candidate_slots', '0')}",
                    f"mixed_value_prereq_corpus_unlocks="
                    f"{micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_summary.get('unlocked_sequence_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_corpus_unknown="
                    f"{micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_summary.get('unknown_prerequisite_slots', '0')}",
                    f"mixed_value_prereq_corpus_conflicts="
                    f"{micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_summary.get('union_conflict_slots', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_corpus_expansion_action(
                    micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_promoted_replay_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prereq_corpus_promoted="
                    f"{micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_promoted_replay_summary.get('prerequisite_added_bytes', '0')}",
                    f"mixed_value_prereq_corpus_clean_total="
                    f"{micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_promoted_replay_summary.get('total_clean_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_corpus_false="
                    f"{micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_promoted_replay_summary.get('prerequisite_false_bytes', '0')}",
                    f"mixed_value_prereq_corpus_issues="
                    f"{micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_promoted_replay_summary.get('issue_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_corpus_expansion_promoted_action(
                    micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_promoted_replay_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "").startswith("mixed_token") and micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prereq_corpus_low_split_false_free="
                    f"{micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_summary.get('false_free_split_sets', '0')}",
                    f"mixed_value_prereq_corpus_low_split_candidates="
                    f"{micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_summary.get('promotion_candidate_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_corpus_low_split_unknown="
                    f"{micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_summary.get('best_false_free_split_unknown_slots', '0')}",
                    f"mixed_value_prereq_corpus_low_split_conflicted="
                    f"{micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_summary.get('best_conflicted_correct_slots', '0')}/"
                    f"{micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_summary.get('best_conflicted_false_slots', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_corpus_low_split_action(
                    micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_promoted_replay_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prereq_corpus_low_split_promoted="
                    f"{micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_promoted_replay_summary.get('low_split_added_bytes', '0')}",
                    f"mixed_value_prereq_corpus_low_split_clean_total="
                    f"{micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_promoted_replay_summary.get('total_clean_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_corpus_low_split_false="
                    f"{micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_promoted_replay_summary.get('low_split_false_bytes', '0')}",
                    f"mixed_value_prereq_corpus_low_split_issues="
                    f"{micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_promoted_replay_summary.get('issue_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_corpus_low_split_promoted_action(
                    micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_promoted_replay_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "").startswith("mixed_token") and micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prereq_corpus_second_low_split_false_free="
                    f"{micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_summary.get('false_free_split_sets', '0')}",
                    f"mixed_value_prereq_corpus_second_low_split_candidates="
                    f"{micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_summary.get('promotion_candidate_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_corpus_second_low_split_unknown="
                    f"{micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_summary.get('best_false_free_split_unknown_slots', '0')}",
                    f"mixed_value_prereq_corpus_second_low_split_conflicted="
                    f"{micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_summary.get('best_conflicted_correct_slots', '0')}/"
                    f"{micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_summary.get('best_conflicted_false_slots', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_corpus_second_low_split_action(
                    micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_promoted_replay_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prereq_corpus_second_low_split_promoted="
                    f"{micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_promoted_replay_summary.get('low_split_added_bytes', '0')}",
                    f"mixed_value_prereq_corpus_second_low_split_clean_total="
                    f"{micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_promoted_replay_summary.get('total_clean_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_corpus_second_low_split_false="
                    f"{micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_promoted_replay_summary.get('low_split_false_bytes', '0')}",
                    f"mixed_value_prereq_corpus_second_low_split_issues="
                    f"{micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_promoted_replay_summary.get('issue_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_corpus_second_low_split_promoted_action(
                    micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_promoted_replay_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prereq_adjacent_promoted="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay_summary.get('prerequisite_added_bytes', '0')}",
                    f"mixed_value_prereq_adjacent_clean_total="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay_summary.get('total_clean_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_adjacent_false="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay_summary.get('prerequisite_false_bytes', '0')}",
                    f"mixed_value_prereq_adjacent_issues="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay_summary.get('issue_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_adjacent_known_promoted_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_sequence_prerequisite_adjacent_known_generalization_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prereq_adjacent_gen_known="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_generalization_summary.get('target_known_slots', '0')}",
                    f"mixed_value_prereq_adjacent_gen_replayable="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_generalization_summary.get('replayable_unknown_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_adjacent_gen_false_free="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_generalization_summary.get('false_free_feature_sets', '0')}",
                    f"mixed_value_prereq_adjacent_gen_blocked="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_generalization_summary.get('blocked_prerequisite_slots', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_adjacent_known_generalization_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_generalization_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "").startswith("mixed_token") and micro_mixed_value_payload_sequence_prerequisite_adjacent_known_low_split_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prereq_adjacent_low_split_features="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_low_split_summary.get('feature_sets', '0')}",
                    f"mixed_value_prereq_adjacent_low_split_replayable="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_low_split_summary.get('replayable_unknown_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_adjacent_low_split_false_free="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_low_split_summary.get('false_free_split_sets', '0')}",
                    f"mixed_value_prereq_adjacent_low_split_candidates="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_low_split_summary.get('promotion_candidate_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_adjacent_known_low_split_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_low_split_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_sequence_prerequisite_adjacent_known_corpus_expansion_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prereq_adjacent_corpus_features="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_corpus_expansion_summary.get('feature_sets', '0')}",
                    f"mixed_value_prereq_adjacent_corpus_unknown="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_corpus_expansion_summary.get('unknown_prerequisite_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_adjacent_corpus_false_free="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_corpus_expansion_summary.get('false_free_rule_sets', '0')}",
                    f"mixed_value_prereq_adjacent_corpus_candidates="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_corpus_expansion_summary.get('promotion_candidate_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_adjacent_known_corpus_expansion_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_corpus_expansion_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "").startswith("mixed_token") and micro_mixed_value_payload_sequence_prerequisite_adjacent_known_fourth_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prereq_adjacent_fourth_unknown="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_fourth_summary.get('unknown_prerequisite_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_adjacent_fourth_candidates="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_fourth_summary.get('promotion_candidate_bytes', '0')}",
                    f"mixed_value_prereq_adjacent_fourth_false="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_fourth_summary.get('adjacent_false_slots', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_adjacent_known_fourth_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_fourth_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prereq_adjacent_transform_false_free="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_summary.get('false_free_transform_sets', '0')}",
                    f"mixed_value_prereq_adjacent_transform_candidates="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_summary.get('promotion_candidate_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_adjacent_transform_unknown="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_summary.get('replayable_unknown_slots', '0')}",
                    f"mixed_value_prereq_adjacent_transform_issues="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_summary.get('issue_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_adjacent_known_transform_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prereq_adjacent_transform_promoted="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay_summary.get('low_split_added_bytes', '0')}",
                    f"mixed_value_prereq_adjacent_transform_clean_total="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay_summary.get('total_clean_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_adjacent_transform_false="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay_summary.get('low_split_false_bytes', '0')}",
                    f"mixed_value_prereq_adjacent_transform_promoted_issues="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay_summary.get('issue_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_adjacent_known_transform_promoted_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_generalization_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prereq_adjacent_transform_gen_known="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_generalization_summary.get('target_known_slots', '0')}",
                    f"mixed_value_prereq_adjacent_transform_gen_replayable="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_generalization_summary.get('replayable_unknown_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_adjacent_transform_gen_false_free="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_generalization_summary.get('false_free_feature_sets', '0')}",
                    f"mixed_value_prereq_adjacent_transform_gen_blocked="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_generalization_summary.get('blocked_prerequisite_slots', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_adjacent_known_transform_generalization_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_generalization_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_second_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prereq_adjacent_transform_second_false_free="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_second_summary.get('false_free_transform_sets', '0')}",
                    f"mixed_value_prereq_adjacent_transform_second_candidates="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_second_summary.get('promotion_candidate_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_adjacent_transform_second_unknown="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_second_summary.get('replayable_unknown_slots', '0')}",
                    f"mixed_value_prereq_adjacent_transform_second_issues="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_second_summary.get('issue_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_adjacent_known_transform_second_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_second_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_low_split_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prereq_adjacent_transform_low_split_features="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_low_split_summary.get('feature_sets', '0')}",
                    f"mixed_value_prereq_adjacent_transform_low_split_replayable="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_low_split_summary.get('replayable_unknown_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_adjacent_transform_low_split_false_free="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_low_split_summary.get('false_free_split_sets', '0')}",
                    f"mixed_value_prereq_adjacent_transform_low_split_candidates="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_low_split_summary.get('promotion_candidate_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_adjacent_known_transform_low_split_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_low_split_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_expansion_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prereq_adjacent_transform_corpus_features="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_expansion_summary.get('feature_sets', '0')}",
                    f"mixed_value_prereq_adjacent_transform_corpus_unknown="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_expansion_summary.get('unknown_prerequisite_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_adjacent_transform_corpus_false_free="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_expansion_summary.get('false_free_rule_sets', '0')}",
                    f"mixed_value_prereq_adjacent_transform_corpus_candidates="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_expansion_summary.get('promotion_candidate_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_adjacent_known_transform_corpus_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_expansion_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_adjacent_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prereq_adjacent_transform_adjacent_unknown="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_adjacent_summary.get('unknown_prerequisite_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_adjacent_transform_adjacent_candidates="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_adjacent_summary.get('promotion_candidate_bytes', '0')}",
                    f"mixed_value_prereq_adjacent_transform_adjacent_false="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_adjacent_summary.get('adjacent_false_slots', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_adjacent_known_transform_adjacent_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_adjacent_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prereq_adjacent_transform_corpus_promoted_total="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay_summary.get('total_clean_bytes', '0')}",
                    f"mixed_value_prereq_adjacent_transform_corpus_last_added="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay_summary.get('low_split_added_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_adjacent_transform_corpus_false="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay_summary.get('low_split_false_bytes', '0')}",
                    f"mixed_value_prereq_adjacent_transform_corpus_issues="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay_summary.get('issue_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_adjacent_known_transform_promoted_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_generalization_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prereq_adjacent_transform_corpus_gen_known="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_generalization_summary.get('target_known_slots', '0')}",
                    f"mixed_value_prereq_adjacent_transform_corpus_gen_replayable="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_generalization_summary.get('replayable_unknown_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_adjacent_transform_corpus_gen_false_free="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_generalization_summary.get('false_free_feature_sets', '0')}",
                    f"mixed_value_prereq_adjacent_transform_corpus_gen_blocked="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_generalization_summary.get('blocked_prerequisite_slots', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_adjacent_known_transform_generalization_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_generalization_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_fourth_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_prereq_adjacent_transform_corpus_fourth_false_free="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_fourth_summary.get('false_free_transform_sets', '0')}",
                    f"mixed_value_prereq_adjacent_transform_corpus_fourth_candidates="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_fourth_summary.get('promotion_candidate_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_adjacent_transform_corpus_fourth_unknown="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_fourth_summary.get('replayable_unknown_slots', '0')}",
                    f"mixed_value_prereq_adjacent_transform_corpus_fourth_issues="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_fourth_summary.get('issue_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_adjacent_known_transform_second_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_fourth_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_low_split_summary
        ):
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_adjacent_transform_corpus_low_split_false_free="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_low_split_summary.get('false_free_split_sets', '0')}",
                    f"mixed_value_prereq_adjacent_transform_corpus_low_split_candidates="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_low_split_summary.get('promotion_candidate_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_adjacent_known_transform_low_split_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_low_split_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_corpus_expansion_summary
        ):
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_adjacent_transform_corpus_final_false_free="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_corpus_expansion_summary.get('false_free_rule_sets', '0')}",
                    f"mixed_value_prereq_adjacent_transform_corpus_final_candidates="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_corpus_expansion_summary.get('promotion_candidate_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_adjacent_known_transform_corpus_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_corpus_expansion_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_adjacent_summary
        ):
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_prereq_adjacent_transform_corpus_adjacent_candidates="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_adjacent_summary.get('promotion_candidate_bytes', '0')}",
                    f"mixed_value_prereq_adjacent_transform_corpus_adjacent_false="
                    f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_adjacent_summary.get('adjacent_false_slots', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_prerequisite_adjacent_known_transform_adjacent_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_adjacent_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "").startswith("mixed_token") and micro_mixed_value_payload_sequence_low_copy_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_sequence_low_copy_false_free="
                    f"{micro_mixed_value_payload_sequence_low_copy_summary.get('false_free_copy_sets', '0')}",
                    f"mixed_value_sequence_low_copy_candidates="
                    f"{micro_mixed_value_payload_sequence_low_copy_summary.get('promotion_candidate_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_sequence_low_copy_unknown="
                    f"{micro_mixed_value_payload_sequence_low_copy_summary.get('replayable_unknown_slots', '0')}",
                    f"mixed_value_sequence_low_copy_issues="
                    f"{micro_mixed_value_payload_sequence_low_copy_summary.get('issue_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_low_copy_action(micro_mixed_value_payload_sequence_low_copy_summary),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_sequence_low_copy_promoted_replay_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_sequence_low_copy_promoted="
                    f"{micro_mixed_value_payload_sequence_low_copy_promoted_replay_summary.get('low_split_added_bytes', '0')}",
                    f"mixed_value_sequence_low_copy_clean_total="
                    f"{micro_mixed_value_payload_sequence_low_copy_promoted_replay_summary.get('total_clean_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_sequence_low_copy_false="
                    f"{micro_mixed_value_payload_sequence_low_copy_promoted_replay_summary.get('low_split_false_bytes', '0')}",
                    f"mixed_value_sequence_low_copy_promoted_issues="
                    f"{micro_mixed_value_payload_sequence_low_copy_promoted_replay_summary.get('issue_rows', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_low_copy_promoted_action(
                    micro_mixed_value_payload_sequence_low_copy_promoted_replay_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_sequence_low_copy_generalization_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_sequence_low_copy_gen_known="
                    f"{micro_mixed_value_payload_sequence_low_copy_generalization_summary.get('target_known_slots', '0')}",
                    f"mixed_value_sequence_low_copy_gen_replayable="
                    f"{micro_mixed_value_payload_sequence_low_copy_generalization_summary.get('replayable_unknown_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_sequence_low_copy_gen_blocked="
                    f"{micro_mixed_value_payload_sequence_low_copy_generalization_summary.get('blocked_prerequisite_slots', '0')}",
                    f"mixed_value_sequence_low_copy_gen_false_free="
                    f"{micro_mixed_value_payload_sequence_low_copy_generalization_summary.get('false_free_feature_sets', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_low_copy_generalization_action(
                    micro_mixed_value_payload_sequence_low_copy_generalization_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "").startswith("mixed_token") and micro_mixed_value_payload_sequence_low_copy_second_summary:
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_sequence_low_copy_second_false_free="
                    f"{micro_mixed_value_payload_sequence_low_copy_second_summary.get('false_free_copy_sets', '0')}",
                    f"mixed_value_sequence_low_copy_second_candidates="
                    f"{micro_mixed_value_payload_sequence_low_copy_second_summary.get('promotion_candidate_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_low_copy_second_action(
                    micro_mixed_value_payload_sequence_low_copy_second_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "").startswith("mixed_token") and micro_mixed_value_payload_sequence_low_copy_low_split_summary:
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_sequence_low_copy_low_split_false_free="
                    f"{micro_mixed_value_payload_sequence_low_copy_low_split_summary.get('false_free_split_sets', '0')}",
                    f"mixed_value_sequence_low_copy_low_split_candidates="
                    f"{micro_mixed_value_payload_sequence_low_copy_low_split_summary.get('promotion_candidate_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_low_copy_low_split_action(
                    micro_mixed_value_payload_sequence_low_copy_low_split_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_sequence_low_copy_corpus_expansion_summary
        ):
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_sequence_low_copy_corpus_false_free="
                    f"{micro_mixed_value_payload_sequence_low_copy_corpus_expansion_summary.get('false_free_rule_sets', '0')}",
                    f"mixed_value_sequence_low_copy_corpus_candidates="
                    f"{micro_mixed_value_payload_sequence_low_copy_corpus_expansion_summary.get('promotion_candidate_bytes', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_low_copy_corpus_action(
                    micro_mixed_value_payload_sequence_low_copy_corpus_expansion_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "").startswith("mixed_token") and micro_mixed_value_payload_sequence_low_copy_adjacent_summary:
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_sequence_low_copy_adjacent_candidates="
                    f"{micro_mixed_value_payload_sequence_low_copy_adjacent_summary.get('promotion_candidate_bytes', '0')}",
                    f"mixed_value_sequence_low_copy_adjacent_false="
                    f"{micro_mixed_value_payload_sequence_low_copy_adjacent_summary.get('adjacent_false_slots', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_low_copy_adjacent_action(
                    micro_mixed_value_payload_sequence_low_copy_adjacent_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if (
            row.get("surface", "").startswith("mixed_token")
            and micro_mixed_value_payload_sequence_blocked_prerequisite_role_transform_summary
        ):
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_blocked_prereq_role_partial_high="
                    f"{micro_mixed_value_payload_sequence_blocked_prerequisite_role_transform_summary.get('partial_high_slots', '0')}",
                    f"mixed_value_blocked_prereq_role_partial_low="
                    f"{micro_mixed_value_payload_sequence_blocked_prerequisite_role_transform_summary.get('partial_low_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_blocked_prereq_role_full_byte_sets="
                    f"{micro_mixed_value_payload_sequence_blocked_prerequisite_role_transform_summary.get('false_free_full_byte_sets', '0')}",
                    f"mixed_value_blocked_prereq_role_candidates="
                    f"{micro_mixed_value_payload_sequence_blocked_prerequisite_role_transform_summary.get('promotion_candidate_bytes', '0')}",
                    f"mixed_value_blocked_prereq_role_oracle_low_features="
                    f"{micro_mixed_value_payload_sequence_blocked_prerequisite_role_transform_summary.get('oracle_target_low_feature_sets', '0')}",
                ],
            )
            row = {
                **row,
                "next_action": mixed_value_sequence_blocked_prerequisite_role_transform_action(
                    micro_mixed_value_payload_sequence_blocked_prerequisite_role_transform_summary
                ),
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        if row.get("surface", "").startswith("mixed_token") and micro_mixed_value_payload_spatial_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_spatial_best_distance="
                    f"{micro_mixed_value_payload_spatial_summary.get('best_aggregate_distance', '0')}",
                    f"mixed_value_spatial_best_correct="
                    f"{micro_mixed_value_payload_spatial_summary.get('best_aggregate_correct_bytes', '0')}",
                    f"mixed_value_spatial_distance320_correct="
                    f"{micro_mixed_value_payload_spatial_summary.get('distance320_correct_bytes', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_spatial_best_false="
                    f"{micro_mixed_value_payload_spatial_summary.get('best_aggregate_false_bytes', '0')}",
                    f"mixed_value_spatial_exact_copy="
                    f"{micro_mixed_value_payload_spatial_summary.get('exact_copy_bytes', '0')}",
                    f"mixed_value_spatial_promotion_ready="
                    f"{micro_mixed_value_payload_spatial_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {**row, "positive_evidence": positive_evidence, "blocking_evidence": blocking_evidence}
        if row.get("surface", "").startswith("mixed_token") and micro_mixed_value_payload_state_opcode_summary:
            positive_evidence = append_evidence(
                positive_evidence,
                [
                    f"mixed_value_state_signal_slots="
                    f"{micro_mixed_value_payload_state_opcode_summary.get('signal_slot_bytes', '0')}",
                    f"mixed_value_state_best_high="
                    f"{micro_mixed_value_payload_state_opcode_summary.get('best_high_correct_slots', '0')}/"
                    f"{micro_mixed_value_payload_state_opcode_summary.get('best_high_false_slots', '0')}",
                ],
            )
            blocking_evidence = append_evidence(
                blocking_evidence,
                [
                    f"mixed_value_state_raw_exact="
                    f"{micro_mixed_value_payload_state_opcode_summary.get('signal_raw_exact_bytes', '0')}/"
                    f"{micro_mixed_value_payload_state_opcode_summary.get('control_raw_exact_bytes', '0')}",
                    f"mixed_value_state_best_byte="
                    f"{micro_mixed_value_payload_state_opcode_summary.get('best_byte_correct_slots', '0')}/"
                    f"{micro_mixed_value_payload_state_opcode_summary.get('best_byte_false_slots', '0')}",
                    f"mixed_value_state_rejected="
                    f"{micro_mixed_value_payload_state_opcode_summary.get('source_state_rejected', '0')}",
                    f"mixed_value_state_promotion_ready="
                    f"{micro_mixed_value_payload_state_opcode_summary.get('promotion_ready_bytes', '0')}",
                ],
            )
            row = {**row, "positive_evidence": positive_evidence, "blocking_evidence": blocking_evidence}
        if (
            row.get("surface", "") == "micro_token"
            and gradient_payload_profile_summary
            and micro_jump_mixed_payload_summary
            and jump_token_payload_profile_summary
        ):
            next_action = (
                "move beyond family splits: derive a state/opcode grammar for mixed-value, "
                "gradient and jump-token payloads"
            )
            if micro_mixed_value_payload_state_opcode_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_state_best_high="
                        f"{micro_mixed_value_payload_state_opcode_summary.get('best_high_correct_slots', '0')}/"
                        f"{micro_mixed_value_payload_state_opcode_summary.get('best_high_false_slots', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_state_best_byte="
                        f"{micro_mixed_value_payload_state_opcode_summary.get('best_byte_correct_slots', '0')}/"
                        f"{micro_mixed_value_payload_state_opcode_summary.get('best_byte_false_slots', '0')}",
                        f"mixed_value_state_rejected="
                        f"{micro_mixed_value_payload_state_opcode_summary.get('source_state_rejected', '0')}",
                    ],
                )
                next_action = (
                    "extend state/opcode search to gradient and jump-token payloads; "
                    "mixed-value source-state contexts are rejected"
                )
            if micro_mixed_value_payload_combo_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_combo_best_byte="
                        f"{micro_mixed_value_payload_combo_summary.get('best_byte_feature_set', '')}/"
                        f"{micro_mixed_value_payload_combo_summary.get('best_byte_correct_slots', '0')}"
                        f"_{micro_mixed_value_payload_combo_summary.get('best_byte_false_slots', '0')}",
                        f"mixed_value_combo_false_free_high="
                        f"{micro_mixed_value_payload_combo_summary.get('best_false_free_high_slots', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_combo_false_free_byte="
                        f"{micro_mixed_value_payload_combo_summary.get('false_free_byte_slots', '0')}",
                        f"mixed_value_combo_promotion_ready="
                        f"{micro_mixed_value_payload_combo_summary.get('promotion_ready_bytes', '0')}",
                    ],
                )
                next_action = mixed_value_payload_combo_action(micro_mixed_value_payload_combo_summary)
            if micro_mixed_value_payload_high_low_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_high_low_slots="
                        f"{micro_mixed_value_payload_high_low_summary.get('selected_high_slots', '0')}",
                        f"mixed_value_high_low_values="
                        f"{micro_mixed_value_payload_high_low_summary.get('selected_low_values', '')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_high_low_best="
                        f"{micro_mixed_value_payload_high_low_summary.get('best_low_feature_set', '')}/"
                        f"{micro_mixed_value_payload_high_low_summary.get('best_low_correct_slots', '0')}"
                        f"_{micro_mixed_value_payload_high_low_summary.get('best_low_false_slots', '0')}",
                        f"mixed_value_high_low_unknown="
                        f"{micro_mixed_value_payload_high_low_summary.get('best_low_unknown_slots', '0')}",
                    ],
                )
                next_action = mixed_value_payload_high_low_action(micro_mixed_value_payload_high_low_summary)
            if micro_mixed_value_payload_external_source_combo_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_external_best_byte="
                        f"{micro_mixed_value_payload_external_source_combo_summary.get('best_byte_feature_set', '')}/"
                        f"{micro_mixed_value_payload_external_source_combo_summary.get('best_byte_correct_slots', '0')}"
                        f"_{micro_mixed_value_payload_external_source_combo_summary.get('best_byte_false_slots', '0')}",
                        f"mixed_value_external_false_free_byte="
                        f"{micro_mixed_value_payload_external_source_combo_summary.get('best_false_free_byte_slots', '0')}",
                        f"mixed_value_external_false_free_high="
                        f"{micro_mixed_value_payload_external_source_combo_summary.get('best_false_free_high_slots', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_external_byte_unknown="
                        f"{micro_mixed_value_payload_external_source_combo_summary.get('best_false_free_byte_unknown_slots', '0')}",
                        f"mixed_value_external_high_unknown="
                        f"{micro_mixed_value_payload_external_source_combo_summary.get('best_false_free_high_unknown_slots', '0')}",
                    ],
                )
                next_action = mixed_value_external_source_combo_action(
                    micro_mixed_value_payload_external_source_combo_summary
                )
            if micro_mixed_value_payload_external_high_low_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_external_high_low_slots="
                        f"{micro_mixed_value_payload_external_high_low_summary.get('selected_high_slots', '0')}",
                        f"mixed_value_external_high_low_values="
                        f"{micro_mixed_value_payload_external_high_low_summary.get('selected_low_values', '')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_external_high_low_best="
                        f"{micro_mixed_value_payload_external_high_low_summary.get('best_low_feature_set', '')}/"
                        f"{micro_mixed_value_payload_external_high_low_summary.get('best_low_correct_slots', '0')}"
                        f"_{micro_mixed_value_payload_external_high_low_summary.get('best_low_false_slots', '0')}",
                        f"mixed_value_external_high_low_false_free="
                        f"{micro_mixed_value_payload_external_high_low_summary.get('false_free_low_slots', '0')}",
                        f"mixed_value_external_high_low_promotion_ready="
                        f"{micro_mixed_value_payload_external_high_low_summary.get('promotion_ready_bytes', '0')}",
                    ],
                )
                next_action = mixed_value_external_high_low_action(
                    micro_mixed_value_payload_external_high_low_summary
                )
            if micro_mixed_value_payload_state_external_combo_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_state_external_best_byte="
                        f"{micro_mixed_value_payload_state_external_combo_summary.get('best_byte_feature_set', '')}/"
                        f"{micro_mixed_value_payload_state_external_combo_summary.get('best_byte_correct_slots', '0')}"
                        f"_{micro_mixed_value_payload_state_external_combo_summary.get('best_byte_false_slots', '0')}",
                        f"mixed_value_state_external_best_high="
                        f"{micro_mixed_value_payload_state_external_combo_summary.get('best_high_feature_set', '')}/"
                        f"{micro_mixed_value_payload_state_external_combo_summary.get('best_high_correct_slots', '0')}"
                        f"_{micro_mixed_value_payload_state_external_combo_summary.get('best_high_false_slots', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_state_external_false_free_byte="
                        f"{micro_mixed_value_payload_state_external_combo_summary.get('best_false_free_byte_slots', '0')}",
                        f"mixed_value_state_external_promotion_ready="
                        f"{micro_mixed_value_payload_state_external_combo_summary.get('promotion_ready_bytes', '0')}",
                    ],
                )
                next_action = mixed_value_state_external_combo_action(
                    micro_mixed_value_payload_state_external_combo_summary
                )
            if micro_mixed_value_payload_sequence_state_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_sequence_high="
                        f"{micro_mixed_value_payload_sequence_state_summary.get('best_false_free_high_slots', '0')}",
                        f"mixed_value_sequence_low_candidates="
                        f"{micro_mixed_value_payload_sequence_state_summary.get('promotion_candidate_bytes', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_sequence_best_byte="
                        f"{micro_mixed_value_payload_sequence_state_summary.get('best_byte_feature_set', '')}/"
                        f"{micro_mixed_value_payload_sequence_state_summary.get('best_byte_correct_slots', '0')}"
                        f"_{micro_mixed_value_payload_sequence_state_summary.get('best_byte_false_slots', '0')}",
                        f"mixed_value_sequence_promotion_ready="
                        f"{micro_mixed_value_payload_sequence_state_summary.get('promotion_ready_bytes', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_state_action(micro_mixed_value_payload_sequence_state_summary)
            if micro_mixed_value_payload_sequence_candidate_review_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_sequence_review_candidates="
                        f"{micro_mixed_value_payload_sequence_candidate_review_summary.get('candidate_bytes', '0')}",
                        f"mixed_value_sequence_review_oracle_correct="
                        f"{micro_mixed_value_payload_sequence_candidate_review_summary.get('correct_bytes', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_sequence_review_known_prereq="
                        f"{micro_mixed_value_payload_sequence_candidate_review_summary.get('known_prerequisite_bytes', '0')}/"
                        f"{micro_mixed_value_payload_sequence_candidate_review_summary.get('prerequisite_bytes', '0')}",
                        f"mixed_value_sequence_review_oracle_dependency="
                        f"{micro_mixed_value_payload_sequence_candidate_review_summary.get('oracle_dependency_bytes', '0')}",
                        f"mixed_value_sequence_review_promotion_ready="
                        f"{micro_mixed_value_payload_sequence_candidate_review_summary.get('promotion_ready_bytes', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_candidate_review_action(
                    micro_mixed_value_payload_sequence_candidate_review_summary
                )
            if micro_mixed_value_payload_prefix_bootstrap_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_prefix_union="
                        f"{micro_mixed_value_payload_prefix_bootstrap_summary.get('union_candidate_slots', '0')}",
                        f"mixed_value_prefix_sequence_unlock="
                        f"{micro_mixed_value_payload_prefix_bootstrap_summary.get('sequence_candidate_unlocked_bytes', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prefix_conflicts="
                        f"{micro_mixed_value_payload_prefix_bootstrap_summary.get('union_conflict_slots', '0')}",
                        f"mixed_value_prefix_promotion_ready="
                        f"{micro_mixed_value_payload_prefix_bootstrap_summary.get('promotion_ready_bytes', '0')}",
                    ],
                )
                next_action = mixed_value_prefix_bootstrap_action(micro_mixed_value_payload_prefix_bootstrap_summary)
            if micro_mixed_value_payload_prefix_sequence_replay_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_prefix_sequence_added="
                        f"{micro_mixed_value_payload_prefix_sequence_replay_summary.get('total_added_bytes', '0')}",
                        f"mixed_value_prefix_sequence_guarded="
                        f"{micro_mixed_value_payload_prefix_sequence_replay_summary.get('guarded_replay_bytes', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prefix_sequence_false="
                        f"{micro_mixed_value_payload_prefix_sequence_replay_summary.get('total_false_bytes', '0')}",
                        f"mixed_value_prefix_sequence_promotion_ready="
                        f"{micro_mixed_value_payload_prefix_sequence_replay_summary.get('promotion_ready_bytes', '0')}",
                    ],
                )
                next_action = mixed_value_prefix_sequence_replay_action(
                    micro_mixed_value_payload_prefix_sequence_replay_summary
                )
            if micro_mixed_value_payload_prefix_sequence_promoted_replay_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_prefix_sequence_promoted="
                        f"{micro_mixed_value_payload_prefix_sequence_promoted_replay_summary.get('mixed_value_added_bytes', '0')}",
                        f"mixed_value_prefix_sequence_clean_total="
                        f"{micro_mixed_value_payload_prefix_sequence_promoted_replay_summary.get('total_clean_bytes', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prefix_sequence_promoted_false="
                        f"{micro_mixed_value_payload_prefix_sequence_promoted_replay_summary.get('mixed_value_false_bytes', '0')}",
                        f"mixed_value_prefix_sequence_promoted_issues="
                        f"{micro_mixed_value_payload_prefix_sequence_promoted_replay_summary.get('issue_rows', '0')}",
                    ],
                )
                next_action = mixed_value_prefix_sequence_promoted_replay_action(
                    micro_mixed_value_payload_prefix_sequence_promoted_replay_summary
                )
            if micro_mixed_value_payload_sequence_promoted_generalization_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_sequence_replayable_unknown="
                        f"{micro_mixed_value_payload_sequence_promoted_generalization_summary.get('replayable_unknown_slots', '0')}",
                        f"mixed_value_sequence_target_known="
                        f"{micro_mixed_value_payload_sequence_promoted_generalization_summary.get('target_known_slots', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_sequence_generalization_false_free="
                        f"{micro_mixed_value_payload_sequence_promoted_generalization_summary.get('false_free_feature_sets', '0')}",
                        f"mixed_value_sequence_generalization_best="
                        f"{micro_mixed_value_payload_sequence_promoted_generalization_summary.get('best_correct_slots', '0')}/"
                        f"{micro_mixed_value_payload_sequence_promoted_generalization_summary.get('best_false_slots', '0')}",
                        f"mixed_value_sequence_blocked="
                        f"{micro_mixed_value_payload_sequence_promoted_generalization_summary.get('blocked_prerequisite_slots', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_promoted_generalization_action(
                    micro_mixed_value_payload_sequence_promoted_generalization_summary
                )
            if micro_mixed_value_payload_sequence_low_split_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_low_split_false_free="
                        f"{micro_mixed_value_payload_sequence_low_split_summary.get('false_free_split_sets', '0')}",
                        f"mixed_value_low_split_candidates="
                        f"{micro_mixed_value_payload_sequence_low_split_summary.get('promotion_candidate_bytes', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_low_split_best_unknown="
                        f"{micro_mixed_value_payload_sequence_low_split_summary.get('best_false_free_split_unknown_slots', '0')}",
                        f"mixed_value_low_split_conflicted="
                        f"{micro_mixed_value_payload_sequence_low_split_summary.get('best_conflicted_correct_slots', '0')}/"
                        f"{micro_mixed_value_payload_sequence_low_split_summary.get('best_conflicted_false_slots', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_low_split_action(
                    micro_mixed_value_payload_sequence_low_split_summary
                )
            if micro_mixed_value_payload_sequence_low_split_promoted_replay_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_low_split_promoted="
                        f"{micro_mixed_value_payload_sequence_low_split_promoted_replay_summary.get('low_split_added_bytes', '0')}",
                        f"mixed_value_low_split_clean_total="
                        f"{micro_mixed_value_payload_sequence_low_split_promoted_replay_summary.get('total_clean_bytes', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_low_split_false="
                        f"{micro_mixed_value_payload_sequence_low_split_promoted_replay_summary.get('low_split_false_bytes', '0')}",
                        f"mixed_value_low_split_issues="
                        f"{micro_mixed_value_payload_sequence_low_split_promoted_replay_summary.get('issue_rows', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_low_split_promoted_replay_action(
                    micro_mixed_value_payload_sequence_low_split_promoted_replay_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_expansion_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_prereq_candidates="
                        f"{micro_mixed_value_payload_sequence_prerequisite_expansion_summary.get('union_candidate_slots', '0')}",
                        f"mixed_value_prereq_unlocks="
                        f"{micro_mixed_value_payload_sequence_prerequisite_expansion_summary.get('unlocked_sequence_slots', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prereq_unknown="
                        f"{micro_mixed_value_payload_sequence_prerequisite_expansion_summary.get('unknown_prerequisite_slots', '0')}",
                        f"mixed_value_prereq_conflicts="
                        f"{micro_mixed_value_payload_sequence_prerequisite_expansion_summary.get('union_conflict_slots', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_expansion_action(
                    micro_mixed_value_payload_sequence_prerequisite_expansion_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_prereq_promoted="
                        f"{micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay_summary.get('prerequisite_added_bytes', '0')}",
                        f"mixed_value_prereq_clean_total="
                        f"{micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay_summary.get('total_clean_bytes', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prereq_false="
                        f"{micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay_summary.get('prerequisite_false_bytes', '0')}",
                        f"mixed_value_prereq_issues="
                        f"{micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay_summary.get('issue_rows', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_expansion_promoted_action(
                    micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_low_split_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_prereq_low_split_false_free="
                        f"{micro_mixed_value_payload_sequence_prerequisite_low_split_summary.get('false_free_split_sets', '0')}",
                        f"mixed_value_prereq_low_split_candidates="
                        f"{micro_mixed_value_payload_sequence_prerequisite_low_split_summary.get('promotion_candidate_bytes', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prereq_low_split_unknown="
                        f"{micro_mixed_value_payload_sequence_prerequisite_low_split_summary.get('best_false_free_split_unknown_slots', '0')}",
                        f"mixed_value_prereq_low_split_conflicted="
                        f"{micro_mixed_value_payload_sequence_prerequisite_low_split_summary.get('best_conflicted_correct_slots', '0')}/"
                        f"{micro_mixed_value_payload_sequence_prerequisite_low_split_summary.get('best_conflicted_false_slots', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_low_split_action(
                    micro_mixed_value_payload_sequence_prerequisite_low_split_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_prereq_low_split_promoted="
                        f"{micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay_summary.get('low_split_added_bytes', '0')}",
                        f"mixed_value_prereq_low_split_clean_total="
                        f"{micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay_summary.get('total_clean_bytes', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prereq_low_split_false="
                        f"{micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay_summary.get('low_split_false_bytes', '0')}",
                        f"mixed_value_prereq_low_split_issues="
                        f"{micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay_summary.get('issue_rows', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_low_split_promoted_action(
                    micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_low_split_generalization_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_prereq_low_split_gen_known="
                        f"{micro_mixed_value_payload_sequence_prerequisite_low_split_generalization_summary.get('target_known_slots', '0')}",
                        f"mixed_value_prereq_low_split_gen_replayable="
                        f"{micro_mixed_value_payload_sequence_prerequisite_low_split_generalization_summary.get('replayable_unknown_slots', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prereq_low_split_gen_false_free="
                        f"{micro_mixed_value_payload_sequence_prerequisite_low_split_generalization_summary.get('false_free_feature_sets', '0')}",
                        f"mixed_value_prereq_low_split_gen_best="
                        f"{micro_mixed_value_payload_sequence_prerequisite_low_split_generalization_summary.get('best_correct_slots', '0')}/"
                        f"{micro_mixed_value_payload_sequence_prerequisite_low_split_generalization_summary.get('best_false_slots', '0')}",
                        f"mixed_value_prereq_low_split_gen_blocked="
                        f"{micro_mixed_value_payload_sequence_prerequisite_low_split_generalization_summary.get('blocked_prerequisite_slots', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_low_split_generalization_action(
                    micro_mixed_value_payload_sequence_prerequisite_low_split_generalization_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_second_low_split_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_prereq_second_low_split_features="
                        f"{micro_mixed_value_payload_sequence_prerequisite_second_low_split_summary.get('feature_sets', '0')}",
                        f"mixed_value_prereq_second_low_split_replayable="
                        f"{micro_mixed_value_payload_sequence_prerequisite_second_low_split_summary.get('replayable_unknown_slots', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prereq_second_low_split_false_free="
                        f"{micro_mixed_value_payload_sequence_prerequisite_second_low_split_summary.get('false_free_split_sets', '0')}",
                        f"mixed_value_prereq_second_low_split_candidates="
                        f"{micro_mixed_value_payload_sequence_prerequisite_second_low_split_summary.get('promotion_candidate_bytes', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_second_low_split_action(
                    micro_mixed_value_payload_sequence_prerequisite_second_low_split_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_second_expansion_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_prereq_second_expansion_features="
                        f"{micro_mixed_value_payload_sequence_prerequisite_second_expansion_summary.get('feature_sets', '0')}",
                        f"mixed_value_prereq_second_expansion_blocked="
                        f"{micro_mixed_value_payload_sequence_prerequisite_second_expansion_summary.get('blocked_sequence_slots', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prereq_second_expansion_unknown="
                        f"{micro_mixed_value_payload_sequence_prerequisite_second_expansion_summary.get('unknown_prerequisite_slots', '0')}",
                        f"mixed_value_prereq_second_expansion_candidates="
                        f"{micro_mixed_value_payload_sequence_prerequisite_second_expansion_summary.get('promotion_candidate_bytes', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_second_expansion_action(
                    micro_mixed_value_payload_sequence_prerequisite_second_expansion_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_prereq_corpus_candidates="
                        f"{micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_summary.get('union_candidate_slots', '0')}",
                        f"mixed_value_prereq_corpus_unlocks="
                        f"{micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_summary.get('unlocked_sequence_slots', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prereq_corpus_unknown="
                        f"{micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_summary.get('unknown_prerequisite_slots', '0')}",
                        f"mixed_value_prereq_corpus_conflicts="
                        f"{micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_summary.get('union_conflict_slots', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_corpus_expansion_action(
                    micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_promoted_replay_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_prereq_corpus_promoted="
                        f"{micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_promoted_replay_summary.get('prerequisite_added_bytes', '0')}",
                        f"mixed_value_prereq_corpus_clean_total="
                        f"{micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_promoted_replay_summary.get('total_clean_bytes', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prereq_corpus_false="
                        f"{micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_promoted_replay_summary.get('prerequisite_false_bytes', '0')}",
                        f"mixed_value_prereq_corpus_issues="
                        f"{micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_promoted_replay_summary.get('issue_rows', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_corpus_expansion_promoted_action(
                    micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_promoted_replay_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_prereq_corpus_low_split_false_free="
                        f"{micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_summary.get('false_free_split_sets', '0')}",
                        f"mixed_value_prereq_corpus_low_split_candidates="
                        f"{micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_summary.get('promotion_candidate_bytes', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prereq_corpus_low_split_unknown="
                        f"{micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_summary.get('best_false_free_split_unknown_slots', '0')}",
                        f"mixed_value_prereq_corpus_low_split_conflicted="
                        f"{micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_summary.get('best_conflicted_correct_slots', '0')}/"
                        f"{micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_summary.get('best_conflicted_false_slots', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_corpus_low_split_action(
                    micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_promoted_replay_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_prereq_corpus_low_split_promoted="
                        f"{micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_promoted_replay_summary.get('low_split_added_bytes', '0')}",
                        f"mixed_value_prereq_corpus_low_split_clean_total="
                        f"{micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_promoted_replay_summary.get('total_clean_bytes', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prereq_corpus_low_split_false="
                        f"{micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_promoted_replay_summary.get('low_split_false_bytes', '0')}",
                        f"mixed_value_prereq_corpus_low_split_issues="
                        f"{micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_promoted_replay_summary.get('issue_rows', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_corpus_low_split_promoted_action(
                    micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_promoted_replay_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_prereq_corpus_second_low_split_false_free="
                        f"{micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_summary.get('false_free_split_sets', '0')}",
                        f"mixed_value_prereq_corpus_second_low_split_candidates="
                        f"{micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_summary.get('promotion_candidate_bytes', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prereq_corpus_second_low_split_unknown="
                        f"{micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_summary.get('best_false_free_split_unknown_slots', '0')}",
                        f"mixed_value_prereq_corpus_second_low_split_conflicted="
                        f"{micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_summary.get('best_conflicted_correct_slots', '0')}/"
                        f"{micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_summary.get('best_conflicted_false_slots', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_corpus_second_low_split_action(
                    micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_promoted_replay_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_prereq_corpus_second_low_split_promoted="
                        f"{micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_promoted_replay_summary.get('low_split_added_bytes', '0')}",
                        f"mixed_value_prereq_corpus_second_low_split_clean_total="
                        f"{micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_promoted_replay_summary.get('total_clean_bytes', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prereq_corpus_second_low_split_false="
                        f"{micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_promoted_replay_summary.get('low_split_false_bytes', '0')}",
                        f"mixed_value_prereq_corpus_second_low_split_issues="
                        f"{micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_promoted_replay_summary.get('issue_rows', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_corpus_second_low_split_promoted_action(
                    micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_promoted_replay_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_prereq_adjacent_promoted="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay_summary.get('prerequisite_added_bytes', '0')}",
                        f"mixed_value_prereq_adjacent_clean_total="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay_summary.get('total_clean_bytes', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prereq_adjacent_false="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay_summary.get('prerequisite_false_bytes', '0')}",
                        f"mixed_value_prereq_adjacent_issues="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay_summary.get('issue_rows', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_adjacent_known_promoted_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_generalization_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_prereq_adjacent_gen_known="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_generalization_summary.get('target_known_slots', '0')}",
                        f"mixed_value_prereq_adjacent_gen_replayable="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_generalization_summary.get('replayable_unknown_slots', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prereq_adjacent_gen_false_free="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_generalization_summary.get('false_free_feature_sets', '0')}",
                        f"mixed_value_prereq_adjacent_gen_blocked="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_generalization_summary.get('blocked_prerequisite_slots', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_adjacent_known_generalization_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_generalization_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_low_split_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_prereq_adjacent_low_split_features="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_low_split_summary.get('feature_sets', '0')}",
                        f"mixed_value_prereq_adjacent_low_split_replayable="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_low_split_summary.get('replayable_unknown_slots', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prereq_adjacent_low_split_false_free="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_low_split_summary.get('false_free_split_sets', '0')}",
                        f"mixed_value_prereq_adjacent_low_split_candidates="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_low_split_summary.get('promotion_candidate_bytes', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_adjacent_known_low_split_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_low_split_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_corpus_expansion_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_prereq_adjacent_corpus_features="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_corpus_expansion_summary.get('feature_sets', '0')}",
                        f"mixed_value_prereq_adjacent_corpus_unknown="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_corpus_expansion_summary.get('unknown_prerequisite_slots', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prereq_adjacent_corpus_false_free="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_corpus_expansion_summary.get('false_free_rule_sets', '0')}",
                        f"mixed_value_prereq_adjacent_corpus_candidates="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_corpus_expansion_summary.get('promotion_candidate_bytes', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_adjacent_known_corpus_expansion_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_corpus_expansion_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_fourth_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_prereq_adjacent_fourth_unknown="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_fourth_summary.get('unknown_prerequisite_slots', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prereq_adjacent_fourth_candidates="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_fourth_summary.get('promotion_candidate_bytes', '0')}",
                        f"mixed_value_prereq_adjacent_fourth_false="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_fourth_summary.get('adjacent_false_slots', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_adjacent_known_fourth_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_fourth_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_prereq_adjacent_transform_false_free="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_summary.get('false_free_transform_sets', '0')}",
                        f"mixed_value_prereq_adjacent_transform_candidates="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_summary.get('promotion_candidate_bytes', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prereq_adjacent_transform_unknown="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_summary.get('replayable_unknown_slots', '0')}",
                        f"mixed_value_prereq_adjacent_transform_issues="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_summary.get('issue_rows', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_adjacent_known_transform_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_prereq_adjacent_transform_promoted="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay_summary.get('low_split_added_bytes', '0')}",
                        f"mixed_value_prereq_adjacent_transform_clean_total="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay_summary.get('total_clean_bytes', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prereq_adjacent_transform_false="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay_summary.get('low_split_false_bytes', '0')}",
                        f"mixed_value_prereq_adjacent_transform_promoted_issues="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay_summary.get('issue_rows', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_adjacent_known_transform_promoted_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_generalization_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_prereq_adjacent_transform_gen_known="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_generalization_summary.get('target_known_slots', '0')}",
                        f"mixed_value_prereq_adjacent_transform_gen_replayable="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_generalization_summary.get('replayable_unknown_slots', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prereq_adjacent_transform_gen_false_free="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_generalization_summary.get('false_free_feature_sets', '0')}",
                        f"mixed_value_prereq_adjacent_transform_gen_blocked="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_generalization_summary.get('blocked_prerequisite_slots', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_adjacent_known_transform_generalization_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_generalization_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_second_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_prereq_adjacent_transform_second_false_free="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_second_summary.get('false_free_transform_sets', '0')}",
                        f"mixed_value_prereq_adjacent_transform_second_candidates="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_second_summary.get('promotion_candidate_bytes', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prereq_adjacent_transform_second_unknown="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_second_summary.get('replayable_unknown_slots', '0')}",
                        f"mixed_value_prereq_adjacent_transform_second_issues="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_second_summary.get('issue_rows', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_adjacent_known_transform_second_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_second_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_low_split_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_prereq_adjacent_transform_low_split_features="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_low_split_summary.get('feature_sets', '0')}",
                        f"mixed_value_prereq_adjacent_transform_low_split_replayable="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_low_split_summary.get('replayable_unknown_slots', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prereq_adjacent_transform_low_split_false_free="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_low_split_summary.get('false_free_split_sets', '0')}",
                        f"mixed_value_prereq_adjacent_transform_low_split_candidates="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_low_split_summary.get('promotion_candidate_bytes', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_adjacent_known_transform_low_split_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_low_split_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_expansion_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_prereq_adjacent_transform_corpus_features="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_expansion_summary.get('feature_sets', '0')}",
                        f"mixed_value_prereq_adjacent_transform_corpus_unknown="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_expansion_summary.get('unknown_prerequisite_slots', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prereq_adjacent_transform_corpus_false_free="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_expansion_summary.get('false_free_rule_sets', '0')}",
                        f"mixed_value_prereq_adjacent_transform_corpus_candidates="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_expansion_summary.get('promotion_candidate_bytes', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_adjacent_known_transform_corpus_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_expansion_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_adjacent_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_prereq_adjacent_transform_adjacent_unknown="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_adjacent_summary.get('unknown_prerequisite_slots', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prereq_adjacent_transform_adjacent_candidates="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_adjacent_summary.get('promotion_candidate_bytes', '0')}",
                        f"mixed_value_prereq_adjacent_transform_adjacent_false="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_adjacent_summary.get('adjacent_false_slots', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_adjacent_known_transform_adjacent_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_adjacent_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_prereq_adjacent_transform_corpus_promoted_total="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay_summary.get('total_clean_bytes', '0')}",
                        f"mixed_value_prereq_adjacent_transform_corpus_last_added="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay_summary.get('low_split_added_bytes', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prereq_adjacent_transform_corpus_false="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay_summary.get('low_split_false_bytes', '0')}",
                        f"mixed_value_prereq_adjacent_transform_corpus_issues="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay_summary.get('issue_rows', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_adjacent_known_transform_promoted_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_generalization_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_prereq_adjacent_transform_corpus_gen_known="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_generalization_summary.get('target_known_slots', '0')}",
                        f"mixed_value_prereq_adjacent_transform_corpus_gen_replayable="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_generalization_summary.get('replayable_unknown_slots', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_adjacent_known_transform_generalization_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_generalization_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_fourth_summary:
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prereq_adjacent_transform_corpus_fourth_false_free="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_fourth_summary.get('false_free_transform_sets', '0')}",
                        f"mixed_value_prereq_adjacent_transform_corpus_fourth_candidates="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_fourth_summary.get('promotion_candidate_bytes', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_adjacent_known_transform_second_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_fourth_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_low_split_summary:
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prereq_adjacent_transform_corpus_low_split_false_free="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_low_split_summary.get('false_free_split_sets', '0')}",
                        f"mixed_value_prereq_adjacent_transform_corpus_low_split_candidates="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_low_split_summary.get('promotion_candidate_bytes', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_adjacent_known_transform_low_split_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_low_split_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_corpus_expansion_summary:
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prereq_adjacent_transform_corpus_final_false_free="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_corpus_expansion_summary.get('false_free_rule_sets', '0')}",
                        f"mixed_value_prereq_adjacent_transform_corpus_final_candidates="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_corpus_expansion_summary.get('promotion_candidate_bytes', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_adjacent_known_transform_corpus_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_corpus_expansion_summary
                )
            if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_adjacent_summary:
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_prereq_adjacent_transform_corpus_adjacent_candidates="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_adjacent_summary.get('promotion_candidate_bytes', '0')}",
                        f"mixed_value_prereq_adjacent_transform_corpus_adjacent_false="
                        f"{micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_adjacent_summary.get('adjacent_false_slots', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_prerequisite_adjacent_known_transform_adjacent_action(
                    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_adjacent_summary
                )
            if micro_mixed_value_payload_sequence_low_copy_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_sequence_low_copy_false_free="
                        f"{micro_mixed_value_payload_sequence_low_copy_summary.get('false_free_copy_sets', '0')}",
                        f"mixed_value_sequence_low_copy_candidates="
                        f"{micro_mixed_value_payload_sequence_low_copy_summary.get('promotion_candidate_bytes', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_low_copy_action(micro_mixed_value_payload_sequence_low_copy_summary)
            if micro_mixed_value_payload_sequence_low_copy_promoted_replay_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_sequence_low_copy_promoted="
                        f"{micro_mixed_value_payload_sequence_low_copy_promoted_replay_summary.get('low_split_added_bytes', '0')}",
                        f"mixed_value_sequence_low_copy_clean_total="
                        f"{micro_mixed_value_payload_sequence_low_copy_promoted_replay_summary.get('total_clean_bytes', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_sequence_low_copy_false="
                        f"{micro_mixed_value_payload_sequence_low_copy_promoted_replay_summary.get('low_split_false_bytes', '0')}",
                        f"mixed_value_sequence_low_copy_promoted_issues="
                        f"{micro_mixed_value_payload_sequence_low_copy_promoted_replay_summary.get('issue_rows', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_low_copy_promoted_action(
                    micro_mixed_value_payload_sequence_low_copy_promoted_replay_summary
                )
            if micro_mixed_value_payload_sequence_low_copy_generalization_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"mixed_value_sequence_low_copy_gen_known="
                        f"{micro_mixed_value_payload_sequence_low_copy_generalization_summary.get('target_known_slots', '0')}",
                        f"mixed_value_sequence_low_copy_gen_replayable="
                        f"{micro_mixed_value_payload_sequence_low_copy_generalization_summary.get('replayable_unknown_slots', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_sequence_low_copy_gen_blocked="
                        f"{micro_mixed_value_payload_sequence_low_copy_generalization_summary.get('blocked_prerequisite_slots', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_low_copy_generalization_action(
                    micro_mixed_value_payload_sequence_low_copy_generalization_summary
                )
            if micro_mixed_value_payload_sequence_low_copy_second_summary:
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_sequence_low_copy_second_candidates="
                        f"{micro_mixed_value_payload_sequence_low_copy_second_summary.get('promotion_candidate_bytes', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_low_copy_second_action(
                    micro_mixed_value_payload_sequence_low_copy_second_summary
                )
            if micro_mixed_value_payload_sequence_low_copy_low_split_summary:
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_sequence_low_copy_low_split_candidates="
                        f"{micro_mixed_value_payload_sequence_low_copy_low_split_summary.get('promotion_candidate_bytes', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_low_copy_low_split_action(
                    micro_mixed_value_payload_sequence_low_copy_low_split_summary
                )
            if micro_mixed_value_payload_sequence_low_copy_corpus_expansion_summary:
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_sequence_low_copy_corpus_candidates="
                        f"{micro_mixed_value_payload_sequence_low_copy_corpus_expansion_summary.get('promotion_candidate_bytes', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_low_copy_corpus_action(
                    micro_mixed_value_payload_sequence_low_copy_corpus_expansion_summary
                )
            if micro_mixed_value_payload_sequence_low_copy_adjacent_summary:
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"mixed_value_sequence_low_copy_adjacent_candidates="
                        f"{micro_mixed_value_payload_sequence_low_copy_adjacent_summary.get('promotion_candidate_bytes', '0')}",
                        f"mixed_value_sequence_low_copy_adjacent_false="
                        f"{micro_mixed_value_payload_sequence_low_copy_adjacent_summary.get('adjacent_false_slots', '0')}",
                    ],
                )
                next_action = mixed_value_sequence_low_copy_adjacent_action(
                    micro_mixed_value_payload_sequence_low_copy_adjacent_summary
                )
            if micro_mixed_value_payload_state_opcode_summary and jump_token_payload_state_opcode_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"jump_token_state_control_anchors="
                        f"{jump_token_payload_state_opcode_summary.get('control_anchor_rows', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"jump_token_state_best_byte="
                        f"{jump_token_payload_state_opcode_summary.get('best_byte_correct_slots', '0')}/"
                        f"{jump_token_payload_state_opcode_summary.get('best_byte_false_slots', '0')}",
                        f"jump_token_state_rejected="
                        f"{jump_token_payload_state_opcode_summary.get('source_state_rejected', '0')}",
                    ],
                )
                next_action = (
                    "extend state/opcode search to gradient payloads; mixed-value and jump-token "
                    "source-state contexts are rejected"
                )
            if (
                gradient_payload_state_opcode_summary
                and micro_mixed_value_payload_state_opcode_summary
                and jump_token_payload_state_opcode_summary
            ):
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"gradient_state_control_anchors="
                        f"{gradient_payload_state_opcode_summary.get('control_anchor_rows', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"gradient_state_best_byte="
                        f"{gradient_payload_state_opcode_summary.get('best_byte_correct_slots', '0')}/"
                        f"{gradient_payload_state_opcode_summary.get('best_byte_false_slots', '0')}",
                        f"gradient_state_rejected="
                        f"{gradient_payload_state_opcode_summary.get('source_state_rejected', '0')}",
                    ],
                )
                next_action = (
                    "derive higher-order gradient opcode grammar; local source-state contexts are rejected "
                    "for mixed-value, jump-token and gradient payloads"
                )
            if (
                gradient_macro_opcode_summary
                and gradient_payload_state_opcode_summary
                and micro_mixed_value_payload_state_opcode_summary
                and jump_token_payload_state_opcode_summary
            ):
                best_target = gradient_macro_opcode_summary.get("best_target_kind", "")
                best_selector = gradient_macro_opcode_summary.get("best_selector_family", "")
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"gradient_macro_best={best_target}/{best_selector}",
                        f"gradient_macro_deterministic="
                        f"{gradient_macro_opcode_summary.get('best_repeated_deterministic_bytes', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"gradient_macro_conflicted="
                        f"{gradient_macro_opcode_summary.get('best_conflicted_bytes', '0')}",
                        f"gradient_macro_exact_payload="
                        f"{gradient_macro_opcode_summary.get('exact_payload_repeated_evidence_bytes', '0')}",
                    ],
                )
                next_action = (
                    "split gradient macro-opcode selectors by dominant-delta conflicts; "
                    "local state remains rejected"
                )
            if (
                gradient_macro_conflict_split_summary
                and gradient_macro_opcode_summary
                and gradient_payload_state_opcode_summary
                and micro_mixed_value_payload_state_opcode_summary
                and jump_token_payload_state_opcode_summary
            ):
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"gradient_macro_split_best="
                        f"{gradient_macro_conflict_split_summary.get('best_split_family', '')}",
                        f"gradient_macro_split_deterministic="
                        f"{gradient_macro_conflict_split_summary.get('best_split_deterministic_bytes', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"gradient_macro_split_remaining="
                        f"{gradient_macro_conflict_split_summary.get('best_split_conflicted_bytes', '0')}",
                        f"gradient_macro_split_low_conflict_singleton="
                        f"{gradient_macro_conflict_split_summary.get('low_conflict_singleton_bytes', '0')}",
                    ],
                )
                next_action = (
                    "resolve residual gradient control-anchor macro conflict; local state remains rejected"
                )
            if (
                gradient_macro_residual_state_summary
                and gradient_macro_conflict_split_summary
                and gradient_macro_opcode_summary
                and gradient_payload_state_opcode_summary
                and micro_mixed_value_payload_state_opcode_summary
                and jump_token_payload_state_opcode_summary
            ):
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"gradient_residual_state_best="
                        f"{gradient_macro_residual_state_summary.get('best_state_selector_family', '')}",
                        f"gradient_residual_state_deterministic="
                        f"{gradient_macro_residual_state_summary.get('best_state_deterministic_bytes', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"gradient_residual_source_conflicted="
                        f"{gradient_macro_residual_state_summary.get('best_source_conflicted_bytes', '0')}",
                        f"gradient_residual_state_singleton="
                        f"{gradient_macro_residual_state_summary.get('best_state_singleton_bytes', '0')}",
                    ],
                )
                next_action = (
                    "expand residual gradient op-index phase bins; local source windows remain conflicted"
                )
            if (
                gradient_macro_phase_summary
                and gradient_macro_residual_state_summary
                and gradient_macro_conflict_split_summary
                and gradient_macro_opcode_summary
                and gradient_payload_state_opcode_summary
                and micro_mixed_value_payload_state_opcode_summary
                and jump_token_payload_state_opcode_summary
            ):
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"gradient_phase_best="
                        f"{gradient_macro_phase_summary.get('best_coarse_target_kind', '')}/"
                        f"{gradient_macro_phase_summary.get('best_coarse_selector_family', '')}",
                        f"gradient_phase_deterministic="
                        f"{gradient_macro_phase_summary.get('best_coarse_deterministic_bytes', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"gradient_phase_conflicted="
                        f"{gradient_macro_phase_summary.get('best_coarse_conflicted_bytes', '0')}",
                        f"gradient_phase_payload_deterministic="
                        f"{gradient_macro_phase_summary.get('best_payload_deterministic_bytes', '0')}",
                    ],
                )
                next_action = (
                    "split gradient op-index phase conflicts; local source windows remain conflicted"
                )
            if (
                gradient_macro_phase_conflict_split_summary
                and gradient_macro_phase_summary
                and gradient_macro_residual_state_summary
                and gradient_macro_conflict_split_summary
                and gradient_macro_opcode_summary
                and gradient_payload_state_opcode_summary
                and micro_mixed_value_payload_state_opcode_summary
                and jump_token_payload_state_opcode_summary
            ):
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"gradient_phase_split_best="
                        f"{gradient_macro_phase_conflict_split_summary.get('best_split_family', '')}",
                        f"gradient_phase_split_deterministic="
                        f"{gradient_macro_phase_conflict_split_summary.get('best_split_deterministic_bytes', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"gradient_phase_split_singleton="
                        f"{gradient_macro_phase_conflict_split_summary.get('best_split_singleton_bytes', '0')}",
                        f"gradient_phase_split_promotion_ready="
                        f"{gradient_macro_phase_conflict_split_summary.get('promotion_ready_bytes', '0')}",
                    ],
                )
                next_action = (
                    "broaden gradient phase grammar; op-index split collapses to singletons"
                )
            if (
                gradient_macro_phase_sequence_summary
                and gradient_macro_phase_conflict_split_summary
                and gradient_macro_phase_summary
                and gradient_macro_residual_state_summary
                and gradient_macro_conflict_split_summary
                and gradient_macro_opcode_summary
                and gradient_payload_state_opcode_summary
                and micro_mixed_value_payload_state_opcode_summary
                and jump_token_payload_state_opcode_summary
            ):
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"gradient_phase_sequence_best="
                        f"{gradient_macro_phase_sequence_summary.get('best_sequence_target_kind', '')}/"
                        f"{gradient_macro_phase_sequence_summary.get('best_sequence_selector_family', '')}",
                        f"gradient_phase_sequence_deterministic="
                        f"{gradient_macro_phase_sequence_summary.get('best_sequence_deterministic_bytes', '0')}",
                        f"gradient_phase_sequence_low_conflict="
                        f"{gradient_macro_phase_sequence_summary.get('low_conflict_sequence_selector_family', '')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"gradient_phase_sequence_conflicted="
                        f"{gradient_macro_phase_sequence_summary.get('best_sequence_conflicted_bytes', '0')}",
                        f"gradient_phase_sequence_low_conflict_singleton="
                        f"{gradient_macro_phase_sequence_summary.get('low_conflict_sequence_singleton_bytes', '0')}",
                        f"gradient_phase_sequence_promotion_ready="
                        f"{gradient_macro_phase_sequence_summary.get('promotion_ready_bytes', '0')}",
                    ],
                )
                next_action = (
                    "probe fixture/op transition grammar; local sequence stays conflicted or singleton-heavy"
                )
            if (
                gradient_macro_fixture_transition_summary
                and gradient_macro_phase_sequence_summary
                and gradient_macro_phase_conflict_split_summary
                and gradient_macro_phase_summary
                and gradient_macro_residual_state_summary
                and gradient_macro_conflict_split_summary
                and gradient_macro_opcode_summary
                and gradient_payload_state_opcode_summary
                and micro_mixed_value_payload_state_opcode_summary
                and jump_token_payload_state_opcode_summary
            ):
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"gradient_fixture_transition_best="
                        f"{gradient_macro_fixture_transition_summary.get('best_transition_target_kind', '')}/"
                        f"{gradient_macro_fixture_transition_summary.get('best_transition_selector_family', '')}",
                        f"gradient_fixture_transition_deterministic="
                        f"{gradient_macro_fixture_transition_summary.get('best_transition_deterministic_bytes', '0')}",
                        f"gradient_fixture_transition_low_conflict="
                        f"{gradient_macro_fixture_transition_summary.get('low_conflict_transition_selector_family', '')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"gradient_fixture_transition_conflicted="
                        f"{gradient_macro_fixture_transition_summary.get('best_transition_conflicted_bytes', '0')}",
                        f"gradient_fixture_transition_low_conflict_singleton="
                        f"{gradient_macro_fixture_transition_summary.get('low_conflict_transition_singleton_bytes', '0')}",
                        f"gradient_fixture_transition_promotion_ready="
                        f"{gradient_macro_fixture_transition_summary.get('promotion_ready_bytes', '0')}",
                    ],
                )
                next_action = (
                    "probe cross-frontier macro state clusters; fixture/op transition stays conflicted or singleton-heavy"
                )
            if (
                gradient_macro_state_cluster_summary
                and gradient_macro_fixture_transition_summary
                and gradient_macro_phase_sequence_summary
                and gradient_macro_phase_conflict_split_summary
                and gradient_macro_phase_summary
                and gradient_macro_residual_state_summary
                and gradient_macro_conflict_split_summary
                and gradient_macro_opcode_summary
                and gradient_payload_state_opcode_summary
                and micro_mixed_value_payload_state_opcode_summary
                and jump_token_payload_state_opcode_summary
            ):
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"gradient_macro_state_cluster_best="
                        f"{gradient_macro_state_cluster_summary.get('best_cluster_target_kind', '')}/"
                        f"{gradient_macro_state_cluster_summary.get('best_cluster_selector_family', '')}",
                        f"gradient_macro_state_cluster_deterministic="
                        f"{gradient_macro_state_cluster_summary.get('best_cluster_deterministic_bytes', '0')}",
                        f"gradient_macro_state_cluster_low_conflict="
                        f"{gradient_macro_state_cluster_summary.get('low_conflict_cluster_selector_family', '')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"gradient_macro_state_cluster_conflicted="
                        f"{gradient_macro_state_cluster_summary.get('best_cluster_conflicted_bytes', '0')}",
                        f"gradient_macro_state_cluster_low_conflict_singleton="
                        f"{gradient_macro_state_cluster_summary.get('low_conflict_cluster_singleton_bytes', '0')}",
                        f"gradient_macro_state_cluster_payload_deterministic="
                        f"{gradient_macro_state_cluster_summary.get('best_payload_deterministic_bytes', '0')}",
                        f"gradient_macro_state_cluster_promotion_ready="
                        f"{gradient_macro_state_cluster_summary.get('promotion_ready_bytes', '0')}",
                    ],
                )
                next_action = "probe payload inside skip/op8 macro-state clusters before promotion"
            if (
                gradient_macro_state_cluster_payload_summary
                and gradient_macro_state_cluster_summary
                and gradient_macro_fixture_transition_summary
                and gradient_macro_phase_sequence_summary
                and gradient_macro_phase_conflict_split_summary
                and gradient_macro_phase_summary
                and gradient_macro_residual_state_summary
                and gradient_macro_conflict_split_summary
                and gradient_macro_opcode_summary
                and gradient_payload_state_opcode_summary
                and micro_mixed_value_payload_state_opcode_summary
                and jump_token_payload_state_opcode_summary
            ):
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"gradient_cluster_payload_best="
                        f"{gradient_macro_state_cluster_payload_summary.get('best_payload_target_kind', '')}/"
                        f"{gradient_macro_state_cluster_payload_summary.get('best_payload_selector_family', '')}",
                        f"gradient_cluster_payload_deterministic="
                        f"{gradient_macro_state_cluster_payload_summary.get('best_payload_deterministic_bytes', '0')}",
                        f"gradient_cluster_payload_coarse="
                        f"{gradient_macro_state_cluster_payload_summary.get('best_coarse_target_kind', '')}/"
                        f"{gradient_macro_state_cluster_payload_summary.get('best_coarse_selector_family', '')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"gradient_cluster_payload_exact_deterministic="
                        f"{gradient_macro_state_cluster_payload_summary.get('exact_payload_deterministic_bytes', '0')}",
                        f"gradient_cluster_payload_conflicted="
                        f"{gradient_macro_state_cluster_payload_summary.get('best_payload_conflicted_bytes', '0')}",
                        f"gradient_cluster_payload_promotion_ready="
                        f"{gradient_macro_state_cluster_payload_summary.get('promotion_ready_bytes', '0')}",
                    ],
                )
                next_action = (
                    "probe source-window transforms inside skip/op8 clusters; payload exact does not repeat"
                )
            if (
                gradient_macro_state_cluster_source_summary
                and gradient_macro_state_cluster_payload_summary
                and gradient_macro_state_cluster_summary
                and gradient_macro_fixture_transition_summary
                and gradient_macro_phase_sequence_summary
                and gradient_macro_phase_conflict_split_summary
                and gradient_macro_phase_summary
                and gradient_macro_residual_state_summary
                and gradient_macro_conflict_split_summary
                and gradient_macro_opcode_summary
                and gradient_payload_state_opcode_summary
                and micro_mixed_value_payload_state_opcode_summary
                and jump_token_payload_state_opcode_summary
            ):
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"gradient_cluster_source_linear="
                        f"{gradient_macro_state_cluster_source_summary.get('linear_exact_bytes', '0')}",
                        f"gradient_cluster_source_control_high="
                        f"{gradient_macro_state_cluster_source_summary.get('control_high_exact_bytes', '0')}",
                        f"gradient_cluster_source_start_high="
                        f"{gradient_macro_state_cluster_source_summary.get('start_high_exact_bytes', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"gradient_cluster_source_control_raw="
                        f"{gradient_macro_state_cluster_source_summary.get('control_raw_exact_bytes', '0')}",
                        f"gradient_cluster_source_start_raw="
                        f"{gradient_macro_state_cluster_source_summary.get('start_raw_exact_bytes', '0')}",
                        f"gradient_cluster_source_promotion_ready="
                        f"{gradient_macro_state_cluster_source_summary.get('promotion_ready_bytes', '0')}",
                    ],
                )
                next_action = (
                    "probe literal/geometric transforms inside skip/op8 clusters; source-window replay is weak"
                )
            if (
                gradient_macro_state_cluster_literal_summary
                and gradient_macro_state_cluster_source_summary
                and gradient_macro_state_cluster_payload_summary
                and gradient_macro_state_cluster_summary
                and gradient_macro_fixture_transition_summary
                and gradient_macro_phase_sequence_summary
                and gradient_macro_phase_conflict_split_summary
                and gradient_macro_phase_summary
                and gradient_macro_residual_state_summary
                and gradient_macro_conflict_split_summary
                and gradient_macro_opcode_summary
                and gradient_payload_state_opcode_summary
                and micro_mixed_value_payload_state_opcode_summary
                and jump_token_payload_state_opcode_summary
            ):
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"gradient_cluster_literal_spatial_best="
                        f"{gradient_macro_state_cluster_literal_summary.get('spatial_best_direction', '')}"
                        f"{gradient_macro_state_cluster_literal_summary.get('spatial_best_distance', '')}/"
                        f"{gradient_macro_state_cluster_literal_summary.get('spatial_best_transform', '')}",
                        f"gradient_cluster_literal_spatial_correct="
                        f"{gradient_macro_state_cluster_literal_summary.get('spatial_best_correct_bytes', '0')}",
                        f"gradient_cluster_literal_source_correct="
                        f"{gradient_macro_state_cluster_literal_summary.get('source_best_correct_bytes', '0')}",
                        f"gradient_cluster_literal_back320_exact="
                        f"{gradient_macro_state_cluster_literal_summary.get('spatial_back_distance320_exact_rows', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"gradient_cluster_literal_spatial_false="
                        f"{gradient_macro_state_cluster_literal_summary.get('spatial_best_false_bytes', '0')}",
                        f"gradient_cluster_literal_spatial_exact="
                        f"{gradient_macro_state_cluster_literal_summary.get('spatial_best_exact_rows', '0')}",
                        f"gradient_cluster_literal_source_exact="
                        f"{gradient_macro_state_cluster_literal_summary.get('source_exact_rows', '0')}",
                        f"gradient_cluster_literal_promotion_ready="
                        f"{gradient_macro_state_cluster_literal_summary.get('promotion_ready_bytes', '0')}",
                    ],
                )
                next_action = (
                    "isolate the lone -320 exact spatial row; broad literal/geometric transforms remain non-promotable"
                )
            if (
                gradient_macro_state_cluster_backref_summary
                and gradient_macro_state_cluster_literal_summary
                and gradient_macro_state_cluster_source_summary
                and gradient_macro_state_cluster_payload_summary
                and gradient_macro_state_cluster_summary
                and gradient_macro_fixture_transition_summary
                and gradient_macro_phase_sequence_summary
                and gradient_macro_phase_conflict_split_summary
                and gradient_macro_phase_summary
                and gradient_macro_residual_state_summary
                and gradient_macro_conflict_split_summary
                and gradient_macro_opcode_summary
                and gradient_payload_state_opcode_summary
                and micro_mixed_value_payload_state_opcode_summary
                and jump_token_payload_state_opcode_summary
            ):
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"gradient_cluster_backref_best="
                        f"{gradient_macro_state_cluster_backref_summary.get('best_rule', '')}",
                        f"gradient_cluster_backref_exact="
                        f"{gradient_macro_state_cluster_backref_summary.get('exact_back320_bytes', '0')}",
                        f"gradient_cluster_backref_candidate="
                        f"{gradient_macro_state_cluster_backref_summary.get('candidate_review_bytes', '0')}",
                        f"gradient_cluster_backref_literal_exact="
                        f"{gradient_macro_state_cluster_backref_summary.get('literal_target_exact_bytes', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"gradient_cluster_backref_false="
                        f"{gradient_macro_state_cluster_backref_summary.get('false_back320_bytes', '0')}",
                        f"gradient_cluster_backref_promotion_ready="
                        f"{gradient_macro_state_cluster_backref_summary.get('promotion_ready_bytes', '0')}",
                    ],
                )
                next_action = "broaden flat-walk -320 backref probe outside macro clusters before promotion"
            if (
                flat_walk_backref_summary
                and gradient_macro_state_cluster_backref_summary
                and gradient_macro_state_cluster_literal_summary
                and gradient_macro_state_cluster_source_summary
                and gradient_macro_state_cluster_payload_summary
                and gradient_macro_state_cluster_summary
                and gradient_macro_fixture_transition_summary
                and gradient_macro_phase_sequence_summary
                and gradient_macro_phase_conflict_split_summary
                and gradient_macro_phase_summary
                and gradient_macro_residual_state_summary
                and gradient_macro_conflict_split_summary
                and gradient_macro_opcode_summary
                and gradient_payload_state_opcode_summary
                and micro_mixed_value_payload_state_opcode_summary
                and jump_token_payload_state_opcode_summary
            ):
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"flat_walk_backref_broad_exact={flat_walk_backref_summary.get('exact_copy_bytes', '0')}",
                        f"flat_walk_backref_broad_distance={flat_walk_backref_summary.get('best_distance', '0')}",
                        f"flat_walk_backref_broad_best_rule={flat_walk_backref_summary.get('best_rule', '')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"flat_walk_backref_broad_known_source="
                        f"{flat_walk_backref_summary.get('exact_known_source_bytes', '0')}",
                        f"flat_walk_backref_broad_unresolved="
                        f"{flat_walk_backref_summary.get('exact_unresolved_source_bytes', '0')}",
                        f"flat_walk_backref_broad_rule_false="
                        f"{flat_walk_backref_summary.get('best_rule_false_bytes', '0')}",
                    ],
                )
                next_action = "decode flat-walk first occurrences/source coverage before -320 replay promotion"
            if (
                flat_walk_palette_context_summary
                and flat_walk_backref_chain_summary
                and flat_walk_backref_summary
                and gradient_macro_state_cluster_backref_summary
                and gradient_macro_state_cluster_literal_summary
                and gradient_macro_state_cluster_source_summary
                and gradient_macro_state_cluster_payload_summary
                and gradient_macro_state_cluster_summary
                and gradient_macro_fixture_transition_summary
                and gradient_macro_phase_sequence_summary
                and gradient_macro_phase_conflict_split_summary
                and gradient_macro_phase_summary
                and gradient_macro_residual_state_summary
                and gradient_macro_conflict_split_summary
                and gradient_macro_opcode_summary
                and gradient_payload_state_opcode_summary
                and micro_mixed_value_payload_state_opcode_summary
                and jump_token_payload_state_opcode_summary
            ):
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"flat_walk_chain_source_candidate="
                        f"{flat_walk_backref_chain_summary.get('any_source_candidate_bytes', '0')}",
                        f"flat_walk_context_copy320="
                        f"{flat_walk_palette_context_summary.get('copy_distance_320_rows', '0')}",
                        f"flat_walk_context_overlap="
                        f"{flat_walk_palette_context_summary.get('best_unique_control_overlap', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"flat_walk_chain_repeated="
                        f"{flat_walk_backref_chain_summary.get('repeated_group_chain_bytes', '0')}",
                        f"flat_walk_chain_blocked="
                        f"{flat_walk_backref_chain_summary.get('blocked_chain_bytes', '0')}",
                        f"flat_walk_context_shared="
                        f"{flat_walk_palette_context_summary.get('shared_context_rows', '0')}",
                        f"flat_walk_context_same_transform="
                        f"{flat_walk_palette_context_summary.get('same_transform_set_rows', '0')}",
                    ],
                )
                next_action = "probe context-normalized palette producers for flat-walk first occurrences"
            if (
                flat_walk_palette_normalized_context_summary
                and flat_walk_palette_context_summary
                and flat_walk_backref_chain_summary
                and flat_walk_backref_summary
                and gradient_macro_state_cluster_backref_summary
                and gradient_macro_state_cluster_literal_summary
                and gradient_macro_state_cluster_source_summary
                and gradient_macro_state_cluster_payload_summary
                and gradient_macro_state_cluster_summary
                and gradient_macro_fixture_transition_summary
                and gradient_macro_phase_sequence_summary
                and gradient_macro_phase_conflict_split_summary
                and gradient_macro_phase_summary
                and gradient_macro_residual_state_summary
                and gradient_macro_conflict_split_summary
                and gradient_macro_opcode_summary
                and gradient_payload_state_opcode_summary
                and micro_mixed_value_payload_state_opcode_summary
                and jump_token_payload_state_opcode_summary
            ):
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"flat_walk_palette_norm_groups="
                        f"{flat_walk_palette_normalized_context_summary.get('repeated_signature_groups', '0')}",
                        f"flat_walk_palette_norm_values="
                        f"{flat_walk_palette_normalized_context_summary.get('palette_value_count', '0')}",
                        f"flat_walk_palette_norm_best_delta_hits="
                        f"{flat_walk_palette_normalized_context_summary.get('best_transform_delta_value_hits', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"flat_walk_palette_norm_uniform_transform="
                        f"{flat_walk_palette_normalized_context_summary.get('uniform_transform_delta_groups', '0')}",
                        f"flat_walk_palette_norm_uniform_offset="
                        f"{flat_walk_palette_normalized_context_summary.get('uniform_offset_delta_groups', '0')}",
                        f"flat_walk_palette_norm_full="
                        f"{flat_walk_palette_normalized_context_summary.get('full_normalized_groups', '0')}",
                        f"flat_walk_palette_norm_promotion_ready="
                        f"{flat_walk_palette_normalized_context_summary.get('promotion_ready_bytes', '0')}",
                    ],
                )
                next_action = (
                    "split palette values inside repeated flat-walk signatures; group-level normalization fails"
                )
            if (
                flat_walk_palette_value_split_summary
                and flat_walk_palette_normalized_context_summary
                and flat_walk_palette_context_summary
                and flat_walk_backref_chain_summary
                and flat_walk_backref_summary
                and gradient_macro_state_cluster_backref_summary
                and gradient_macro_state_cluster_literal_summary
                and gradient_macro_state_cluster_source_summary
                and gradient_macro_state_cluster_payload_summary
                and gradient_macro_state_cluster_summary
                and gradient_macro_fixture_transition_summary
                and gradient_macro_phase_sequence_summary
                and gradient_macro_phase_conflict_split_summary
                and gradient_macro_phase_summary
                and gradient_macro_residual_state_summary
                and gradient_macro_conflict_split_summary
                and gradient_macro_opcode_summary
                and gradient_payload_state_opcode_summary
                and micro_mixed_value_payload_state_opcode_summary
                and jump_token_payload_state_opcode_summary
            ):
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"flat_walk_palette_value_rows="
                        f"{flat_walk_palette_value_split_summary.get('value_rows', '0')}",
                        f"flat_walk_palette_value_best_transform="
                        f"{flat_walk_palette_value_split_summary.get('best_transform_delta', '')}/"
                        f"{flat_walk_palette_value_split_summary.get('best_transform_delta_values', '0')}",
                        f"flat_walk_palette_value_best_pair="
                        f"{flat_walk_palette_value_split_summary.get('best_delta_pair', '')}/"
                        f"{flat_walk_palette_value_split_summary.get('best_delta_pair_values', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"flat_walk_palette_value_transform_groups="
                        f"{flat_walk_palette_value_split_summary.get('transform_delta_groups', '0')}",
                        f"flat_walk_palette_value_pair_groups="
                        f"{flat_walk_palette_value_split_summary.get('delta_pair_groups', '0')}",
                        f"flat_walk_palette_value_promotion_ready="
                        f"{flat_walk_palette_value_split_summary.get('promotion_ready_bytes', '0')}",
                    ],
                )
                next_action = (
                    "derive a compact palette-value delta table; best transform delta covers only 8/14 values"
                )
            if (
                flat_walk_palette_value_table_summary
                and flat_walk_palette_value_split_summary
                and flat_walk_palette_normalized_context_summary
                and flat_walk_palette_context_summary
                and flat_walk_backref_chain_summary
                and flat_walk_backref_summary
                and gradient_macro_state_cluster_backref_summary
                and gradient_macro_state_cluster_literal_summary
                and gradient_macro_state_cluster_source_summary
                and gradient_macro_state_cluster_payload_summary
                and gradient_macro_state_cluster_summary
                and gradient_macro_fixture_transition_summary
                and gradient_macro_phase_sequence_summary
                and gradient_macro_phase_conflict_split_summary
                and gradient_macro_phase_summary
                and gradient_macro_residual_state_summary
                and gradient_macro_conflict_split_summary
                and gradient_macro_opcode_summary
                and gradient_payload_state_opcode_summary
                and micro_mixed_value_payload_state_opcode_summary
                and jump_token_payload_state_opcode_summary
            ):
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"flat_walk_value_table_multi="
                        f"{flat_walk_palette_value_table_summary.get('multi_signature_values', '0')}",
                        f"flat_walk_value_table_stable_transform="
                        f"{flat_walk_palette_value_table_summary.get('stable_transform_multi_values', '0')}",
                        f"flat_walk_value_table_best_transform="
                        f"{flat_walk_palette_value_table_summary.get('best_value_transform', '')}/"
                        f"{flat_walk_palette_value_table_summary.get('best_value_transform_rows', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"flat_walk_value_table_conflicted_transform="
                        f"{flat_walk_palette_value_table_summary.get('conflicted_transform_multi_values', '0')}",
                        f"flat_walk_value_table_stable_pair="
                        f"{flat_walk_palette_value_table_summary.get('stable_pair_multi_values', '0')}",
                        f"flat_walk_value_table_promotion_ready="
                        f"{flat_walk_palette_value_table_summary.get('promotion_ready_bytes', '0')}",
                    ],
                )
                next_action = "seek compressed-stream selectors for conflicted flat-walk palette values"
            if flat_walk_palette_compressed_selector_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"flat_walk_compressed_conflicted="
                        f"{flat_walk_palette_compressed_selector_summary.get('conflicted_value_rows', '0')}",
                        f"flat_walk_compressed_best_transform="
                        f"{flat_walk_palette_compressed_selector_summary.get('best_transform_selector', '')}/"
                        f"{flat_walk_palette_compressed_selector_summary.get('best_transform_selector_rows', '0')}->"
                        f"{flat_walk_palette_compressed_selector_summary.get('best_transform_selector_delta', '')}",
                        f"flat_walk_compressed_best_pair="
                        f"{flat_walk_palette_compressed_selector_summary.get('best_pair_selector', '')}/"
                        f"{flat_walk_palette_compressed_selector_summary.get('best_pair_selector_rows', '0')}",
                        f"flat_walk_compressed_exact_transform_groups="
                        f"{flat_walk_palette_compressed_selector_summary.get('exact_transform_compressed_groups', '0')}",
                        f"flat_walk_compressed_exact_pair_groups="
                        f"{flat_walk_palette_compressed_selector_summary.get('exact_pair_compressed_groups', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"flat_walk_compressed_best_transform_rows="
                        f"{flat_walk_palette_compressed_selector_summary.get('best_transform_selector_rows', '0')}/"
                        f"{flat_walk_palette_compressed_selector_summary.get('conflicted_value_rows', '0')}",
                        f"flat_walk_compressed_best_pair_rows="
                        f"{flat_walk_palette_compressed_selector_summary.get('best_pair_selector_rows', '0')}/"
                        f"{flat_walk_palette_compressed_selector_summary.get('conflicted_value_rows', '0')}",
                        f"flat_walk_compressed_promotion_ready="
                        f"{flat_walk_palette_compressed_selector_summary.get('promotion_ready_bytes', '0')}",
                    ],
                )
                next_action = flat_walk_compressed_selector_action(flat_walk_palette_compressed_selector_summary)
            if flat_walk_palette_compressed_combo_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"flat_walk_combo_best_transform="
                        f"{flat_walk_palette_compressed_combo_summary.get('best_transform_feature_set', '')}/"
                        f"{flat_walk_palette_compressed_combo_summary.get('best_transform_exact_conflicted_rows', '0')}"
                        f"_multirow="
                        f"{flat_walk_palette_compressed_combo_summary.get('best_transform_multirow_conflicted_rows', '0')}",
                        f"flat_walk_combo_best_pair="
                        f"{flat_walk_palette_compressed_combo_summary.get('best_pair_feature_set', '')}/"
                        f"{flat_walk_palette_compressed_combo_summary.get('best_pair_exact_conflicted_rows', '0')}",
                        f"flat_walk_combo_full_transform_sets="
                        f"{flat_walk_palette_compressed_combo_summary.get('full_transform_cover_sets', '0')}",
                        f"flat_walk_combo_full_pair_sets="
                        f"{flat_walk_palette_compressed_combo_summary.get('full_pair_cover_sets', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"flat_walk_combo_pair_singletons="
                        f"{flat_walk_palette_compressed_combo_summary.get('best_pair_singleton_conflicted_rows', '0')}",
                        f"flat_walk_combo_pair_multirow="
                        f"{flat_walk_palette_compressed_combo_summary.get('best_pair_multirow_conflicted_rows', '0')}",
                        f"flat_walk_combo_promotion_ready="
                        f"{flat_walk_palette_compressed_combo_summary.get('promotion_ready_bytes', '0')}",
                    ],
                )
                next_action = flat_walk_compressed_combo_action(flat_walk_palette_compressed_combo_summary)
            if flat_walk_palette_compressed_formula_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"flat_walk_formula_transform_exact="
                        f"{flat_walk_palette_compressed_formula_summary.get('transform_formula_exact_rows', '0')}/"
                        f"{flat_walk_palette_compressed_formula_summary.get('value_rows', '0')}",
                        f"flat_walk_formula_pair_exact="
                        f"{flat_walk_palette_compressed_formula_summary.get('pair_formula_exact_rows', '0')}/"
                        f"{flat_walk_palette_compressed_formula_summary.get('value_rows', '0')}",
                        f"flat_walk_formula_conflicted_pair_exact="
                        f"{flat_walk_palette_compressed_formula_summary.get('pair_formula_exact_conflicted_rows', '0')}/"
                        f"{flat_walk_palette_compressed_formula_summary.get('conflicted_value_rows', '0')}",
                        f"flat_walk_formula_raw_delta_groups="
                        f"{flat_walk_palette_compressed_formula_summary.get('raw_delta_groups', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"flat_walk_formula_scope_rows="
                        f"{flat_walk_palette_compressed_formula_summary.get('value_rows', '0')}",
                        f"flat_walk_formula_mismatches="
                        f"{flat_walk_palette_compressed_formula_summary.get('pair_formula_mismatch_rows', '0')}",
                        f"flat_walk_formula_promotion_ready="
                        f"{flat_walk_palette_compressed_formula_summary.get('promotion_ready_bytes', '0')}",
                    ],
                )
                next_action = flat_walk_compressed_formula_action(flat_walk_palette_compressed_formula_summary)
            if flat_walk_palette_corpus_formula_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"flat_walk_corpus_formula_exact="
                        f"{flat_walk_palette_corpus_formula_summary.get('shift_formula_exact_rows', '0')}/"
                        f"{flat_walk_palette_corpus_formula_summary.get('value_rows', '0')}",
                        f"flat_walk_corpus_formula_conflicted_exact="
                        f"{flat_walk_palette_corpus_formula_summary.get('shift_formula_exact_conflicted_rows', '0')}/"
                        f"{flat_walk_palette_corpus_formula_summary.get('known_conflicted_value_rows', '0')}",
                        f"flat_walk_corpus_formula_multi_exact="
                        f"{flat_walk_palette_corpus_formula_summary.get('shift_formula_exact_known_multi_rows', '0')}/"
                        f"{flat_walk_palette_corpus_formula_summary.get('known_multi_signature_value_rows', '0')}",
                        f"flat_walk_corpus_formula_pools="
                        f"{flat_walk_palette_corpus_formula_summary.get('candidate_pools', '0')}",
                        f"flat_walk_corpus_formula_transform_sets="
                        f"{flat_walk_palette_corpus_formula_summary.get('transform_sets', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"flat_walk_corpus_formula_candidate_scope="
                        f"{flat_walk_palette_corpus_formula_summary.get('candidate_target_rows', '0')}/"
                        f"{flat_walk_palette_corpus_formula_summary.get('target_rows', '0')}",
                        f"flat_walk_corpus_formula_mismatches="
                        f"{flat_walk_palette_corpus_formula_summary.get('shift_formula_mismatch_rows', '0')}",
                        f"flat_walk_corpus_formula_promotion_ready="
                        f"{flat_walk_palette_corpus_formula_summary.get('promotion_ready_bytes', '0')}",
                    ],
                )
                next_action = flat_walk_corpus_formula_action(flat_walk_palette_corpus_formula_summary)
            if flat_walk_palette_promotion_candidate_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"flat_walk_palette_candidate_targets="
                        f"{flat_walk_palette_promotion_candidate_summary.get('candidate_ready_target_rows', '0')}",
                        f"flat_walk_palette_candidate_bytes="
                        f"{flat_walk_palette_promotion_candidate_summary.get('candidate_ready_bytes', '0')}",
                        f"flat_walk_palette_candidate_plus_unlock="
                        f"{flat_walk_palette_promotion_candidate_summary.get('total_candidate_plus_unlock_bytes', '0')}",
                        f"flat_walk_palette_candidate_raw_plus_unlock="
                        f"{flat_walk_palette_promotion_candidate_summary.get('raw_candidate_plus_unlock_bytes', '0')}",
                        f"flat_walk_palette_candidate_overlap="
                        f"{flat_walk_palette_promotion_candidate_summary.get('backref_candidate_overlap_bytes', '0')}",
                        f"flat_walk_palette_candidate_unique_unlock="
                        f"{flat_walk_palette_promotion_candidate_summary.get('unique_backref_unlock_bytes', '0')}",
                        f"flat_walk_palette_candidate_values="
                        f"{flat_walk_palette_promotion_candidate_summary.get('formula_exact_value_rows', '0')}/"
                        f"{flat_walk_palette_promotion_candidate_summary.get('formula_value_rows', '0')}",
                    ],
                )
                candidate_blocking = [
                    f"flat_walk_palette_candidate_promotion_ready="
                    f"{flat_walk_palette_promotion_candidate_summary.get('promotion_ready_bytes', '0')}",
                    f"flat_walk_palette_candidate_issues="
                    f"{flat_walk_palette_promotion_candidate_summary.get('issue_rows', '0')}",
                ]
                if flat_walk_palette_formula_replay_summary:
                    candidate_blocking.insert(
                        0,
                        f"flat_walk_palette_candidate_replayed="
                        f"{flat_walk_palette_formula_replay_summary.get('replayed_target_rows', '0')}/"
                        f"{flat_walk_palette_promotion_candidate_summary.get('candidate_ready_target_rows', '0')}",
                    )
                else:
                    candidate_blocking.insert(
                        0,
                        f"flat_walk_palette_candidate_replay_needed="
                        f"{flat_walk_palette_promotion_candidate_summary.get('candidate_ready_target_rows', '0')}",
                    )
                blocking_evidence = append_evidence(blocking_evidence, candidate_blocking)
                if not flat_walk_palette_formula_replay_summary:
                    next_action = flat_walk_palette_promotion_candidate_action(
                        flat_walk_palette_promotion_candidate_summary
                    )
            if flat_walk_palette_formula_replay_summary:
                positive_evidence = append_evidence(
                    positive_evidence,
                    [
                        f"flat_walk_palette_replay_targets="
                        f"{flat_walk_palette_formula_replay_summary.get('replayed_target_rows', '0')}/"
                        f"{flat_walk_palette_formula_replay_summary.get('target_rows', '0')}",
                        f"flat_walk_palette_replay_added="
                        f"{flat_walk_palette_formula_replay_summary.get('formula_added_bytes', '0')}",
                        f"flat_walk_palette_replay_exact="
                        f"{flat_walk_palette_formula_replay_summary.get('formula_exact_bytes', '0')}",
                    ],
                )
                blocking_evidence = append_evidence(
                    blocking_evidence,
                    [
                        f"flat_walk_palette_replay_false="
                        f"{flat_walk_palette_formula_replay_summary.get('formula_false_bytes', '0')}",
                        f"flat_walk_palette_replay_skipped="
                        f"{flat_walk_palette_formula_replay_summary.get('skipped_known_bytes', '0')}/"
                        f"{flat_walk_palette_formula_replay_summary.get('skipped_rejected_bytes', '0')}",
                        f"flat_walk_palette_replay_issues="
                        f"{flat_walk_palette_formula_replay_summary.get('issue_rows', '0')}",
                    ],
                )
                if not flat_walk_palette_formula_replay_consumed(
                    flat_walk_palette_formula_replay_summary,
                    flat_walk_palette_promotion_candidate_summary,
                ):
                    next_action = flat_walk_palette_formula_replay_action(
                        flat_walk_palette_formula_replay_summary,
                        flat_walk_palette_promotion_candidate_summary,
                    )
                elif gradient_sequence_high_safe_low_exception_source_terminal_replay_union_summary:
                    next_action = gradient_sequence_high_safe_low_exception_source_terminal_replay_union_action(
                        gradient_sequence_high_safe_low_exception_source_terminal_replay_union_summary
                    )
                elif gradient_sequence_high_safe_low_exception_source_terminal_replay_support_summary:
                    next_action = gradient_sequence_high_safe_low_exception_source_terminal_replay_support_action(
                        gradient_sequence_high_safe_low_exception_source_terminal_replay_support_summary
                    )
                elif gradient_sequence_high_safe_low_exception_source_terminal_chain_context_summary:
                    next_action = gradient_sequence_high_safe_low_exception_source_terminal_chain_context_action(
                        gradient_sequence_high_safe_low_exception_source_terminal_chain_context_summary
                    )
                elif gradient_sequence_high_safe_low_exception_source_terminal_delta_summary:
                    next_action = gradient_sequence_high_safe_low_exception_source_terminal_delta_action(
                        gradient_sequence_high_safe_low_exception_source_terminal_delta_summary
                    )
                elif gradient_sequence_high_safe_low_exception_source_terminal_review_summary:
                    next_action = gradient_sequence_high_safe_low_exception_source_terminal_review_action(
                        gradient_sequence_high_safe_low_exception_source_terminal_review_summary
                    )
                elif gradient_sequence_high_safe_low_exception_source_terminal_summary:
                    next_action = gradient_sequence_high_safe_low_exception_source_terminal_action(
                        gradient_sequence_high_safe_low_exception_source_terminal_summary
                    )
                elif gradient_sequence_high_safe_low_exception_source_chain_summary:
                    next_action = gradient_sequence_high_safe_low_exception_source_chain_action(
                        gradient_sequence_high_safe_low_exception_source_chain_summary
                    )
                elif gradient_sequence_high_safe_low_exception_source_dependency_summary:
                    next_action = gradient_sequence_high_safe_low_exception_source_dependency_action(
                        gradient_sequence_high_safe_low_exception_source_dependency_summary
                    )
                elif gradient_sequence_high_safe_low_exception_prerequisite_state_summary:
                    next_action = gradient_sequence_high_safe_low_exception_prerequisite_state_action(
                        gradient_sequence_high_safe_low_exception_prerequisite_state_summary
                    )
                elif gradient_sequence_high_safe_low_exception_external_state_summary:
                    next_action = gradient_sequence_high_safe_low_exception_external_state_action(
                        gradient_sequence_high_safe_low_exception_external_state_summary
                    )
                elif gradient_sequence_high_safe_low_exception_row_family_summary:
                    next_action = gradient_sequence_high_safe_low_exception_row_family_action(
                        gradient_sequence_high_safe_low_exception_row_family_summary
                    )
                elif gradient_sequence_high_safe_low_exception_alignment_review_summary:
                    next_action = gradient_sequence_high_safe_low_exception_alignment_review_action(
                        gradient_sequence_high_safe_low_exception_alignment_review_summary
                    )
                elif gradient_sequence_high_safe_low_exception_alignment_summary:
                    next_action = gradient_sequence_high_safe_low_exception_alignment_action(
                        gradient_sequence_high_safe_low_exception_alignment_summary
                    )
                elif gradient_sequence_high_safe_low_exception_summary:
                    next_action = gradient_sequence_high_safe_low_exception_action(
                        gradient_sequence_high_safe_low_exception_summary
                    )
                elif gradient_sequence_high_safe_low_bucket_split_summary:
                    next_action = gradient_sequence_high_safe_low_bucket_split_action(
                        gradient_sequence_high_safe_low_bucket_split_summary
                    )
                elif gradient_sequence_high_safe_row_template_summary:
                    next_action = gradient_sequence_high_safe_row_template_action(
                        gradient_sequence_high_safe_row_template_summary
                    )
                elif gradient_sequence_high_safe_row_markov_summary:
                    next_action = gradient_sequence_high_safe_row_markov_action(
                        gradient_sequence_high_safe_row_markov_summary
                    )
                elif gradient_sequence_high_safe_row_transition_summary:
                    next_action = gradient_sequence_high_safe_row_transition_action(
                        gradient_sequence_high_safe_row_transition_summary
                    )
                elif gradient_sequence_high_safe_control_opcode_summary:
                    next_action = gradient_sequence_high_safe_control_opcode_action(
                        gradient_sequence_high_safe_control_opcode_summary
                    )
                elif gradient_sequence_high_safe_source_window_summary:
                    next_action = gradient_sequence_high_safe_source_window_action(
                        gradient_sequence_high_safe_source_window_summary
                    )
                elif gradient_sequence_high_safe_transform_low_summary:
                    next_action = gradient_sequence_high_safe_transform_low_action(
                        gradient_sequence_high_safe_transform_low_summary
                    )
                elif gradient_sequence_high_safe_row_corpus_low_summary:
                    next_action = gradient_sequence_high_safe_row_corpus_low_action(
                        gradient_sequence_high_safe_row_corpus_low_summary
                    )
                elif gradient_sequence_high_safe_source_profile_low_summary:
                    next_action = gradient_sequence_high_safe_source_profile_low_action(
                        gradient_sequence_high_safe_source_profile_low_summary
                    )
                elif gradient_sequence_high_safe_low_summary:
                    next_action = gradient_sequence_high_safe_low_action(
                        gradient_sequence_high_safe_low_summary
                    )
                elif gradient_sequence_known_state_summary:
                    next_action = gradient_sequence_known_state_action(
                        gradient_sequence_known_state_summary
                    )
                elif gradient_nonlocal_known_spatial_summary:
                    next_action = gradient_nonlocal_known_spatial_action(
                        gradient_nonlocal_known_spatial_summary
                    )
                elif gradient_seed_delta_payload_opcode_summary:
                    next_action = gradient_seed_delta_payload_opcode_action(
                        gradient_seed_delta_payload_opcode_summary
                    )
                elif gradient_macro_source_profile_state_summary:
                    next_action = gradient_macro_source_profile_state_action(
                        gradient_macro_source_profile_state_summary
                    )
                elif gradient_source_profile_high_safe_low_summary:
                    next_action = gradient_source_profile_high_safe_low_action(
                        gradient_source_profile_high_safe_low_summary
                    )
                elif gradient_source_profile_high_low_summary:
                    next_action = gradient_source_profile_high_low_action(
                        gradient_source_profile_high_low_summary
                    )
                elif gradient_shape_peer_copy_summary:
                    next_action = gradient_shape_peer_copy_action(gradient_shape_peer_copy_summary)
                elif flat_walk_palette_post_formula_vertical_copy_summary:
                    next_action = flat_walk_palette_post_formula_vertical_copy_action(
                        flat_walk_palette_post_formula_vertical_copy_summary
                    )
                elif micro_mixed_value_payload_sequence_blocked_prerequisite_role_transform_summary:
                    next_action = mixed_value_sequence_blocked_prerequisite_role_transform_action(
                        micro_mixed_value_payload_sequence_blocked_prerequisite_role_transform_summary
                    )
                elif micro_mixed_value_payload_sequence_low_copy_adjacent_summary:
                    next_action = mixed_value_sequence_low_copy_adjacent_action(
                        micro_mixed_value_payload_sequence_low_copy_adjacent_summary
                    )
                elif micro_mixed_value_payload_sequence_low_copy_corpus_expansion_summary:
                    next_action = mixed_value_sequence_low_copy_corpus_action(
                        micro_mixed_value_payload_sequence_low_copy_corpus_expansion_summary
                    )
                elif micro_mixed_value_payload_sequence_low_copy_low_split_summary:
                    next_action = mixed_value_sequence_low_copy_low_split_action(
                        micro_mixed_value_payload_sequence_low_copy_low_split_summary
                    )
                elif micro_mixed_value_payload_sequence_low_copy_second_summary:
                    next_action = mixed_value_sequence_low_copy_second_action(
                        micro_mixed_value_payload_sequence_low_copy_second_summary
                    )
                elif micro_mixed_value_payload_sequence_low_copy_generalization_summary:
                    next_action = mixed_value_sequence_low_copy_generalization_action(
                        micro_mixed_value_payload_sequence_low_copy_generalization_summary
                    )
                elif micro_mixed_value_payload_sequence_low_copy_promoted_replay_summary:
                    next_action = mixed_value_sequence_low_copy_promoted_action(
                        micro_mixed_value_payload_sequence_low_copy_promoted_replay_summary
                    )
                elif micro_mixed_value_payload_sequence_low_copy_summary:
                    next_action = mixed_value_sequence_low_copy_action(
                        micro_mixed_value_payload_sequence_low_copy_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_adjacent_summary:
                    next_action = mixed_value_sequence_prerequisite_adjacent_known_transform_adjacent_action(
                        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_adjacent_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_corpus_expansion_summary:
                    next_action = mixed_value_sequence_prerequisite_adjacent_known_transform_corpus_action(
                        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_corpus_expansion_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_low_split_summary:
                    next_action = mixed_value_sequence_prerequisite_adjacent_known_transform_low_split_action(
                        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_low_split_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_fourth_summary:
                    next_action = mixed_value_sequence_prerequisite_adjacent_known_transform_second_action(
                        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_fourth_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_generalization_summary:
                    next_action = mixed_value_sequence_prerequisite_adjacent_known_transform_generalization_action(
                        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_generalization_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay_summary:
                    next_action = mixed_value_sequence_prerequisite_adjacent_known_transform_promoted_action(
                        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_adjacent_summary:
                    next_action = mixed_value_sequence_prerequisite_adjacent_known_transform_adjacent_action(
                        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_adjacent_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_expansion_summary:
                    next_action = mixed_value_sequence_prerequisite_adjacent_known_transform_corpus_action(
                        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_expansion_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_low_split_summary:
                    next_action = mixed_value_sequence_prerequisite_adjacent_known_transform_low_split_action(
                        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_low_split_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_second_summary:
                    next_action = mixed_value_sequence_prerequisite_adjacent_known_transform_second_action(
                        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_second_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_generalization_summary:
                    next_action = mixed_value_sequence_prerequisite_adjacent_known_transform_generalization_action(
                        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_generalization_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay_summary:
                    next_action = mixed_value_sequence_prerequisite_adjacent_known_transform_promoted_action(
                        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_summary:
                    next_action = mixed_value_sequence_prerequisite_adjacent_known_transform_action(
                        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_adjacent_known_fourth_summary:
                    next_action = mixed_value_sequence_prerequisite_adjacent_known_fourth_action(
                        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_fourth_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_adjacent_known_corpus_expansion_summary:
                    next_action = mixed_value_sequence_prerequisite_adjacent_known_corpus_expansion_action(
                        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_corpus_expansion_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_adjacent_known_low_split_summary:
                    next_action = mixed_value_sequence_prerequisite_adjacent_known_low_split_action(
                        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_low_split_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_adjacent_known_generalization_summary:
                    next_action = mixed_value_sequence_prerequisite_adjacent_known_generalization_action(
                        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_generalization_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay_summary:
                    next_action = mixed_value_sequence_prerequisite_adjacent_known_promoted_action(
                        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_promoted_replay_summary:
                    next_action = mixed_value_sequence_prerequisite_corpus_second_low_split_promoted_action(
                        micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_promoted_replay_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_summary:
                    next_action = mixed_value_sequence_prerequisite_corpus_second_low_split_action(
                        micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_promoted_replay_summary:
                    next_action = mixed_value_sequence_prerequisite_corpus_low_split_promoted_action(
                        micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_promoted_replay_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_summary:
                    next_action = mixed_value_sequence_prerequisite_corpus_low_split_action(
                        micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_promoted_replay_summary:
                    next_action = mixed_value_sequence_prerequisite_corpus_expansion_promoted_action(
                        micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_promoted_replay_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_summary:
                    next_action = mixed_value_sequence_prerequisite_corpus_expansion_action(
                        micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_second_expansion_summary:
                    next_action = mixed_value_sequence_prerequisite_second_expansion_action(
                        micro_mixed_value_payload_sequence_prerequisite_second_expansion_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_second_low_split_summary:
                    next_action = mixed_value_sequence_prerequisite_second_low_split_action(
                        micro_mixed_value_payload_sequence_prerequisite_second_low_split_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_low_split_generalization_summary:
                    next_action = mixed_value_sequence_prerequisite_low_split_generalization_action(
                        micro_mixed_value_payload_sequence_prerequisite_low_split_generalization_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay_summary:
                    next_action = mixed_value_sequence_prerequisite_low_split_promoted_action(
                        micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_low_split_summary:
                    next_action = mixed_value_sequence_prerequisite_low_split_action(
                        micro_mixed_value_payload_sequence_prerequisite_low_split_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay_summary:
                    next_action = mixed_value_sequence_prerequisite_expansion_promoted_action(
                        micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay_summary
                    )
                elif micro_mixed_value_payload_sequence_prerequisite_expansion_summary:
                    next_action = mixed_value_sequence_prerequisite_expansion_action(
                        micro_mixed_value_payload_sequence_prerequisite_expansion_summary
                    )
                elif micro_mixed_value_payload_sequence_low_split_promoted_replay_summary:
                    next_action = mixed_value_sequence_low_split_promoted_replay_action(
                        micro_mixed_value_payload_sequence_low_split_promoted_replay_summary
                    )
                elif micro_mixed_value_payload_sequence_low_split_summary:
                    next_action = mixed_value_sequence_low_split_action(
                        micro_mixed_value_payload_sequence_low_split_summary
                    )
                elif micro_mixed_value_payload_sequence_promoted_generalization_summary:
                    next_action = mixed_value_sequence_promoted_generalization_action(
                        micro_mixed_value_payload_sequence_promoted_generalization_summary
                    )
                elif micro_mixed_value_payload_prefix_sequence_promoted_replay_summary:
                    next_action = mixed_value_prefix_sequence_promoted_replay_action(
                        micro_mixed_value_payload_prefix_sequence_promoted_replay_summary
                    )
                elif micro_mixed_value_payload_prefix_sequence_replay_summary:
                    next_action = mixed_value_prefix_sequence_replay_action(
                        micro_mixed_value_payload_prefix_sequence_replay_summary
                    )
                elif micro_mixed_value_payload_prefix_bootstrap_summary:
                    next_action = mixed_value_prefix_bootstrap_action(micro_mixed_value_payload_prefix_bootstrap_summary)
                elif micro_mixed_value_payload_sequence_candidate_review_summary:
                    next_action = mixed_value_sequence_candidate_review_action(
                        micro_mixed_value_payload_sequence_candidate_review_summary
                    )
                elif micro_mixed_value_payload_sequence_state_summary:
                    next_action = mixed_value_sequence_state_action(micro_mixed_value_payload_sequence_state_summary)
                elif micro_mixed_value_payload_state_external_combo_summary:
                    next_action = mixed_value_state_external_combo_action(
                        micro_mixed_value_payload_state_external_combo_summary
                    )
                elif micro_mixed_value_payload_external_high_low_summary:
                    next_action = mixed_value_external_high_low_action(
                        micro_mixed_value_payload_external_high_low_summary
                    )
                elif micro_mixed_value_payload_external_source_combo_summary:
                    next_action = mixed_value_external_source_combo_action(
                        micro_mixed_value_payload_external_source_combo_summary
                    )
                elif micro_mixed_value_payload_high_low_summary:
                    next_action = mixed_value_payload_high_low_action(micro_mixed_value_payload_high_low_summary)
                elif micro_mixed_value_payload_combo_summary:
                    next_action = mixed_value_payload_combo_action(micro_mixed_value_payload_combo_summary)
                else:
                    next_action = "continue unresolved decoder probes after deduped flat-walk palette replay"
            row = {
                **row,
                "next_action": next_action,
                "positive_evidence": positive_evidence,
                "blocking_evidence": blocking_evidence,
            }
        enriched.append(
            {
                "priority": 0,
                "track": classify_track(row),
                "surface": row.get("surface", ""),
                "rows": int_value(row, "rows"),
                "bytes": bytes_,
                "promotion_ready_bytes": ready,
                "signal_score": signal_score(row),
                "status": status,
                "next_action": row.get("next_action", ""),
                "positive_evidence": row.get("positive_evidence", ""),
                "blocking_evidence": row.get("blocking_evidence", ""),
            }
        )

    enriched.sort(
        key=lambda row: (
            str(row["surface"]) != "noisy_all",
            int(row["promotion_ready_bytes"]) > 0,
            int(row["bytes"]),
            int(row["signal_score"]),
            str(row["surface"]),
        ),
        reverse=True,
    )
    for index, row in enumerate(enriched, start=1):
        row["priority"] = index
    return enriched


def build_stable_walk_decision(
    summary: dict[str, str],
    groups: list[dict[str, str]],
    backref_summary: dict[str, str] | None,
    source_summary: dict[str, str] | None,
    source_grammar_summary: dict[str, str] | None,
    value_context_summary: dict[str, str] | None,
    context_rules_summary: dict[str, str] | None,
    sequence_summary: dict[str, str] | None,
    alternation_summary: dict[str, str] | None,
    alternation_replay_summary: dict[str, str] | None,
    length_sequence_summary: dict[str, str] | None,
    length_control_summary: dict[str, str] | None,
    length_opcode_summary: dict[str, str] | None,
    length_interval_summary: dict[str, str] | None,
) -> dict[str, str] | None:
    repeated_bytes = int_value(summary, "repeated_signature_bytes")
    copy_bytes = int_value(summary, "copy_distance_320_bytes")
    if repeated_bytes <= 0:
        return None

    strongest = groups[0] if groups else {}
    positive = [
        f"repeated_signature_bytes={repeated_bytes}",
        f"exact_repeat_bytes={int_value(summary, 'exact_repeat_bytes')}",
        f"copy_distance_320_bytes={copy_bytes}",
    ]
    if strongest:
        positive.append(f"top_signature={strongest.get('signed_shape_key', '')}")
        positive.append(f"top_offsets={strongest.get('start_offsets', '')}")

    blocking = ["source_control_unresolved", "promotion_ready=0"]
    if backref_summary:
        positive.append(f"backref_distance={backref_summary.get('best_distance', '')}")
        positive.append(f"backref_exact_bytes={backref_summary.get('distance_320_exact_bytes', '0')}")
        blocking.append(f"backref_known_source_bytes={backref_summary.get('distance_320_known_source_bytes', '0')}")
    if source_summary:
        blocking.append(f"source_probe_best_exact_bytes={source_summary.get('best_exact_bytes_total', '0')}")
        blocking.append(f"source_probe_full_matches={source_summary.get('full_match_rows', '0')}")
    if source_grammar_summary:
        positive.append(f"source_grammar_value_hit_bytes={source_grammar_summary.get('local_value_hit_bytes', '0')}")
        blocking.append(f"source_grammar_literal_run_bytes={source_grammar_summary.get('local_repeated_literal_bytes', '0')}")
    if value_context_summary:
        positive.append(f"value_context_repeated_bytes={value_context_summary.get('repeated_context_bytes', '0')}")
        positive.append(f"value_context_repeated_shape_bytes={value_context_summary.get('repeated_shape_bytes', '0')}")
        blocking.append(
            f"value_context_repeated_value_length_bytes="
            f"{value_context_summary.get('repeated_value_length_context_bytes', '0')}"
        )
        blocking.append(
            f"value_context_repeated_value_length_shape_bytes="
            f"{value_context_summary.get('repeated_value_length_shape_bytes', '0')}"
        )
    if context_rules_summary:
        positive.append(
            f"context_rule_deterministic_exact_bytes="
            f"{context_rules_summary.get('deterministic_context_exact_bytes', '0')}"
        )
        blocking.append(f"context_rule_conflicted_bytes={context_rules_summary.get('conflicted_rule_bytes', '0')}")
    if sequence_summary:
        positive.append(
            f"sequence_shape_step_bytes={sequence_summary.get('deterministic_shape_offset_step_bytes', '0')}"
        )
        blocking.append(f"sequence_transition_bytes={sequence_summary.get('transition_bytes', '0')}")
    if alternation_summary:
        positive.append(f"alternating_suffix_bytes={alternation_summary.get('suffix_alternating_bytes', '0')}")
        blocking.append(f"alternating_run_bytes={alternation_summary.get('run_bytes', '0')}")
    if alternation_replay_summary:
        positive.append(f"alternation_replay_exact_bytes={alternation_replay_summary.get('exact_oracle_bytes', '0')}")
        positive.append(f"alternation_replay_length_hit_bytes={alternation_replay_summary.get('length_local_hit_bytes', '0')}")
        blocking.append("alternation_replay_uses_oracle_lengths")
    if length_sequence_summary:
        positive.append(f"length_sequence_ordered_bytes={length_sequence_summary.get('ordered_sequence_bytes', '0')}")
        positive.append(f"length_sequence_suffix_ordered_bytes={length_sequence_summary.get('suffix_ordered_bytes', '0')}")
        blocking.append(f"length_sequence_compact_bytes={length_sequence_summary.get('compact_sequence_bytes', '0')}")
        blocking.append(
            f"length_sequence_multi_segment_selector_bytes="
            f"{length_sequence_summary.get('multi_segment_selector_rule_bytes', '0')}"
        )
    if length_control_summary:
        positive.append(f"length_control_best_pool={length_control_summary.get('best_pool', '')}")
        blocking.append(f"length_control_compact_bytes={length_control_summary.get('compact_pool_bytes', '0')}")
    if length_opcode_summary:
        positive.append(f"length_opcode_candidate_bytes={length_opcode_summary.get('candidate_bytes', '0')}")
        blocking.append(f"length_opcode_direct_after_bytes={length_opcode_summary.get('direct_after_bytes', '0')}")
        blocking.append(f"length_opcode_nearby_value_run_bytes={length_opcode_summary.get('nearby_value_run_bytes', '0')}")
        blocking.append(f"length_opcode_repeated_context_bytes={length_opcode_summary.get('repeated_context_bytes', '0')}")
    if length_interval_summary:
        positive.append(f"length_interval_transition_bytes={length_interval_summary.get('transition_bytes', '0')}")
        positive.append(f"length_interval_marker_bytes={length_interval_summary.get('marker_transition_bytes', '0')}")
        blocking.append(f"length_interval_stable_signature_bytes={length_interval_summary.get('stable_signature_bytes', '0')}")
        blocking.append(f"length_interval_conflicted_offset_bytes={length_interval_summary.get('conflicted_offset_bytes', '0')}")

    return {
        "surface": "micro_token_stable_walks",
        "rows": summary.get("repeated_signature_rows", "0"),
        "bytes": str(repeated_bytes),
        "promotion_ready_bytes": "0",
        "next_action": "map the +320 exact repeats to a source/control pair before promoting a copy rule",
        "positive_evidence": "; ".join(value for value in positive if value),
        "blocking_evidence": "; ".join(blocking),
    }


def append_optional_stable_walk_decision(
    decisions: list[dict[str, str]],
    summary_path: Path,
    groups_path: Path,
    backrefs_summary_path: Path,
    sources_summary_path: Path,
    source_grammar_summary_path: Path,
    value_context_summary_path: Path,
    context_rules_summary_path: Path,
    sequence_summary_path: Path,
    alternation_summary_path: Path,
    alternation_replay_summary_path: Path,
    length_sequence_summary_path: Path,
    length_control_summary_path: Path,
    length_opcode_summary_path: Path,
    length_interval_summary_path: Path,
) -> list[dict[str, str]]:
    if not summary_path.exists() or not groups_path.exists():
        return decisions
    summary_rows = read_rows(summary_path)
    if not summary_rows:
        return decisions
    backref_summary_rows = read_rows(backrefs_summary_path) if backrefs_summary_path.exists() else []
    backref_summary = backref_summary_rows[0] if backref_summary_rows else None
    source_summary_rows = read_rows(sources_summary_path) if sources_summary_path.exists() else []
    source_summary = source_summary_rows[0] if source_summary_rows else None
    source_grammar_summary_rows = (
        read_rows(source_grammar_summary_path) if source_grammar_summary_path.exists() else []
    )
    source_grammar_summary = source_grammar_summary_rows[0] if source_grammar_summary_rows else None
    value_context_summary_rows = read_rows(value_context_summary_path) if value_context_summary_path.exists() else []
    value_context_summary = value_context_summary_rows[0] if value_context_summary_rows else None
    context_rules_summary_rows = read_rows(context_rules_summary_path) if context_rules_summary_path.exists() else []
    context_rules_summary = context_rules_summary_rows[0] if context_rules_summary_rows else None
    sequence_summary_rows = read_rows(sequence_summary_path) if sequence_summary_path.exists() else []
    sequence_summary = sequence_summary_rows[0] if sequence_summary_rows else None
    alternation_summary_rows = read_rows(alternation_summary_path) if alternation_summary_path.exists() else []
    alternation_summary = alternation_summary_rows[0] if alternation_summary_rows else None
    alternation_replay_summary_rows = (
        read_rows(alternation_replay_summary_path) if alternation_replay_summary_path.exists() else []
    )
    alternation_replay_summary = alternation_replay_summary_rows[0] if alternation_replay_summary_rows else None
    length_sequence_summary_rows = read_rows(length_sequence_summary_path) if length_sequence_summary_path.exists() else []
    length_sequence_summary = length_sequence_summary_rows[0] if length_sequence_summary_rows else None
    length_control_summary_rows = read_rows(length_control_summary_path) if length_control_summary_path.exists() else []
    length_control_summary = length_control_summary_rows[0] if length_control_summary_rows else None
    length_opcode_summary_rows = read_rows(length_opcode_summary_path) if length_opcode_summary_path.exists() else []
    length_opcode_summary = length_opcode_summary_rows[0] if length_opcode_summary_rows else None
    length_interval_summary_rows = read_rows(length_interval_summary_path) if length_interval_summary_path.exists() else []
    length_interval_summary = length_interval_summary_rows[0] if length_interval_summary_rows else None
    decision = build_stable_walk_decision(
        summary_rows[0],
        read_rows(groups_path),
        backref_summary,
        source_summary,
        source_grammar_summary,
        value_context_summary,
        context_rules_summary,
        sequence_summary,
        alternation_summary,
        alternation_replay_summary,
        length_sequence_summary,
        length_control_summary,
        length_opcode_summary,
        length_interval_summary,
    )
    if decision is None:
        return decisions
    return [*decisions, decision]


def build_summary(queue: list[dict[str, object]], review_summary: dict[str, str]) -> dict[str, object]:
    tracks = Counter(str(row["track"]) for row in queue)
    bytes_by_track = Counter()
    for row in queue:
        bytes_by_track[str(row["track"])] += int(row["bytes"])
    top = queue[0] if queue else {}
    blocked = [row for row in queue if row["status"] == "blocked_review"]
    top_track = bytes_by_track.most_common(1)[0][0] if bytes_by_track else ""
    return {
        "scope": "total",
        "decision_rows": len(queue),
        "total_bytes": sum(int(row["bytes"]) for row in queue),
        "promotion_ready_bytes": sum(int(row["promotion_ready_bytes"]) for row in queue),
        "blocked_rows": len(blocked),
        "blocked_bytes": sum(int(row["bytes"]) for row in blocked),
        "tracks": json.dumps(dict(sorted(tracks.items())), sort_keys=True),
        "top_track": top_track,
        "top_surface": top.get("surface", ""),
        "top_action": top.get("next_action", ""),
        "issue_rows": review_summary.get("issue_rows", "0"),
    }


def render_table(rows: list[dict[str, object]]) -> str:
    body = []
    for row in rows:
        body.append(
            "<tr>"
            f"<td>{html.escape(str(row['priority']))}</td>"
            f"<td>{html.escape(str(row['track']))}</td>"
            f"<td>{html.escape(str(row['surface']))}</td>"
            f"<td>{html.escape(str(row['bytes']))}</td>"
            f"<td>{html.escape(str(row['signal_score']))}</td>"
            f"<td>{html.escape(str(row['status']))}</td>"
            f"<td>{html.escape(str(row['next_action']))}</td>"
            "</tr>"
        )
    return "\n".join(body)


def build_html(summary: dict[str, object], queue: list[dict[str, object]], title: str) -> str:
    data_json = json.dumps({"summary": summary, "queue": queue}, indent=2, sort_keys=True)
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #111; color: #eee; }}
a {{ color: #8bd3ff; }}
table {{ border-collapse: collapse; width: 100%; background: #181818; }}
th, td {{ border: 1px solid #333; padding: .45rem .55rem; vertical-align: top; }}
th {{ background: #222; text-align: left; }}
.metric {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: .75rem; margin: 1rem 0; }}
.box {{ background: #181818; border: 1px solid #333; padding: .75rem; }}
.num {{ font-size: 1.4rem; font-weight: 700; }}
.muted {{ color: #aaa; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="metric">
  <div class="box"><div class="num">{html.escape(str(summary['decision_rows']))}</div><div class="muted">decisions</div></div>
  <div class="box"><div class="num">{html.escape(str(summary['total_bytes']))}</div><div class="muted">bytes revus</div></div>
  <div class="box"><div class="num">{html.escape(str(summary['promotion_ready_bytes']))}</div><div class="muted">bytes promotables</div></div>
  <div class="box"><div class="num">{html.escape(str(summary['blocked_rows']))}</div><div class="muted">lignes bloquees</div></div>
  <div class="box"><div class="num">{html.escape(str(summary['top_track']))}</div><div class="muted">piste dominante</div></div>
</div>
<p>Prochaine action: <strong>{html.escape(str(summary['top_action']))}</strong></p>
<table>
<thead>
<tr><th>#</th><th>Piste</th><th>Surface</th><th>Bytes</th><th>Signal</th><th>Etat</th><th>Action</th></tr>
</thead>
<tbody>
{render_table(queue)}
</tbody>
</table>
<script type="application/json" id="roadmap-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a prioritized .tex decoder roadmap.")
    parser.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)
    parser.add_argument("--review-summary", type=Path, default=DEFAULT_REVIEW_SUMMARY)
    parser.add_argument("--stable-walks-summary", type=Path, default=DEFAULT_STABLE_WALKS_SUMMARY)
    parser.add_argument("--stable-walks-groups", type=Path, default=DEFAULT_STABLE_WALKS_GROUPS)
    parser.add_argument("--stable-backrefs-summary", type=Path, default=DEFAULT_STABLE_BACKREFS_SUMMARY)
    parser.add_argument("--stable-sources-summary", type=Path, default=DEFAULT_STABLE_SOURCES_SUMMARY)
    parser.add_argument("--stable-source-grammar-summary", type=Path, default=DEFAULT_STABLE_SOURCE_GRAMMAR_SUMMARY)
    parser.add_argument("--stable-value-context-summary", type=Path, default=DEFAULT_STABLE_VALUE_CONTEXT_SUMMARY)
    parser.add_argument("--stable-context-rules-summary", type=Path, default=DEFAULT_STABLE_CONTEXT_RULES_SUMMARY)
    parser.add_argument("--stable-sequences-summary", type=Path, default=DEFAULT_STABLE_SEQUENCES_SUMMARY)
    parser.add_argument("--stable-alternation-summary", type=Path, default=DEFAULT_STABLE_ALTERNATION_SUMMARY)
    parser.add_argument(
        "--stable-alternation-replay-summary",
        type=Path,
        default=DEFAULT_STABLE_ALTERNATION_REPLAY_SUMMARY,
    )
    parser.add_argument("--stable-length-sequence-summary", type=Path, default=DEFAULT_STABLE_LENGTH_SEQUENCE_SUMMARY)
    parser.add_argument("--stable-length-control-summary", type=Path, default=DEFAULT_STABLE_LENGTH_CONTROL_SUMMARY)
    parser.add_argument("--stable-length-opcode-summary", type=Path, default=DEFAULT_STABLE_LENGTH_OPCODE_SUMMARY)
    parser.add_argument("--stable-length-interval-summary", type=Path, default=DEFAULT_STABLE_LENGTH_INTERVAL_SUMMARY)
    parser.add_argument("--flat-walk-backref-summary", type=Path, default=DEFAULT_FLAT_WALK_BACKREF_SUMMARY)
    parser.add_argument(
        "--flat-walk-backref-chain-summary",
        type=Path,
        default=DEFAULT_FLAT_WALK_BACKREF_CHAIN_SUMMARY,
    )
    parser.add_argument(
        "--flat-walk-palette-context-summary",
        type=Path,
        default=DEFAULT_FLAT_WALK_PALETTE_CONTEXT_SUMMARY,
    )
    parser.add_argument(
        "--flat-walk-palette-normalized-context-summary",
        type=Path,
        default=DEFAULT_FLAT_WALK_PALETTE_NORMALIZED_CONTEXT_SUMMARY,
    )
    parser.add_argument(
        "--flat-walk-palette-value-split-summary",
        type=Path,
        default=DEFAULT_FLAT_WALK_PALETTE_VALUE_SPLIT_SUMMARY,
    )
    parser.add_argument(
        "--flat-walk-palette-value-table-summary",
        type=Path,
        default=DEFAULT_FLAT_WALK_PALETTE_VALUE_TABLE_SUMMARY,
    )
    parser.add_argument(
        "--flat-walk-palette-compressed-selector-summary",
        type=Path,
        default=DEFAULT_FLAT_WALK_PALETTE_COMPRESSED_SELECTOR_SUMMARY,
    )
    parser.add_argument(
        "--flat-walk-palette-compressed-combo-summary",
        type=Path,
        default=DEFAULT_FLAT_WALK_PALETTE_COMPRESSED_COMBO_SUMMARY,
    )
    parser.add_argument(
        "--flat-walk-palette-compressed-formula-summary",
        type=Path,
        default=DEFAULT_FLAT_WALK_PALETTE_COMPRESSED_FORMULA_SUMMARY,
    )
    parser.add_argument(
        "--flat-walk-palette-corpus-formula-summary",
        type=Path,
        default=DEFAULT_FLAT_WALK_PALETTE_CORPUS_FORMULA_SUMMARY,
    )
    parser.add_argument(
        "--flat-walk-palette-promotion-candidate-summary",
        type=Path,
        default=DEFAULT_FLAT_WALK_PALETTE_PROMOTION_CANDIDATE_SUMMARY,
    )
    parser.add_argument(
        "--flat-walk-palette-formula-replay-summary",
        type=Path,
        default=DEFAULT_FLAT_WALK_PALETTE_FORMULA_REPLAY_SUMMARY,
    )
    parser.add_argument(
        "--flat-walk-palette-post-formula-vertical-copy-summary",
        type=Path,
        default=DEFAULT_FLAT_WALK_PALETTE_POST_FORMULA_VERTICAL_COPY_SUMMARY,
    )
    parser.add_argument(
        "--gradient-shape-peer-copy-summary",
        type=Path,
        default=DEFAULT_GRADIENT_SHAPE_PEER_COPY_SUMMARY,
    )
    parser.add_argument(
        "--gradient-source-profile-high-low-summary",
        type=Path,
        default=DEFAULT_GRADIENT_SOURCE_PROFILE_HIGH_LOW_SUMMARY,
    )
    parser.add_argument(
        "--gradient-source-profile-high-safe-low-summary",
        type=Path,
        default=DEFAULT_GRADIENT_SOURCE_PROFILE_HIGH_SAFE_LOW_SUMMARY,
    )
    parser.add_argument(
        "--gradient-payload-profile-summary",
        type=Path,
        default=DEFAULT_GRADIENT_PAYLOAD_PROFILE_SUMMARY,
    )
    parser.add_argument(
        "--gradient-payload-state-opcode-summary",
        type=Path,
        default=DEFAULT_GRADIENT_PAYLOAD_STATE_OPCODE_SUMMARY,
    )
    parser.add_argument(
        "--gradient-macro-opcode-summary",
        type=Path,
        default=DEFAULT_GRADIENT_MACRO_OPCODE_SUMMARY,
    )
    parser.add_argument(
        "--gradient-macro-conflict-split-summary",
        type=Path,
        default=DEFAULT_GRADIENT_MACRO_CONFLICT_SPLIT_SUMMARY,
    )
    parser.add_argument(
        "--gradient-macro-residual-state-summary",
        type=Path,
        default=DEFAULT_GRADIENT_MACRO_RESIDUAL_STATE_SUMMARY,
    )
    parser.add_argument(
        "--gradient-macro-phase-summary",
        type=Path,
        default=DEFAULT_GRADIENT_MACRO_PHASE_SUMMARY,
    )
    parser.add_argument(
        "--gradient-macro-phase-conflict-split-summary",
        type=Path,
        default=DEFAULT_GRADIENT_MACRO_PHASE_CONFLICT_SPLIT_SUMMARY,
    )
    parser.add_argument(
        "--gradient-macro-phase-sequence-summary",
        type=Path,
        default=DEFAULT_GRADIENT_MACRO_PHASE_SEQUENCE_SUMMARY,
    )
    parser.add_argument(
        "--gradient-macro-fixture-transition-summary",
        type=Path,
        default=DEFAULT_GRADIENT_MACRO_FIXTURE_TRANSITION_SUMMARY,
    )
    parser.add_argument(
        "--gradient-macro-state-cluster-summary",
        type=Path,
        default=DEFAULT_GRADIENT_MACRO_STATE_CLUSTER_SUMMARY,
    )
    parser.add_argument(
        "--gradient-macro-source-profile-state-summary",
        type=Path,
        default=DEFAULT_GRADIENT_MACRO_SOURCE_PROFILE_STATE_SUMMARY,
    )
    parser.add_argument(
        "--gradient-seed-delta-payload-opcode-summary",
        type=Path,
        default=DEFAULT_GRADIENT_SEED_DELTA_PAYLOAD_OPCODE_SUMMARY,
    )
    parser.add_argument(
        "--gradient-nonlocal-known-spatial-summary",
        type=Path,
        default=DEFAULT_GRADIENT_NONLOCAL_KNOWN_SPATIAL_SUMMARY,
    )
    parser.add_argument(
        "--gradient-sequence-known-state-summary",
        type=Path,
        default=DEFAULT_GRADIENT_SEQUENCE_KNOWN_STATE_SUMMARY,
    )
    parser.add_argument(
        "--gradient-sequence-high-safe-low-summary",
        type=Path,
        default=DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_SUMMARY,
    )
    parser.add_argument(
        "--gradient-sequence-high-safe-source-profile-low-summary",
        type=Path,
        default=DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_SOURCE_PROFILE_LOW_SUMMARY,
    )
    parser.add_argument(
        "--gradient-sequence-high-safe-row-corpus-low-summary",
        type=Path,
        default=DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_ROW_CORPUS_LOW_SUMMARY,
    )
    parser.add_argument(
        "--gradient-sequence-high-safe-transform-low-summary",
        type=Path,
        default=DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_TRANSFORM_LOW_SUMMARY,
    )
    parser.add_argument(
        "--gradient-sequence-high-safe-source-window-summary",
        type=Path,
        default=DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_SOURCE_WINDOW_SUMMARY,
    )
    parser.add_argument(
        "--gradient-sequence-high-safe-control-opcode-summary",
        type=Path,
        default=DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_CONTROL_OPCODE_SUMMARY,
    )
    parser.add_argument(
        "--gradient-sequence-high-safe-row-transition-summary",
        type=Path,
        default=DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_ROW_TRANSITION_SUMMARY,
    )
    parser.add_argument(
        "--gradient-sequence-high-safe-row-markov-summary",
        type=Path,
        default=DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_ROW_MARKOV_SUMMARY,
    )
    parser.add_argument(
        "--gradient-sequence-high-safe-row-template-summary",
        type=Path,
        default=DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_ROW_TEMPLATE_SUMMARY,
    )
    parser.add_argument(
        "--gradient-sequence-high-safe-low-bucket-split-summary",
        type=Path,
        default=DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_BUCKET_SPLIT_SUMMARY,
    )
    parser.add_argument(
        "--gradient-sequence-high-safe-low-exception-summary",
        type=Path,
        default=DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_SUMMARY,
    )
    parser.add_argument(
        "--gradient-sequence-high-safe-low-exception-alignment-summary",
        type=Path,
        default=DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_ALIGNMENT_SUMMARY,
    )
    parser.add_argument(
        "--gradient-sequence-high-safe-low-exception-alignment-review-summary",
        type=Path,
        default=DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_ALIGNMENT_REVIEW_SUMMARY,
    )
    parser.add_argument(
        "--gradient-sequence-high-safe-low-exception-row-family-summary",
        type=Path,
        default=DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_ROW_FAMILY_SUMMARY,
    )
    parser.add_argument(
        "--gradient-sequence-high-safe-low-exception-external-state-summary",
        type=Path,
        default=DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_EXTERNAL_STATE_SUMMARY,
    )
    parser.add_argument(
        "--gradient-sequence-high-safe-low-exception-prerequisite-state-summary",
        type=Path,
        default=DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_PREREQUISITE_STATE_SUMMARY,
    )
    parser.add_argument(
        "--gradient-sequence-high-safe-low-exception-source-dependency-summary",
        type=Path,
        default=DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_SOURCE_DEPENDENCY_SUMMARY,
    )
    parser.add_argument(
        "--gradient-sequence-high-safe-low-exception-source-chain-summary",
        type=Path,
        default=DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_SOURCE_CHAIN_SUMMARY,
    )
    parser.add_argument(
        "--gradient-sequence-high-safe-low-exception-source-terminal-summary",
        type=Path,
        default=DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_SOURCE_TERMINAL_SUMMARY,
    )
    parser.add_argument(
        "--gradient-sequence-high-safe-low-exception-source-terminal-review-summary",
        type=Path,
        default=DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_SOURCE_TERMINAL_REVIEW_SUMMARY,
    )
    parser.add_argument(
        "--gradient-sequence-high-safe-low-exception-source-terminal-delta-summary",
        type=Path,
        default=DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_SOURCE_TERMINAL_DELTA_SUMMARY,
    )
    parser.add_argument(
        "--gradient-sequence-high-safe-low-exception-source-terminal-chain-context-summary",
        type=Path,
        default=DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_SOURCE_TERMINAL_CHAIN_CONTEXT_SUMMARY,
    )
    parser.add_argument(
        "--gradient-sequence-high-safe-low-exception-source-terminal-replay-support-summary",
        type=Path,
        default=DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_SOURCE_TERMINAL_REPLAY_SUPPORT_SUMMARY,
    )
    parser.add_argument(
        "--gradient-sequence-high-safe-low-exception-source-terminal-replay-union-summary",
        type=Path,
        default=DEFAULT_GRADIENT_SEQUENCE_HIGH_SAFE_LOW_EXCEPTION_SOURCE_TERMINAL_REPLAY_UNION_SUMMARY,
    )
    parser.add_argument(
        "--gradient-macro-state-cluster-payload-summary",
        type=Path,
        default=DEFAULT_GRADIENT_MACRO_STATE_CLUSTER_PAYLOAD_SUMMARY,
    )
    parser.add_argument(
        "--gradient-macro-state-cluster-source-summary",
        type=Path,
        default=DEFAULT_GRADIENT_MACRO_STATE_CLUSTER_SOURCE_SUMMARY,
    )
    parser.add_argument(
        "--gradient-macro-state-cluster-literal-summary",
        type=Path,
        default=DEFAULT_GRADIENT_MACRO_STATE_CLUSTER_LITERAL_SUMMARY,
    )
    parser.add_argument(
        "--gradient-macro-state-cluster-backref-summary",
        type=Path,
        default=DEFAULT_GRADIENT_MACRO_STATE_CLUSTER_BACKREF_SUMMARY,
    )
    parser.add_argument(
        "--micro-jump-mixed-payload-summary",
        type=Path,
        default=DEFAULT_MICRO_JUMP_MIXED_PAYLOAD_SUMMARY,
    )
    parser.add_argument(
        "--jump-token-payload-profile-summary",
        type=Path,
        default=DEFAULT_JUMP_TOKEN_PAYLOAD_PROFILE_SUMMARY,
    )
    parser.add_argument(
        "--jump-token-payload-state-opcode-summary",
        type=Path,
        default=DEFAULT_JUMP_TOKEN_PAYLOAD_STATE_OPCODE_SUMMARY,
    )
    parser.add_argument("--micro-token-family-split-summary", type=Path, default=DEFAULT_MICRO_TOKEN_FAMILY_SPLIT_SUMMARY)
    parser.add_argument(
        "--micro-mixed-value-subfamily-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_SUBFAMILY_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-dominant-control-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_DOMINANT_CONTROL_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-local-grammar-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_LOCAL_GRAMMAR_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-predictor-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_PREDICTOR_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-combo-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_COMBO_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-high-low-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_HIGH_LOW_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-source-profile-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SOURCE_PROFILE_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-external-source-combo-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_EXTERNAL_SOURCE_COMBO_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-external-high-low-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_EXTERNAL_HIGH_LOW_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-state-external-combo-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_STATE_EXTERNAL_COMBO_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-state-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_STATE_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-candidate-review-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_CANDIDATE_REVIEW_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-prefix-bootstrap-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_PREFIX_BOOTSTRAP_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-prefix-sequence-replay-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_PREFIX_SEQUENCE_REPLAY_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-prefix-sequence-promoted-replay-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_PREFIX_SEQUENCE_PROMOTED_REPLAY_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-promoted-generalization-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PROMOTED_GENERALIZATION_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-low-split-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_LOW_SPLIT_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-low-split-promoted-replay-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_LOW_SPLIT_PROMOTED_REPLAY_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-expansion-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_EXPANSION_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-expansion-promoted-replay-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_EXPANSION_PROMOTED_REPLAY_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-low-split-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_LOW_SPLIT_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-low-split-promoted-replay-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_LOW_SPLIT_PROMOTED_REPLAY_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-low-split-generalization-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_LOW_SPLIT_GENERALIZATION_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-second-low-split-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_SECOND_LOW_SPLIT_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-second-expansion-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_SECOND_EXPANSION_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-corpus-expansion-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_CORPUS_EXPANSION_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-corpus-expansion-promoted-replay-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_CORPUS_EXPANSION_PROMOTED_REPLAY_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-corpus-low-split-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_CORPUS_LOW_SPLIT_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-corpus-low-split-promoted-replay-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_CORPUS_LOW_SPLIT_PROMOTED_REPLAY_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-corpus-second-low-split-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_CORPUS_SECOND_LOW_SPLIT_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-corpus-second-low-split-promoted-replay-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_CORPUS_SECOND_LOW_SPLIT_PROMOTED_REPLAY_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-adjacent-known-third-promoted-replay-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_THIRD_PROMOTED_REPLAY_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-adjacent-known-generalization-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_GENERALIZATION_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-adjacent-known-low-split-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_LOW_SPLIT_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-adjacent-known-corpus-expansion-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_CORPUS_EXPANSION_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-adjacent-known-fourth-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_FOURTH_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-adjacent-known-transform-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_TRANSFORM_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-adjacent-known-transform-promoted-replay-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_TRANSFORM_PROMOTED_REPLAY_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-adjacent-known-transform-generalization-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_TRANSFORM_GENERALIZATION_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-adjacent-known-transform-second-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_TRANSFORM_SECOND_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-adjacent-known-transform-low-split-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_TRANSFORM_LOW_SPLIT_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-adjacent-known-transform-corpus-expansion-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_TRANSFORM_CORPUS_EXPANSION_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-adjacent-known-transform-adjacent-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_TRANSFORM_ADJACENT_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-adjacent-known-transform-corpus-third-promoted-replay-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_TRANSFORM_CORPUS_THIRD_PROMOTED_REPLAY_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-adjacent-known-transform-corpus-third-generalization-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_TRANSFORM_CORPUS_THIRD_GENERALIZATION_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-adjacent-known-transform-corpus-fourth-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_TRANSFORM_CORPUS_FOURTH_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-adjacent-known-transform-corpus-third-low-split-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_TRANSFORM_CORPUS_THIRD_LOW_SPLIT_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-adjacent-known-transform-corpus-third-corpus-expansion-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_TRANSFORM_CORPUS_THIRD_CORPUS_EXPANSION_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-prerequisite-adjacent-known-transform-corpus-third-adjacent-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_PREREQUISITE_ADJACENT_KNOWN_TRANSFORM_CORPUS_THIRD_ADJACENT_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-low-copy-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_LOW_COPY_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-low-copy-promoted-replay-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_LOW_COPY_PROMOTED_REPLAY_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-low-copy-generalization-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_LOW_COPY_GENERALIZATION_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-low-copy-second-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_LOW_COPY_SECOND_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-low-copy-low-split-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_LOW_COPY_LOW_SPLIT_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-low-copy-corpus-expansion-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_LOW_COPY_CORPUS_EXPANSION_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-low-copy-adjacent-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_LOW_COPY_ADJACENT_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-sequence-blocked-prerequisite-role-transform-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SEQUENCE_BLOCKED_PREREQUISITE_ROLE_TRANSFORM_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-spatial-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SPATIAL_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-state-opcode-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_STATE_OPCODE_SUMMARY,
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Decoder Roadmap")
    args = parser.parse_args()

    decisions = append_optional_stable_walk_decision(
        read_rows(args.decisions),
        args.stable_walks_summary,
        args.stable_walks_groups,
        args.stable_backrefs_summary,
        args.stable_sources_summary,
        args.stable_source_grammar_summary,
        args.stable_value_context_summary,
        args.stable_context_rules_summary,
        args.stable_sequences_summary,
        args.stable_alternation_summary,
        args.stable_alternation_replay_summary,
        args.stable_length_sequence_summary,
        args.stable_length_control_summary,
        args.stable_length_opcode_summary,
        args.stable_length_interval_summary,
    )
    review_summary = read_rows(args.review_summary)[0]
    gradient_payload_profile_rows = (
        read_rows(args.gradient_payload_profile_summary)
        if args.gradient_payload_profile_summary.exists()
        else []
    )
    gradient_payload_profile_summary = gradient_payload_profile_rows[0] if gradient_payload_profile_rows else None
    gradient_payload_state_opcode_rows = (
        read_rows(args.gradient_payload_state_opcode_summary)
        if args.gradient_payload_state_opcode_summary.exists()
        else []
    )
    gradient_payload_state_opcode_summary = (
        gradient_payload_state_opcode_rows[0] if gradient_payload_state_opcode_rows else None
    )
    gradient_macro_opcode_rows = (
        read_rows(args.gradient_macro_opcode_summary)
        if args.gradient_macro_opcode_summary.exists()
        else []
    )
    gradient_macro_opcode_summary = gradient_macro_opcode_rows[0] if gradient_macro_opcode_rows else None
    gradient_macro_conflict_split_rows = (
        read_rows(args.gradient_macro_conflict_split_summary)
        if args.gradient_macro_conflict_split_summary.exists()
        else []
    )
    gradient_macro_conflict_split_summary = (
        gradient_macro_conflict_split_rows[0] if gradient_macro_conflict_split_rows else None
    )
    gradient_macro_residual_state_rows = (
        read_rows(args.gradient_macro_residual_state_summary)
        if args.gradient_macro_residual_state_summary.exists()
        else []
    )
    gradient_macro_residual_state_summary = (
        gradient_macro_residual_state_rows[0] if gradient_macro_residual_state_rows else None
    )
    gradient_macro_phase_rows = (
        read_rows(args.gradient_macro_phase_summary) if args.gradient_macro_phase_summary.exists() else []
    )
    gradient_macro_phase_summary = gradient_macro_phase_rows[0] if gradient_macro_phase_rows else None
    gradient_macro_phase_conflict_split_rows = (
        read_rows(args.gradient_macro_phase_conflict_split_summary)
        if args.gradient_macro_phase_conflict_split_summary.exists()
        else []
    )
    gradient_macro_phase_conflict_split_summary = (
        gradient_macro_phase_conflict_split_rows[0] if gradient_macro_phase_conflict_split_rows else None
    )
    gradient_macro_phase_sequence_rows = (
        read_rows(args.gradient_macro_phase_sequence_summary)
        if args.gradient_macro_phase_sequence_summary.exists()
        else []
    )
    gradient_macro_phase_sequence_summary = (
        gradient_macro_phase_sequence_rows[0] if gradient_macro_phase_sequence_rows else None
    )
    gradient_macro_fixture_transition_rows = (
        read_rows(args.gradient_macro_fixture_transition_summary)
        if args.gradient_macro_fixture_transition_summary.exists()
        else []
    )
    gradient_macro_fixture_transition_summary = (
        gradient_macro_fixture_transition_rows[0] if gradient_macro_fixture_transition_rows else None
    )
    gradient_macro_state_cluster_rows = (
        read_rows(args.gradient_macro_state_cluster_summary)
        if args.gradient_macro_state_cluster_summary.exists()
        else []
    )
    gradient_macro_state_cluster_summary = (
        gradient_macro_state_cluster_rows[0] if gradient_macro_state_cluster_rows else None
    )
    gradient_macro_source_profile_state_rows = (
        read_rows(args.gradient_macro_source_profile_state_summary)
        if args.gradient_macro_source_profile_state_summary.exists()
        else []
    )
    gradient_macro_source_profile_state_summary = (
        gradient_macro_source_profile_state_rows[0]
        if gradient_macro_source_profile_state_rows
        else None
    )
    gradient_seed_delta_payload_opcode_rows = (
        read_rows(args.gradient_seed_delta_payload_opcode_summary)
        if args.gradient_seed_delta_payload_opcode_summary.exists()
        else []
    )
    gradient_seed_delta_payload_opcode_summary = (
        gradient_seed_delta_payload_opcode_rows[0]
        if gradient_seed_delta_payload_opcode_rows
        else None
    )
    gradient_nonlocal_known_spatial_rows = (
        read_rows(args.gradient_nonlocal_known_spatial_summary)
        if args.gradient_nonlocal_known_spatial_summary.exists()
        else []
    )
    gradient_nonlocal_known_spatial_summary = (
        gradient_nonlocal_known_spatial_rows[0]
        if gradient_nonlocal_known_spatial_rows
        else None
    )
    gradient_sequence_known_state_rows = (
        read_rows(args.gradient_sequence_known_state_summary)
        if args.gradient_sequence_known_state_summary.exists()
        else []
    )
    gradient_sequence_known_state_summary = (
        gradient_sequence_known_state_rows[0]
        if gradient_sequence_known_state_rows
        else None
    )
    gradient_sequence_high_safe_low_rows = (
        read_rows(args.gradient_sequence_high_safe_low_summary)
        if args.gradient_sequence_high_safe_low_summary.exists()
        else []
    )
    gradient_sequence_high_safe_low_summary = (
        gradient_sequence_high_safe_low_rows[0]
        if gradient_sequence_high_safe_low_rows
        else None
    )
    gradient_sequence_high_safe_source_profile_low_rows = (
        read_rows(args.gradient_sequence_high_safe_source_profile_low_summary)
        if args.gradient_sequence_high_safe_source_profile_low_summary.exists()
        else []
    )
    gradient_sequence_high_safe_source_profile_low_summary = (
        gradient_sequence_high_safe_source_profile_low_rows[0]
        if gradient_sequence_high_safe_source_profile_low_rows
        else None
    )
    gradient_sequence_high_safe_row_corpus_low_rows = (
        read_rows(args.gradient_sequence_high_safe_row_corpus_low_summary)
        if args.gradient_sequence_high_safe_row_corpus_low_summary.exists()
        else []
    )
    gradient_sequence_high_safe_row_corpus_low_summary = (
        gradient_sequence_high_safe_row_corpus_low_rows[0]
        if gradient_sequence_high_safe_row_corpus_low_rows
        else None
    )
    gradient_sequence_high_safe_transform_low_rows = (
        read_rows(args.gradient_sequence_high_safe_transform_low_summary)
        if args.gradient_sequence_high_safe_transform_low_summary.exists()
        else []
    )
    gradient_sequence_high_safe_transform_low_summary = (
        gradient_sequence_high_safe_transform_low_rows[0]
        if gradient_sequence_high_safe_transform_low_rows
        else None
    )
    gradient_sequence_high_safe_source_window_rows = (
        read_rows(args.gradient_sequence_high_safe_source_window_summary)
        if args.gradient_sequence_high_safe_source_window_summary.exists()
        else []
    )
    gradient_sequence_high_safe_source_window_summary = (
        gradient_sequence_high_safe_source_window_rows[0]
        if gradient_sequence_high_safe_source_window_rows
        else None
    )
    gradient_sequence_high_safe_control_opcode_rows = (
        read_rows(args.gradient_sequence_high_safe_control_opcode_summary)
        if args.gradient_sequence_high_safe_control_opcode_summary.exists()
        else []
    )
    gradient_sequence_high_safe_control_opcode_summary = (
        gradient_sequence_high_safe_control_opcode_rows[0]
        if gradient_sequence_high_safe_control_opcode_rows
        else None
    )
    gradient_sequence_high_safe_row_transition_rows = (
        read_rows(args.gradient_sequence_high_safe_row_transition_summary)
        if args.gradient_sequence_high_safe_row_transition_summary.exists()
        else []
    )
    gradient_sequence_high_safe_row_transition_summary = (
        gradient_sequence_high_safe_row_transition_rows[0]
        if gradient_sequence_high_safe_row_transition_rows
        else None
    )
    gradient_sequence_high_safe_row_markov_rows = (
        read_rows(args.gradient_sequence_high_safe_row_markov_summary)
        if args.gradient_sequence_high_safe_row_markov_summary.exists()
        else []
    )
    gradient_sequence_high_safe_row_markov_summary = (
        gradient_sequence_high_safe_row_markov_rows[0]
        if gradient_sequence_high_safe_row_markov_rows
        else None
    )
    gradient_sequence_high_safe_row_template_rows = (
        read_rows(args.gradient_sequence_high_safe_row_template_summary)
        if args.gradient_sequence_high_safe_row_template_summary.exists()
        else []
    )
    gradient_sequence_high_safe_row_template_summary = (
        gradient_sequence_high_safe_row_template_rows[0]
        if gradient_sequence_high_safe_row_template_rows
        else None
    )
    gradient_sequence_high_safe_low_bucket_split_rows = (
        read_rows(args.gradient_sequence_high_safe_low_bucket_split_summary)
        if args.gradient_sequence_high_safe_low_bucket_split_summary.exists()
        else []
    )
    gradient_sequence_high_safe_low_bucket_split_summary = (
        gradient_sequence_high_safe_low_bucket_split_rows[0]
        if gradient_sequence_high_safe_low_bucket_split_rows
        else None
    )
    gradient_sequence_high_safe_low_exception_rows = (
        read_rows(args.gradient_sequence_high_safe_low_exception_summary)
        if args.gradient_sequence_high_safe_low_exception_summary.exists()
        else []
    )
    gradient_sequence_high_safe_low_exception_summary = (
        gradient_sequence_high_safe_low_exception_rows[0]
        if gradient_sequence_high_safe_low_exception_rows
        else None
    )
    gradient_sequence_high_safe_low_exception_alignment_rows = (
        read_rows(args.gradient_sequence_high_safe_low_exception_alignment_summary)
        if args.gradient_sequence_high_safe_low_exception_alignment_summary.exists()
        else []
    )
    gradient_sequence_high_safe_low_exception_alignment_summary = (
        gradient_sequence_high_safe_low_exception_alignment_rows[0]
        if gradient_sequence_high_safe_low_exception_alignment_rows
        else None
    )
    gradient_sequence_high_safe_low_exception_alignment_review_rows = (
        read_rows(args.gradient_sequence_high_safe_low_exception_alignment_review_summary)
        if args.gradient_sequence_high_safe_low_exception_alignment_review_summary.exists()
        else []
    )
    gradient_sequence_high_safe_low_exception_alignment_review_summary = (
        gradient_sequence_high_safe_low_exception_alignment_review_rows[0]
        if gradient_sequence_high_safe_low_exception_alignment_review_rows
        else None
    )
    gradient_sequence_high_safe_low_exception_row_family_rows = (
        read_rows(args.gradient_sequence_high_safe_low_exception_row_family_summary)
        if args.gradient_sequence_high_safe_low_exception_row_family_summary.exists()
        else []
    )
    gradient_sequence_high_safe_low_exception_row_family_summary = (
        gradient_sequence_high_safe_low_exception_row_family_rows[0]
        if gradient_sequence_high_safe_low_exception_row_family_rows
        else None
    )
    gradient_sequence_high_safe_low_exception_external_state_rows = (
        read_rows(args.gradient_sequence_high_safe_low_exception_external_state_summary)
        if args.gradient_sequence_high_safe_low_exception_external_state_summary.exists()
        else []
    )
    gradient_sequence_high_safe_low_exception_external_state_summary = (
        gradient_sequence_high_safe_low_exception_external_state_rows[0]
        if gradient_sequence_high_safe_low_exception_external_state_rows
        else None
    )
    gradient_sequence_high_safe_low_exception_prerequisite_state_rows = (
        read_rows(args.gradient_sequence_high_safe_low_exception_prerequisite_state_summary)
        if args.gradient_sequence_high_safe_low_exception_prerequisite_state_summary.exists()
        else []
    )
    gradient_sequence_high_safe_low_exception_prerequisite_state_summary = (
        gradient_sequence_high_safe_low_exception_prerequisite_state_rows[0]
        if gradient_sequence_high_safe_low_exception_prerequisite_state_rows
        else None
    )
    gradient_sequence_high_safe_low_exception_source_dependency_rows = (
        read_rows(args.gradient_sequence_high_safe_low_exception_source_dependency_summary)
        if args.gradient_sequence_high_safe_low_exception_source_dependency_summary.exists()
        else []
    )
    gradient_sequence_high_safe_low_exception_source_dependency_summary = (
        gradient_sequence_high_safe_low_exception_source_dependency_rows[0]
        if gradient_sequence_high_safe_low_exception_source_dependency_rows
        else None
    )
    gradient_sequence_high_safe_low_exception_source_chain_rows = (
        read_rows(args.gradient_sequence_high_safe_low_exception_source_chain_summary)
        if args.gradient_sequence_high_safe_low_exception_source_chain_summary.exists()
        else []
    )
    gradient_sequence_high_safe_low_exception_source_chain_summary = (
        gradient_sequence_high_safe_low_exception_source_chain_rows[0]
        if gradient_sequence_high_safe_low_exception_source_chain_rows
        else None
    )
    gradient_sequence_high_safe_low_exception_source_terminal_rows = (
        read_rows(args.gradient_sequence_high_safe_low_exception_source_terminal_summary)
        if args.gradient_sequence_high_safe_low_exception_source_terminal_summary.exists()
        else []
    )
    gradient_sequence_high_safe_low_exception_source_terminal_summary = (
        gradient_sequence_high_safe_low_exception_source_terminal_rows[0]
        if gradient_sequence_high_safe_low_exception_source_terminal_rows
        else None
    )
    gradient_sequence_high_safe_low_exception_source_terminal_review_rows = (
        read_rows(args.gradient_sequence_high_safe_low_exception_source_terminal_review_summary)
        if args.gradient_sequence_high_safe_low_exception_source_terminal_review_summary.exists()
        else []
    )
    gradient_sequence_high_safe_low_exception_source_terminal_review_summary = (
        gradient_sequence_high_safe_low_exception_source_terminal_review_rows[0]
        if gradient_sequence_high_safe_low_exception_source_terminal_review_rows
        else None
    )
    gradient_sequence_high_safe_low_exception_source_terminal_delta_rows = (
        read_rows(args.gradient_sequence_high_safe_low_exception_source_terminal_delta_summary)
        if args.gradient_sequence_high_safe_low_exception_source_terminal_delta_summary.exists()
        else []
    )
    gradient_sequence_high_safe_low_exception_source_terminal_delta_summary = (
        gradient_sequence_high_safe_low_exception_source_terminal_delta_rows[0]
        if gradient_sequence_high_safe_low_exception_source_terminal_delta_rows
        else None
    )
    gradient_sequence_high_safe_low_exception_source_terminal_chain_context_rows = (
        read_rows(args.gradient_sequence_high_safe_low_exception_source_terminal_chain_context_summary)
        if args.gradient_sequence_high_safe_low_exception_source_terminal_chain_context_summary.exists()
        else []
    )
    gradient_sequence_high_safe_low_exception_source_terminal_chain_context_summary = (
        gradient_sequence_high_safe_low_exception_source_terminal_chain_context_rows[0]
        if gradient_sequence_high_safe_low_exception_source_terminal_chain_context_rows
        else None
    )
    gradient_sequence_high_safe_low_exception_source_terminal_replay_support_rows = (
        read_rows(args.gradient_sequence_high_safe_low_exception_source_terminal_replay_support_summary)
        if args.gradient_sequence_high_safe_low_exception_source_terminal_replay_support_summary.exists()
        else []
    )
    gradient_sequence_high_safe_low_exception_source_terminal_replay_support_summary = (
        gradient_sequence_high_safe_low_exception_source_terminal_replay_support_rows[0]
        if gradient_sequence_high_safe_low_exception_source_terminal_replay_support_rows
        else None
    )
    gradient_sequence_high_safe_low_exception_source_terminal_replay_union_rows = (
        read_rows(args.gradient_sequence_high_safe_low_exception_source_terminal_replay_union_summary)
        if args.gradient_sequence_high_safe_low_exception_source_terminal_replay_union_summary.exists()
        else []
    )
    gradient_sequence_high_safe_low_exception_source_terminal_replay_union_summary = (
        gradient_sequence_high_safe_low_exception_source_terminal_replay_union_rows[0]
        if gradient_sequence_high_safe_low_exception_source_terminal_replay_union_rows
        else None
    )
    gradient_macro_state_cluster_payload_rows = (
        read_rows(args.gradient_macro_state_cluster_payload_summary)
        if args.gradient_macro_state_cluster_payload_summary.exists()
        else []
    )
    gradient_macro_state_cluster_payload_summary = (
        gradient_macro_state_cluster_payload_rows[0] if gradient_macro_state_cluster_payload_rows else None
    )
    gradient_macro_state_cluster_source_rows = (
        read_rows(args.gradient_macro_state_cluster_source_summary)
        if args.gradient_macro_state_cluster_source_summary.exists()
        else []
    )
    gradient_macro_state_cluster_source_summary = (
        gradient_macro_state_cluster_source_rows[0] if gradient_macro_state_cluster_source_rows else None
    )
    gradient_macro_state_cluster_literal_rows = (
        read_rows(args.gradient_macro_state_cluster_literal_summary)
        if args.gradient_macro_state_cluster_literal_summary.exists()
        else []
    )
    gradient_macro_state_cluster_literal_summary = (
        gradient_macro_state_cluster_literal_rows[0] if gradient_macro_state_cluster_literal_rows else None
    )
    gradient_macro_state_cluster_backref_rows = (
        read_rows(args.gradient_macro_state_cluster_backref_summary)
        if args.gradient_macro_state_cluster_backref_summary.exists()
        else []
    )
    gradient_macro_state_cluster_backref_summary = (
        gradient_macro_state_cluster_backref_rows[0] if gradient_macro_state_cluster_backref_rows else None
    )
    flat_walk_backref_rows = (
        read_rows(args.flat_walk_backref_summary) if args.flat_walk_backref_summary.exists() else []
    )
    flat_walk_backref_summary = flat_walk_backref_rows[0] if flat_walk_backref_rows else None
    flat_walk_backref_chain_rows = (
        read_rows(args.flat_walk_backref_chain_summary)
        if args.flat_walk_backref_chain_summary.exists()
        else []
    )
    flat_walk_backref_chain_summary = (
        flat_walk_backref_chain_rows[0] if flat_walk_backref_chain_rows else None
    )
    flat_walk_palette_context_rows = (
        read_rows(args.flat_walk_palette_context_summary)
        if args.flat_walk_palette_context_summary.exists()
        else []
    )
    flat_walk_palette_context_summary = (
        flat_walk_palette_context_rows[0] if flat_walk_palette_context_rows else None
    )
    flat_walk_palette_normalized_context_rows = (
        read_rows(args.flat_walk_palette_normalized_context_summary)
        if args.flat_walk_palette_normalized_context_summary.exists()
        else []
    )
    flat_walk_palette_normalized_context_summary = (
        flat_walk_palette_normalized_context_rows[0] if flat_walk_palette_normalized_context_rows else None
    )
    flat_walk_palette_value_split_rows = (
        read_rows(args.flat_walk_palette_value_split_summary)
        if args.flat_walk_palette_value_split_summary.exists()
        else []
    )
    flat_walk_palette_value_split_summary = (
        flat_walk_palette_value_split_rows[0] if flat_walk_palette_value_split_rows else None
    )
    flat_walk_palette_value_table_rows = (
        read_rows(args.flat_walk_palette_value_table_summary)
        if args.flat_walk_palette_value_table_summary.exists()
        else []
    )
    flat_walk_palette_value_table_summary = (
        flat_walk_palette_value_table_rows[0] if flat_walk_palette_value_table_rows else None
    )
    flat_walk_palette_compressed_selector_rows = (
        read_rows(args.flat_walk_palette_compressed_selector_summary)
        if args.flat_walk_palette_compressed_selector_summary.exists()
        else []
    )
    flat_walk_palette_compressed_selector_summary = (
        flat_walk_palette_compressed_selector_rows[0] if flat_walk_palette_compressed_selector_rows else None
    )
    flat_walk_palette_compressed_combo_rows = (
        read_rows(args.flat_walk_palette_compressed_combo_summary)
        if args.flat_walk_palette_compressed_combo_summary.exists()
        else []
    )
    flat_walk_palette_compressed_combo_summary = (
        flat_walk_palette_compressed_combo_rows[0] if flat_walk_palette_compressed_combo_rows else None
    )
    flat_walk_palette_compressed_formula_rows = (
        read_rows(args.flat_walk_palette_compressed_formula_summary)
        if args.flat_walk_palette_compressed_formula_summary.exists()
        else []
    )
    flat_walk_palette_compressed_formula_summary = (
        flat_walk_palette_compressed_formula_rows[0] if flat_walk_palette_compressed_formula_rows else None
    )
    flat_walk_palette_corpus_formula_rows = (
        read_rows(args.flat_walk_palette_corpus_formula_summary)
        if args.flat_walk_palette_corpus_formula_summary.exists()
        else []
    )
    flat_walk_palette_corpus_formula_summary = (
        flat_walk_palette_corpus_formula_rows[0] if flat_walk_palette_corpus_formula_rows else None
    )
    flat_walk_palette_promotion_candidate_rows = (
        read_rows(args.flat_walk_palette_promotion_candidate_summary)
        if args.flat_walk_palette_promotion_candidate_summary.exists()
        else []
    )
    flat_walk_palette_promotion_candidate_summary = (
        flat_walk_palette_promotion_candidate_rows[0] if flat_walk_palette_promotion_candidate_rows else None
    )
    flat_walk_palette_formula_replay_rows = (
        read_rows(args.flat_walk_palette_formula_replay_summary)
        if args.flat_walk_palette_formula_replay_summary.exists()
        else []
    )
    flat_walk_palette_formula_replay_summary = (
        flat_walk_palette_formula_replay_rows[0] if flat_walk_palette_formula_replay_rows else None
    )
    flat_walk_palette_post_formula_vertical_copy_rows = (
        read_rows(args.flat_walk_palette_post_formula_vertical_copy_summary)
        if args.flat_walk_palette_post_formula_vertical_copy_summary.exists()
        else []
    )
    flat_walk_palette_post_formula_vertical_copy_summary = (
        flat_walk_palette_post_formula_vertical_copy_rows[0]
        if flat_walk_palette_post_formula_vertical_copy_rows
        else None
    )
    gradient_shape_peer_copy_rows = (
        read_rows(args.gradient_shape_peer_copy_summary)
        if args.gradient_shape_peer_copy_summary.exists()
        else []
    )
    gradient_shape_peer_copy_summary = (
        gradient_shape_peer_copy_rows[0] if gradient_shape_peer_copy_rows else None
    )
    gradient_source_profile_high_low_rows = (
        read_rows(args.gradient_source_profile_high_low_summary)
        if args.gradient_source_profile_high_low_summary.exists()
        else []
    )
    gradient_source_profile_high_low_summary = (
        gradient_source_profile_high_low_rows[0] if gradient_source_profile_high_low_rows else None
    )
    gradient_source_profile_high_safe_low_rows = (
        read_rows(args.gradient_source_profile_high_safe_low_summary)
        if args.gradient_source_profile_high_safe_low_summary.exists()
        else []
    )
    gradient_source_profile_high_safe_low_summary = (
        gradient_source_profile_high_safe_low_rows[0]
        if gradient_source_profile_high_safe_low_rows
        else None
    )
    micro_token_family_split_rows = (
        read_rows(args.micro_token_family_split_summary) if args.micro_token_family_split_summary.exists() else []
    )
    micro_token_family_split_summary = micro_token_family_split_rows[0] if micro_token_family_split_rows else None
    micro_jump_mixed_payload_rows = (
        read_rows(args.micro_jump_mixed_payload_summary)
        if args.micro_jump_mixed_payload_summary.exists()
        else []
    )
    micro_jump_mixed_payload_summary = micro_jump_mixed_payload_rows[0] if micro_jump_mixed_payload_rows else None
    jump_token_payload_profile_rows = (
        read_rows(args.jump_token_payload_profile_summary)
        if args.jump_token_payload_profile_summary.exists()
        else []
    )
    jump_token_payload_profile_summary = jump_token_payload_profile_rows[0] if jump_token_payload_profile_rows else None
    jump_token_payload_state_opcode_rows = (
        read_rows(args.jump_token_payload_state_opcode_summary)
        if args.jump_token_payload_state_opcode_summary.exists()
        else []
    )
    jump_token_payload_state_opcode_summary = (
        jump_token_payload_state_opcode_rows[0] if jump_token_payload_state_opcode_rows else None
    )
    micro_mixed_value_subfamily_rows = (
        read_rows(args.micro_mixed_value_subfamily_summary)
        if args.micro_mixed_value_subfamily_summary.exists()
        else []
    )
    micro_mixed_value_subfamily_summary = (
        micro_mixed_value_subfamily_rows[0] if micro_mixed_value_subfamily_rows else None
    )
    micro_mixed_value_dominant_control_rows = (
        read_rows(args.micro_mixed_value_dominant_control_summary)
        if args.micro_mixed_value_dominant_control_summary.exists()
        else []
    )
    micro_mixed_value_dominant_control_summary = (
        micro_mixed_value_dominant_control_rows[0] if micro_mixed_value_dominant_control_rows else None
    )
    micro_mixed_value_payload_local_grammar_rows = (
        read_rows(args.micro_mixed_value_payload_local_grammar_summary)
        if args.micro_mixed_value_payload_local_grammar_summary.exists()
        else []
    )
    micro_mixed_value_payload_local_grammar_summary = (
        micro_mixed_value_payload_local_grammar_rows[0] if micro_mixed_value_payload_local_grammar_rows else None
    )
    micro_mixed_value_payload_predictor_rows = (
        read_rows(args.micro_mixed_value_payload_predictor_summary)
        if args.micro_mixed_value_payload_predictor_summary.exists()
        else []
    )
    micro_mixed_value_payload_predictor_summary = (
        micro_mixed_value_payload_predictor_rows[0] if micro_mixed_value_payload_predictor_rows else None
    )
    micro_mixed_value_payload_combo_rows = (
        read_rows(args.micro_mixed_value_payload_combo_summary)
        if args.micro_mixed_value_payload_combo_summary.exists()
        else []
    )
    micro_mixed_value_payload_combo_summary = (
        micro_mixed_value_payload_combo_rows[0] if micro_mixed_value_payload_combo_rows else None
    )
    micro_mixed_value_payload_high_low_rows = (
        read_rows(args.micro_mixed_value_payload_high_low_summary)
        if args.micro_mixed_value_payload_high_low_summary.exists()
        else []
    )
    micro_mixed_value_payload_high_low_summary = (
        micro_mixed_value_payload_high_low_rows[0] if micro_mixed_value_payload_high_low_rows else None
    )
    micro_mixed_value_payload_source_profile_rows = (
        read_rows(args.micro_mixed_value_payload_source_profile_summary)
        if args.micro_mixed_value_payload_source_profile_summary.exists()
        else []
    )
    micro_mixed_value_payload_source_profile_summary = (
        micro_mixed_value_payload_source_profile_rows[0] if micro_mixed_value_payload_source_profile_rows else None
    )
    micro_mixed_value_payload_external_source_combo_rows = (
        read_rows(args.micro_mixed_value_payload_external_source_combo_summary)
        if args.micro_mixed_value_payload_external_source_combo_summary.exists()
        else []
    )
    micro_mixed_value_payload_external_source_combo_summary = (
        micro_mixed_value_payload_external_source_combo_rows[0]
        if micro_mixed_value_payload_external_source_combo_rows
        else None
    )
    micro_mixed_value_payload_external_high_low_rows = (
        read_rows(args.micro_mixed_value_payload_external_high_low_summary)
        if args.micro_mixed_value_payload_external_high_low_summary.exists()
        else []
    )
    micro_mixed_value_payload_external_high_low_summary = (
        micro_mixed_value_payload_external_high_low_rows[0]
        if micro_mixed_value_payload_external_high_low_rows
        else None
    )
    micro_mixed_value_payload_state_external_combo_rows = (
        read_rows(args.micro_mixed_value_payload_state_external_combo_summary)
        if args.micro_mixed_value_payload_state_external_combo_summary.exists()
        else []
    )
    micro_mixed_value_payload_state_external_combo_summary = (
        micro_mixed_value_payload_state_external_combo_rows[0]
        if micro_mixed_value_payload_state_external_combo_rows
        else None
    )
    micro_mixed_value_payload_sequence_state_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_state_summary)
        if args.micro_mixed_value_payload_sequence_state_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_state_summary = (
        micro_mixed_value_payload_sequence_state_rows[0]
        if micro_mixed_value_payload_sequence_state_rows
        else None
    )
    micro_mixed_value_payload_sequence_candidate_review_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_candidate_review_summary)
        if args.micro_mixed_value_payload_sequence_candidate_review_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_candidate_review_summary = (
        micro_mixed_value_payload_sequence_candidate_review_rows[0]
        if micro_mixed_value_payload_sequence_candidate_review_rows
        else None
    )
    micro_mixed_value_payload_prefix_bootstrap_rows = (
        read_rows(args.micro_mixed_value_payload_prefix_bootstrap_summary)
        if args.micro_mixed_value_payload_prefix_bootstrap_summary.exists()
        else []
    )
    micro_mixed_value_payload_prefix_bootstrap_summary = (
        micro_mixed_value_payload_prefix_bootstrap_rows[0]
        if micro_mixed_value_payload_prefix_bootstrap_rows
        else None
    )
    micro_mixed_value_payload_prefix_sequence_replay_rows = (
        read_rows(args.micro_mixed_value_payload_prefix_sequence_replay_summary)
        if args.micro_mixed_value_payload_prefix_sequence_replay_summary.exists()
        else []
    )
    micro_mixed_value_payload_prefix_sequence_replay_summary = (
        micro_mixed_value_payload_prefix_sequence_replay_rows[0]
        if micro_mixed_value_payload_prefix_sequence_replay_rows
        else None
    )
    micro_mixed_value_payload_prefix_sequence_promoted_replay_rows = (
        read_rows(args.micro_mixed_value_payload_prefix_sequence_promoted_replay_summary)
        if args.micro_mixed_value_payload_prefix_sequence_promoted_replay_summary.exists()
        else []
    )
    micro_mixed_value_payload_prefix_sequence_promoted_replay_summary = (
        micro_mixed_value_payload_prefix_sequence_promoted_replay_rows[0]
        if micro_mixed_value_payload_prefix_sequence_promoted_replay_rows
        else None
    )
    micro_mixed_value_payload_sequence_promoted_generalization_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_promoted_generalization_summary)
        if args.micro_mixed_value_payload_sequence_promoted_generalization_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_promoted_generalization_summary = (
        micro_mixed_value_payload_sequence_promoted_generalization_rows[0]
        if micro_mixed_value_payload_sequence_promoted_generalization_rows
        else None
    )
    micro_mixed_value_payload_sequence_low_split_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_low_split_summary)
        if args.micro_mixed_value_payload_sequence_low_split_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_low_split_summary = (
        micro_mixed_value_payload_sequence_low_split_rows[0]
        if micro_mixed_value_payload_sequence_low_split_rows
        else None
    )
    micro_mixed_value_payload_sequence_low_split_promoted_replay_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_low_split_promoted_replay_summary)
        if args.micro_mixed_value_payload_sequence_low_split_promoted_replay_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_low_split_promoted_replay_summary = (
        micro_mixed_value_payload_sequence_low_split_promoted_replay_rows[0]
        if micro_mixed_value_payload_sequence_low_split_promoted_replay_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_expansion_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_expansion_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_expansion_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_expansion_summary = (
        micro_mixed_value_payload_sequence_prerequisite_expansion_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_expansion_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay_summary = (
        micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_low_split_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_low_split_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_low_split_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_low_split_summary = (
        micro_mixed_value_payload_sequence_prerequisite_low_split_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_low_split_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay_summary = (
        micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_low_split_generalization_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_low_split_generalization_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_low_split_generalization_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_low_split_generalization_summary = (
        micro_mixed_value_payload_sequence_prerequisite_low_split_generalization_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_low_split_generalization_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_second_low_split_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_second_low_split_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_second_low_split_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_second_low_split_summary = (
        micro_mixed_value_payload_sequence_prerequisite_second_low_split_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_second_low_split_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_second_expansion_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_second_expansion_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_second_expansion_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_second_expansion_summary = (
        micro_mixed_value_payload_sequence_prerequisite_second_expansion_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_second_expansion_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_summary = (
        micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_promoted_replay_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_promoted_replay_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_promoted_replay_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_promoted_replay_summary = (
        micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_promoted_replay_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_promoted_replay_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_summary = (
        micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_promoted_replay_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_promoted_replay_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_promoted_replay_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_promoted_replay_summary = (
        micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_promoted_replay_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_promoted_replay_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_summary = (
        micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_promoted_replay_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_promoted_replay_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_promoted_replay_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_promoted_replay_summary = (
        micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_promoted_replay_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_promoted_replay_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay_summary = (
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_generalization_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_generalization_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_generalization_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_generalization_summary = (
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_generalization_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_generalization_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_low_split_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_low_split_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_low_split_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_low_split_summary = (
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_low_split_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_low_split_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_corpus_expansion_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_corpus_expansion_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_corpus_expansion_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_corpus_expansion_summary = (
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_corpus_expansion_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_corpus_expansion_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_fourth_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_fourth_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_fourth_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_fourth_summary = (
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_fourth_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_fourth_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_summary = (
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay_summary = (
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_generalization_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_generalization_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_generalization_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_generalization_summary = (
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_generalization_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_generalization_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_second_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_second_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_second_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_second_summary = (
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_second_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_second_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_low_split_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_low_split_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_low_split_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_low_split_summary = (
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_low_split_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_low_split_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_expansion_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_expansion_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_expansion_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_expansion_summary = (
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_expansion_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_expansion_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_adjacent_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_adjacent_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_adjacent_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_adjacent_summary = (
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_adjacent_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_adjacent_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay_summary = (
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_generalization_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_generalization_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_generalization_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_generalization_summary = (
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_generalization_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_generalization_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_fourth_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_fourth_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_fourth_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_fourth_summary = (
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_fourth_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_fourth_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_low_split_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_low_split_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_low_split_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_low_split_summary = (
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_low_split_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_low_split_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_corpus_expansion_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_corpus_expansion_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_corpus_expansion_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_corpus_expansion_summary = (
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_corpus_expansion_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_corpus_expansion_rows
        else None
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_adjacent_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_adjacent_summary)
        if args.micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_adjacent_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_adjacent_summary = (
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_adjacent_rows[0]
        if micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_adjacent_rows
        else None
    )
    micro_mixed_value_payload_sequence_low_copy_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_low_copy_summary)
        if args.micro_mixed_value_payload_sequence_low_copy_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_low_copy_summary = (
        micro_mixed_value_payload_sequence_low_copy_rows[0]
        if micro_mixed_value_payload_sequence_low_copy_rows
        else None
    )
    micro_mixed_value_payload_sequence_low_copy_promoted_replay_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_low_copy_promoted_replay_summary)
        if args.micro_mixed_value_payload_sequence_low_copy_promoted_replay_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_low_copy_promoted_replay_summary = (
        micro_mixed_value_payload_sequence_low_copy_promoted_replay_rows[0]
        if micro_mixed_value_payload_sequence_low_copy_promoted_replay_rows
        else None
    )
    micro_mixed_value_payload_sequence_low_copy_generalization_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_low_copy_generalization_summary)
        if args.micro_mixed_value_payload_sequence_low_copy_generalization_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_low_copy_generalization_summary = (
        micro_mixed_value_payload_sequence_low_copy_generalization_rows[0]
        if micro_mixed_value_payload_sequence_low_copy_generalization_rows
        else None
    )
    micro_mixed_value_payload_sequence_low_copy_second_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_low_copy_second_summary)
        if args.micro_mixed_value_payload_sequence_low_copy_second_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_low_copy_second_summary = (
        micro_mixed_value_payload_sequence_low_copy_second_rows[0]
        if micro_mixed_value_payload_sequence_low_copy_second_rows
        else None
    )
    micro_mixed_value_payload_sequence_low_copy_low_split_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_low_copy_low_split_summary)
        if args.micro_mixed_value_payload_sequence_low_copy_low_split_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_low_copy_low_split_summary = (
        micro_mixed_value_payload_sequence_low_copy_low_split_rows[0]
        if micro_mixed_value_payload_sequence_low_copy_low_split_rows
        else None
    )
    micro_mixed_value_payload_sequence_low_copy_corpus_expansion_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_low_copy_corpus_expansion_summary)
        if args.micro_mixed_value_payload_sequence_low_copy_corpus_expansion_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_low_copy_corpus_expansion_summary = (
        micro_mixed_value_payload_sequence_low_copy_corpus_expansion_rows[0]
        if micro_mixed_value_payload_sequence_low_copy_corpus_expansion_rows
        else None
    )
    micro_mixed_value_payload_sequence_low_copy_adjacent_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_low_copy_adjacent_summary)
        if args.micro_mixed_value_payload_sequence_low_copy_adjacent_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_low_copy_adjacent_summary = (
        micro_mixed_value_payload_sequence_low_copy_adjacent_rows[0]
        if micro_mixed_value_payload_sequence_low_copy_adjacent_rows
        else None
    )
    micro_mixed_value_payload_sequence_blocked_prerequisite_role_transform_rows = (
        read_rows(args.micro_mixed_value_payload_sequence_blocked_prerequisite_role_transform_summary)
        if args.micro_mixed_value_payload_sequence_blocked_prerequisite_role_transform_summary.exists()
        else []
    )
    micro_mixed_value_payload_sequence_blocked_prerequisite_role_transform_summary = (
        micro_mixed_value_payload_sequence_blocked_prerequisite_role_transform_rows[0]
        if micro_mixed_value_payload_sequence_blocked_prerequisite_role_transform_rows
        else None
    )
    micro_mixed_value_payload_spatial_rows = (
        read_rows(args.micro_mixed_value_payload_spatial_summary)
        if args.micro_mixed_value_payload_spatial_summary.exists()
        else []
    )
    micro_mixed_value_payload_spatial_summary = (
        micro_mixed_value_payload_spatial_rows[0] if micro_mixed_value_payload_spatial_rows else None
    )
    micro_mixed_value_payload_state_opcode_rows = (
        read_rows(args.micro_mixed_value_payload_state_opcode_summary)
        if args.micro_mixed_value_payload_state_opcode_summary.exists()
        else []
    )
    micro_mixed_value_payload_state_opcode_summary = (
        micro_mixed_value_payload_state_opcode_rows[0] if micro_mixed_value_payload_state_opcode_rows else None
    )
    queue = build_queue(
        decisions,
        gradient_payload_profile_summary,
        gradient_payload_state_opcode_summary,
        gradient_macro_opcode_summary,
        gradient_macro_conflict_split_summary,
        gradient_macro_residual_state_summary,
        gradient_macro_phase_summary,
        gradient_macro_phase_conflict_split_summary,
        gradient_macro_phase_sequence_summary,
        gradient_macro_fixture_transition_summary,
        gradient_macro_state_cluster_summary,
        gradient_macro_source_profile_state_summary,
        gradient_seed_delta_payload_opcode_summary,
        gradient_nonlocal_known_spatial_summary,
        gradient_sequence_known_state_summary,
        gradient_sequence_high_safe_low_summary,
        gradient_sequence_high_safe_source_profile_low_summary,
        gradient_sequence_high_safe_row_corpus_low_summary,
        gradient_sequence_high_safe_transform_low_summary,
        gradient_sequence_high_safe_source_window_summary,
        gradient_sequence_high_safe_control_opcode_summary,
        gradient_sequence_high_safe_row_transition_summary,
        gradient_sequence_high_safe_row_markov_summary,
        gradient_sequence_high_safe_row_template_summary,
        gradient_sequence_high_safe_low_bucket_split_summary,
        gradient_sequence_high_safe_low_exception_summary,
        gradient_sequence_high_safe_low_exception_alignment_summary,
        gradient_sequence_high_safe_low_exception_alignment_review_summary,
        gradient_sequence_high_safe_low_exception_row_family_summary,
        gradient_sequence_high_safe_low_exception_external_state_summary,
        gradient_sequence_high_safe_low_exception_prerequisite_state_summary,
        gradient_sequence_high_safe_low_exception_source_dependency_summary,
        gradient_sequence_high_safe_low_exception_source_chain_summary,
        gradient_sequence_high_safe_low_exception_source_terminal_summary,
        gradient_sequence_high_safe_low_exception_source_terminal_review_summary,
        gradient_sequence_high_safe_low_exception_source_terminal_delta_summary,
        gradient_sequence_high_safe_low_exception_source_terminal_chain_context_summary,
        gradient_sequence_high_safe_low_exception_source_terminal_replay_support_summary,
        gradient_sequence_high_safe_low_exception_source_terminal_replay_union_summary,
        gradient_macro_state_cluster_payload_summary,
        gradient_macro_state_cluster_source_summary,
        gradient_macro_state_cluster_literal_summary,
        gradient_macro_state_cluster_backref_summary,
        flat_walk_backref_summary,
        flat_walk_backref_chain_summary,
        flat_walk_palette_context_summary,
        flat_walk_palette_normalized_context_summary,
        flat_walk_palette_value_split_summary,
        flat_walk_palette_value_table_summary,
        flat_walk_palette_compressed_selector_summary,
        flat_walk_palette_compressed_combo_summary,
        flat_walk_palette_compressed_formula_summary,
        flat_walk_palette_corpus_formula_summary,
        flat_walk_palette_promotion_candidate_summary,
        flat_walk_palette_formula_replay_summary,
        flat_walk_palette_post_formula_vertical_copy_summary,
        gradient_shape_peer_copy_summary,
        gradient_source_profile_high_low_summary,
        gradient_source_profile_high_safe_low_summary,
        micro_jump_mixed_payload_summary,
        jump_token_payload_profile_summary,
        jump_token_payload_state_opcode_summary,
        micro_token_family_split_summary,
        micro_mixed_value_subfamily_summary,
        micro_mixed_value_dominant_control_summary,
        micro_mixed_value_payload_local_grammar_summary,
        micro_mixed_value_payload_predictor_summary,
        micro_mixed_value_payload_combo_summary,
        micro_mixed_value_payload_high_low_summary,
        micro_mixed_value_payload_source_profile_summary,
        micro_mixed_value_payload_external_source_combo_summary,
        micro_mixed_value_payload_external_high_low_summary,
        micro_mixed_value_payload_state_external_combo_summary,
        micro_mixed_value_payload_sequence_state_summary,
        micro_mixed_value_payload_sequence_candidate_review_summary,
        micro_mixed_value_payload_prefix_bootstrap_summary,
        micro_mixed_value_payload_prefix_sequence_replay_summary,
        micro_mixed_value_payload_prefix_sequence_promoted_replay_summary,
        micro_mixed_value_payload_sequence_promoted_generalization_summary,
        micro_mixed_value_payload_sequence_low_split_summary,
        micro_mixed_value_payload_sequence_low_split_promoted_replay_summary,
        micro_mixed_value_payload_sequence_prerequisite_expansion_summary,
        micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay_summary,
        micro_mixed_value_payload_sequence_prerequisite_low_split_summary,
        micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay_summary,
        micro_mixed_value_payload_sequence_prerequisite_low_split_generalization_summary,
        micro_mixed_value_payload_sequence_prerequisite_second_low_split_summary,
        micro_mixed_value_payload_sequence_prerequisite_second_expansion_summary,
        micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_summary,
        micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_promoted_replay_summary,
        micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_summary,
        micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_promoted_replay_summary,
        micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_summary,
        micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_promoted_replay_summary,
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay_summary,
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_generalization_summary,
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_low_split_summary,
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_corpus_expansion_summary,
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_fourth_summary,
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_summary,
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay_summary,
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_generalization_summary,
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_second_summary,
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_low_split_summary,
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_expansion_summary,
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_adjacent_summary,
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay_summary,
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_generalization_summary,
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_fourth_summary,
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_low_split_summary,
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_corpus_expansion_summary,
        micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_adjacent_summary,
        micro_mixed_value_payload_sequence_low_copy_summary,
        micro_mixed_value_payload_sequence_low_copy_promoted_replay_summary,
        micro_mixed_value_payload_sequence_low_copy_generalization_summary,
        micro_mixed_value_payload_sequence_low_copy_second_summary,
        micro_mixed_value_payload_sequence_low_copy_low_split_summary,
        micro_mixed_value_payload_sequence_low_copy_corpus_expansion_summary,
        micro_mixed_value_payload_sequence_low_copy_adjacent_summary,
        micro_mixed_value_payload_sequence_blocked_prerequisite_role_transform_summary,
        micro_mixed_value_payload_spatial_summary,
        micro_mixed_value_payload_state_opcode_summary,
    )
    summary = build_summary(queue, review_summary)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "queue.csv", QUEUE_FIELDNAMES, queue)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, queue, args.title))

    print(f"Roadmap decisions: {summary['decision_rows']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"Top track: {summary['top_track']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
