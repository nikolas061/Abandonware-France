#!/usr/bin/env python3
"""Summarize noisy nonzero gap probes into promotion decisions."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_noisy_review")
DEFAULT_NOISY = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_noisy_shape_probe/summary.csv")
DEFAULT_GRADIENT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_probe/summary.csv")
DEFAULT_GRADIENT_REPEAT_CONTEXT = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_repeat_context_probe/summary.csv"
)
DEFAULT_GRADIENT_SEED_UNLOCK = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_unlock_probe/summary.csv"
)
DEFAULT_GRADIENT_SEED_SHIFT_FAMILY = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_shift_family_probe/summary.csv"
)
DEFAULT_GRADIENT_SEED_DELTA_SELECTOR = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_selector_probe/summary.csv"
)
DEFAULT_GRADIENT_SEED_DELTA_CONTEXT = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_context_probe/summary.csv"
)
DEFAULT_GRADIENT_SEED_DELTA_PHASE = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_phase_probe/summary.csv"
)
DEFAULT_GRADIENT_SEED_DELTA_STATE = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_state_probe/summary.csv"
)
DEFAULT_GRADIENT_SEED_DELTA_OPCODE_SEQUENCE = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_opcode_sequence_probe/summary.csv"
)
DEFAULT_GRADIENT_SEED_DELTA_SEMANTIC_OPCODE = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_semantic_opcode_probe/summary.csv"
)
DEFAULT_GRADIENT_SEED_DELTA_PAYLOAD_OPCODE = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_gradient_seed_delta_payload_opcode_probe/summary.csv"
)
DEFAULT_FLAT = Path("output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_probe/summary.csv")
DEFAULT_FLAT_SOURCE = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_source_probe/summary.csv"
)
DEFAULT_FLAT_SHAPE_CONTROL = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_shape_control_probe/summary.csv"
)
DEFAULT_FLAT_VALUE = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_value_probe/summary.csv"
)
DEFAULT_FLAT_BACKREF = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_backref_probe/summary.csv"
)
DEFAULT_FLAT_PALETTE_SEED = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_seed_probe/summary.csv"
)
DEFAULT_FLAT_PALETTE_MIX = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_mix_probe/summary.csv"
)
DEFAULT_FLAT_BACKREF_CHAIN = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_backref_chain_probe/summary.csv"
)
DEFAULT_FLAT_PALETTE_SIGNATURE = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_signature_probe/summary.csv"
)
DEFAULT_FLAT_PALETTE_CONTEXT = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_flat_walk_palette_context_probe/summary.csv"
)
DEFAULT_MICRO_TOKEN = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_micro_token_probe/summary.csv"
)
DEFAULT_MIXED_TOKEN_UNIQUENESS = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_token_uniqueness_probe/summary.csv"
)
DEFAULT_MIXED_TOKEN_BAND = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_token_band_probe/summary.csv"
)
DEFAULT_MIXED_TOKEN_BACKREF = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_token_backref_probe/summary.csv"
)
DEFAULT_MIXED_TOKEN_CONTROL = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_token_control_probe/summary.csv"
)
DEFAULT_MIXED_TOKEN_CONTROL_CONTEXT = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_token_control_context_probe/summary.csv"
)
DEFAULT_JUMP_TOKEN = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_jump_token_probe/summary.csv"
)
DEFAULT_JUMP_TOKEN_BACKREF = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_jump_token_backref_probe/summary.csv"
)
DEFAULT_JUMP_TOKEN_CONTEXT = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_jump_token_context_probe/summary.csv"
)
DEFAULT_DENSE_JUMP = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_dense_jump_probe/summary.csv"
)
DEFAULT_DENSE_CONTROL = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_dense_control_probe/summary.csv"
)
DEFAULT_CONTROL_SIGNAL_GATE = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_control_signal_gate_probe/summary.csv"
)
DEFAULT_WEAK_CONTROL_VALUE = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_weak_control_value_probe/summary.csv"
)
DEFAULT_DIRECTION_VALUE = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_probe/summary.csv"
)
DEFAULT_DIRECTION_VALUE_OFFSET = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_offset_probe/summary.csv"
)
DEFAULT_DIRECTION_VALUE_DELTA_CONTEXT = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_delta_context_probe/summary.csv"
)
DEFAULT_DIRECTION_VALUE_PAYLOAD_GRAMMAR = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_payload_grammar_probe/summary.csv"
)
DEFAULT_DIRECTION_VALUE_SOURCE_PROFILE = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_source_profile_probe/summary.csv"
)
DEFAULT_DIRECTION_VALUE_SOURCE_VALUE = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_source_value_probe/summary.csv"
)
DEFAULT_DIRECTION_VALUE_SOURCE_WINDOW = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_source_window_probe/summary.csv"
)
DEFAULT_DIRECTION_VALUE_CONTROL_CONTEXT = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_control_context_probe/summary.csv"
)
DEFAULT_DIRECTION_VALUE_EXACT_CONTEXT = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_exact_context_probe/summary.csv"
)
DEFAULT_DIRECTION_VALUE_PARTIAL_CONTEXT = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_direction_value_partial_context_probe/summary.csv"
)
DEFAULT_REPEATED_NIBBLE = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_repeated_nibble_probe/summary.csv"
)
DEFAULT_REPEATED_NIBBLE_CONTEXT = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_repeated_nibble_context_probe/summary.csv"
)
DEFAULT_MIXED_JUMP = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_jump_probe/summary.csv"
)
DEFAULT_MIXED_JUMP_CONTEXT = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_jump_context_probe/summary.csv"
)
DEFAULT_MIXED_CONTROL = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_mixed_control_probe/summary.csv"
)
DEFAULT_RESIDUAL_JUMP = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_residual_jump_probe/summary.csv"
)
DEFAULT_RESIDUAL_CONTROL = Path(
    "output/tex_gap_decoder_len64_promoted_tiny_nonzero_gap_residual_control_probe/summary.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
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
    "gradient_seed_delta_payload_opcode_mapping_bytes",
    "gradient_seed_delta_payload_opcode_groups",
    "gradient_seed_delta_payload_opcode_repeated_bytes",
    "gradient_seed_delta_payload_opcode_raw_byte_repeated_bytes",
    "gradient_seed_delta_payload_opcode_bitfield_repeated_bytes",
    "gradient_seed_delta_payload_opcode_local_ngram_repeated_bytes",
    "gradient_seed_delta_payload_opcode_offset_token_repeated_bytes",
    "gradient_seed_delta_payload_opcode_sequence_role_repeated_bytes",
    "gradient_seed_delta_payload_opcode_combo_repeated_bytes",
    "gradient_seed_delta_payload_opcode_conflicted_bytes",
    "gradient_seed_delta_payload_opcode_best_family",
    "flat_walk_rows",
    "flat_walk_bytes",
    "plateau_bytes",
    "flat_length_exact_total",
    "flat_length_symbol_count",
    "flat_transition_exact_total",
    "flat_transition_symbol_count",
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
]

DECISION_FIELDNAMES = [
    "surface",
    "rows",
    "bytes",
    "positive_evidence",
    "blocking_evidence",
    "promotion_ready_bytes",
    "next_action",
]


def read_summary(path: Path) -> dict[str, str]:
    with path.open(newline="") as handle:
        return next(csv.DictReader(handle))


def ratio(numerator: int, denominator: int) -> str:
    return f"{(numerator / denominator) if denominator else 0.0:.6f}"


def build_rows(
    noisy: dict[str, str],
    gradient: dict[str, str],
    gradient_repeat_context: dict[str, str],
    gradient_seed_unlock: dict[str, str],
    gradient_seed_shift_family: dict[str, str],
    gradient_seed_delta_selector: dict[str, str],
    gradient_seed_delta_context: dict[str, str],
    gradient_seed_delta_phase: dict[str, str],
    gradient_seed_delta_state: dict[str, str],
    gradient_seed_delta_opcode_sequence: dict[str, str],
    gradient_seed_delta_semantic_opcode: dict[str, str],
    gradient_seed_delta_payload_opcode: dict[str, str],
    flat: dict[str, str],
    flat_source: dict[str, str],
    flat_shape_control: dict[str, str],
    flat_value: dict[str, str],
    flat_backref: dict[str, str],
    flat_palette_seed: dict[str, str],
    flat_palette_mix: dict[str, str],
    flat_backref_chain: dict[str, str],
    flat_palette_signature: dict[str, str],
    flat_palette_context: dict[str, str],
    micro_token: dict[str, str],
    mixed_token_uniqueness: dict[str, str],
    mixed_token_band: dict[str, str],
    mixed_token_backref: dict[str, str],
    mixed_token_control: dict[str, str],
    mixed_token_control_context: dict[str, str],
    jump_token: dict[str, str],
    jump_token_backref: dict[str, str],
    jump_token_context: dict[str, str],
    repeated_nibble: dict[str, str],
    repeated_nibble_context: dict[str, str],
    mixed_jump: dict[str, str],
    mixed_jump_context: dict[str, str],
    mixed_control: dict[str, str],
    residual_jump: dict[str, str],
    residual_control: dict[str, str],
    dense_jump: dict[str, str],
    dense_control: dict[str, str],
    control_signal_gate: dict[str, str],
    weak_control_value: dict[str, str],
    direction_value: dict[str, str],
    direction_value_offset: dict[str, str],
    direction_value_delta_context: dict[str, str],
    direction_value_payload_grammar: dict[str, str],
    direction_value_source_profile: dict[str, str],
    direction_value_source_value: dict[str, str],
    direction_value_source_window: dict[str, str],
    direction_value_control_context: dict[str, str],
    direction_value_exact_context: dict[str, str],
    direction_value_partial_context: dict[str, str],
) -> tuple[dict[str, str], list[dict[str, str]]]:
    noisy_rows = int_value(noisy, "target_rows")
    noisy_bytes = int_value(noisy, "target_bytes")
    gradient_rows = int_value(gradient, "target_rows")
    gradient_bytes = int_value(gradient, "target_bytes")
    flat_rows = int_value(flat, "target_rows")
    flat_bytes = int_value(flat, "target_bytes")
    length_exact = int_value(flat_source, "length_exact_total")
    length_symbols = int_value(flat_source, "length_symbol_count")
    transition_exact = int_value(flat_source, "transition_exact_total")
    transition_symbols = int_value(flat_source, "transition_symbol_count")
    micro_rows = int_value(micro_token, "target_rows")
    micro_bytes = int_value(micro_token, "target_bytes")
    jump_rows = int_value(jump_token, "target_rows")
    jump_bytes = int_value(jump_token, "target_bytes")
    repeated_rows = int_value(repeated_nibble, "target_rows")
    repeated_bytes = int_value(repeated_nibble, "target_bytes")
    mixed_rows = int_value(mixed_jump, "target_rows")
    mixed_bytes = int_value(mixed_jump, "target_bytes")
    mixed_control_rows = int_value(mixed_control, "target_rows")
    mixed_control_bytes = int_value(mixed_control, "target_bytes")
    residual_rows = int_value(residual_jump, "target_rows")
    residual_bytes = int_value(residual_jump, "target_bytes")
    residual_control_rows = int_value(residual_control, "target_rows")
    residual_control_bytes = int_value(residual_control, "target_bytes")
    dense_rows = int_value(dense_jump, "target_rows")
    dense_bytes = int_value(dense_jump, "target_bytes")
    dense_control_rows = int_value(dense_control, "target_rows")
    dense_control_bytes = int_value(dense_control, "target_bytes")
    control_signal_gate_rows = int_value(control_signal_gate, "surface_rows")
    control_signal_gate_bytes = int_value(control_signal_gate, "surface_bytes")
    decision_rows = [
        {
            "surface": "noisy_all",
            "rows": str(noisy_rows),
            "bytes": str(noisy_bytes),
            "positive_evidence": (
                f"gradient_like={noisy.get('gradient_like_rows', '0')} rows/"
                f"{noisy.get('gradient_like_bytes', '0')} bytes; "
                f"periodic={noisy.get('periodic_rows', '0')} rows/"
                f"{noisy.get('periodic_bytes', '0')} bytes"
            ),
            "blocking_evidence": (
                f"source_like={noisy.get('source_like_bytes', '0')} bytes; "
                f"full_matches={noisy.get('full_match_rows', '0')}; "
                f"best_exact_total={noisy.get('best_exact_bytes_total', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "continue grammar search by shape class",
        },
        {
            "surface": "gradient_like",
            "rows": str(gradient_rows),
            "bytes": str(gradient_bytes),
            "positive_evidence": (
                f"small_delta_ratio={gradient.get('small_delta_ratio', '0')}; "
                f"zero_delta_count={gradient.get('zero_delta_count', '0')}; "
                f"step_delta_count={gradient.get('step_delta_count', '0')}"
            ),
            "blocking_evidence": (
                f"linear_ge75_rows={gradient.get('linear_ge75_rows', '0')}; "
                f"linear_best_single={gradient.get('linear_best_single_exact_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "tokenize signed small-delta walks before value promotion",
        },
        {
            "surface": "gradient_repeat_context",
            "rows": gradient_repeat_context.get("target_rows", "0"),
            "bytes": gradient_repeat_context.get("target_bytes", "0"),
            "positive_evidence": (
                f"repeated_payload={gradient_repeat_context.get('repeated_payload_bytes', '0')} bytes; "
                f"copy_distance_320={gradient_repeat_context.get('copy_distance_320_bytes', '0')} bytes"
            ),
            "blocking_evidence": (
                f"copy_unlock={gradient_repeat_context.get('copy_unlock_bytes', '0')} bytes; "
                f"control_ref_distinct={gradient_repeat_context.get('control_ref_distinct_groups', '0')}; "
                f"promotion_ready={gradient_repeat_context.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "derive the first gradient occurrence before using distance-320 copy reuse",
        },
        {
            "surface": "gradient_seed_unlock",
            "rows": gradient_seed_unlock.get("seed_rows", "0"),
            "bytes": gradient_seed_unlock.get("seed_bytes", "0"),
            "positive_evidence": (
                f"candidate_seed={gradient_seed_unlock.get('candidate_seed_bytes', '0')} bytes; "
                f"copy_unlock={gradient_seed_unlock.get('copy_unlock_bytes', '0')} bytes; "
                f"potential={gradient_seed_unlock.get('total_seed_plus_unlock_bytes', '0')} bytes"
            ),
            "blocking_evidence": (
                f"repeated_transform_set={gradient_seed_unlock.get('repeated_transform_set_bytes', '0')} bytes; "
                f"blocked_seed={gradient_seed_unlock.get('blocked_seed_bytes', '0')} bytes; "
                f"promotion_ready={gradient_seed_unlock.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "require repeated seed transform evidence before replaying distance-320 gradient copies",
        },
        {
            "surface": "gradient_seed_shift_family",
            "rows": gradient_seed_shift_family.get("candidate_rows", "0"),
            "bytes": gradient_seed_shift_family.get("candidate_bytes", "0"),
            "positive_evidence": (
                f"identity_family={gradient_seed_shift_family.get('identity_shift_family_bytes', '0')} bytes; "
                f"repeated_family={gradient_seed_shift_family.get('repeated_family_bytes', '0')} bytes; "
                f"copy_unlock={gradient_seed_shift_family.get('copy_unlock_bytes', '0')} bytes"
            ),
            "blocking_evidence": (
                f"exact_shift_set={gradient_seed_shift_family.get('repeated_exact_shift_set_bytes', '0')} bytes; "
                f"distinct_deltas={gradient_seed_shift_family.get('distinct_shift_deltas', '0')}; "
                f"promotion_ready={gradient_seed_shift_family.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "derive the per-value shift selector before promoting the shared control-window shift family",
        },
        {
            "surface": "gradient_seed_delta_selector",
            "rows": gradient_seed_delta_selector.get("mapping_rows", "0"),
            "bytes": gradient_seed_delta_selector.get("mapping_value_bytes", "0"),
            "positive_evidence": (
                f"deltas={gradient_seed_delta_selector.get('delta_values', '0')}; "
                f"row_local_repeat={gradient_seed_delta_selector.get('row_local_repeated_deterministic_bytes', '0')} bytes; "
                f"target_oracle_repeat={gradient_seed_delta_selector.get('target_oracle_repeated_deterministic_bytes', '0')} bytes"
            ),
            "blocking_evidence": (
                f"source_only_repeat={gradient_seed_delta_selector.get('source_only_repeated_deterministic_bytes', '0')} bytes; "
                f"source_only_conflict={gradient_seed_delta_selector.get('source_only_conflicted_bytes', '0')} evidence-bytes; "
                f"promotion_ready={gradient_seed_delta_selector.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "reject target-value shortcuts and search for a source-side delta selector",
        },
        {
            "surface": "gradient_seed_delta_context",
            "rows": gradient_seed_delta_context.get("mapping_rows", "0"),
            "bytes": gradient_seed_delta_context.get("mapping_value_bytes", "0"),
            "positive_evidence": (
                f"deltas={gradient_seed_delta_context.get('delta_values', '0')}; "
                f"singleton={gradient_seed_delta_context.get('source_context_singleton_deterministic_bytes', '0')} bytes; "
                f"best_family={gradient_seed_delta_context.get('best_source_context_family', '')}"
            ),
            "blocking_evidence": (
                f"repeated_context={gradient_seed_delta_context.get('source_context_repeated_deterministic_bytes', '0')} bytes; "
                f"conflicted={gradient_seed_delta_context.get('source_context_conflicted_bytes', '0')} evidence-bytes; "
                f"promotion_ready={gradient_seed_delta_context.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "move beyond immediate control-window neighborhood; test broader control grammar/source phase",
        },
        {
            "surface": "gradient_seed_delta_phase",
            "rows": gradient_seed_delta_phase.get("mapping_rows", "0"),
            "bytes": gradient_seed_delta_phase.get("mapping_value_bytes", "0"),
            "positive_evidence": (
                f"selectors={gradient_seed_delta_phase.get('selector_groups', '0')}; "
                f"singleton={gradient_seed_delta_phase.get('singleton_deterministic_bytes', '0')} evidence-bytes; "
                f"best_family={gradient_seed_delta_phase.get('best_phase_family', '')}"
            ),
            "blocking_evidence": (
                f"repeated={gradient_seed_delta_phase.get('repeated_deterministic_bytes', '0')} bytes; "
                f"source_phase={gradient_seed_delta_phase.get('source_value_phase_repeated_bytes', '0')} bytes; "
                f"broad_control={gradient_seed_delta_phase.get('broad_control_phase_repeated_bytes', '0')} bytes; "
                f"wide_relative={gradient_seed_delta_phase.get('wide_relative_repeated_bytes', '0')} bytes; "
                f"conflicted={gradient_seed_delta_phase.get('conflicted_bytes', '0')} evidence-bytes; "
                f"promotion_ready={gradient_seed_delta_phase.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "move from selector scans to stateful control grammar over the two gradient seed rows",
        },
        {
            "surface": "gradient_seed_delta_state",
            "rows": gradient_seed_delta_state.get("mapping_rows", "0"),
            "bytes": gradient_seed_delta_state.get("mapping_value_bytes", "0"),
            "positive_evidence": (
                f"states={gradient_seed_delta_state.get('state_groups', '0')}; "
                f"singleton={gradient_seed_delta_state.get('singleton_deterministic_bytes', '0')} evidence-bytes; "
                f"best_family={gradient_seed_delta_state.get('best_state_family', '')}"
            ),
            "blocking_evidence": (
                f"repeated={gradient_seed_delta_state.get('repeated_deterministic_bytes', '0')} bytes; "
                f"prefix={gradient_seed_delta_state.get('prefix_accumulator_repeated_bytes', '0')} bytes; "
                f"fsm={gradient_seed_delta_state.get('fsm_repeated_bytes', '0')} bytes; "
                f"nibble={gradient_seed_delta_state.get('nibble_counter_repeated_bytes', '0')} bytes; "
                f"parser={gradient_seed_delta_state.get('parser_counter_repeated_bytes', '0')} bytes; "
                f"conflicted={gradient_seed_delta_state.get('conflicted_bytes', '0')} evidence-bytes; "
                f"promotion_ready={gradient_seed_delta_state.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "stop stateless/state-selector scans here; inspect seed-row opcode sequencing directly",
        },
        {
            "surface": "gradient_seed_delta_opcode_sequence",
            "rows": gradient_seed_delta_opcode_sequence.get("seed_rows", "0"),
            "bytes": gradient_seed_delta_opcode_sequence.get("mapping_value_bytes", "0"),
            "positive_evidence": (
                f"transitions={gradient_seed_delta_opcode_sequence.get('transition_rows', '0')}; "
                f"groups={gradient_seed_delta_opcode_sequence.get('transition_groups', '0')}; "
                f"offset_reuse={gradient_seed_delta_opcode_sequence.get('offset_reuse_bytes', '0')} bytes; "
                f"constant_delta_seeds={gradient_seed_delta_opcode_sequence.get('constant_delta_seed_rows', '0')}"
            ),
            "blocking_evidence": (
                f"repeated={gradient_seed_delta_opcode_sequence.get('repeated_transition_bytes', '0')} bytes; "
                f"conflicted={gradient_seed_delta_opcode_sequence.get('conflicted_transition_bytes', '0')} evidence-bytes; "
                f"best_family={gradient_seed_delta_opcode_sequence.get('best_transition_family', '')}; "
                f"promotion_ready={gradient_seed_delta_opcode_sequence.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "derive a semantic opcode stream for the two seed rows; raw offset/source ordering is exhausted",
        },
        {
            "surface": "gradient_seed_delta_semantic_opcode",
            "rows": gradient_seed_delta_semantic_opcode.get("seed_rows", "0"),
            "bytes": gradient_seed_delta_semantic_opcode.get("mapping_value_bytes", "0"),
            "positive_evidence": (
                f"contexts={gradient_seed_delta_semantic_opcode.get('operation_context_rows', '0')}; "
                f"groups={gradient_seed_delta_semantic_opcode.get('semantic_groups', '0')}; "
                f"kind_patterns={gradient_seed_delta_semantic_opcode.get('kind_patterns', '0')}; "
                f"length_patterns={gradient_seed_delta_semantic_opcode.get('length_patterns', '0')}"
            ),
            "blocking_evidence": (
                f"repeated={gradient_seed_delta_semantic_opcode.get('repeated_deterministic_bytes', '0')} bytes; "
                f"op_context={gradient_seed_delta_semantic_opcode.get('op_context_repeated_bytes', '0')} bytes; "
                f"op_neighborhood={gradient_seed_delta_semantic_opcode.get('op_neighborhood_repeated_bytes', '0')} bytes; "
                f"source_role={gradient_seed_delta_semantic_opcode.get('source_role_repeated_bytes', '0')} bytes; "
                f"control_token={gradient_seed_delta_semantic_opcode.get('control_token_repeated_bytes', '0')} bytes; "
                f"combo={gradient_seed_delta_semantic_opcode.get('semantic_combo_repeated_bytes', '0')} bytes; "
                f"conflicted={gradient_seed_delta_semantic_opcode.get('conflicted_bytes', '0')} evidence-bytes; "
                f"promotion_ready={gradient_seed_delta_semantic_opcode.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "derive opcode-token grammar from the unresolved gap payload, not from operation-neighborhood selectors",
        },
        {
            "surface": "gradient_seed_delta_payload_opcode",
            "rows": gradient_seed_delta_payload_opcode.get("seed_rows", "0"),
            "bytes": gradient_seed_delta_payload_opcode.get("mapping_value_bytes", "0"),
            "positive_evidence": (
                f"groups={gradient_seed_delta_payload_opcode.get('token_groups', '0')}; "
                f"repeated={gradient_seed_delta_payload_opcode.get('repeated_deterministic_bytes', '0')} bytes; "
                f"sequence_role={gradient_seed_delta_payload_opcode.get('sequence_role_repeated_bytes', '0')} bytes; "
                f"combo={gradient_seed_delta_payload_opcode.get('payload_combo_repeated_bytes', '0')} bytes"
            ),
            "blocking_evidence": (
                f"raw_byte={gradient_seed_delta_payload_opcode.get('raw_byte_repeated_bytes', '0')} bytes; "
                f"bitfield={gradient_seed_delta_payload_opcode.get('bitfield_repeated_bytes', '0')} bytes; "
                f"local_ngram={gradient_seed_delta_payload_opcode.get('local_ngram_repeated_bytes', '0')} bytes; "
                f"offset_token={gradient_seed_delta_payload_opcode.get('offset_token_repeated_bytes', '0')} bytes; "
                f"conflicted={gradient_seed_delta_payload_opcode.get('conflicted_bytes', '0')} evidence-bytes; "
                f"best_family={gradient_seed_delta_payload_opcode.get('best_token_family', '')}; "
                f"promotion_ready={gradient_seed_delta_payload_opcode.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "turn the weak position-only payload signal into a larger grammar before promoting any seed delta rule",
        },
        {
            "surface": "flat_walk",
            "rows": str(flat_rows),
            "bytes": str(flat_bytes),
            "positive_evidence": (
                f"plateau_bytes={flat.get('plateau_bytes', '0')}; "
                f"run_shapes={flat.get('run_length_shape_groups', '0')}; "
                f"repeated_shape_bytes={flat.get('run_length_repeated_bytes', '0')}"
            ),
            "blocking_evidence": (
                f"transition_shapes={flat.get('transition_shape_groups', '0')}; "
                f"best_transition_shape_bytes={flat.get('best_transition_shape_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "derive plateau/transition grammar without local-source shortcut",
        },
        {
            "surface": "flat_walk_source",
            "rows": flat_source.get("target_rows", "0"),
            "bytes": flat_source.get("target_bytes", "0"),
            "positive_evidence": (
                f"length_exact={length_exact}/{length_symbols} "
                f"({ratio(length_exact, length_symbols)}); "
                f"transition_exact={transition_exact}/{transition_symbols} "
                f"({ratio(transition_exact, transition_symbols)})"
            ),
            "blocking_evidence": (
                f"both_ge50_rows={flat_source.get('both_ge50_rows', '0')}; "
                f"length_best_single={flat_source.get('length_best_single_exact', '0')}; "
                f"transition_best_single={flat_source.get('transition_best_single_exact', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "reject simple byte/nibble source table for plateau runs",
        },
        {
            "surface": "flat_walk_shape_control",
            "rows": flat_shape_control.get("target_rows", "0"),
            "bytes": flat_shape_control.get("target_bytes", "0"),
            "positive_evidence": (
                f"repeated_pure_selectors={flat_shape_control.get('repeated_pure_selector_rows', '0')}; "
                f"covered={flat_shape_control.get('repeated_pure_covered_rows', '0')} rows/"
                f"{flat_shape_control.get('repeated_pure_covered_bytes', '0')} bytes; "
                f"best_repeated={flat_shape_control.get('best_repeated_pure_rows', '0')} rows/"
                f"{flat_shape_control.get('best_repeated_pure_bytes', '0')} bytes"
            ),
            "blocking_evidence": "shape-only selectors; no run-value producer; promotion_ready=0",
            "promotion_ready_bytes": "0",
            "next_action": "combine flat-walk shape selectors with value and length grammar",
        },
        {
            "surface": "flat_walk_value",
            "rows": flat_value.get("target_rows", "0"),
            "bytes": flat_value.get("target_bytes", "0"),
            "positive_evidence": (
                f"rules={flat_value.get('rule_rows', '0')}; "
                f"best_any={flat_value.get('best_any_correct_bytes', '0')}/"
                f"{flat_value.get('target_bytes', '0')} bytes; "
                f"prefix_copy_exact={flat_value.get('prefix_copy_exact_bytes', '0')} bytes"
            ),
            "blocking_evidence": (
                f"false_free_multirow={flat_value.get('false_free_multirow_rule_rows', '0')}; "
                f"best_false_free_exact={flat_value.get('best_false_free_exact_bytes', '0')}; "
                f"best_any_false={flat_value.get('best_any_false_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "derive a non-oracle value producer before replay promotion",
        },
        {
            "surface": "flat_walk_backref",
            "rows": flat_backref.get("target_rows", "0"),
            "bytes": flat_backref.get("target_bytes", "0"),
            "positive_evidence": (
                f"exact_copy={flat_backref.get('exact_copy_rows', '0')} rows/"
                f"{flat_backref.get('exact_copy_bytes', '0')} bytes; "
                f"best_distance={flat_backref.get('best_distance', '0')}; "
                f"best_distance_exact={flat_backref.get('best_distance_exact_bytes', '0')} bytes"
            ),
            "blocking_evidence": (
                f"known_source={flat_backref.get('exact_known_source_bytes', '0')} bytes; "
                f"unresolved_source={flat_backref.get('exact_unresolved_source_bytes', '0')} bytes; "
                f"best_rule_false={flat_backref.get('best_rule_false_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "decode first occurrences before enabling distance-copy replay",
        },
        {
            "surface": "flat_walk_palette_seed",
            "rows": flat_palette_seed.get("candidate_rows", "0"),
            "bytes": flat_palette_seed.get("candidate_bytes", "0"),
            "positive_evidence": (
                f"control_candidate={flat_palette_seed.get('control_candidate_bytes', '0')} bytes; "
                f"copy_unlock={flat_palette_seed.get('copy_unlock_bytes', '0')} bytes; "
                f"potential={flat_palette_seed.get('total_candidate_plus_unlock_bytes', '0')} bytes"
            ),
            "blocking_evidence": (
                f"multirow_groups={flat_palette_seed.get('multirow_group_rows', '0')}; "
                f"best_group={flat_palette_seed.get('best_group', '')}; "
                "singleton only"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "seek a repeated palette-seed selector before replay promotion",
        },
        {
            "surface": "flat_walk_palette_mix",
            "rows": flat_palette_mix.get("candidate_rows", "0"),
            "bytes": flat_palette_mix.get("candidate_bytes", "0"),
            "positive_evidence": (
                f"control_candidate={flat_palette_mix.get('control_candidate_bytes', '0')} bytes; "
                f"mixed_candidate={flat_palette_mix.get('mixed_candidate_bytes', '0')} bytes; "
                f"copy_unlock={flat_palette_mix.get('copy_unlock_bytes', '0')} bytes; "
                f"potential={flat_palette_mix.get('total_candidate_plus_unlock_bytes', '0')} bytes"
            ),
            "blocking_evidence": (
                f"multirow_groups={flat_palette_mix.get('multirow_group_rows', '0')}; "
                f"best_group={flat_palette_mix.get('best_group', '')}; "
                f"max_mix={flat_palette_mix.get('max_mix_transforms', '0')}; review only"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "require repeated mixed-transform palette evidence before replay promotion",
        },
        {
            "surface": "flat_walk_backref_chain",
            "rows": flat_backref_chain.get("exact_copy_rows", "0"),
            "bytes": flat_backref_chain.get("any_source_chain_bytes", "0"),
            "positive_evidence": (
                f"exact_copy={flat_backref_chain.get('exact_copy_rows', '0')} rows/"
                f"{flat_backref_chain.get('exact_copy_bytes', '0')} bytes; "
                f"seed_sources={flat_backref_chain.get('seed_source_candidate_rows', '0')} rows/"
                f"{flat_backref_chain.get('seed_source_candidate_bytes', '0')} bytes; "
                f"mix_sources={flat_backref_chain.get('mix_source_candidate_rows', '0')} rows/"
                f"{flat_backref_chain.get('mix_source_candidate_bytes', '0')} bytes"
            ),
            "blocking_evidence": (
                f"repeated_chain={flat_backref_chain.get('repeated_group_chain_bytes', '0')} bytes; "
                f"blocked_chain={flat_backref_chain.get('blocked_chain_bytes', '0')} bytes; "
                f"promotion_ready={flat_backref_chain.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "find repeated first-occurrence palette groups before copy-chain replay",
        },
        {
            "surface": "flat_walk_palette_signature",
            "rows": flat_palette_signature.get("repeated_signature_rows", "0"),
            "bytes": flat_palette_signature.get("repeated_signature_bytes", "0"),
            "positive_evidence": (
                f"signature_groups={flat_palette_signature.get('signature_groups', '0')}; "
                f"repeated={flat_palette_signature.get('repeated_signature_groups', '0')} groups/"
                f"{flat_palette_signature.get('repeated_signature_bytes', '0')} bytes; "
                f"copy_backed={flat_palette_signature.get('copy_backed_signature_bytes', '0')} bytes"
            ),
            "blocking_evidence": (
                f"candidate_repeated={flat_palette_signature.get('candidate_repeated_bytes', '0')} bytes; "
                f"promotion_ready={flat_palette_signature.get('promotion_ready_bytes', '0')}; "
                "palette signature repeats without a repeated source producer"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "derive a repeated source producer for copy-backed palette signatures",
        },
        {
            "surface": "flat_walk_palette_context",
            "rows": flat_palette_context.get("context_rows", "0"),
            "bytes": flat_palette_context.get("repeated_signature_bytes", "0"),
            "positive_evidence": (
                f"copy_distance_320={flat_palette_context.get('copy_distance_320_rows', '0')} groups; "
                f"same_pool={flat_palette_context.get('same_candidate_pool_rows', '0')} groups; "
                f"best_overlap={flat_palette_context.get('best_unique_control_overlap', '0')}"
            ),
            "blocking_evidence": (
                f"same_transform={flat_palette_context.get('same_transform_set_rows', '0')}; "
                f"same_control_mod={flat_palette_context.get('same_control_ref_mod64_rows', '0')}; "
                f"shared_context={flat_palette_context.get('shared_context_rows', '0')}; "
                f"promotion_ready={flat_palette_context.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "look beyond fixed control-window context for repeated palette producers",
        },
        {
            "surface": "micro_token",
            "rows": str(micro_rows),
            "bytes": str(micro_bytes),
            "positive_evidence": (
                f"small_delta_ratio={micro_token.get('small_delta_ratio', '0')}; "
                f"signed_repeated_bytes={micro_token.get('signed_repeated_bytes', '0')}; "
                f"plateau_walk_bytes={micro_token.get('plateau_walk_bytes', '0')}"
            ),
            "blocking_evidence": (
                f"jump_delta_count={micro_token.get('jump_delta_count', '0')}; "
                f"jump_mixed_bytes={micro_token.get('jump_mixed_bytes', '0')}; "
                f"promotion_ready={micro_token.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "split jump-mixed rows before promoting signed-delta token shapes",
        },
        {
            "surface": "mixed_token_uniqueness",
            "rows": mixed_token_uniqueness.get("target_rows", "0"),
            "bytes": mixed_token_uniqueness.get("target_bytes", "0"),
            "positive_evidence": (
                f"top_nibble={mixed_token_uniqueness.get('dominant_top_nibble', '')} "
                f"{mixed_token_uniqueness.get('dominant_top_nibble_rows', '0')} rows/"
                f"{mixed_token_uniqueness.get('dominant_top_nibble_bytes', '0')} bytes; "
                f"control_ref_repeated={mixed_token_uniqueness.get('control_ref_repeated_bytes', '0')} bytes"
            ),
            "blocking_evidence": (
                f"coarse_repeated={mixed_token_uniqueness.get('coarse_repeated_bytes', '0')} bytes; "
                f"signed_repeated={mixed_token_uniqueness.get('signed_repeated_bytes', '0')} bytes; "
                f"profile_repeated={mixed_token_uniqueness.get('transition_profile_repeated_bytes', '0')} bytes; "
                f"promotion_ready={mixed_token_uniqueness.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "split mixed-token rows by coarse value band before token-shape promotion",
        },
        {
            "surface": "mixed_token_band",
            "rows": mixed_token_band.get("target_rows", "0"),
            "bytes": mixed_token_band.get("target_bytes", "0"),
            "positive_evidence": (
                f"top_nibble={mixed_token_band.get('dominant_top_nibble', '')} "
                f"{mixed_token_band.get('dominant_top_nibble_rows', '0')} rows/"
                f"{mixed_token_band.get('dominant_top_nibble_bytes', '0')} bytes; "
                f"low_profiles={mixed_token_band.get('low_profile_groups', '0')}"
            ),
            "blocking_evidence": (
                f"low_repeated={mixed_token_band.get('low_profile_repeated_bytes', '0')} bytes; "
                f"dominant_low_repeated={mixed_token_band.get('dominant_top_low_profile_repeated_bytes', '0')} bytes; "
                f"promotion_ready={mixed_token_band.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "seek external control for mixed-token value bands",
        },
        {
            "surface": "mixed_token_backref",
            "rows": mixed_token_backref.get("target_rows", "0"),
            "bytes": mixed_token_backref.get("target_bytes", "0"),
            "positive_evidence": (
                f"distance_rows={mixed_token_backref.get('distance_rows', '0')}; "
                f"best_distance={mixed_token_backref.get('best_distance', '0')}; "
                f"best_correct={mixed_token_backref.get('best_distance_correct_bytes', '0')} bytes"
            ),
            "blocking_evidence": (
                f"exact_copy={mixed_token_backref.get('exact_copy_bytes', '0')} bytes; "
                f"best_false={mixed_token_backref.get('best_distance_false_bytes', '0')} bytes; "
                f"best_rule_false={mixed_token_backref.get('best_rule_false_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "continue mixed-token grammar search without backward-copy replay",
        },
        {
            "surface": "mixed_token_control",
            "rows": mixed_token_control.get("target_rows", "0"),
            "bytes": mixed_token_control.get("target_bytes", "0"),
            "positive_evidence": (
                f"candidate_windows={mixed_token_control.get('candidate_windows', '0')}; "
                f"top_ge75={mixed_token_control.get('top_nibble_ge75_rows', '0')} rows; "
                f"best_ratio={mixed_token_control.get('best_overall_ratio', '0')}"
            ),
            "blocking_evidence": (
                f"top_only={mixed_token_control.get('top_nibble_only_bytes', '0')} bytes; "
                f"profile_like={mixed_token_control.get('profile_like_bytes', '0')} bytes; "
                f"byte_ge75={mixed_token_control.get('byte_ge75_rows', '0')}; "
                f"promotion_ready={mixed_token_control.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "reject high-nibble-only control matches and continue mixed-token value grammar",
        },
        {
            "surface": "mixed_token_control_context",
            "rows": mixed_token_control_context.get("target_rows", "0"),
            "bytes": mixed_token_control_context.get("target_bytes", "0"),
            "positive_evidence": (
                f"repeated_signal_top={mixed_token_control_context.get('repeated_signal_top_bytes', '0')} bytes; "
                f"repeated_offset_context={mixed_token_control_context.get('repeated_offset_context_bytes', '0')} bytes"
            ),
            "blocking_evidence": (
                f"payload_signatures={mixed_token_control_context.get('payload_signature_groups', '0')}; "
                f"repeated_payload={mixed_token_control_context.get('repeated_payload_bytes', '0')} bytes; "
                f"full_byte_ge50={mixed_token_control_context.get('full_byte_ge50_bytes', '0')} bytes"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "keep mixed-token control signals blocked until payload or full-byte context repeats",
        },
        {
            "surface": "jump_token",
            "rows": str(jump_rows),
            "bytes": str(jump_bytes),
            "positive_evidence": (
                f"long_island_bytes={jump_token.get('long_island_bytes', '0')}; "
                f"signed_repeated_bytes={jump_token.get('jump_signed_repeated_bytes', '0')}; "
                f"nibble_repeated_bytes={jump_token.get('jump_nibble_pair_repeated_bytes', '0')}"
            ),
            "blocking_evidence": (
                f"jump_delta_ratio={jump_token.get('jump_delta_ratio', '0')}; "
                f"exact_repeated_bytes={jump_token.get('jump_exact_pair_repeated_bytes', '0')}; "
                f"promotion_ready={jump_token.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "split dense jump weaves before exact byte-pair promotion",
        },
        {
            "surface": "jump_token_backref",
            "rows": jump_token_backref.get("target_rows", "0"),
            "bytes": jump_token_backref.get("target_bytes", "0"),
            "positive_evidence": (
                f"distance_rows={jump_token_backref.get('distance_rows', '0')}; "
                f"best_distance={jump_token_backref.get('best_distance', '0')}; "
                f"best_correct={jump_token_backref.get('best_distance_correct_bytes', '0')} bytes"
            ),
            "blocking_evidence": (
                f"exact_copy={jump_token_backref.get('exact_copy_bytes', '0')} bytes; "
                f"best_false={jump_token_backref.get('best_distance_false_bytes', '0')} bytes; "
                f"best_rule_false={jump_token_backref.get('best_rule_false_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "treat repeated jump shapes as grammar, not backward-copy replay",
        },
        {
            "surface": "jump_token_context",
            "rows": jump_token_context.get("target_rows", "0"),
            "bytes": jump_token_context.get("target_bytes", "0"),
            "positive_evidence": (
                f"repeated_groups={jump_token_context.get('repeated_group_rows', '0')}; "
                f"candidate_bytes={jump_token_context.get('repeated_candidate_bytes', '0')}; "
                f"same_structure_groups={jump_token_context.get('same_structure_groups', '0')}"
            ),
            "blocking_evidence": (
                f"shared_context={jump_token_context.get('shared_context_bytes', '0')} bytes; "
                f"conflicted_context={jump_token_context.get('conflicted_context_bytes', '0')} bytes; "
                f"copy_backed={jump_token_context.get('copy_backed_group_bytes', '0')} bytes"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "keep repeated jump-token context blocked until a shared decoder context emerges",
        },
        {
            "surface": "repeated_nibble",
            "rows": str(repeated_rows),
            "bytes": str(repeated_bytes),
            "positive_evidence": (
                f"pingpong_rows={repeated_nibble.get('pingpong_rows', '0')}; "
                f"repeated_band_bytes={repeated_nibble.get('repeated_band_pair_bytes', '0')}; "
                f"band_phase_repeated_bytes={repeated_nibble.get('band_phase_repeated_bytes', '0')}"
            ),
            "blocking_evidence": (
                f"best_source_ratio={repeated_nibble.get('best_overall_ratio', '0')}; "
                f"exact_repeated_bytes={repeated_nibble.get('exact_pair_repeated_bytes', '0')}; "
                f"promotion_ready={repeated_nibble.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "derive value-band grammar before byte-pair promotion",
        },
        {
            "surface": "repeated_nibble_context",
            "rows": repeated_nibble_context.get("target_rows", "0"),
            "bytes": repeated_nibble_context.get("target_bytes", "0"),
            "positive_evidence": (
                f"repeated_band={repeated_nibble_context.get('repeated_band_pair_bytes', '0')} bytes; "
                f"repeated_phase={repeated_nibble_context.get('repeated_phase_context_bytes', '0')} bytes"
            ),
            "blocking_evidence": (
                f"payload_signatures={repeated_nibble_context.get('payload_signature_groups', '0')}; "
                f"repeated_payload={repeated_nibble_context.get('repeated_payload_bytes', '0')} bytes; "
                f"source_ge50={repeated_nibble_context.get('source_ge50_bytes', '0')} bytes"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "keep repeated-nibble bands blocked until payload or source context repeats",
        },
        {
            "surface": "mixed_jump",
            "rows": str(mixed_rows),
            "bytes": str(mixed_bytes),
            "positive_evidence": (
                f"dominant_band_rows={mixed_jump.get('dominant_band_rows', '0')}; "
                f"zero_band_rows={mixed_jump.get('zero_band_rows', '0')}; "
                f"long_island_bytes={mixed_jump.get('long_island_bytes', '0')}"
            ),
            "blocking_evidence": (
                f"best_source_ratio={mixed_jump.get('best_overall_ratio', '0')}; "
                f"nibble_repeated_bytes={mixed_jump.get('nibble_repeated_bytes', '0')}; "
                f"promotion_ready={mixed_jump.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "split by dominant band before mixed jump promotion",
        },
        {
            "surface": "mixed_jump_context",
            "rows": mixed_jump_context.get("target_rows", "0"),
            "bytes": mixed_jump_context.get("target_bytes", "0"),
            "positive_evidence": (
                f"repeated_band={mixed_jump_context.get('repeated_band_pair_bytes', '0')} bytes; "
                f"dominant_band={mixed_jump_context.get('dominant_band_bytes', '0')} bytes"
            ),
            "blocking_evidence": (
                f"payload_signatures={mixed_jump_context.get('payload_signature_groups', '0')}; "
                f"repeated_payload={mixed_jump_context.get('repeated_payload_bytes', '0')} bytes; "
                f"source_ge50={mixed_jump_context.get('source_ge50_bytes', '0')} bytes"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "keep mixed-jump dominant bands blocked until payload context repeats",
        },
        {
            "surface": "mixed_control",
            "rows": str(mixed_control_rows),
            "bytes": str(mixed_control_bytes),
            "positive_evidence": (
                f"candidate_windows={mixed_control.get('candidate_windows', '0')}; "
                f"phase_ge75_rows={mixed_control.get('phase_ge75_rows', '0')}; "
                f"source_like_bytes={mixed_control.get('source_like_bytes', '0')}"
            ),
            "blocking_evidence": (
                f"phase_ge75_long_rows={mixed_control.get('phase_ge75_long_rows', '0')}; "
                f"phase_ge75_long_bytes={mixed_control.get('phase_ge75_long_bytes', '0')}; "
                f"promotion_ready={mixed_control.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "reject direction-only mixed jump signals and seek value grammar",
        },
        {
            "surface": "residual_jump",
            "rows": str(residual_rows),
            "bytes": str(residual_bytes),
            "positive_evidence": (
                f"sparse_rows={residual_jump.get('sparse_rows', '0')}; "
                f"long_island_bytes={residual_jump.get('long_island_bytes', '0')}; "
                f"dominant_band_rows={residual_jump.get('dominant_band_rows', '0')}"
            ),
            "blocking_evidence": (
                f"best_source_ratio={residual_jump.get('best_overall_ratio', '0')}; "
                f"exact_repeated_bytes={residual_jump.get('exact_repeated_bytes', '0')}; "
                f"promotion_ready={residual_jump.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "fold sparse and long-island residuals into the next control grammar pass",
        },
        {
            "surface": "residual_control",
            "rows": str(residual_control_rows),
            "bytes": str(residual_control_bytes),
            "positive_evidence": (
                f"candidate_windows={residual_control.get('candidate_windows', '0')}; "
                f"phase_ge75_rows={residual_control.get('phase_ge75_rows', '0')}; "
                f"source_like_bytes={residual_control.get('source_like_bytes', '0')}"
            ),
            "blocking_evidence": (
                f"phase_ge75_long_rows={residual_control.get('phase_ge75_long_rows', '0')}; "
                f"phase_ge75_long_bytes={residual_control.get('phase_ge75_long_bytes', '0')}; "
                f"promotion_ready={residual_control.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "discard short residual-control coincidences and require long phase evidence",
        },
        {
            "surface": "dense_jump",
            "rows": str(dense_rows),
            "bytes": str(dense_bytes),
            "positive_evidence": (
                f"direction_switch_ratio={dense_jump.get('direction_switch_ratio', '0')}; "
                f"single_byte_island_ratio={dense_jump.get('single_byte_island_ratio', '0')}; "
                f"alternating_bytes={dense_jump.get('alternating_bytes', '0')}"
            ),
            "blocking_evidence": (
                f"phase_repeated_bytes={dense_jump.get('phase_repeated_bytes', '0')}; "
                f"direction_repeated_bytes={dense_jump.get('direction_repeated_bytes', '0')}; "
                f"promotion_ready={dense_jump.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "seek an external control signal for dense jump weave phases",
        },
        {
            "surface": "dense_control",
            "rows": str(dense_control_rows),
            "bytes": str(dense_control_bytes),
            "positive_evidence": (
                f"direction_ge75_rows={dense_control.get('direction_ge75_rows', '0')}; "
                f"phase_ge75_rows={dense_control.get('phase_ge75_rows', '0')}; "
                f"source_like_bytes={dense_control.get('source_like_bytes', '0')}"
            ),
            "blocking_evidence": (
                f"candidate_windows={dense_control.get('candidate_windows', '0')}; "
                f"phase_ge75_long_rows={dense_control.get('phase_ge75_long_rows', '0')}; "
                f"promotion_ready={dense_control.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "reject short control coincidences and require long phase matches",
        },
        {
            "surface": "control_signal_gate",
            "rows": str(control_signal_gate_rows),
            "bytes": str(control_signal_gate_bytes),
            "positive_evidence": (
                f"surfaces={control_signal_gate.get('surface_count', '0')}; "
                f"candidate_windows={control_signal_gate.get('candidate_windows', '0')}; "
                f"direction_ge75_bytes={control_signal_gate.get('direction_ge75_bytes', '0')}"
            ),
            "blocking_evidence": (
                f"direction_only_bytes={control_signal_gate.get('direction_only_bytes', '0')}; "
                f"short_phase_bytes={control_signal_gate.get('short_phase_bytes', '0')}; "
                f"phase_ge75_long_bytes={control_signal_gate.get('phase_ge75_long_bytes', '0')}; "
                f"promotion_ready={control_signal_gate.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "treat direction-only control matches as rejected evidence and continue value grammar search",
        },
        {
            "surface": "weak_control_value",
            "rows": weak_control_value.get("target_rows", "0"),
            "bytes": weak_control_value.get("target_bytes", "0"),
            "positive_evidence": (
                f"magnitude_ge75={weak_control_value.get('magnitude_ge75_rows', '0')} rows/"
                f"{weak_control_value.get('magnitude_ge75_bytes', '0')} bytes; "
                f"repeated_signal={weak_control_value.get('best_signal_repeated_bytes', '0')} bytes"
            ),
            "blocking_evidence": (
                f"payload_signatures={weak_control_value.get('payload_signature_groups', '0')}; "
                f"repeated_payload={weak_control_value.get('repeated_payload_bytes', '0')} bytes; "
                f"promotion_ready={weak_control_value.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "keep weak control rows blocked until payload-level reuse appears",
        },
        {
            "surface": "direction_value",
            "rows": direction_value.get("target_rows", "0"),
            "bytes": direction_value.get("target_bytes", "0"),
            "positive_evidence": (
                f"value_ge75={direction_value.get('value_ge75_rows', '0')} rows/"
                f"{direction_value.get('value_ge75_bytes', '0')} bytes; "
                f"value_exact={direction_value.get('value_exact_rows', '0')} rows/"
                f"{direction_value.get('value_exact_bytes', '0')} bytes"
            ),
            "blocking_evidence": (
                f"repeated_direction_value={direction_value.get('repeated_direction_value_groups', '0')} groups/"
                f"{direction_value.get('repeated_direction_value_bytes', '0')} bytes; "
                f"conflicted_offset={direction_value.get('conflicted_offset_bytes', '0')} bytes; "
                f"promotion_ready={direction_value.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "split value buckets by stable offset before any direction-value promotion",
        },
        {
            "surface": "direction_value_offset",
            "rows": direction_value_offset.get("target_rows", "0"),
            "bytes": direction_value_offset.get("target_bytes", "0"),
            "positive_evidence": (
                f"value_exact={direction_value_offset.get('value_exact_rows', '0')} rows/"
                f"{direction_value_offset.get('value_exact_bytes', '0')} bytes; "
                f"repeated_key={direction_value_offset.get('repeated_key_groups', '0')} groups/"
                f"{direction_value_offset.get('repeated_key_bytes', '0')} bytes"
            ),
            "blocking_evidence": (
                f"same_delta={direction_value_offset.get('same_delta_bytes', '0')} bytes; "
                f"surface_stable={direction_value_offset.get('surface_stable_delta_bytes', '0')} bytes; "
                f"conflicted_delta={direction_value_offset.get('conflicted_delta_bytes', '0')} bytes"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "discard direction-value offset shortcuts and continue grammar search",
        },
        {
            "surface": "direction_value_delta_context",
            "rows": direction_value_delta_context.get("target_rows", "0"),
            "bytes": direction_value_delta_context.get("target_bytes", "0"),
            "positive_evidence": (
                f"best_context={direction_value_delta_context.get('best_context_name', '')}; "
                f"best_stable={direction_value_delta_context.get('best_stable_bytes', '0')} bytes; "
                f"split_all_singleton={direction_value_delta_context.get('split_all_singleton_bytes', '0')} bytes"
            ),
            "blocking_evidence": (
                f"repeated_stable={direction_value_delta_context.get('best_repeated_stable_bytes', '0')} bytes; "
                f"repeated_payload={direction_value_delta_context.get('repeated_payload_bytes', '0')} bytes; "
                f"promotion_ready={direction_value_delta_context.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "reject singleton-only delta splits and look for a grammar signal shared across rows",
        },
        {
            "surface": "direction_value_payload_grammar",
            "rows": direction_value_payload_grammar.get("target_rows", "0"),
            "bytes": direction_value_payload_grammar.get("target_bytes", "0"),
            "positive_evidence": (
                f"top_token_nibble_repeat="
                f"{direction_value_payload_grammar.get('repeated_top_token_nibble_bytes', '0')} bytes; "
                f"dominant_jump={direction_value_payload_grammar.get('dominant_jump_bytes', '0')} bytes"
            ),
            "blocking_evidence": (
                f"transition_profile_repeat="
                f"{direction_value_payload_grammar.get('repeated_transition_profile_bytes', '0')} bytes; "
                f"repeated_payload={direction_value_payload_grammar.get('repeated_payload_bytes', '0')} bytes; "
                f"exact_profile_unique={direction_value_payload_grammar.get('exact_profile_unique_bytes', '0')} bytes"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "treat broad payload bands as hints only until transition profiles repeat",
        },
        {
            "surface": "direction_value_source_profile",
            "rows": direction_value_source_profile.get("target_rows", "0"),
            "bytes": direction_value_source_profile.get("target_bytes", "0"),
            "positive_evidence": (
                f"best_segment_gap={direction_value_source_profile.get('best_segment_gap_bytes', '0')} bytes; "
                f"profile_overlap_ge75={direction_value_source_profile.get('profile_overlap_ge75_bytes', '0')} bytes; "
                f"exact_profile={direction_value_source_profile.get('exact_profile_match_bytes', '0')} bytes"
            ),
            "blocking_evidence": (
                f"positional_ge50={direction_value_source_profile.get('positional_ge50_bytes', '0')} bytes; "
                f"repeated_source_profile={direction_value_source_profile.get('repeated_source_profile_bytes', '0')} bytes; "
                f"promotion_ready={direction_value_source_profile.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "use segment-gap profile overlap as evidence, but require repeated source profiles before replay",
        },
        {
            "surface": "direction_value_source_value",
            "rows": direction_value_source_value.get("target_rows", "0"),
            "bytes": direction_value_source_value.get("target_bytes", "0"),
            "positive_evidence": (
                f"transforms={direction_value_source_value.get('transform_count', '0')}; "
                f"best_exact_total={direction_value_source_value.get('best_exact_total', '0')} bytes; "
                f"top_transform={direction_value_source_value.get('top_best_transform', '')}"
            ),
            "blocking_evidence": (
                f"max_ratio={direction_value_source_value.get('best_exact_ratio_max', '0')}; "
                f"rows_ge25={direction_value_source_value.get('rows_ge25', '0')}; "
                f"exact_match_bytes={direction_value_source_value.get('exact_match_bytes', '0')}; "
                f"promotion_ready={direction_value_source_value.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "reject fixed source-value transforms and keep looking for a control grammar",
        },
        {
            "surface": "direction_value_source_window",
            "rows": direction_value_source_window.get("target_rows", "0"),
            "bytes": direction_value_source_window.get("target_bytes", "0"),
            "positive_evidence": (
                f"radius={direction_value_source_window.get('scan_radius', '0')}; "
                f"best_exact_total={direction_value_source_window.get('best_exact_total', '0')} bytes; "
                f"rows_ge25={direction_value_source_window.get('rows_ge25', '0')}"
            ),
            "blocking_evidence": (
                f"max_ratio={direction_value_source_window.get('best_exact_ratio_max', '0')}; "
                f"rows_ge50={direction_value_source_window.get('rows_ge50', '0')}; "
                f"exact_match_bytes={direction_value_source_window.get('exact_match_bytes', '0')}; "
                f"promotion_ready={direction_value_source_window.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "reject local source-window drift unless a stronger grammar or repeated replay signal appears",
        },
        {
            "surface": "direction_value_control_context",
            "rows": direction_value_control_context.get("target_rows", "0"),
            "bytes": direction_value_control_context.get("target_bytes", "0"),
            "positive_evidence": (
                f"direction_signal_repeat="
                f"{direction_value_control_context.get('repeated_direction_signal_bytes', '0')} bytes; "
                f"direction_context_repeat="
                f"{direction_value_control_context.get('repeated_direction_context_bytes', '0')} bytes; "
                f"best_context={direction_value_control_context.get('best_repeated_context', '')}"
            ),
            "blocking_evidence": (
                f"combined_context_repeat="
                f"{direction_value_control_context.get('repeated_combined_context_bytes', '0')} bytes; "
                f"op_phase_repeat={direction_value_control_context.get('repeated_op_phase_bytes', '0')} bytes; "
                f"repeated_payload={direction_value_control_context.get('repeated_payload_bytes', '0')} bytes; "
                f"promotion_ready={direction_value_control_context.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "treat raw signal repetition as too broad until combined control context or payload repeats",
        },
        {
            "surface": "direction_value_exact_context",
            "rows": direction_value_exact_context.get("target_rows", "0"),
            "bytes": direction_value_exact_context.get("target_bytes", "0"),
            "positive_evidence": (
                f"repeated_key={direction_value_exact_context.get('repeated_key_groups', '0')} groups/"
                f"{direction_value_exact_context.get('repeated_key_bytes', '0')} bytes; "
                f"payload_signatures={direction_value_exact_context.get('payload_signature_groups', '0')}"
            ),
            "blocking_evidence": (
                f"repeated_payload={direction_value_exact_context.get('repeated_payload_bytes', '0')} bytes; "
                f"conflicted_delta={direction_value_exact_context.get('conflicted_delta_bytes', '0')} bytes; "
                f"promotion_ready={direction_value_exact_context.get('promotion_ready_bytes', '0')}"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "treat exact value buckets as unique local payloads until payload reuse appears",
        },
        {
            "surface": "direction_value_partial_context",
            "rows": direction_value_partial_context.get("target_rows", "0"),
            "bytes": direction_value_partial_context.get("target_bytes", "0"),
            "positive_evidence": (
                f"ratio_ge90={direction_value_partial_context.get('ratio_ge90_rows', '0')} rows/"
                f"{direction_value_partial_context.get('ratio_ge90_bytes', '0')} bytes; "
                f"best_value_exact_total={direction_value_partial_context.get('best_value_exact_total', '0')}"
            ),
            "blocking_evidence": (
                f"repeated_key={direction_value_partial_context.get('repeated_key_bytes', '0')} bytes; "
                f"repeated_payload={direction_value_partial_context.get('repeated_payload_bytes', '0')} bytes; "
                f"conflicted_delta={direction_value_partial_context.get('conflicted_delta_bytes', '0')} bytes"
            ),
            "promotion_ready_bytes": "0",
            "next_action": "treat partial value buckets as local evidence until payload reuse appears",
        },
    ]
    issue_rows = (
        int_value(noisy, "issue_rows")
        + int_value(gradient, "issue_rows")
        + int_value(gradient_repeat_context, "issue_rows")
        + int_value(gradient_seed_unlock, "issue_rows")
        + int_value(gradient_seed_shift_family, "issue_rows")
        + int_value(gradient_seed_delta_selector, "issue_rows")
        + int_value(gradient_seed_delta_context, "issue_rows")
        + int_value(gradient_seed_delta_phase, "issue_rows")
        + int_value(gradient_seed_delta_state, "issue_rows")
        + int_value(gradient_seed_delta_opcode_sequence, "issue_rows")
        + int_value(gradient_seed_delta_semantic_opcode, "issue_rows")
        + int_value(gradient_seed_delta_payload_opcode, "issue_rows")
        + int_value(flat, "issue_rows")
        + int_value(flat_source, "issue_rows")
        + int_value(flat_shape_control, "issue_rows")
        + int_value(flat_value, "issue_rows")
        + int_value(flat_backref, "issue_rows")
        + int_value(flat_palette_seed, "issue_rows")
        + int_value(flat_palette_mix, "issue_rows")
        + int_value(flat_backref_chain, "issue_rows")
        + int_value(flat_palette_signature, "issue_rows")
        + int_value(flat_palette_context, "issue_rows")
        + int_value(micro_token, "issue_rows")
        + int_value(mixed_token_uniqueness, "issue_rows")
        + int_value(mixed_token_band, "issue_rows")
        + int_value(mixed_token_backref, "issue_rows")
        + int_value(mixed_token_control, "issue_rows")
        + int_value(mixed_token_control_context, "issue_rows")
        + int_value(jump_token, "issue_rows")
        + int_value(jump_token_backref, "issue_rows")
        + int_value(jump_token_context, "issue_rows")
        + int_value(repeated_nibble, "issue_rows")
        + int_value(repeated_nibble_context, "issue_rows")
        + int_value(mixed_jump, "issue_rows")
        + int_value(mixed_jump_context, "issue_rows")
        + int_value(mixed_control, "issue_rows")
        + int_value(residual_jump, "issue_rows")
        + int_value(residual_control, "issue_rows")
        + int_value(dense_jump, "issue_rows")
        + int_value(dense_control, "issue_rows")
        + int_value(control_signal_gate, "issue_rows")
        + int_value(weak_control_value, "issue_rows")
        + int_value(direction_value, "issue_rows")
        + int_value(direction_value_offset, "issue_rows")
        + int_value(direction_value_delta_context, "issue_rows")
        + int_value(direction_value_payload_grammar, "issue_rows")
        + int_value(direction_value_source_profile, "issue_rows")
        + int_value(direction_value_source_value, "issue_rows")
        + int_value(direction_value_source_window, "issue_rows")
        + int_value(direction_value_control_context, "issue_rows")
        + int_value(direction_value_exact_context, "issue_rows")
        + int_value(direction_value_partial_context, "issue_rows")
    )
    summary = {
        "scope": "total",
        "noisy_rows": str(noisy_rows),
        "noisy_bytes": str(noisy_bytes),
        "gradient_rows": str(gradient_rows),
        "gradient_bytes": str(gradient_bytes),
        "gradient_repeat_context_rows": gradient_repeat_context.get("target_rows", "0"),
        "gradient_repeat_context_bytes": gradient_repeat_context.get("target_bytes", "0"),
        "gradient_repeat_context_repeated_payload_bytes": gradient_repeat_context.get("repeated_payload_bytes", "0"),
        "gradient_repeat_context_copy_distance_320_bytes": gradient_repeat_context.get(
            "copy_distance_320_bytes", "0"
        ),
        "gradient_repeat_context_copy_unlock_bytes": gradient_repeat_context.get("copy_unlock_bytes", "0"),
        "gradient_repeat_context_control_ref_distinct_groups": gradient_repeat_context.get(
            "control_ref_distinct_groups", "0"
        ),
        "gradient_seed_unlock_seed_bytes": gradient_seed_unlock.get("seed_bytes", "0"),
        "gradient_seed_unlock_candidate_seed_bytes": gradient_seed_unlock.get("candidate_seed_bytes", "0"),
        "gradient_seed_unlock_control_seed_bytes": gradient_seed_unlock.get("control_seed_bytes", "0"),
        "gradient_seed_unlock_single_transform_seed_bytes": gradient_seed_unlock.get(
            "single_transform_seed_bytes", "0"
        ),
        "gradient_seed_unlock_mixed_transform_seed_bytes": gradient_seed_unlock.get(
            "mixed_transform_seed_bytes", "0"
        ),
        "gradient_seed_unlock_copy_unlock_bytes": gradient_seed_unlock.get("copy_unlock_bytes", "0"),
        "gradient_seed_unlock_total_potential_bytes": gradient_seed_unlock.get(
            "total_seed_plus_unlock_bytes", "0"
        ),
        "gradient_seed_unlock_repeated_transform_set_bytes": gradient_seed_unlock.get(
            "repeated_transform_set_bytes", "0"
        ),
        "gradient_seed_unlock_blocked_seed_bytes": gradient_seed_unlock.get("blocked_seed_bytes", "0"),
        "gradient_seed_shift_family_candidate_bytes": gradient_seed_shift_family.get("candidate_bytes", "0"),
        "gradient_seed_shift_family_identity_bytes": gradient_seed_shift_family.get(
            "identity_shift_family_bytes", "0"
        ),
        "gradient_seed_shift_family_repeated_family_bytes": gradient_seed_shift_family.get(
            "repeated_family_bytes", "0"
        ),
        "gradient_seed_shift_family_repeated_exact_shift_set_bytes": gradient_seed_shift_family.get(
            "repeated_exact_shift_set_bytes", "0"
        ),
        "gradient_seed_shift_family_copy_unlock_bytes": gradient_seed_shift_family.get(
            "copy_unlock_bytes", "0"
        ),
        "gradient_seed_shift_family_total_potential_bytes": gradient_seed_shift_family.get(
            "total_potential_bytes", "0"
        ),
        "gradient_seed_shift_family_distinct_shift_deltas": gradient_seed_shift_family.get(
            "distinct_shift_deltas", "0"
        ),
        "gradient_seed_delta_selector_mapping_bytes": gradient_seed_delta_selector.get("mapping_value_bytes", "0"),
        "gradient_seed_delta_selector_source_only_repeated_bytes": gradient_seed_delta_selector.get(
            "source_only_repeated_deterministic_bytes", "0"
        ),
        "gradient_seed_delta_selector_source_only_conflicted_bytes": gradient_seed_delta_selector.get(
            "source_only_conflicted_bytes", "0"
        ),
        "gradient_seed_delta_selector_best_source_family": gradient_seed_delta_selector.get(
            "best_source_only_family", ""
        ),
        "gradient_seed_delta_selector_row_local_repeated_bytes": gradient_seed_delta_selector.get(
            "row_local_repeated_deterministic_bytes", "0"
        ),
        "gradient_seed_delta_selector_target_oracle_repeated_bytes": gradient_seed_delta_selector.get(
            "target_oracle_repeated_deterministic_bytes", "0"
        ),
        "gradient_seed_delta_selector_delta_values": gradient_seed_delta_selector.get("delta_values", "0"),
        "gradient_seed_delta_context_mapping_bytes": gradient_seed_delta_context.get("mapping_value_bytes", "0"),
        "gradient_seed_delta_context_repeated_bytes": gradient_seed_delta_context.get(
            "source_context_repeated_deterministic_bytes", "0"
        ),
        "gradient_seed_delta_context_singleton_bytes": gradient_seed_delta_context.get(
            "source_context_singleton_deterministic_bytes", "0"
        ),
        "gradient_seed_delta_context_conflicted_bytes": gradient_seed_delta_context.get(
            "source_context_conflicted_bytes", "0"
        ),
        "gradient_seed_delta_context_best_family": gradient_seed_delta_context.get(
            "best_source_context_family", ""
        ),
        "gradient_seed_delta_context_delta_values": gradient_seed_delta_context.get("delta_values", "0"),
        "gradient_seed_delta_phase_mapping_bytes": gradient_seed_delta_phase.get("mapping_value_bytes", "0"),
        "gradient_seed_delta_phase_selector_groups": gradient_seed_delta_phase.get("selector_groups", "0"),
        "gradient_seed_delta_phase_repeated_bytes": gradient_seed_delta_phase.get(
            "repeated_deterministic_bytes", "0"
        ),
        "gradient_seed_delta_phase_source_value_repeated_bytes": gradient_seed_delta_phase.get(
            "source_value_phase_repeated_bytes", "0"
        ),
        "gradient_seed_delta_phase_broad_control_repeated_bytes": gradient_seed_delta_phase.get(
            "broad_control_phase_repeated_bytes", "0"
        ),
        "gradient_seed_delta_phase_wide_relative_repeated_bytes": gradient_seed_delta_phase.get(
            "wide_relative_repeated_bytes", "0"
        ),
        "gradient_seed_delta_phase_conflicted_bytes": gradient_seed_delta_phase.get("conflicted_bytes", "0"),
        "gradient_seed_delta_phase_best_family": gradient_seed_delta_phase.get("best_phase_family", ""),
        "gradient_seed_delta_phase_delta_values": gradient_seed_delta_phase.get("delta_values", "0"),
        "gradient_seed_delta_state_mapping_bytes": gradient_seed_delta_state.get("mapping_value_bytes", "0"),
        "gradient_seed_delta_state_groups": gradient_seed_delta_state.get("state_groups", "0"),
        "gradient_seed_delta_state_repeated_bytes": gradient_seed_delta_state.get(
            "repeated_deterministic_bytes", "0"
        ),
        "gradient_seed_delta_state_prefix_repeated_bytes": gradient_seed_delta_state.get(
            "prefix_accumulator_repeated_bytes", "0"
        ),
        "gradient_seed_delta_state_fsm_repeated_bytes": gradient_seed_delta_state.get("fsm_repeated_bytes", "0"),
        "gradient_seed_delta_state_nibble_repeated_bytes": gradient_seed_delta_state.get(
            "nibble_counter_repeated_bytes", "0"
        ),
        "gradient_seed_delta_state_parser_repeated_bytes": gradient_seed_delta_state.get(
            "parser_counter_repeated_bytes", "0"
        ),
        "gradient_seed_delta_state_conflicted_bytes": gradient_seed_delta_state.get("conflicted_bytes", "0"),
        "gradient_seed_delta_state_best_family": gradient_seed_delta_state.get("best_state_family", ""),
        "gradient_seed_delta_state_delta_values": gradient_seed_delta_state.get("delta_values", "0"),
        "gradient_seed_delta_opcode_sequence_mapping_bytes": gradient_seed_delta_opcode_sequence.get(
            "mapping_value_bytes", "0"
        ),
        "gradient_seed_delta_opcode_sequence_transition_groups": gradient_seed_delta_opcode_sequence.get(
            "transition_groups", "0"
        ),
        "gradient_seed_delta_opcode_sequence_repeated_bytes": gradient_seed_delta_opcode_sequence.get(
            "repeated_transition_bytes", "0"
        ),
        "gradient_seed_delta_opcode_sequence_conflicted_bytes": gradient_seed_delta_opcode_sequence.get(
            "conflicted_transition_bytes", "0"
        ),
        "gradient_seed_delta_opcode_sequence_offset_reuse_bytes": gradient_seed_delta_opcode_sequence.get(
            "offset_reuse_bytes", "0"
        ),
        "gradient_seed_delta_opcode_sequence_constant_seed_rows": gradient_seed_delta_opcode_sequence.get(
            "constant_delta_seed_rows", "0"
        ),
        "gradient_seed_delta_opcode_sequence_best_family": gradient_seed_delta_opcode_sequence.get(
            "best_transition_family", ""
        ),
        "gradient_seed_delta_semantic_opcode_mapping_bytes": gradient_seed_delta_semantic_opcode.get(
            "mapping_value_bytes", "0"
        ),
        "gradient_seed_delta_semantic_opcode_groups": gradient_seed_delta_semantic_opcode.get(
            "semantic_groups", "0"
        ),
        "gradient_seed_delta_semantic_opcode_repeated_bytes": gradient_seed_delta_semantic_opcode.get(
            "repeated_deterministic_bytes", "0"
        ),
        "gradient_seed_delta_semantic_opcode_op_context_repeated_bytes": gradient_seed_delta_semantic_opcode.get(
            "op_context_repeated_bytes", "0"
        ),
        "gradient_seed_delta_semantic_opcode_op_neighborhood_repeated_bytes": (
            gradient_seed_delta_semantic_opcode.get("op_neighborhood_repeated_bytes", "0")
        ),
        "gradient_seed_delta_semantic_opcode_source_role_repeated_bytes": gradient_seed_delta_semantic_opcode.get(
            "source_role_repeated_bytes", "0"
        ),
        "gradient_seed_delta_semantic_opcode_control_token_repeated_bytes": (
            gradient_seed_delta_semantic_opcode.get("control_token_repeated_bytes", "0")
        ),
        "gradient_seed_delta_semantic_opcode_combo_repeated_bytes": gradient_seed_delta_semantic_opcode.get(
            "semantic_combo_repeated_bytes", "0"
        ),
        "gradient_seed_delta_semantic_opcode_conflicted_bytes": gradient_seed_delta_semantic_opcode.get(
            "conflicted_bytes", "0"
        ),
        "gradient_seed_delta_semantic_opcode_best_family": gradient_seed_delta_semantic_opcode.get(
            "best_semantic_family", ""
        ),
        "gradient_seed_delta_payload_opcode_mapping_bytes": gradient_seed_delta_payload_opcode.get(
            "mapping_value_bytes", "0"
        ),
        "gradient_seed_delta_payload_opcode_groups": gradient_seed_delta_payload_opcode.get("token_groups", "0"),
        "gradient_seed_delta_payload_opcode_repeated_bytes": gradient_seed_delta_payload_opcode.get(
            "repeated_deterministic_bytes", "0"
        ),
        "gradient_seed_delta_payload_opcode_raw_byte_repeated_bytes": gradient_seed_delta_payload_opcode.get(
            "raw_byte_repeated_bytes", "0"
        ),
        "gradient_seed_delta_payload_opcode_bitfield_repeated_bytes": gradient_seed_delta_payload_opcode.get(
            "bitfield_repeated_bytes", "0"
        ),
        "gradient_seed_delta_payload_opcode_local_ngram_repeated_bytes": gradient_seed_delta_payload_opcode.get(
            "local_ngram_repeated_bytes", "0"
        ),
        "gradient_seed_delta_payload_opcode_offset_token_repeated_bytes": gradient_seed_delta_payload_opcode.get(
            "offset_token_repeated_bytes", "0"
        ),
        "gradient_seed_delta_payload_opcode_sequence_role_repeated_bytes": gradient_seed_delta_payload_opcode.get(
            "sequence_role_repeated_bytes", "0"
        ),
        "gradient_seed_delta_payload_opcode_combo_repeated_bytes": gradient_seed_delta_payload_opcode.get(
            "payload_combo_repeated_bytes", "0"
        ),
        "gradient_seed_delta_payload_opcode_conflicted_bytes": gradient_seed_delta_payload_opcode.get(
            "conflicted_bytes", "0"
        ),
        "gradient_seed_delta_payload_opcode_best_family": gradient_seed_delta_payload_opcode.get(
            "best_token_family", ""
        ),
        "flat_walk_rows": str(flat_rows),
        "flat_walk_bytes": str(flat_bytes),
        "plateau_bytes": flat.get("plateau_bytes", "0"),
        "flat_length_exact_total": str(length_exact),
        "flat_length_symbol_count": str(length_symbols),
        "flat_transition_exact_total": str(transition_exact),
        "flat_transition_symbol_count": str(transition_symbols),
        "flat_shape_control_selector_rows": flat_shape_control.get("selector_rows", "0"),
        "flat_shape_control_repeated_pure_rows": flat_shape_control.get("repeated_pure_selector_rows", "0"),
        "flat_shape_control_repeated_pure_covered_bytes": flat_shape_control.get(
            "repeated_pure_covered_bytes", "0"
        ),
        "flat_shape_control_best_repeated_pure_bytes": flat_shape_control.get(
            "best_repeated_pure_bytes", "0"
        ),
        "flat_value_rule_rows": flat_value.get("rule_rows", "0"),
        "flat_value_false_free_multirow_rules": flat_value.get("false_free_multirow_rule_rows", "0"),
        "flat_value_best_any_correct_bytes": flat_value.get("best_any_correct_bytes", "0"),
        "flat_value_best_any_false_bytes": flat_value.get("best_any_false_bytes", "0"),
        "flat_value_prefix_copy_exact_bytes": flat_value.get("prefix_copy_exact_bytes", "0"),
        "flat_backref_exact_copy_bytes": flat_backref.get("exact_copy_bytes", "0"),
        "flat_backref_exact_known_source_bytes": flat_backref.get("exact_known_source_bytes", "0"),
        "flat_backref_exact_unresolved_source_bytes": flat_backref.get("exact_unresolved_source_bytes", "0"),
        "flat_backref_best_distance": flat_backref.get("best_distance", "0"),
        "flat_palette_seed_candidate_bytes": flat_palette_seed.get("candidate_bytes", "0"),
        "flat_palette_seed_control_candidate_bytes": flat_palette_seed.get("control_candidate_bytes", "0"),
        "flat_palette_seed_copy_unlock_bytes": flat_palette_seed.get("copy_unlock_bytes", "0"),
        "flat_palette_seed_total_potential_bytes": flat_palette_seed.get("total_candidate_plus_unlock_bytes", "0"),
        "flat_palette_seed_multirow_group_rows": flat_palette_seed.get("multirow_group_rows", "0"),
        "flat_palette_mix_candidate_bytes": flat_palette_mix.get("candidate_bytes", "0"),
        "flat_palette_mix_control_candidate_bytes": flat_palette_mix.get("control_candidate_bytes", "0"),
        "flat_palette_mix_mixed_candidate_bytes": flat_palette_mix.get("mixed_candidate_bytes", "0"),
        "flat_palette_mix_copy_unlock_bytes": flat_palette_mix.get("copy_unlock_bytes", "0"),
        "flat_palette_mix_total_potential_bytes": flat_palette_mix.get("total_candidate_plus_unlock_bytes", "0"),
        "flat_palette_mix_multirow_group_rows": flat_palette_mix.get("multirow_group_rows", "0"),
        "flat_backref_chain_any_source_chain_bytes": flat_backref_chain.get("any_source_chain_bytes", "0"),
        "flat_backref_chain_repeated_group_chain_bytes": flat_backref_chain.get("repeated_group_chain_bytes", "0"),
        "flat_backref_chain_blocked_chain_bytes": flat_backref_chain.get("blocked_chain_bytes", "0"),
        "flat_palette_signature_repeated_bytes": flat_palette_signature.get("repeated_signature_bytes", "0"),
        "flat_palette_signature_copy_backed_bytes": flat_palette_signature.get("copy_backed_signature_bytes", "0"),
        "flat_palette_signature_candidate_repeated_bytes": flat_palette_signature.get("candidate_repeated_bytes", "0"),
        "flat_palette_context_shared_rows": flat_palette_context.get("shared_context_rows", "0"),
        "flat_palette_context_best_overlap": flat_palette_context.get("best_unique_control_overlap", "0"),
        "micro_token_rows": str(micro_rows),
        "micro_token_bytes": str(micro_bytes),
        "micro_small_delta_count": micro_token.get("small_delta_count", "0"),
        "micro_jump_delta_count": micro_token.get("jump_delta_count", "0"),
        "micro_signed_repeated_bytes": micro_token.get("signed_repeated_bytes", "0"),
        "micro_jump_mixed_bytes": micro_token.get("jump_mixed_bytes", "0"),
        "mixed_token_rows": mixed_token_uniqueness.get("target_rows", "0"),
        "mixed_token_bytes": mixed_token_uniqueness.get("target_bytes", "0"),
        "mixed_token_signed_repeated_bytes": mixed_token_uniqueness.get("signed_repeated_bytes", "0"),
        "mixed_token_dominant_top_nibble_bytes": mixed_token_uniqueness.get("dominant_top_nibble_bytes", "0"),
        "mixed_token_band_low_repeated_bytes": mixed_token_band.get("low_profile_repeated_bytes", "0"),
        "mixed_token_band_dominant_low_repeated_bytes": mixed_token_band.get(
            "dominant_top_low_profile_repeated_bytes", "0"
        ),
        "mixed_token_backref_exact_copy_bytes": mixed_token_backref.get("exact_copy_bytes", "0"),
        "mixed_token_backref_best_false_bytes": mixed_token_backref.get("best_distance_false_bytes", "0"),
        "mixed_token_control_candidate_windows": mixed_token_control.get("candidate_windows", "0"),
        "mixed_token_control_top_only_bytes": mixed_token_control.get("top_nibble_only_bytes", "0"),
        "mixed_token_control_profile_like_bytes": mixed_token_control.get("profile_like_bytes", "0"),
        "mixed_token_control_best_ratio": mixed_token_control.get("best_overall_ratio", "0"),
        "mixed_token_control_context_repeated_signal_bytes": mixed_token_control_context.get(
            "repeated_signal_top_bytes", "0"
        ),
        "mixed_token_control_context_repeated_offset_bytes": mixed_token_control_context.get(
            "repeated_offset_context_bytes", "0"
        ),
        "mixed_token_control_context_repeated_payload_bytes": mixed_token_control_context.get(
            "repeated_payload_bytes", "0"
        ),
        "mixed_token_control_context_full_byte_ge50_bytes": mixed_token_control_context.get(
            "full_byte_ge50_bytes", "0"
        ),
        "jump_token_rows": str(jump_rows),
        "jump_token_bytes": str(jump_bytes),
        "jump_delta_count": jump_token.get("jump_delta_count", "0"),
        "jump_delta_ratio": jump_token.get("jump_delta_ratio", "0"),
        "jump_long_island_bytes": jump_token.get("long_island_bytes", "0"),
        "jump_signed_repeated_bytes": jump_token.get("jump_signed_repeated_bytes", "0"),
        "jump_exact_repeated_bytes": jump_token.get("jump_exact_pair_repeated_bytes", "0"),
        "jump_backref_exact_copy_bytes": jump_token_backref.get("exact_copy_bytes", "0"),
        "jump_backref_best_distance": jump_token_backref.get("best_distance", "0"),
        "jump_backref_best_false_bytes": jump_token_backref.get("best_distance_false_bytes", "0"),
        "jump_token_context_repeated_groups": jump_token_context.get("repeated_group_rows", "0"),
        "jump_token_context_candidate_bytes": jump_token_context.get("repeated_candidate_bytes", "0"),
        "jump_token_context_shared_context_bytes": jump_token_context.get("shared_context_bytes", "0"),
        "jump_token_context_conflicted_context_bytes": jump_token_context.get("conflicted_context_bytes", "0"),
        "jump_token_context_copy_backed_bytes": jump_token_context.get("copy_backed_group_bytes", "0"),
        "repeated_nibble_rows": str(repeated_rows),
        "repeated_nibble_bytes": str(repeated_bytes),
        "repeated_nibble_pingpong_rows": repeated_nibble.get("pingpong_rows", "0"),
        "repeated_nibble_band_repeated_bytes": repeated_nibble.get("repeated_band_pair_bytes", "0"),
        "repeated_nibble_best_ratio": repeated_nibble.get("best_overall_ratio", "0"),
        "repeated_nibble_context_repeated_band_bytes": repeated_nibble_context.get(
            "repeated_band_pair_bytes", "0"
        ),
        "repeated_nibble_context_repeated_phase_bytes": repeated_nibble_context.get(
            "repeated_phase_context_bytes", "0"
        ),
        "repeated_nibble_context_repeated_payload_bytes": repeated_nibble_context.get(
            "repeated_payload_bytes", "0"
        ),
        "repeated_nibble_context_source_ge50_bytes": repeated_nibble_context.get("source_ge50_bytes", "0"),
        "mixed_jump_rows": str(mixed_rows),
        "mixed_jump_bytes": str(mixed_bytes),
        "mixed_jump_dominant_band_rows": mixed_jump.get("dominant_band_rows", "0"),
        "mixed_jump_zero_band_rows": mixed_jump.get("zero_band_rows", "0"),
        "mixed_jump_best_ratio": mixed_jump.get("best_overall_ratio", "0"),
        "mixed_jump_context_repeated_band_bytes": mixed_jump_context.get("repeated_band_pair_bytes", "0"),
        "mixed_jump_context_repeated_payload_bytes": mixed_jump_context.get("repeated_payload_bytes", "0"),
        "mixed_jump_context_source_ge50_bytes": mixed_jump_context.get("source_ge50_bytes", "0"),
        "mixed_control_rows": str(mixed_control_rows),
        "mixed_control_bytes": str(mixed_control_bytes),
        "mixed_control_candidate_windows": mixed_control.get("candidate_windows", "0"),
        "mixed_control_phase_ge75_rows": mixed_control.get("phase_ge75_rows", "0"),
        "mixed_control_phase_ge75_long_rows": mixed_control.get("phase_ge75_long_rows", "0"),
        "mixed_control_source_like_bytes": mixed_control.get("source_like_bytes", "0"),
        "residual_jump_rows": str(residual_rows),
        "residual_jump_bytes": str(residual_bytes),
        "residual_jump_sparse_rows": residual_jump.get("sparse_rows", "0"),
        "residual_jump_long_island_bytes": residual_jump.get("long_island_bytes", "0"),
        "residual_jump_best_ratio": residual_jump.get("best_overall_ratio", "0"),
        "residual_control_rows": str(residual_control_rows),
        "residual_control_bytes": str(residual_control_bytes),
        "residual_control_candidate_windows": residual_control.get("candidate_windows", "0"),
        "residual_control_phase_ge75_rows": residual_control.get("phase_ge75_rows", "0"),
        "residual_control_phase_ge75_long_rows": residual_control.get("phase_ge75_long_rows", "0"),
        "residual_control_source_like_bytes": residual_control.get("source_like_bytes", "0"),
        "dense_jump_rows": str(dense_rows),
        "dense_jump_bytes": str(dense_bytes),
        "dense_direction_switch_ratio": dense_jump.get("direction_switch_ratio", "0"),
        "dense_single_byte_island_ratio": dense_jump.get("single_byte_island_ratio", "0"),
        "dense_phase_repeated_bytes": dense_jump.get("phase_repeated_bytes", "0"),
        "dense_control_rows": str(dense_control_rows),
        "dense_control_bytes": str(dense_control_bytes),
        "dense_control_candidate_windows": dense_control.get("candidate_windows", "0"),
        "dense_control_phase_ge75_rows": dense_control.get("phase_ge75_rows", "0"),
        "dense_control_phase_ge75_long_rows": dense_control.get("phase_ge75_long_rows", "0"),
        "dense_control_source_like_bytes": dense_control.get("source_like_bytes", "0"),
        "control_signal_gate_rows": str(control_signal_gate_rows),
        "control_signal_gate_bytes": str(control_signal_gate_bytes),
        "control_signal_gate_candidate_windows": control_signal_gate.get("candidate_windows", "0"),
        "control_signal_gate_direction_only_bytes": control_signal_gate.get("direction_only_bytes", "0"),
        "control_signal_gate_short_phase_bytes": control_signal_gate.get("short_phase_bytes", "0"),
        "control_signal_gate_phase_ge75_long_bytes": control_signal_gate.get("phase_ge75_long_bytes", "0"),
        "weak_control_value_rows": weak_control_value.get("target_rows", "0"),
        "weak_control_value_bytes": weak_control_value.get("target_bytes", "0"),
        "weak_control_value_magnitude_ge75_bytes": weak_control_value.get("magnitude_ge75_bytes", "0"),
        "weak_control_value_repeated_signal_bytes": weak_control_value.get("best_signal_repeated_bytes", "0"),
        "weak_control_value_repeated_payload_bytes": weak_control_value.get("repeated_payload_bytes", "0"),
        "direction_value_rows": direction_value.get("target_rows", "0"),
        "direction_value_bytes": direction_value.get("target_bytes", "0"),
        "direction_value_ge75_bytes": direction_value.get("value_ge75_bytes", "0"),
        "direction_value_exact_bytes": direction_value.get("value_exact_bytes", "0"),
        "direction_value_conflicted_offset_bytes": direction_value.get("conflicted_offset_bytes", "0"),
        "direction_value_offset_rows": direction_value_offset.get("target_rows", "0"),
        "direction_value_offset_bytes": direction_value_offset.get("target_bytes", "0"),
        "direction_value_offset_repeated_bytes": direction_value_offset.get("repeated_key_bytes", "0"),
        "direction_value_offset_same_delta_bytes": direction_value_offset.get("same_delta_bytes", "0"),
        "direction_value_offset_conflicted_delta_bytes": direction_value_offset.get("conflicted_delta_bytes", "0"),
        "direction_value_delta_context_rows": direction_value_delta_context.get("target_rows", "0"),
        "direction_value_delta_context_bytes": direction_value_delta_context.get("target_bytes", "0"),
        "direction_value_delta_context_best_stable_bytes": direction_value_delta_context.get("best_stable_bytes", "0"),
        "direction_value_delta_context_best_repeated_stable_bytes": direction_value_delta_context.get(
            "best_repeated_stable_bytes", "0"
        ),
        "direction_value_delta_context_split_all_singleton_bytes": direction_value_delta_context.get(
            "split_all_singleton_bytes", "0"
        ),
        "direction_value_delta_context_repeated_payload_bytes": direction_value_delta_context.get(
            "repeated_payload_bytes", "0"
        ),
        "direction_value_payload_grammar_rows": direction_value_payload_grammar.get("target_rows", "0"),
        "direction_value_payload_grammar_bytes": direction_value_payload_grammar.get("target_bytes", "0"),
        "direction_value_payload_grammar_repeated_top_token_nibble_bytes": direction_value_payload_grammar.get(
            "repeated_top_token_nibble_bytes", "0"
        ),
        "direction_value_payload_grammar_repeated_transition_profile_bytes": direction_value_payload_grammar.get(
            "repeated_transition_profile_bytes", "0"
        ),
        "direction_value_payload_grammar_repeated_payload_bytes": direction_value_payload_grammar.get(
            "repeated_payload_bytes", "0"
        ),
        "direction_value_payload_grammar_exact_profile_unique_bytes": direction_value_payload_grammar.get(
            "exact_profile_unique_bytes", "0"
        ),
        "direction_value_source_profile_rows": direction_value_source_profile.get("target_rows", "0"),
        "direction_value_source_profile_bytes": direction_value_source_profile.get("target_bytes", "0"),
        "direction_value_source_profile_best_segment_gap_bytes": direction_value_source_profile.get(
            "best_segment_gap_bytes", "0"
        ),
        "direction_value_source_profile_overlap_ge75_bytes": direction_value_source_profile.get(
            "profile_overlap_ge75_bytes", "0"
        ),
        "direction_value_source_profile_exact_profile_match_bytes": direction_value_source_profile.get(
            "exact_profile_match_bytes", "0"
        ),
        "direction_value_source_profile_positional_ge50_bytes": direction_value_source_profile.get(
            "positional_ge50_bytes", "0"
        ),
        "direction_value_source_profile_repeated_source_profile_bytes": direction_value_source_profile.get(
            "repeated_source_profile_bytes", "0"
        ),
        "direction_value_source_value_rows": direction_value_source_value.get("target_rows", "0"),
        "direction_value_source_value_bytes": direction_value_source_value.get("target_bytes", "0"),
        "direction_value_source_value_best_exact_total": direction_value_source_value.get("best_exact_total", "0"),
        "direction_value_source_value_best_exact_ratio_max": direction_value_source_value.get(
            "best_exact_ratio_max", "0"
        ),
        "direction_value_source_value_rows_ge25": direction_value_source_value.get("rows_ge25", "0"),
        "direction_value_source_value_exact_match_bytes": direction_value_source_value.get("exact_match_bytes", "0"),
        "direction_value_source_value_repeated_transform_bytes": direction_value_source_value.get(
            "repeated_best_transform_bytes", "0"
        ),
        "direction_value_source_window_rows": direction_value_source_window.get("target_rows", "0"),
        "direction_value_source_window_bytes": direction_value_source_window.get("target_bytes", "0"),
        "direction_value_source_window_best_exact_total": direction_value_source_window.get("best_exact_total", "0"),
        "direction_value_source_window_best_exact_ratio_max": direction_value_source_window.get(
            "best_exact_ratio_max", "0"
        ),
        "direction_value_source_window_rows_ge25": direction_value_source_window.get("rows_ge25", "0"),
        "direction_value_source_window_rows_ge50": direction_value_source_window.get("rows_ge50", "0"),
        "direction_value_source_window_exact_match_bytes": direction_value_source_window.get(
            "exact_match_bytes", "0"
        ),
        "direction_value_source_window_repeated_offset_delta_bytes": direction_value_source_window.get(
            "repeated_best_offset_delta_bytes", "0"
        ),
        "direction_value_source_window_repeated_transform_bytes": direction_value_source_window.get(
            "repeated_best_transform_bytes", "0"
        ),
        "direction_value_control_context_rows": direction_value_control_context.get("target_rows", "0"),
        "direction_value_control_context_bytes": direction_value_control_context.get("target_bytes", "0"),
        "direction_value_control_context_repeated_direction_signal_bytes": direction_value_control_context.get(
            "repeated_direction_signal_bytes", "0"
        ),
        "direction_value_control_context_repeated_direction_context_bytes": direction_value_control_context.get(
            "repeated_direction_context_bytes", "0"
        ),
        "direction_value_control_context_repeated_combined_context_bytes": direction_value_control_context.get(
            "repeated_combined_context_bytes", "0"
        ),
        "direction_value_control_context_repeated_op_phase_bytes": direction_value_control_context.get(
            "repeated_op_phase_bytes", "0"
        ),
        "direction_value_control_context_repeated_payload_bytes": direction_value_control_context.get(
            "repeated_payload_bytes", "0"
        ),
        "direction_value_control_context_best_repeated_context_bytes": direction_value_control_context.get(
            "best_repeated_context_bytes", "0"
        ),
        "direction_value_exact_context_rows": direction_value_exact_context.get("target_rows", "0"),
        "direction_value_exact_context_bytes": direction_value_exact_context.get("target_bytes", "0"),
        "direction_value_exact_context_repeated_key_bytes": direction_value_exact_context.get("repeated_key_bytes", "0"),
        "direction_value_exact_context_repeated_payload_bytes": direction_value_exact_context.get(
            "repeated_payload_bytes", "0"
        ),
        "direction_value_exact_context_conflicted_delta_bytes": direction_value_exact_context.get(
            "conflicted_delta_bytes", "0"
        ),
        "direction_value_partial_context_rows": direction_value_partial_context.get("target_rows", "0"),
        "direction_value_partial_context_bytes": direction_value_partial_context.get("target_bytes", "0"),
        "direction_value_partial_context_repeated_key_bytes": direction_value_partial_context.get(
            "repeated_key_bytes", "0"
        ),
        "direction_value_partial_context_repeated_payload_bytes": direction_value_partial_context.get(
            "repeated_payload_bytes", "0"
        ),
        "direction_value_partial_context_conflicted_delta_bytes": direction_value_partial_context.get(
            "conflicted_delta_bytes", "0"
        ),
        "promotion_ready_bytes": "0",
        "review_bytes": str(noisy_bytes),
        "decision_rows": str(len(decision_rows)),
        "blocked_rows": str(sum(1 for row in decision_rows if row["promotion_ready_bytes"] == "0")),
        "issue_rows": str(issue_rows),
    }
    return summary, decision_rows


def render_table(rows: list[dict[str, str]], fields: list[str]) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    decisions: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "decisions": decisions}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("decisions.csv", output_dir / "decisions.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{
  color-scheme: dark;
  --bg: #111416;
  --panel: #172023;
  --line: #31424a;
  --text: #edf5f4;
  --muted: #9dafb5;
  --accent: #77d3b1;
  --warn: #f0c36a;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.wrap {{ width: min(1500px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12191b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 720; letter-spacing: 0; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 22px; font-weight: 760; line-height: 1.05; margin-top: 4px; }}
.warn {{ color: var(--warn); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1200px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Aggregates noisy nonzero gap evidence into promotion decisions.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Noisy bytes</div><div class="value">{summary['noisy_bytes']}</div></div>
    <div class="stat"><div class="label">Review bytes</div><div class="value warn">{summary['review_bytes']}</div></div>
    <div class="stat"><div class="label">Promotion-ready bytes</div><div class="value">{summary['promotion_ready_bytes']}</div></div>
    <div class="stat"><div class="label">Decision rows</div><div class="value">{summary['decision_rows']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2><div>{links}</div></section>
  <section class="panel"><h2>Decisions</h2>{render_table(decisions, DECISION_FIELDNAMES)}</section>
</main>
<script>
const TEX_GAP_DECODER_LEN64_PROMOTED_NONZERO_GAP_NOISY_REVIEW = {data_json};
</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize .tex noisy nonzero gap review probes.")
    parser.add_argument("--noisy", type=Path, default=DEFAULT_NOISY)
    parser.add_argument("--gradient", type=Path, default=DEFAULT_GRADIENT)
    parser.add_argument("--gradient-repeat-context", type=Path, default=DEFAULT_GRADIENT_REPEAT_CONTEXT)
    parser.add_argument("--gradient-seed-unlock", type=Path, default=DEFAULT_GRADIENT_SEED_UNLOCK)
    parser.add_argument("--gradient-seed-shift-family", type=Path, default=DEFAULT_GRADIENT_SEED_SHIFT_FAMILY)
    parser.add_argument("--gradient-seed-delta-selector", type=Path, default=DEFAULT_GRADIENT_SEED_DELTA_SELECTOR)
    parser.add_argument("--gradient-seed-delta-context", type=Path, default=DEFAULT_GRADIENT_SEED_DELTA_CONTEXT)
    parser.add_argument("--gradient-seed-delta-phase", type=Path, default=DEFAULT_GRADIENT_SEED_DELTA_PHASE)
    parser.add_argument("--gradient-seed-delta-state", type=Path, default=DEFAULT_GRADIENT_SEED_DELTA_STATE)
    parser.add_argument(
        "--gradient-seed-delta-opcode-sequence",
        type=Path,
        default=DEFAULT_GRADIENT_SEED_DELTA_OPCODE_SEQUENCE,
    )
    parser.add_argument(
        "--gradient-seed-delta-semantic-opcode",
        type=Path,
        default=DEFAULT_GRADIENT_SEED_DELTA_SEMANTIC_OPCODE,
    )
    parser.add_argument(
        "--gradient-seed-delta-payload-opcode",
        type=Path,
        default=DEFAULT_GRADIENT_SEED_DELTA_PAYLOAD_OPCODE,
    )
    parser.add_argument("--flat", type=Path, default=DEFAULT_FLAT)
    parser.add_argument("--flat-source", type=Path, default=DEFAULT_FLAT_SOURCE)
    parser.add_argument("--flat-shape-control", type=Path, default=DEFAULT_FLAT_SHAPE_CONTROL)
    parser.add_argument("--flat-value", type=Path, default=DEFAULT_FLAT_VALUE)
    parser.add_argument("--flat-backref", type=Path, default=DEFAULT_FLAT_BACKREF)
    parser.add_argument("--flat-palette-seed", type=Path, default=DEFAULT_FLAT_PALETTE_SEED)
    parser.add_argument("--flat-palette-mix", type=Path, default=DEFAULT_FLAT_PALETTE_MIX)
    parser.add_argument("--flat-backref-chain", type=Path, default=DEFAULT_FLAT_BACKREF_CHAIN)
    parser.add_argument("--flat-palette-signature", type=Path, default=DEFAULT_FLAT_PALETTE_SIGNATURE)
    parser.add_argument("--flat-palette-context", type=Path, default=DEFAULT_FLAT_PALETTE_CONTEXT)
    parser.add_argument("--micro-token", type=Path, default=DEFAULT_MICRO_TOKEN)
    parser.add_argument("--jump-token", type=Path, default=DEFAULT_JUMP_TOKEN)
    parser.add_argument("--jump-token-backref", type=Path, default=DEFAULT_JUMP_TOKEN_BACKREF)
    parser.add_argument("--jump-token-context", type=Path, default=DEFAULT_JUMP_TOKEN_CONTEXT)
    parser.add_argument("--repeated-nibble", type=Path, default=DEFAULT_REPEATED_NIBBLE)
    parser.add_argument("--repeated-nibble-context", type=Path, default=DEFAULT_REPEATED_NIBBLE_CONTEXT)
    parser.add_argument("--mixed-jump", type=Path, default=DEFAULT_MIXED_JUMP)
    parser.add_argument("--mixed-jump-context", type=Path, default=DEFAULT_MIXED_JUMP_CONTEXT)
    parser.add_argument("--mixed-control", type=Path, default=DEFAULT_MIXED_CONTROL)
    parser.add_argument("--residual-jump", type=Path, default=DEFAULT_RESIDUAL_JUMP)
    parser.add_argument("--residual-control", type=Path, default=DEFAULT_RESIDUAL_CONTROL)
    parser.add_argument("--dense-jump", type=Path, default=DEFAULT_DENSE_JUMP)
    parser.add_argument("--dense-control", type=Path, default=DEFAULT_DENSE_CONTROL)
    parser.add_argument("--control-signal-gate", type=Path, default=DEFAULT_CONTROL_SIGNAL_GATE)
    parser.add_argument("--weak-control-value", type=Path, default=DEFAULT_WEAK_CONTROL_VALUE)
    parser.add_argument("--direction-value", type=Path, default=DEFAULT_DIRECTION_VALUE)
    parser.add_argument("--direction-value-offset", type=Path, default=DEFAULT_DIRECTION_VALUE_OFFSET)
    parser.add_argument("--direction-value-delta-context", type=Path, default=DEFAULT_DIRECTION_VALUE_DELTA_CONTEXT)
    parser.add_argument(
        "--direction-value-payload-grammar",
        type=Path,
        default=DEFAULT_DIRECTION_VALUE_PAYLOAD_GRAMMAR,
    )
    parser.add_argument(
        "--direction-value-source-profile",
        type=Path,
        default=DEFAULT_DIRECTION_VALUE_SOURCE_PROFILE,
    )
    parser.add_argument(
        "--direction-value-source-value",
        type=Path,
        default=DEFAULT_DIRECTION_VALUE_SOURCE_VALUE,
    )
    parser.add_argument(
        "--direction-value-source-window",
        type=Path,
        default=DEFAULT_DIRECTION_VALUE_SOURCE_WINDOW,
    )
    parser.add_argument(
        "--direction-value-control-context",
        type=Path,
        default=DEFAULT_DIRECTION_VALUE_CONTROL_CONTEXT,
    )
    parser.add_argument(
        "--direction-value-exact-context",
        type=Path,
        default=DEFAULT_DIRECTION_VALUE_EXACT_CONTEXT,
    )
    parser.add_argument(
        "--direction-value-partial-context",
        type=Path,
        default=DEFAULT_DIRECTION_VALUE_PARTIAL_CONTEXT,
    )
    parser.add_argument("--mixed-token-uniqueness", type=Path, default=DEFAULT_MIXED_TOKEN_UNIQUENESS)
    parser.add_argument("--mixed-token-band", type=Path, default=DEFAULT_MIXED_TOKEN_BAND)
    parser.add_argument("--mixed-token-backref", type=Path, default=DEFAULT_MIXED_TOKEN_BACKREF)
    parser.add_argument("--mixed-token-control", type=Path, default=DEFAULT_MIXED_TOKEN_CONTROL)
    parser.add_argument("--mixed-token-control-context", type=Path, default=DEFAULT_MIXED_TOKEN_CONTROL_CONTEXT)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Tiny Nonzero Gap Noisy Review",
    )
    args = parser.parse_args()

    summary, decisions = build_rows(
        read_summary(args.noisy),
        read_summary(args.gradient),
        read_summary(args.gradient_repeat_context),
        read_summary(args.gradient_seed_unlock),
        read_summary(args.gradient_seed_shift_family),
        read_summary(args.gradient_seed_delta_selector),
        read_summary(args.gradient_seed_delta_context),
        read_summary(args.gradient_seed_delta_phase),
        read_summary(args.gradient_seed_delta_state),
        read_summary(args.gradient_seed_delta_opcode_sequence),
        read_summary(args.gradient_seed_delta_semantic_opcode),
        read_summary(args.gradient_seed_delta_payload_opcode),
        read_summary(args.flat),
        read_summary(args.flat_source),
        read_summary(args.flat_shape_control),
        read_summary(args.flat_value),
        read_summary(args.flat_backref),
        read_summary(args.flat_palette_seed),
        read_summary(args.flat_palette_mix),
        read_summary(args.flat_backref_chain),
        read_summary(args.flat_palette_signature),
        read_summary(args.flat_palette_context),
        read_summary(args.micro_token),
        read_summary(args.mixed_token_uniqueness),
        read_summary(args.mixed_token_band),
        read_summary(args.mixed_token_backref),
        read_summary(args.mixed_token_control),
        read_summary(args.mixed_token_control_context),
        read_summary(args.jump_token),
        read_summary(args.jump_token_backref),
        read_summary(args.jump_token_context),
        read_summary(args.repeated_nibble),
        read_summary(args.repeated_nibble_context),
        read_summary(args.mixed_jump),
        read_summary(args.mixed_jump_context),
        read_summary(args.mixed_control),
        read_summary(args.residual_jump),
        read_summary(args.residual_control),
        read_summary(args.dense_jump),
        read_summary(args.dense_control),
        read_summary(args.control_signal_gate),
        read_summary(args.weak_control_value),
        read_summary(args.direction_value),
        read_summary(args.direction_value_offset),
        read_summary(args.direction_value_delta_context),
        read_summary(args.direction_value_payload_grammar),
        read_summary(args.direction_value_source_profile),
        read_summary(args.direction_value_source_value),
        read_summary(args.direction_value_source_window),
        read_summary(args.direction_value_control_context),
        read_summary(args.direction_value_exact_context),
        read_summary(args.direction_value_partial_context),
    )
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "decisions.csv", DECISION_FIELDNAMES, decisions)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, decisions, args.output, args.title))

    print(f"Noisy review bytes: {summary['review_bytes']}")
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"Decision rows: {summary['decision_rows']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
