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
DEFAULT_GRADIENT_PAYLOAD_PROFILE_SUMMARY = Path("output/tex_gradient_payload_profile/summary.csv")
DEFAULT_MICRO_JUMP_MIXED_PAYLOAD_SUMMARY = Path("output/tex_micro_jump_mixed_payload/summary.csv")
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
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SOURCE_PROFILE_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_source_profile/summary.csv"
)
DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SPATIAL_SUMMARY = Path(
    "output/tex_micro_mixed_value_payload_spatial/summary.csv"
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


def build_queue(
    decisions: list[dict[str, str]],
    gradient_payload_profile_summary: dict[str, str] | None = None,
    micro_jump_mixed_payload_summary: dict[str, str] | None = None,
    micro_token_family_split_summary: dict[str, str] | None = None,
    micro_mixed_value_subfamily_summary: dict[str, str] | None = None,
    micro_mixed_value_dominant_control_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_local_grammar_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_predictor_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_source_profile_summary: dict[str, str] | None = None,
    micro_mixed_value_payload_spatial_summary: dict[str, str] | None = None,
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
    parser.add_argument(
        "--gradient-payload-profile-summary",
        type=Path,
        default=DEFAULT_GRADIENT_PAYLOAD_PROFILE_SUMMARY,
    )
    parser.add_argument(
        "--micro-jump-mixed-payload-summary",
        type=Path,
        default=DEFAULT_MICRO_JUMP_MIXED_PAYLOAD_SUMMARY,
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
        "--micro-mixed-value-payload-source-profile-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SOURCE_PROFILE_SUMMARY,
    )
    parser.add_argument(
        "--micro-mixed-value-payload-spatial-summary",
        type=Path,
        default=DEFAULT_MICRO_MIXED_VALUE_PAYLOAD_SPATIAL_SUMMARY,
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
    micro_mixed_value_payload_source_profile_rows = (
        read_rows(args.micro_mixed_value_payload_source_profile_summary)
        if args.micro_mixed_value_payload_source_profile_summary.exists()
        else []
    )
    micro_mixed_value_payload_source_profile_summary = (
        micro_mixed_value_payload_source_profile_rows[0] if micro_mixed_value_payload_source_profile_rows else None
    )
    micro_mixed_value_payload_spatial_rows = (
        read_rows(args.micro_mixed_value_payload_spatial_summary)
        if args.micro_mixed_value_payload_spatial_summary.exists()
        else []
    )
    micro_mixed_value_payload_spatial_summary = (
        micro_mixed_value_payload_spatial_rows[0] if micro_mixed_value_payload_spatial_rows else None
    )
    queue = build_queue(
        decisions,
        gradient_payload_profile_summary,
        micro_jump_mixed_payload_summary,
        micro_token_family_split_summary,
        micro_mixed_value_subfamily_summary,
        micro_mixed_value_dominant_control_summary,
        micro_mixed_value_payload_local_grammar_summary,
        micro_mixed_value_payload_predictor_summary,
        micro_mixed_value_payload_source_profile_summary,
        micro_mixed_value_payload_spatial_summary,
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
