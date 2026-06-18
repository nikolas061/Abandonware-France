#!/usr/bin/env python3
"""Run the reproducible Full HD validation/report pipeline."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_ARCHIVES = sorted(Path("C/LOLG").glob("*.MIX"))


@dataclass(frozen=True)
class Step:
    name: str
    command: list[str]
    requires_pillow: bool = False
    optional: bool = False


def has_module(name: str) -> bool:
    result = subprocess.run(
        [sys.executable, "-c", f"import {name}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def run_step(step: Step, dry_run: bool) -> int:
    print(f"==> {step.name}", flush=True)
    print(" ".join(shlex_quote(part) for part in step.command), flush=True)
    if dry_run:
        return 0
    result = subprocess.run(step.command, check=False)
    return result.returncode


def shlex_quote(value: str) -> str:
    if not value:
        return "''"
    safe = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_+-=.,/:")
    if all(char in safe for char in value):
        return value
    return "'" + value.replace("'", "'\"'\"'") + "'"


def quick_steps(fail_on_issues: bool) -> list[Step]:
    audit = [sys.executable, "tools/lolg_hd_audit.py"]
    final_audit = [sys.executable, "tools/lolg_hd_audit.py"]
    if fail_on_issues:
        audit.append("--fail-on-issues")
        final_audit.append("--fail-on-issues")
    return [
        Step("audit Full HD", audit),
        Step("dashboard Full HD", [sys.executable, "tools/lolg_hd_dashboard.py"]),
        Step("audit final Full HD", final_audit),
    ]


def report_steps(fail_on_issues: bool) -> list[Step]:
    archive_args = [str(path) for path in DEFAULT_ARCHIVES]
    steps = [
        Step("inventaire Full HD", [sys.executable, "tools/lolg_hd_inventory.py"], requires_pillow=True),
        Step(
            "couverture archives Full HD",
            [sys.executable, "tools/lolg_hd_archive_coverage.py", *archive_args],
        ),
        Step("couverture textures .tex HD", [sys.executable, "tools/lolg_tex_hd_coverage.py"]),
        Step("couverture references .tex", [sys.executable, "tools/lolg_tex_reference_coverage.py"]),
        Step(
            "gradient-like noisy .tex",
            [sys.executable, "tools/lolg_tex_gap_decoder_len64_promoted_nonzero_gap_gradient_probe.py"],
            requires_pillow=True,
        ),
        Step(
            "flat-walk noisy .tex",
            [sys.executable, "tools/lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_probe.py"],
        ),
        Step(
            "backrefs flat-walk noisy .tex",
            [sys.executable, "tools/lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_backref_probe.py"],
        ),
        Step(
            "seeds palette flat-walk noisy .tex",
            [sys.executable, "tools/lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_seed_probe.py"],
        ),
        Step(
            "mix palette flat-walk noisy .tex",
            [sys.executable, "tools/lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_mix_probe.py"],
        ),
        Step(
            "chain backrefs palette flat-walk noisy .tex",
            [sys.executable, "tools/lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_backref_chain_probe.py"],
        ),
        Step(
            "signatures palette flat-walk noisy .tex",
            [sys.executable, "tools/lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_signature_probe.py"],
        ),
        Step(
            "contextes palette flat-walk noisy .tex",
            [sys.executable, "tools/lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_context_probe.py"],
        ),
        Step(
            "normalisation contextes palette flat-walk noisy .tex",
            [
                sys.executable,
                "tools/lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_normalized_context_probe.py",
            ],
        ),
        Step(
            "split valeurs palette flat-walk noisy .tex",
            [sys.executable, "tools/lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_value_split_probe.py"],
        ),
        Step(
            "table valeurs palette flat-walk noisy .tex",
            [sys.executable, "tools/lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_value_table_probe.py"],
        ),
        Step(
            "selecteurs compresses palette flat-walk noisy .tex",
            [
                sys.executable,
                "tools/lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_compressed_selector_probe.py",
            ],
        ),
        Step(
            "combinaisons selecteurs compresses palette flat-walk noisy .tex",
            [
                sys.executable,
                "tools/lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_compressed_combo_probe.py",
            ],
        ),
        Step(
            "formules compresses palette flat-walk noisy .tex",
            [
                sys.executable,
                "tools/lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_compressed_formula_probe.py",
            ],
        ),
        Step(
            "formules corpus palette flat-walk noisy .tex",
            [
                sys.executable,
                "tools/lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_corpus_formula_probe.py",
            ],
        ),
        Step(
            "candidats promotion palette flat-walk noisy .tex",
            [
                sys.executable,
                "tools/lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_promotion_candidate_probe.py",
            ],
        ),
        Step(
            "replay formule palette flat-walk noisy .tex",
            [
                sys.executable,
                "tools/lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_formula_replay.py",
            ],
            requires_pillow=True,
        ),
        Step(
            "copies verticales post-formule palette flat-walk noisy .tex",
            [
                sys.executable,
                "tools/lolg_tex_gap_decoder_len64_promoted_nonzero_gap_flat_walk_palette_post_formula_vertical_copy_probe.py",
            ],
        ),
        Step(
            "copies pair meme forme gradient post-formule .tex",
            [
                sys.executable,
                "tools/lolg_tex_gap_decoder_len64_promoted_nonzero_gap_gradient_shape_peer_copy_probe.py",
            ],
        ),
        Step(
            "contexte gradients repetes .tex",
            [
                sys.executable,
                "tools/lolg_tex_gap_decoder_len64_promoted_nonzero_gap_gradient_repeat_context_probe.py",
            ],
        ),
        Step(
            "seeds gradients repetes .tex",
            [
                sys.executable,
                "tools/lolg_tex_gap_decoder_len64_promoted_nonzero_gap_gradient_seed_unlock_probe.py",
            ],
        ),
        Step(
            "famille shifts seeds gradients .tex",
            [
                sys.executable,
                "tools/lolg_tex_gap_decoder_len64_promoted_nonzero_gap_gradient_seed_shift_family_probe.py",
            ],
        ),
        Step(
            "selecteurs delta seeds gradients .tex",
            [
                sys.executable,
                "tools/lolg_tex_gap_decoder_len64_promoted_nonzero_gap_gradient_seed_delta_selector_probe.py",
            ],
        ),
        Step(
            "contexte delta seeds gradients .tex",
            [
                sys.executable,
                "tools/lolg_tex_gap_decoder_len64_promoted_nonzero_gap_gradient_seed_delta_context_probe.py",
            ],
        ),
        Step(
            "phase delta seeds gradients .tex",
            [
                sys.executable,
                "tools/lolg_tex_gap_decoder_len64_promoted_nonzero_gap_gradient_seed_delta_phase_probe.py",
            ],
        ),
        Step(
            "etat delta seeds gradients .tex",
            [
                sys.executable,
                "tools/lolg_tex_gap_decoder_len64_promoted_nonzero_gap_gradient_seed_delta_state_probe.py",
            ],
        ),
        Step(
            "sequence opcode seeds gradients .tex",
            [
                sys.executable,
                "tools/lolg_tex_gap_decoder_len64_promoted_nonzero_gap_gradient_seed_delta_opcode_sequence_probe.py",
            ],
        ),
        Step(
            "semantique opcode seeds gradients .tex",
            [
                sys.executable,
                "tools/lolg_tex_gap_decoder_len64_promoted_nonzero_gap_gradient_seed_delta_semantic_opcode_probe.py",
            ],
        ),
        Step(
            "payload opcode seeds gradients .tex",
            [
                sys.executable,
                "tools/lolg_tex_gap_decoder_len64_promoted_nonzero_gap_gradient_seed_delta_payload_opcode_probe.py",
            ],
        ),
        Step("profil payload gradient .tex", [sys.executable, "tools/lolg_tex_gradient_payload_profile_probe.py"]),
        Step(
            "spatial connu nonlocal gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_nonlocal_known_spatial_probe.py"],
        ),
        Step(
            "etat sequence connue gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_sequence_known_state_probe.py"],
        ),
        Step(
            "bas apres high-safe sequence gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_sequence_high_safe_low_probe.py"],
        ),
        Step(
            "source-profile apres high-safe sequence gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_sequence_high_safe_source_profile_low_probe.py"],
        ),
        Step(
            "row/corpus apres high-safe sequence gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_sequence_high_safe_row_corpus_low_probe.py"],
        ),
        Step(
            "transform low apres row/corpus gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_sequence_high_safe_transform_low_probe.py"],
        ),
        Step(
            "source-window residuel gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_sequence_high_safe_source_window_probe.py"],
        ),
        Step(
            "controle/opcode residuel high-safe gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_sequence_high_safe_control_opcode_probe.py"],
        ),
        Step(
            "transition low cross-row high-safe gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_sequence_high_safe_row_transition_probe.py"],
        ),
        Step(
            "markov low row-local high-safe gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_sequence_high_safe_row_markov_probe.py"],
        ),
        Step(
            "template low row high-safe gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_sequence_high_safe_row_template_probe.py"],
        ),
        Step(
            "split bucket low high-safe gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_sequence_high_safe_low_bucket_split_probe.py"],
        ),
        Step(
            "exceptions low high-safe gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_sequence_high_safe_low_exception_probe.py"],
        ),
        Step(
            "alignement exceptions low high-safe gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_sequence_high_safe_low_exception_alignment_probe.py"],
        ),
        Step(
            "revue alignement exceptions low high-safe gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_sequence_high_safe_low_exception_alignment_review.py"],
        ),
        Step(
            "familles row exceptions low high-safe gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_sequence_high_safe_low_exception_row_family_probe.py"],
        ),
        Step(
            "etat externe exceptions low high-safe gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_state_probe.py"],
        ),
        Step(
            "dependances source exceptions low high-safe gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_probe.py"],
        ),
        Step(
            "chaines source exceptions low high-safe gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_chain_probe.py"],
        ),
        Step(
            "terminaux source exceptions low high-safe gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_probe.py"],
        ),
        Step(
            "revue terminaux source exceptions low high-safe gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_review.py"],
        ),
        Step(
            "delta terminaux source exceptions low high-safe gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_delta_probe.py"],
        ),
        Step(
            "contexte chaines terminaux source exceptions low high-safe gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_chain_context_probe.py"],
        ),
        Step(
            "support replay terminaux source exceptions low high-safe gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_support_probe.py"],
        ),
        Step(
            "union replay terminaux source exceptions low high-safe gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_review.py"],
        ),
        Step(
            "garde union replay terminaux source exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_review.py",
            ],
        ),
        Step(
            "split garde union replay terminaux source exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_split_review.py",
            ],
        ),
        Step(
            "couverture garde union replay terminaux source exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_review.py",
            ],
        ),
        Step(
            "promotion couverture garde union replay terminaux source exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_promoted_replay.py",
            ],
        ),
        Step(
            "dependances source exceptions low high-safe gradient base replay promue .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_probe.py",
                "--replay-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_promoted_replay",
                "--title",
                "Lands of Lore II .tex Gradient Sequence High-Safe Low Exception Source-Dependency Promoted Replay Probe",
            ],
        ),
        Step(
            "chaines source exceptions low high-safe gradient base replay promue .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_chain_probe.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_promoted_replay/slots.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_chain_promoted_replay",
                "--title",
                "Lands of Lore II .tex Gradient Sequence High-Safe Low Exception Source-Chain Promoted Replay Probe",
            ],
        ),
        Step(
            "terminaux source exceptions low high-safe gradient base replay promue .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_probe.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_promoted_replay/slots.csv",
                "--terminals",
                "output/tex_gradient_sequence_high_safe_low_exception_source_chain_promoted_replay/terminals.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_promoted_replay",
                "--title",
                "Lands of Lore II .tex Gradient Sequence High-Safe Low Exception Source-Terminal Promoted Replay Probe",
            ],
        ),
        Step(
            "revue terminaux source exceptions low high-safe gradient base replay promue .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_review.py",
                "--terminals",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_promoted_replay/terminals.csv",
                "--chains",
                "output/tex_gradient_sequence_high_safe_low_exception_source_chain_promoted_replay/chains.csv",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_promoted_replay/slots.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_review_promoted_replay",
                "--title",
                "Lands of Lore II .tex Gradient Sequence High-Safe Low Exception Source-Terminal Review Promoted Replay",
            ],
        ),
        Step(
            "contexte chaines terminaux source exceptions low high-safe gradient base replay promue .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_chain_context_probe.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_promoted_replay/slots.csv",
                "--terminals",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_promoted_replay/terminals.csv",
                "--review-chains",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_review_promoted_replay/chains.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_chain_context_promoted_replay",
                "--title",
                "Lands of Lore II .tex Gradient Sequence High-Safe Low Exception Source-Terminal Chain Context Promoted Replay Probe",
            ],
        ),
        Step(
            "support replay terminaux source exceptions low high-safe gradient base replay promue .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_support_probe.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_promoted_replay/slots.csv",
                "--terminals",
                "output/tex_gradient_sequence_high_safe_low_exception_source_chain_promoted_replay/terminals.csv",
                "--chains",
                "output/tex_gradient_sequence_high_safe_low_exception_source_chain_promoted_replay/chains.csv",
                "--candidates",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_promoted_replay/candidates.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_support_promoted_replay",
                "--title",
                "Lands of Lore II .tex Gradient Sequence High-Safe Low Exception Source-Terminal Replay Support Promoted Replay Probe",
            ],
        ),
        Step(
            "union replay terminaux source exceptions low high-safe gradient base replay promue .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_promoted_replay/slots.csv",
                "--terminals",
                "output/tex_gradient_sequence_high_safe_low_exception_source_chain_promoted_replay/terminals.csv",
                "--source-terminals",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_promoted_replay/terminals.csv",
                "--chains",
                "output/tex_gradient_sequence_high_safe_low_exception_source_chain_promoted_replay/chains.csv",
                "--review-chains",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_review_promoted_replay/chains.csv",
                "--chain-context-candidates",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_chain_context_promoted_replay/candidates.csv",
                "--replay-support-candidates",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_support_promoted_replay/candidates.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_promoted_replay",
                "--title",
                "Lands of Lore II .tex Gradient Sequence High-Safe Low Exception Source-Terminal Replay Union Promoted Replay Review",
            ],
        ),
        Step(
            "couverture garde union replay terminaux source exceptions low high-safe gradient base replay promue .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_promoted_replay/slots.csv",
                "--source-terminals",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_promoted_replay/terminals.csv",
                "--chains",
                "output/tex_gradient_sequence_high_safe_low_exception_source_chain_promoted_replay/chains.csv",
                "--union-roots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_promoted_replay/roots.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_promoted_base",
            ],
        ),
        Step(
            "seconde promotion couverture garde union replay terminaux source exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_promoted_replay.py",
                "--base-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_promoted_replay/fixtures.csv",
                "--dependency-slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_promoted_replay/slots.csv",
                "--guard-roots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_promoted_base/roots.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_second_promoted_replay",
                "--title",
                "Lands of Lore II .tex Gradient Source Terminal Guard Cover Second Promoted Replay",
            ],
        ),
        Step(
            "dependances source exceptions low high-safe gradient seconde base replay promue .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_probe.py",
                "--replay-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_second_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_second_promoted_replay",
                "--title",
                "Lands of Lore II .tex Gradient Sequence High-Safe Low Exception Source-Dependency Second Promoted Replay Probe",
            ],
        ),
        Step(
            "revue noyau residuel dependances source low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_residual_core_review.py",
            ],
        ),
        Step(
            "revue sources terminales externes exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_source_review.py",
            ],
        ),
        Step(
            "selecteur small nonzero sources terminales externes exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector_probe.py",
            ],
        ),
        Step(
            "grammaire compact-control sources terminales externes exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_compact_control_grammar_probe.py",
            ],
        ),
        Step(
            "pont spatial gradient sources terminales externes exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_gradient_bridge_probe.py",
            ],
        ),
        Step(
            "selecteur pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_selector_probe.py",
            ],
        ),
        Step(
            "producteur delta pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer_probe.py",
            ],
        ),
        Step(
            "combinator cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_combinator_probe.py",
            ],
        ),
        Step(
            "garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_guard_probe.py",
            ],
        ),
        Step(
            "support garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_support_probe.py",
            ],
        ),
        Step(
            "revue target-only garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_only_review.py",
            ],
        ),
        Step(
            "fixtures regles gaps .tex",
            [sys.executable, "tools/lolg_tex_gap_rule_fixtures.py"],
        ),
        Step(
            "fixtures regles gaps etendues .tex",
            [
                sys.executable,
                "tools/lolg_tex_gap_rule_fixtures.py",
                "--limit",
                "0",
                "-o",
                "output/tex_gap_rule_fixtures_expanded",
                "--title",
                "Lands of Lore II .tex Expanded Gap Rule Fixtures",
            ],
        ),
        Step(
            "evidence independante garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_independent_evidence_probe.py",
            ],
        ),
        Step(
            "corpus etendu garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_expanded_corpus_probe.py",
            ],
        ),
        Step(
            "revue pair-mod garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_pair_mod_review.py",
            ],
        ),
        Step(
            "support raffine garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_refined_support_probe.py",
            ],
        ),
        Step(
            "variante formule garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_formula_variant_probe.py",
            ],
        ),
        Step(
            "gate contexte tail garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_tail_context_gate_probe.py",
            ],
        ),
        Step(
            "support non-tail garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_non_tail_support_probe.py",
            ],
        ),
        Step(
            "split familles pair garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_pair_family_split_probe.py",
            ],
        ),
        Step(
            "pont familles garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_family_bridge_probe.py",
            ],
        ),
        Step(
            "resolveur atomes garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_atom_resolver_probe.py",
            ],
        ),
        Step(
            "gating target-overlap garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_overlap_gate_probe.py",
            ],
        ),
        Step(
            "split carrier target-overlap garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_split_probe.py",
            ],
        ),
        Step(
            "switch local carrier cible garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_local_switch_probe.py",
            ],
        ),
        Step(
            "split contexte carrier cible garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_split_probe.py",
            ],
        ),
        Step(
            "revue contexte carrier cible garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_review.py",
            ],
        ),
        Step(
            "promotion contexte carrier cible garde cinq octets pont spatial sources terminales externes exceptions low high-safe gradient .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_promoted_replay.py",
            ],
        ),
        Step(
            "dependances source exceptions low high-safe gradient base carrier-context promue .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_probe.py",
                "--replay-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_carrier_context_promoted_replay",
                "--title",
                "Lands of Lore II .tex Gradient Source-Dependency Carrier-Context Promoted Replay Probe",
            ],
        ),
        Step(
            "coeur residuel dependances source base carrier-context promue .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_residual_core_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_carrier_context_promoted_replay/slots.csv",
                "--edges",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_carrier_context_promoted_replay/edges.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_carrier_context_residual_core",
            ],
        ),
        Step(
            "sources terminales externes base carrier-context promue .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_source_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_carrier_context_promoted_replay/slots.csv",
                "--terminals",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_carrier_context_residual_core/terminals.csv",
                "--fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_source_carrier_context_promoted_replay",
            ],
        ),
        Step(
            "selecteur small nonzero sources terminales externes base carrier-context promue .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector_probe.py",
                "--blocker-spans",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_source_carrier_context_promoted_replay/spans.csv",
                "--fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector_carrier_context_promoted_replay",
            ],
        ),
        Step(
            "pont spatial sources terminales externes base carrier-context promue .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_gradient_bridge_probe.py",
                "--targets",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector_carrier_context_promoted_replay/targets.csv",
                "--small-gaps",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector_carrier_context_promoted_replay/small_gaps.csv",
                "--fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_gradient_bridge_carrier_context_promoted_replay",
            ],
        ),
        Step(
            "selecteur pont spatial sources terminales externes base carrier-context promue .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_selector_probe.py",
                "--targets",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector_carrier_context_promoted_replay/targets.csv",
                "--small-gaps",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector_carrier_context_promoted_replay/small_gaps.csv",
                "--fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_selector_carrier_context_promoted_replay",
            ],
        ),
        Step(
            "producteur delta pont spatial sources terminales externes base carrier-context promue .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer_probe.py",
                "--targets",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_selector_carrier_context_promoted_replay/targets.csv",
                "--small-gaps",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector_carrier_context_promoted_replay/small_gaps.csv",
                "--fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer_carrier_context_promoted_replay",
            ],
        ),
        Step(
            "garde producteur delta pont spatial base carrier-context promue .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer_guard_probe.py",
                "--targets",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer_carrier_context_promoted_replay/targets.csv",
                "--producers",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer_carrier_context_promoted_replay/producers.csv",
                "--candidates",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer_carrier_context_promoted_replay/candidates.csv",
                "--small-gaps",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector_carrier_context_promoted_replay/small_gaps.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer_guard_carrier_context_promoted_replay",
            ],
        ),
        Step(
            "promotion garde producteur delta pont spatial base carrier-context promue .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer_guard_promoted_replay.py",
                "--base-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_context_promoted_replay/fixtures.csv",
                "--guard-targets",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer_guard_carrier_context_promoted_replay/targets.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer_guard_carrier_context_promoted_replay_promoted",
                "--title",
                "Lands of Lore II .tex Guarded Delta Producer Carrier-Context Promoted Replay",
            ],
        ),
        Step(
            "dependances source apres promotion delta-guard .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_probe.py",
                "--replay-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer_guard_carrier_context_promoted_replay_promoted/fixtures.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_delta_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Gradient Source-Dependency Delta Guard Promoted Replay Probe",
            ],
        ),
        Step(
            "coeur residuel dependances source apres promotion delta-guard .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_residual_core_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_delta_guard_promoted_replay/slots.csv",
                "--edges",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_delta_guard_promoted_replay/edges.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_delta_guard_promoted_residual_core",
            ],
        ),
        Step(
            "sources terminales externes apres promotion delta-guard .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_source_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_delta_guard_promoted_replay/slots.csv",
                "--terminals",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_delta_guard_promoted_residual_core/terminals.csv",
                "--fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer_guard_carrier_context_promoted_replay_promoted/fixtures.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_source_delta_guard_promoted_replay",
            ],
        ),
        Step(
            "selecteur small nonzero final apres promotion delta-guard .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector_probe.py",
                "--blocker-spans",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_source_delta_guard_promoted_replay/spans.csv",
                "--fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer_guard_carrier_context_promoted_replay_promoted/fixtures.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector_delta_guard_promoted_replay",
            ],
        ),
        Step(
            "revue sources small nonzero finale apres promotion delta-guard .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_source_review.py",
                "--targets",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector_delta_guard_promoted_replay/targets.csv",
                "--source-candidates",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector_delta_guard_promoted_replay/source_candidates.csv",
                "--small-gaps",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector_delta_guard_promoted_replay/small_gaps.csv",
                "--fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer_guard_carrier_context_promoted_replay_promoted/fixtures.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_source_review_delta_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Final Small Nonzero Source Review Delta Guard Promoted Replay",
            ],
        ),
        Step(
            "preuve elargie small nonzero finale apres promotion delta-guard .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_broader_evidence_probe.py",
                "--targets",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector_delta_guard_promoted_replay/targets.csv",
                "--small-gaps",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector_delta_guard_promoted_replay/small_gaps.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_broader_evidence_delta_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Final Small Nonzero Broader Evidence Delta Guard Promoted Replay",
            ],
        ),
        Step(
            "revue garde relative small nonzero finale apres promotion delta-guard .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_relative_guard_review.py",
                "--broader-summary",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_broader_evidence_delta_guard_promoted_replay/summary.csv",
                "--broader-formulas",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_broader_evidence_delta_guard_promoted_replay/formulas.csv",
                "--broader-guards",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_broader_evidence_delta_guard_promoted_replay/guards.csv",
                "--targets",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector_delta_guard_promoted_replay/targets.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_relative_guard_review_delta_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Final Small Nonzero Relative Guard Review Delta Guard Promoted Replay",
            ],
        ),
        Step(
            "promotion garde relative small nonzero finale apres promotion delta-guard .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_relative_guard_promoted_replay.py",
                "--base-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_delta_producer_guard_carrier_context_promoted_replay_promoted/fixtures.csv",
                "--review-summary",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_relative_guard_review_delta_guard_promoted_replay/summary.csv",
                "--targets",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_relative_guard_review_delta_guard_promoted_replay/targets.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_relative_guard_promoted_replay_delta_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Final Small Nonzero Relative Guard Promoted Replay Delta Guard Promoted Replay",
            ],
        ),
        Step(
            "dependances source apres promotion finale garde relative small nonzero .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_probe.py",
                "--replay-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_relative_guard_promoted_replay_delta_guard_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_final_relative_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Gradient Sequence High-Safe Low Exception Source-Dependency Final Relative Guard Promoted Replay",
            ],
        ),
        Step(
            "noyau residuel dependances source apres promotion finale garde relative .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_residual_core_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_final_relative_guard_promoted_replay/slots.csv",
                "--edges",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_final_relative_guard_promoted_replay/edges.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_final_relative_guard_promoted_residual_core",
            ],
        ),
        Step(
            "sources terminales externes apres promotion finale garde relative .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_source_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_final_relative_guard_promoted_replay/slots.csv",
                "--terminals",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_final_relative_guard_promoted_residual_core/terminals.csv",
                "--fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_relative_guard_promoted_replay_delta_guard_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_source_final_relative_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Gradient External Terminal Source Review Final Relative Guard Promoted Replay",
            ],
        ),
        Step(
            "chaines source apres promotion finale garde relative .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_chain_probe.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_final_relative_guard_promoted_replay/slots.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_chain_final_relative_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Gradient Source Chain Final Relative Guard Promoted Replay",
            ],
        ),
        Step(
            "terminaux source apres promotion finale garde relative .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_probe.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_final_relative_guard_promoted_replay/slots.csv",
                "--terminals",
                "output/tex_gradient_sequence_high_safe_low_exception_source_chain_final_relative_guard_promoted_replay/terminals.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_final_relative_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Gradient Source Terminal Final Relative Guard Promoted Replay",
            ],
        ),
        Step(
            "revue terminaux source apres promotion finale garde relative .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_review.py",
                "--terminals",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_final_relative_guard_promoted_replay/terminals.csv",
                "--chains",
                "output/tex_gradient_sequence_high_safe_low_exception_source_chain_final_relative_guard_promoted_replay/chains.csv",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_final_relative_guard_promoted_replay/slots.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_review_final_relative_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Gradient Source Terminal Review Final Relative Guard Promoted Replay",
            ],
        ),
        Step(
            "contexte chaines terminaux apres promotion finale garde relative .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_chain_context_probe.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_final_relative_guard_promoted_replay/slots.csv",
                "--terminals",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_final_relative_guard_promoted_replay/terminals.csv",
                "--review-chains",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_review_final_relative_guard_promoted_replay/chains.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_chain_context_final_relative_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Gradient Source Terminal Chain Context Final Relative Guard Promoted Replay",
            ],
        ),
        Step(
            "support replay terminaux source apres promotion finale garde relative .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_support_probe.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_final_relative_guard_promoted_replay/slots.csv",
                "--terminals",
                "output/tex_gradient_sequence_high_safe_low_exception_source_chain_final_relative_guard_promoted_replay/terminals.csv",
                "--chains",
                "output/tex_gradient_sequence_high_safe_low_exception_source_chain_final_relative_guard_promoted_replay/chains.csv",
                "--candidates",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_final_relative_guard_promoted_replay/candidates.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_support_final_relative_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Gradient Source Terminal Replay Support Final Relative Guard Promoted Replay",
            ],
        ),
        Step(
            "union replay terminaux source apres promotion finale garde relative .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_final_relative_guard_promoted_replay/slots.csv",
                "--terminals",
                "output/tex_gradient_sequence_high_safe_low_exception_source_chain_final_relative_guard_promoted_replay/terminals.csv",
                "--source-terminals",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_final_relative_guard_promoted_replay/terminals.csv",
                "--chains",
                "output/tex_gradient_sequence_high_safe_low_exception_source_chain_final_relative_guard_promoted_replay/chains.csv",
                "--review-chains",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_review_final_relative_guard_promoted_replay/chains.csv",
                "--chain-context-candidates",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_chain_context_final_relative_guard_promoted_replay/candidates.csv",
                "--replay-support-candidates",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_support_final_relative_guard_promoted_replay/candidates.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_final_relative_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Gradient Source Terminal Replay Union Final Relative Guard Promoted Replay",
            ],
        ),
        Step(
            "garde union replay terminaux source apres promotion finale garde relative .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_final_relative_guard_promoted_replay/slots.csv",
                "--source-terminals",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_final_relative_guard_promoted_replay/terminals.csv",
                "--chains",
                "output/tex_gradient_sequence_high_safe_low_exception_source_chain_final_relative_guard_promoted_replay/chains.csv",
                "--union-roots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_final_relative_guard_promoted_replay/roots.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_final_relative_guard_promoted_replay",
            ],
        ),
        Step(
            "split garde union replay terminaux source apres promotion finale garde relative .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_split_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_final_relative_guard_promoted_replay/slots.csv",
                "--source-terminals",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_final_relative_guard_promoted_replay/terminals.csv",
                "--chains",
                "output/tex_gradient_sequence_high_safe_low_exception_source_chain_final_relative_guard_promoted_replay/chains.csv",
                "--union-roots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_final_relative_guard_promoted_replay/roots.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_split_final_relative_guard_promoted_replay",
            ],
        ),
        Step(
            "couverture garde union replay terminaux source apres promotion finale garde relative .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_final_relative_guard_promoted_replay/slots.csv",
                "--source-terminals",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_final_relative_guard_promoted_replay/terminals.csv",
                "--chains",
                "output/tex_gradient_sequence_high_safe_low_exception_source_chain_final_relative_guard_promoted_replay/chains.csv",
                "--union-roots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_final_relative_guard_promoted_replay/roots.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_final_relative_guard_promoted_replay",
            ],
        ),
        Step(
            "promotion couverture garde union replay terminaux source apres promotion finale garde relative .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_promoted_replay.py",
                "--base-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_relative_guard_promoted_replay_delta_guard_promoted_replay/fixtures.csv",
                "--dependency-slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_final_relative_guard_promoted_replay/slots.csv",
                "--guard-roots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_final_relative_guard_promoted_replay/roots.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_final_relative_guard_promoted_replay_promoted",
                "--title",
                "Lands of Lore II .tex Gradient Source Terminal Guard Cover Final Relative Promoted Replay",
            ],
        ),
        Step(
            "dependances source apres promotion finale garde connue .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_probe.py",
                "--replay-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_final_relative_guard_promoted_replay_promoted/fixtures.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_final_known_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Gradient Source-Dependency Final Known Guard Promoted Replay",
            ],
        ),
        Step(
            "noyau residuel dependances source apres promotion finale garde connue .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_residual_core_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_final_known_guard_promoted_replay/slots.csv",
                "--edges",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_final_known_guard_promoted_replay/edges.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_final_known_guard_promoted_residual_core",
            ],
        ),
        Step(
            "revue garde bucket-split source apres promotion finale garde connue .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_bucket_split_guard_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_final_known_guard_promoted_replay/slots.csv",
                "--base-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_final_relative_guard_promoted_replay_promoted/fixtures.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_bucket_split_guard_final_known_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Source Bucket-Split Guard Final Known Guard Promoted Replay",
            ],
        ),
        Step(
            "promotion garde bucket-split source apres promotion finale garde connue .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_bucket_split_guard_promoted_replay.py",
                "--base-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_final_relative_guard_promoted_replay_promoted/fixtures.csv",
                "--targets",
                "output/tex_gradient_sequence_high_safe_low_exception_source_bucket_split_guard_final_known_guard_promoted_replay/targets.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_bucket_split_guard_final_known_guard_promoted_replay_promoted",
                "--title",
                "Lands of Lore II .tex Source Bucket-Split Guard Final Known Guard Promoted Replay",
            ],
        ),
        Step(
            "dependances source apres promotion bucket-split finale .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_probe.py",
                "--replay-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_source_bucket_split_guard_final_known_guard_promoted_replay_promoted/fixtures.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_bucket_split_guard_final_known_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Source-Dependency Bucket-Split Guard Final Known Guard Promoted Replay",
            ],
        ),
        Step(
            "noyau residuel dependances source apres promotion bucket-split finale .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_residual_core_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_bucket_split_guard_final_known_guard_promoted_replay/slots.csv",
                "--edges",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_bucket_split_guard_final_known_guard_promoted_replay/edges.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_bucket_split_guard_final_known_guard_promoted_residual_core",
            ],
        ),
        Step(
            "chaines source apres promotion bucket-split finale .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_chain_probe.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_bucket_split_guard_final_known_guard_promoted_replay/slots.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_chain_bucket_split_guard_final_known_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Source-Chain Bucket-Split Guard Final Known Guard Promoted Replay",
            ],
        ),
        Step(
            "terminaux source apres promotion bucket-split finale .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_probe.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_bucket_split_guard_final_known_guard_promoted_replay/slots.csv",
                "--terminals",
                "output/tex_gradient_sequence_high_safe_low_exception_source_chain_bucket_split_guard_final_known_guard_promoted_replay/terminals.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_bucket_split_guard_final_known_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Source-Terminal Bucket-Split Guard Final Known Guard Promoted Replay",
            ],
        ),
        Step(
            "revue terminaux source apres promotion bucket-split finale .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_review.py",
                "--terminals",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_bucket_split_guard_final_known_guard_promoted_replay/terminals.csv",
                "--chains",
                "output/tex_gradient_sequence_high_safe_low_exception_source_chain_bucket_split_guard_final_known_guard_promoted_replay/chains.csv",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_bucket_split_guard_final_known_guard_promoted_replay/slots.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_review_bucket_split_guard_final_known_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Source-Terminal Review Bucket-Split Guard Final Known Guard Promoted Replay",
            ],
        ),
        Step(
            "contexte chaines terminaux source apres promotion bucket-split finale .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_chain_context_probe.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_bucket_split_guard_final_known_guard_promoted_replay/slots.csv",
                "--terminals",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_bucket_split_guard_final_known_guard_promoted_replay/terminals.csv",
                "--review-chains",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_review_bucket_split_guard_final_known_guard_promoted_replay/chains.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_chain_context_bucket_split_guard_final_known_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Source-Terminal Chain Context Bucket-Split Guard Final Known Guard Promoted Replay",
            ],
        ),
        Step(
            "support replay terminaux source apres promotion bucket-split finale .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_support_probe.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_bucket_split_guard_final_known_guard_promoted_replay/slots.csv",
                "--terminals",
                "output/tex_gradient_sequence_high_safe_low_exception_source_chain_bucket_split_guard_final_known_guard_promoted_replay/terminals.csv",
                "--chains",
                "output/tex_gradient_sequence_high_safe_low_exception_source_chain_bucket_split_guard_final_known_guard_promoted_replay/chains.csv",
                "--candidates",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_bucket_split_guard_final_known_guard_promoted_replay/candidates.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_support_bucket_split_guard_final_known_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Source-Terminal Replay Support Bucket-Split Guard Final Known Guard Promoted Replay",
            ],
        ),
        Step(
            "union replay terminaux source apres promotion bucket-split finale .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_bucket_split_guard_final_known_guard_promoted_replay/slots.csv",
                "--terminals",
                "output/tex_gradient_sequence_high_safe_low_exception_source_chain_bucket_split_guard_final_known_guard_promoted_replay/terminals.csv",
                "--source-terminals",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_bucket_split_guard_final_known_guard_promoted_replay/terminals.csv",
                "--chains",
                "output/tex_gradient_sequence_high_safe_low_exception_source_chain_bucket_split_guard_final_known_guard_promoted_replay/chains.csv",
                "--review-chains",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_review_bucket_split_guard_final_known_guard_promoted_replay/chains.csv",
                "--chain-context-candidates",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_chain_context_bucket_split_guard_final_known_guard_promoted_replay/candidates.csv",
                "--replay-support-candidates",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_support_bucket_split_guard_final_known_guard_promoted_replay/candidates.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_bucket_split_guard_final_known_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Source-Terminal Replay Union Bucket-Split Guard Final Known Guard Promoted Replay",
            ],
        ),
        Step(
            "couverture garde union replay terminaux source apres promotion bucket-split finale .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_bucket_split_guard_final_known_guard_promoted_replay/slots.csv",
                "--source-terminals",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_bucket_split_guard_final_known_guard_promoted_replay/terminals.csv",
                "--chains",
                "output/tex_gradient_sequence_high_safe_low_exception_source_chain_bucket_split_guard_final_known_guard_promoted_replay/chains.csv",
                "--union-roots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_bucket_split_guard_final_known_guard_promoted_replay/roots.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_bucket_split_guard_final_known_guard_promoted_replay",
            ],
        ),
        Step(
            "promotion couverture garde union replay terminaux source apres promotion bucket-split finale .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_promoted_replay.py",
                "--base-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_source_bucket_split_guard_final_known_guard_promoted_replay_promoted/fixtures.csv",
                "--dependency-slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_bucket_split_guard_final_known_guard_promoted_replay/slots.csv",
                "--guard-roots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_bucket_split_guard_final_known_guard_promoted_replay/roots.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_bucket_split_guard_final_known_guard_promoted_replay_promoted",
                "--title",
                "Lands of Lore II .tex Source-Terminal Guard Cover Bucket-Split Final Known Promoted Replay",
            ],
        ),
        Step(
            "revue garde source-byte apres promotion bucket-split finale .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_byte_guard_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_bucket_split_guard_final_known_guard_promoted_replay/slots.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_bucket_split_guard_final_known_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Source Byte Guard Bucket-Split Final Known Promoted Replay",
            ],
        ),
        Step(
            "promotion garde source-byte apres promotion terminale bucket-split finale .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_byte_guard_promoted_replay.py",
                "--base-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_bucket_split_guard_final_known_guard_promoted_replay_promoted/fixtures.csv",
                "--targets",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_bucket_split_guard_final_known_guard_promoted_replay/targets.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_bucket_split_terminal_guard_promoted_replay_promoted",
                "--title",
                "Lands of Lore II .tex Source Byte Guard Bucket-Split Terminal Guard Promoted Replay",
            ],
        ),
        Step(
            "dependances source apres promotion source-byte finale .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_probe.py",
                "--replay-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_bucket_split_terminal_guard_promoted_replay_promoted/fixtures.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_source_byte_guard_bucket_split_terminal_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Source-Dependency Source Byte Guard Bucket-Split Terminal Guard Promoted Replay",
            ],
        ),
        Step(
            "noyau residuel dependances source apres promotion source-byte finale .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_residual_core_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_source_byte_guard_bucket_split_terminal_guard_promoted_replay/slots.csv",
                "--edges",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_source_byte_guard_bucket_split_terminal_guard_promoted_replay/edges.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_source_byte_guard_bucket_split_terminal_guard_promoted_residual_core",
            ],
        ),
        Step(
            "revue deuxieme garde source-byte apres promotion source-byte finale .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_byte_guard_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_source_byte_guard_bucket_split_terminal_guard_promoted_replay/slots.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_second_source_byte_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Second Source Byte Guard After Source Byte Promoted Replay",
            ],
        ),
        Step(
            "promotion deuxieme garde source-byte .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_byte_guard_promoted_replay.py",
                "--base-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_bucket_split_terminal_guard_promoted_replay_promoted/fixtures.csv",
                "--targets",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_second_source_byte_guard_promoted_replay/targets.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_second_source_byte_guard_promoted_replay_promoted",
                "--title",
                "Lands of Lore II .tex Second Source Byte Guard Promoted Replay",
            ],
        ),
        Step(
            "dependances source apres deuxieme promotion source-byte .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_probe.py",
                "--replay-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_second_source_byte_guard_promoted_replay_promoted/fixtures.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_second_source_byte_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Source-Dependency Second Source Byte Guard Promoted Replay",
            ],
        ),
        Step(
            "noyau residuel apres deuxieme promotion source-byte .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_residual_core_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_second_source_byte_guard_promoted_replay/slots.csv",
                "--edges",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_second_source_byte_guard_promoted_replay/edges.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_second_source_byte_guard_promoted_residual_core",
            ],
        ),
        Step(
            "revue troisieme garde source-byte apres deuxieme promotion .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_byte_guard_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_second_source_byte_guard_promoted_replay/slots.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_third_source_byte_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Third Source Byte Guard After Second Source Byte Promoted Replay",
            ],
        ),
        Step(
            "promotion troisieme garde source-byte .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_byte_guard_promoted_replay.py",
                "--base-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_second_source_byte_guard_promoted_replay_promoted/fixtures.csv",
                "--targets",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_third_source_byte_guard_promoted_replay/targets.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_third_source_byte_guard_promoted_replay_promoted",
                "--title",
                "Lands of Lore II .tex Third Source Byte Guard Promoted Replay",
            ],
        ),
        Step(
            "dependances source apres troisieme promotion source-byte .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_probe.py",
                "--replay-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_third_source_byte_guard_promoted_replay_promoted/fixtures.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_third_source_byte_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Source-Dependency Third Source Byte Guard Promoted Replay",
            ],
        ),
        Step(
            "noyau residuel apres troisieme promotion source-byte .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_residual_core_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_third_source_byte_guard_promoted_replay/slots.csv",
                "--edges",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_third_source_byte_guard_promoted_replay/edges.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_third_source_byte_guard_promoted_residual_core",
            ],
        ),
        Step(
            "revue quatrieme garde source-byte apres troisieme promotion .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_byte_guard_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_third_source_byte_guard_promoted_replay/slots.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_fourth_source_byte_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Fourth Source Byte Guard After Third Source Byte Promoted Replay",
            ],
        ),
        Step(
            "promotion quatrieme garde source-byte .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_byte_guard_promoted_replay.py",
                "--base-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_third_source_byte_guard_promoted_replay_promoted/fixtures.csv",
                "--targets",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_fourth_source_byte_guard_promoted_replay/targets.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_fourth_source_byte_guard_promoted_replay_promoted",
                "--title",
                "Lands of Lore II .tex Fourth Source Byte Guard Promoted Replay",
            ],
        ),
        Step(
            "dependances source apres quatrieme promotion source-byte .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_probe.py",
                "--replay-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_fourth_source_byte_guard_promoted_replay_promoted/fixtures.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_fourth_source_byte_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Source-Dependency Fourth Source Byte Guard Promoted Replay",
            ],
        ),
        Step(
            "noyau residuel apres quatrieme promotion source-byte .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_residual_core_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_fourth_source_byte_guard_promoted_replay/slots.csv",
                "--edges",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_fourth_source_byte_guard_promoted_replay/edges.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_fourth_source_byte_guard_promoted_residual_core",
            ],
        ),
        Step(
            "revue cinquieme garde source-byte apres quatrieme promotion .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_byte_guard_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_fourth_source_byte_guard_promoted_replay/slots.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_fifth_source_byte_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Fifth Source Byte Guard After Fourth Source Byte Promoted Replay",
            ],
        ),
        Step(
            "promotion cinquieme garde source-byte .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_byte_guard_promoted_replay.py",
                "--base-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_fourth_source_byte_guard_promoted_replay_promoted/fixtures.csv",
                "--targets",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_fifth_source_byte_guard_promoted_replay/targets.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_fifth_source_byte_guard_promoted_replay_promoted",
                "--title",
                "Lands of Lore II .tex Fifth Source Byte Guard Promoted Replay",
            ],
        ),
        Step(
            "dependances source apres cinquieme promotion source-byte .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_probe.py",
                "--replay-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_fifth_source_byte_guard_promoted_replay_promoted/fixtures.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_fifth_source_byte_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Source-Dependency Fifth Source Byte Guard Promoted Replay",
            ],
        ),
        Step(
            "noyau residuel apres cinquieme promotion source-byte .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_residual_core_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_fifth_source_byte_guard_promoted_replay/slots.csv",
                "--edges",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_fifth_source_byte_guard_promoted_replay/edges.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_fifth_source_byte_guard_promoted_residual_core",
            ],
        ),
        Step(
            "revue sixieme garde source-byte apres cinquieme promotion .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_byte_guard_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_fifth_source_byte_guard_promoted_replay/slots.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_sixth_source_byte_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Sixth Source Byte Guard After Fifth Source Byte Promoted Replay",
            ],
        ),
        Step(
            "promotion sixieme garde source-byte .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_byte_guard_promoted_replay.py",
                "--base-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_fifth_source_byte_guard_promoted_replay_promoted/fixtures.csv",
                "--targets",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_sixth_source_byte_guard_promoted_replay/targets.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_sixth_source_byte_guard_promoted_replay_promoted",
                "--title",
                "Lands of Lore II .tex Sixth Source Byte Guard Promoted Replay",
            ],
        ),
        Step(
            "dependances source apres sixieme promotion source-byte .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_probe.py",
                "--replay-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_sixth_source_byte_guard_promoted_replay_promoted/fixtures.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_sixth_source_byte_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Source-Dependency Sixth Source Byte Guard Promoted Replay",
            ],
        ),
        Step(
            "noyau residuel apres sixieme promotion source-byte .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_residual_core_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_sixth_source_byte_guard_promoted_replay/slots.csv",
                "--edges",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_sixth_source_byte_guard_promoted_replay/edges.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_sixth_source_byte_guard_promoted_residual_core",
            ],
        ),
        Step(
            "revue septieme garde source-byte apres sixieme promotion .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_byte_guard_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_sixth_source_byte_guard_promoted_replay/slots.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_seventh_source_byte_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Seventh Source Byte Guard After Sixth Source Byte Promoted Replay",
            ],
        ),
        Step(
            "promotion septieme garde source-byte .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_byte_guard_promoted_replay.py",
                "--base-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_sixth_source_byte_guard_promoted_replay_promoted/fixtures.csv",
                "--targets",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_seventh_source_byte_guard_promoted_replay/targets.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_seventh_source_byte_guard_promoted_replay_promoted",
                "--title",
                "Lands of Lore II .tex Seventh Source Byte Guard Promoted Replay",
            ],
        ),
        Step(
            "dependances source apres septieme promotion source-byte .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_probe.py",
                "--replay-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_seventh_source_byte_guard_promoted_replay_promoted/fixtures.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_seventh_source_byte_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Source-Dependency Seventh Source Byte Guard Promoted Replay",
            ],
        ),
        Step(
            "noyau residuel apres septieme promotion source-byte .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_residual_core_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_seventh_source_byte_guard_promoted_replay/slots.csv",
                "--edges",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_seventh_source_byte_guard_promoted_replay/edges.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_seventh_source_byte_guard_promoted_residual_core",
            ],
        ),
        Step(
            "revue huitieme garde source-byte apres septieme promotion .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_byte_guard_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_seventh_source_byte_guard_promoted_replay/slots.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_eighth_source_byte_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Eighth Source Byte Guard After Seventh Source Byte Promoted Replay",
            ],
        ),
        Step(
            "promotion huitieme garde source-byte .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_byte_guard_promoted_replay.py",
                "--base-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_seventh_source_byte_guard_promoted_replay_promoted/fixtures.csv",
                "--targets",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_eighth_source_byte_guard_promoted_replay/targets.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_eighth_source_byte_guard_promoted_replay_promoted",
                "--title",
                "Lands of Lore II .tex Eighth Source Byte Guard Promoted Replay",
            ],
        ),
        Step(
            "dependances source apres huitieme promotion source-byte .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_probe.py",
                "--replay-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_eighth_source_byte_guard_promoted_replay_promoted/fixtures.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_eighth_source_byte_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Source-Dependency Eighth Source Byte Guard Promoted Replay",
            ],
        ),
        Step(
            "noyau residuel apres huitieme promotion source-byte .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_residual_core_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_eighth_source_byte_guard_promoted_replay/slots.csv",
                "--edges",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_eighth_source_byte_guard_promoted_replay/edges.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_eighth_source_byte_guard_promoted_residual_core",
            ],
        ),
        Step(
            "revue neuvieme garde source-byte apres huitieme promotion .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_byte_guard_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_eighth_source_byte_guard_promoted_replay/slots.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_ninth_source_byte_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Ninth Source Byte Guard After Eighth Source Byte Promoted Replay",
            ],
        ),
        Step(
            "promotion neuvieme garde source-byte .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_byte_guard_promoted_replay.py",
                "--base-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_eighth_source_byte_guard_promoted_replay_promoted/fixtures.csv",
                "--targets",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_ninth_source_byte_guard_promoted_replay/targets.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_ninth_source_byte_guard_promoted_replay_promoted",
                "--title",
                "Lands of Lore II .tex Ninth Source Byte Guard Promoted Replay",
            ],
        ),
        Step(
            "dependances source apres neuvieme promotion source-byte .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_probe.py",
                "--replay-fixtures",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_ninth_source_byte_guard_promoted_replay_promoted/fixtures.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_ninth_source_byte_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Source-Dependency Ninth Source Byte Guard Promoted Replay",
            ],
        ),
        Step(
            "noyau residuel apres neuvieme promotion source-byte .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_dependency_residual_core_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_ninth_source_byte_guard_promoted_replay/slots.csv",
                "--edges",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_ninth_source_byte_guard_promoted_replay/edges.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_ninth_source_byte_guard_promoted_residual_core",
            ],
        ),
        Step(
            "revue dixieme garde source-byte apres neuvieme promotion .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_source_byte_guard_review.py",
                "--slots",
                "output/tex_gradient_sequence_high_safe_low_exception_source_dependency_ninth_source_byte_guard_promoted_replay/slots.csv",
                "-o",
                "output/tex_gradient_sequence_high_safe_low_exception_source_byte_guard_tenth_source_byte_guard_promoted_replay",
                "--title",
                "Lands of Lore II .tex Tenth Source Byte Guard After Ninth Source Byte Promoted Replay",
            ],
        ),
        Step(
            "haut/bas source-profile gradient post-formule .tex",
            [sys.executable, "tools/lolg_tex_gradient_source_profile_high_low_probe.py"],
        ),
        Step(
            "bas apres high-safe source-profile gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_source_profile_high_safe_low_probe.py"],
        ),
        Step(
            "etat opcode payload gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_payload_state_opcode_probe.py"],
        ),
        Step(
            "macro opcode payload gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_macro_opcode_probe.py"],
        ),
        Step(
            "split conflits macro opcode gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_macro_conflict_split_probe.py"],
        ),
        Step(
            "etat residuel macro opcode gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_macro_residual_state_probe.py"],
        ),
        Step(
            "phase macro opcode gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_macro_phase_probe.py"],
        ),
        Step(
            "split conflits phase macro opcode gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_macro_phase_conflict_split_probe.py"],
        ),
        Step(
            "sequence phase macro opcode gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_macro_phase_sequence_probe.py"],
        ),
        Step(
            "transition fixture/op macro opcode gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_macro_fixture_transition_probe.py"],
        ),
        Step(
            "cluster etat macro opcode gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_macro_state_cluster_probe.py"],
        ),
        Step(
            "etat macro + source-profile gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_macro_source_profile_state_probe.py"],
        ),
        Step(
            "payload cluster etat macro opcode gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_macro_state_cluster_payload_probe.py"],
        ),
        Step(
            "source cluster etat macro opcode gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_macro_state_cluster_source_probe.py"],
        ),
        Step(
            "literal/geometrie cluster etat macro opcode gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_macro_state_cluster_literal_probe.py"],
        ),
        Step(
            "backrefs cluster etat macro opcode gradient .tex",
            [sys.executable, "tools/lolg_tex_gradient_macro_state_cluster_backref_probe.py"],
        ),
        Step("split micro jump .tex", [sys.executable, "tools/lolg_tex_micro_jump_split.py"]),
        Step("positions micro jump .tex", [sys.executable, "tools/lolg_tex_micro_jump_positions.py"]),
        Step("payload jump-mixed micro .tex", [sys.executable, "tools/lolg_tex_micro_jump_mixed_payload_probe.py"]),
        Step(
            "jump-token noisy .tex",
            [sys.executable, "tools/lolg_tex_gap_decoder_len64_promoted_nonzero_gap_jump_token_probe.py"],
            requires_pillow=True,
        ),
        Step("profil payload jump-token .tex", [sys.executable, "tools/lolg_tex_jump_token_payload_profile_probe.py"]),
        Step(
            "etat opcode payload jump-token .tex",
            [sys.executable, "tools/lolg_tex_jump_token_payload_state_opcode_probe.py"],
        ),
        Step("stable walks micro .tex", [sys.executable, "tools/lolg_tex_micro_stable_walks.py"]),
        Step("backrefs stable walks micro .tex", [sys.executable, "tools/lolg_tex_micro_stable_backref_probe.py"]),
        Step("sources stable walks micro .tex", [sys.executable, "tools/lolg_tex_micro_stable_source_probe.py"]),
        Step("grammaire sources stable walks micro .tex", [sys.executable, "tools/lolg_tex_micro_stable_source_grammar.py"]),
        Step("contextes valeurs stable walks micro .tex", [sys.executable, "tools/lolg_tex_micro_stable_value_context.py"]),
        Step("regles contextes stable walks micro .tex", [sys.executable, "tools/lolg_tex_micro_stable_context_rule_probe.py"]),
        Step("sequences stable walks micro .tex", [sys.executable, "tools/lolg_tex_micro_stable_sequence_probe.py"]),
        Step("alternances stable walks micro .tex", [sys.executable, "tools/lolg_tex_micro_stable_alternation_probe.py"]),
        Step("replay alternances stable walks micro .tex", [sys.executable, "tools/lolg_tex_micro_stable_alternation_replay.py"]),
        Step("sequences longueurs alternances stable walks micro .tex", [sys.executable, "tools/lolg_tex_micro_stable_length_sequence_probe.py"]),
        Step("controle longueurs alternances stable walks micro .tex", [sys.executable, "tools/lolg_tex_micro_stable_length_control_probe.py"]),
        Step("opcode longueurs alternances stable walks micro .tex", [sys.executable, "tools/lolg_tex_micro_stable_length_opcode_probe.py"]),
        Step("intervalles longueurs alternances stable walks micro .tex", [sys.executable, "tools/lolg_tex_micro_stable_length_interval_probe.py"]),
        Step("split familles micro-token .tex", [sys.executable, "tools/lolg_tex_micro_token_family_split_probe.py"]),
        Step("sous-familles mixed-value micro-token .tex", [sys.executable, "tools/lolg_tex_micro_mixed_value_subfamily_probe.py"]),
        Step(
            "controle dominant mixed-value micro-token .tex",
            [sys.executable, "tools/lolg_tex_micro_mixed_value_dominant_control_probe.py"],
        ),
        Step(
            "grammaire locale payload mixed-value micro-token .tex",
            [sys.executable, "tools/lolg_tex_micro_mixed_value_payload_local_grammar_probe.py"],
        ),
        Step(
            "prediction payload mixed-value micro-token .tex",
            [sys.executable, "tools/lolg_tex_micro_mixed_value_payload_predictor_probe.py"],
        ),
        Step(
            "combinaisons payload mixed-value micro-token .tex",
            [sys.executable, "tools/lolg_tex_micro_mixed_value_payload_combo_probe.py"],
        ),
        Step(
            "haut/bas payload mixed-value micro-token .tex",
            [sys.executable, "tools/lolg_tex_micro_mixed_value_payload_high_low_probe.py"],
        ),
        Step(
            "sources payload mixed-value micro-token .tex",
            [sys.executable, "tools/lolg_tex_micro_mixed_value_payload_source_profile_probe.py"],
        ),
        Step(
            "combinaisons sources payload mixed-value micro-token .tex",
            [sys.executable, "tools/lolg_tex_micro_mixed_value_payload_external_source_combo_probe.py"],
        ),
        Step(
            "haut/bas sources payload mixed-value micro-token .tex",
            [sys.executable, "tools/lolg_tex_micro_mixed_value_payload_external_high_low_probe.py"],
        ),
        Step(
            "combinaisons etat/source payload mixed-value micro-token .tex",
            [sys.executable, "tools/lolg_tex_micro_mixed_value_payload_state_external_combo_probe.py"],
        ),
        Step(
            "etat sequence payload mixed-value micro-token .tex",
            [sys.executable, "tools/lolg_tex_micro_mixed_value_payload_sequence_state_probe.py"],
        ),
        Step(
            "revue candidats sequence payload mixed-value micro-token .tex",
            [sys.executable, "tools/lolg_tex_micro_mixed_value_payload_sequence_candidate_review.py"],
        ),
        Step(
            "bootstrap prefixes payload mixed-value micro-token .tex",
            [sys.executable, "tools/lolg_tex_micro_mixed_value_payload_prefix_bootstrap_probe.py"],
        ),
        Step(
            "replay prefixes/sequence payload mixed-value micro-token .tex",
            [sys.executable, "tools/lolg_tex_micro_mixed_value_payload_prefix_sequence_replay.py"],
        ),
        Step(
            "promotion replay prefixes/sequence payload mixed-value micro-token .tex",
            [sys.executable, "tools/lolg_tex_micro_mixed_value_payload_prefix_sequence_promoted_replay.py"],
            requires_pillow=True,
        ),
        Step(
            "generalisation sequence apres promotion mixed-value micro-token .tex",
            [sys.executable, "tools/lolg_tex_micro_mixed_value_payload_sequence_promoted_generalization_probe.py"],
        ),
        Step(
            "split low sequence mixed-value micro-token .tex",
            [sys.executable, "tools/lolg_tex_micro_mixed_value_payload_sequence_low_split_probe.py"],
        ),
        Step(
            "promotion split low sequence mixed-value micro-token .tex",
            [sys.executable, "tools/lolg_tex_micro_mixed_value_payload_sequence_low_split_promoted_replay.py"],
            requires_pillow=True,
        ),
        Step(
            "expansion prerequis sequence mixed-value micro-token .tex",
            [sys.executable, "tools/lolg_tex_micro_mixed_value_payload_sequence_prerequisite_expansion_probe.py"],
        ),
        Step(
            "promotion expansion prerequis sequence mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay.py",
            ],
            requires_pillow=True,
        ),
        Step(
            "split low sequence apres prerequis mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_low_split_probe.py",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_low_split",
            ],
        ),
        Step(
            "promotion split low sequence apres prerequis mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_low_split_promoted_replay.py",
                "--base-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay/fixtures.csv",
                "--low-split-slots",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_low_split/slots.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay",
            ],
            requires_pillow=True,
        ),
        Step(
            "generalisation sequence apres split low prerequis mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_promoted_generalization_probe.py",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_low_split_generalization",
            ],
        ),
        Step(
            "split low residuel sequence apres prerequis mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_low_split_probe.py",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay/fixtures.csv",
                "--max-features",
                "3",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_second_low_split_max3",
            ],
        ),
        Step(
            "expansion residuelle prerequis sequence mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_prerequisite_expansion_probe.py",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay/fixtures.csv",
                "--max-features",
                "3",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_second_expansion_max3",
            ],
        ),
        Step(
            "expansion corpus prerequis sequence mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_probe.py",
            ],
        ),
        Step(
            "promotion expansion corpus prerequis sequence mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay.py",
                "--base-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_low_split_promoted_replay/fixtures.csv",
                "--prerequisite-slots",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_expansion/slots.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_promoted_replay",
            ],
            requires_pillow=True,
        ),
        Step(
            "split low sequence apres corpus prerequis mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_low_split_probe.py",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_promoted_replay/fixtures.csv",
                "--max-features",
                "3",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_low_split",
            ],
        ),
        Step(
            "promotion split low sequence apres corpus prerequis mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_low_split_promoted_replay.py",
                "--base-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_promoted_replay/fixtures.csv",
                "--low-split-slots",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_low_split/slots.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_promoted_replay",
            ],
            requires_pillow=True,
        ),
        Step(
            "second split low sequence corpus mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_low_split_probe.py",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_promoted_replay/fixtures.csv",
                "--max-features",
                "3",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split",
            ],
        ),
        Step(
            "promotion second split low sequence corpus mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_low_split_promoted_replay.py",
                "--base-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_low_split_promoted_replay/fixtures.csv",
                "--low-split-slots",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split/slots.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_promoted_replay",
            ],
            requires_pillow=True,
        ),
        Step(
            "prerequis adjacent-known sequence mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_probe.py",
            ],
        ),
        Step(
            "promotion prerequis adjacent-known sequence mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay.py",
                "--base-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_corpus_second_low_split_promoted_replay/fixtures.csv",
                "--prerequisite-slots",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known/slots.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_promoted_replay",
            ],
            requires_pillow=True,
        ),
        Step(
            "second prerequis adjacent-known sequence mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_probe.py",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_second",
            ],
        ),
        Step(
            "promotion second prerequis adjacent-known sequence mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay.py",
                "--base-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_promoted_replay/fixtures.csv",
                "--prerequisite-slots",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_second/slots.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_second_promoted_replay",
            ],
            requires_pillow=True,
        ),
        Step(
            "troisieme prerequis adjacent-known sequence mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_probe.py",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_second_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third",
            ],
        ),
        Step(
            "promotion troisieme prerequis adjacent-known sequence mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_prerequisite_expansion_promoted_replay.py",
                "--base-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_second_promoted_replay/fixtures.csv",
                "--prerequisite-slots",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third/slots.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay",
            ],
            requires_pillow=True,
        ),
        Step(
            "generalisation sequence apres adjacent-known mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_promoted_generalization_probe.py",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_generalization",
            ],
        ),
        Step(
            "split low residuel apres adjacent-known mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_low_split_probe.py",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay/fixtures.csv",
                "--max-features",
                "3",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_low_split",
            ],
        ),
        Step(
            "expansion corpus residuelle apres adjacent-known mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_probe.py",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_corpus_expansion",
            ],
        ),
        Step(
            "quatrieme prerequis adjacent-known sequence mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_probe.py",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_fourth",
            ],
        ),
        Step(
            "transform residuel apres adjacent-known mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_transform_probe.py",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform",
            ],
        ),
        Step(
            "promotion transform residuel apres adjacent-known mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_low_split_promoted_replay.py",
                "--base-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_third_promoted_replay/fixtures.csv",
                "--low-split-slots",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform/slots.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay",
                "--title",
                "Lands of Lore II .tex Sequence Transform Promoted Replay",
            ],
            requires_pillow=True,
        ),
        Step(
            "generalisation sequence apres transform mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_promoted_generalization_probe.py",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_generalization",
            ],
        ),
        Step(
            "second transform residuel apres adjacent-known mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_transform_probe.py",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_second",
            ],
        ),
        Step(
            "split low residuel apres transform mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_low_split_probe.py",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay/fixtures.csv",
                "--max-features",
                "3",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_low_split",
            ],
        ),
        Step(
            "expansion corpus residuelle apres transform mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_probe.py",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_expansion",
            ],
        ),
        Step(
            "prerequis adjacent-known residuel apres transform mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_probe.py",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_adjacent",
            ],
        ),
        Step(
            "transform corpus residuel apres transform mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_transform_probe.py",
                "--training-scope",
                "corpus",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus",
            ],
        ),
        Step(
            "promotion transform corpus residuel mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_low_split_promoted_replay.py",
                "--base-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_promoted_replay/fixtures.csv",
                "--low-split-slots",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus/slots.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_promoted_replay",
                "--title",
                "Lands of Lore II .tex Sequence Corpus Transform Promoted Replay",
            ],
            requires_pillow=True,
        ),
        Step(
            "generalisation sequence apres transform corpus mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_promoted_generalization_probe.py",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_generalization",
            ],
        ),
        Step(
            "second transform corpus residuel mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_transform_probe.py",
                "--training-scope",
                "corpus",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_second",
            ],
        ),
        Step(
            "promotion second transform corpus mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_low_split_promoted_replay.py",
                "--base-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_promoted_replay/fixtures.csv",
                "--low-split-slots",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_second/slots.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_second_promoted_replay",
                "--title",
                "Lands of Lore II .tex Sequence Corpus Transform Second Promoted Replay",
            ],
            requires_pillow=True,
        ),
        Step(
            "generalisation sequence apres second transform corpus mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_promoted_generalization_probe.py",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_second_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_second_generalization",
            ],
        ),
        Step(
            "troisieme transform corpus residuel mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_transform_probe.py",
                "--training-scope",
                "corpus",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_second_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third",
            ],
        ),
        Step(
            "promotion troisieme transform corpus mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_low_split_promoted_replay.py",
                "--base-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_second_promoted_replay/fixtures.csv",
                "--low-split-slots",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third/slots.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay",
                "--title",
                "Lands of Lore II .tex Sequence Corpus Transform Third Promoted Replay",
            ],
            requires_pillow=True,
        ),
        Step(
            "generalisation sequence apres troisieme transform corpus mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_promoted_generalization_probe.py",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_generalization",
            ],
        ),
        Step(
            "quatrieme transform corpus residuel mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_transform_probe.py",
                "--training-scope",
                "corpus",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_fourth",
            ],
        ),
        Step(
            "split low residuel apres transform corpus mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_low_split_probe.py",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay/fixtures.csv",
                "--max-features",
                "3",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_low_split",
            ],
        ),
        Step(
            "expansion corpus residuelle apres transform corpus mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_probe.py",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_corpus_expansion",
            ],
        ),
        Step(
            "prerequis adjacent-known apres transform corpus mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_probe.py",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_adjacent",
            ],
        ),
        Step(
            "low-copy residuel sequence mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_low_copy_probe.py",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_low_copy",
            ],
        ),
        Step(
            "promotion low-copy sequence mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_low_split_promoted_replay.py",
                "--base-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_transform_corpus_third_promoted_replay/fixtures.csv",
                "--low-split-slots",
                "output/tex_micro_mixed_value_payload_sequence_low_copy/slots.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_low_copy_promoted_replay",
                "--title",
                "Lands of Lore II .tex Sequence Low Copy Promoted Replay",
            ],
            requires_pillow=True,
        ),
        Step(
            "etat prerequis exceptions low gradient apres low-copy .tex",
            [
                sys.executable,
                "tools/lolg_tex_gradient_sequence_high_safe_low_exception_prerequisite_state_probe.py",
            ],
        ),
        Step(
            "generalisation apres low-copy sequence mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_promoted_generalization_probe.py",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_low_copy_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_low_copy_generalization",
            ],
        ),
        Step(
            "second low-copy sequence mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_low_copy_probe.py",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_low_copy_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_low_copy_second",
            ],
        ),
        Step(
            "split low residuel apres low-copy mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_low_split_probe.py",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_low_copy_promoted_replay/fixtures.csv",
                "--max-features",
                "3",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_low_copy_low_split",
            ],
        ),
        Step(
            "expansion corpus residuelle apres low-copy mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_prerequisite_corpus_expansion_probe.py",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_low_copy_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_low_copy_corpus_expansion",
            ],
        ),
        Step(
            "prerequis adjacent-known apres low-copy mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_prerequisite_adjacent_known_probe.py",
                "--replay-fixtures",
                "output/tex_micro_mixed_value_payload_sequence_low_copy_promoted_replay/fixtures.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_low_copy_adjacent",
            ],
        ),
        Step(
            "transform roles prerequis bloques apres low-copy mixed-value micro-token .tex",
            [
                sys.executable,
                "tools/lolg_tex_micro_mixed_value_payload_sequence_blocked_prerequisite_role_transform_probe.py",
                "--sequence-slots",
                "output/tex_micro_mixed_value_payload_sequence_low_copy_generalization/slots.csv",
                "-o",
                "output/tex_micro_mixed_value_payload_sequence_blocked_prerequisite_role_transform",
            ],
        ),
        Step(
            "spatial payload mixed-value micro-token .tex",
            [sys.executable, "tools/lolg_tex_micro_mixed_value_payload_spatial_probe.py"],
        ),
        Step(
            "etat opcode payload mixed-value micro-token .tex",
            [sys.executable, "tools/lolg_tex_micro_mixed_value_payload_state_opcode_probe.py"],
        ),
        Step("roadmap decodeur .tex", [sys.executable, "tools/lolg_tex_decoder_roadmap.py"]),
        Step("inventaire historique projet", [sys.executable, "tools/lolg_project_legacy_inventory.py"]),
    ]
    return steps + quick_steps(fail_on_issues)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Lands of Lore 2 Full HD validation steps.")
    parser.add_argument(
        "--mode",
        choices=["quick", "reports"],
        default="quick",
        help="quick validates existing outputs; reports also regenerates lightweight reports.",
    )
    parser.add_argument("--fail-on-issues", action="store_true", help="Make audit failures return non-zero.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without running them.")
    parser.add_argument(
        "--keep-going",
        action="store_true",
        help="Continue after failed optional/report steps and return a final failure summary.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not shutil.which(sys.executable):
        raise SystemExit(f"Python executable not found: {sys.executable}")

    pillow_available = True if args.dry_run else has_module("PIL")
    steps = quick_steps(args.fail_on_issues) if args.mode == "quick" else report_steps(args.fail_on_issues)
    failures: list[tuple[str, int]] = []

    for step in steps:
        if step.requires_pillow and not pillow_available:
            message = f"{step.name}: dependency missing: Pillow/PIL"
            if args.keep_going or step.optional:
                print(f"SKIP {message}", flush=True)
                failures.append((step.name, 127))
                continue
            raise SystemExit(message)

        code = run_step(step, args.dry_run)
        if code:
            failures.append((step.name, code))
            if not args.keep_going:
                raise SystemExit(code)

    if failures:
        print("Failures:", flush=True)
        for name, code in failures:
            print(f"  {name}: exit {code}", flush=True)
        raise SystemExit(1)

    print("Full HD pipeline: pass", flush=True)


if __name__ == "__main__":
    main()
