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
        Step("split micro jump .tex", [sys.executable, "tools/lolg_tex_micro_jump_split.py"]),
        Step("positions micro jump .tex", [sys.executable, "tools/lolg_tex_micro_jump_positions.py"]),
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
            "sources payload mixed-value micro-token .tex",
            [sys.executable, "tools/lolg_tex_micro_mixed_value_payload_source_profile_probe.py"],
        ),
        Step(
            "spatial payload mixed-value micro-token .tex",
            [sys.executable, "tools/lolg_tex_micro_mixed_value_payload_spatial_probe.py"],
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
