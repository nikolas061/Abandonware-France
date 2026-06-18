#!/usr/bin/env python3
"""Review guarded compact-token selectors for the final frontier 80 pre-run pair."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path

import lolg_tex_old_clean_byte_union_frontier80_tail_compact_token_review as token_review
from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value


DEFAULT_SLOTS = token_review.DEFAULT_SLOTS
DEFAULT_BASE_FIXTURES = token_review.DEFAULT_BASE_FIXTURES
DEFAULT_MANIFEST = token_review.DEFAULT_MANIFEST
DEFAULT_DELTA_TARGETS = token_review.DEFAULT_DELTA_TARGETS
DEFAULT_OUTPUT = Path("output/tex_old_clean_byte_union_frontier80_tail_compact_token_guard_split_review")

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_key",
    "target_pair_offset",
    "target_pair_hex",
    "target_run_value",
    "target_delta",
    "selector_rows",
    "target_full_selector_rows",
    "guard_candidate_rows",
    "zero_false_guard_rows",
    "strong_guard_rows",
    "weak_guard_rows",
    "target_only_guard_rows",
    "rejected_guard_rows",
    "best_selector",
    "best_family",
    "best_guard_feature",
    "best_guard_value",
    "best_target_output_hex",
    "best_known_exact_rows",
    "best_known_false_rows",
    "best_known_miss_rows",
    "best_target_full_rows",
    "best_unknown_full_rows",
    "best_selected_rows",
    "best_known_exact_samples",
    "best_known_false_samples",
    "review_verdict",
    "next_probe",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "selector",
    "family",
    "source_pool",
    "source_ref",
    "transform",
    "guard_feature",
    "guard_value",
    "target_output_hex",
    "target_expected_hex",
    "target_full_rows",
    "known_exact_rows",
    "known_false_rows",
    "known_miss_rows",
    "unknown_full_rows",
    "selected_rows",
    "output_rows",
    "verdict",
    "target_samples",
    "known_exact_samples",
    "known_false_samples",
    "unknown_full_samples",
]

TARGET_FIELDNAMES = [
    "rank",
    "slot_rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "target_offset",
    "source_offset",
    "expected_byte",
    "predicted_byte",
    "best_selector",
    "best_guard_feature",
    "best_guard_value",
    "best_formula",
    "best_guard_family",
    "best_guard_key",
    "promotion_ready",
    "issues",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        return list(csv.DictReader(handle))


def context_id(context: token_review.PairContext) -> str:
    return token_review.context_id(context)


def feature_priority(feature: str) -> int:
    if feature == "control_prefix_bytes":
        return 0
    if feature == "fragment_bytes":
        return 1
    if feature == "segment_gap_bytes":
        return 2
    if feature == "run_value":
        return 3
    if feature.startswith("run_length"):
        return 4
    if feature.startswith("pair_offset_mod"):
        return 5
    if feature.startswith("cp_b"):
        return 20
    if feature.startswith("fr_b"):
        return 30
    if feature.startswith("seg_b"):
        return 40
    if feature.startswith("seg_pair_"):
        return 50
    if feature.startswith("seg_run_"):
        return 60
    return 100


def context_features(context: token_review.PairContext) -> dict[str, str]:
    segment = context.segment
    control_prefix = context.control_prefix
    fragment = context.fragment
    run_length = context.run_end - context.run_start
    features = {
        "control_prefix_bytes": str(len(control_prefix)),
        "fragment_bytes": str(len(fragment)),
        "segment_gap_bytes": str(len(segment)),
        "run_value": f"{context.run_value:02x}",
        "run_length_bucket": "ge12" if run_length >= 12 else "lt12",
        "pair_offset_mod2": str(context.pair_start % 2),
        "pair_offset_mod4": str(context.pair_start % 4),
        "pair_offset_mod8": str(context.pair_start % 8),
        "pair_offset_mod16": str(context.pair_start % 16),
    }
    for index, value in enumerate(control_prefix[:12]):
        features[f"cp_b{index:02d}"] = f"{value:02x}"
    for index, value in enumerate(fragment[:4]):
        features[f"fr_b{index:02d}"] = f"{value:02x}"
    for index, value in enumerate(segment[:32]):
        features[f"seg_b{index:02d}"] = f"{value:02x}"
    for relative in range(-8, 9):
        pair_index = context.pair_start + relative
        if 0 <= pair_index < len(segment):
            features[f"seg_pair_{relative:+d}"] = f"{segment[pair_index]:02x}"
        run_index = context.run_start + relative
        if 0 <= run_index < len(segment):
            features[f"seg_run_{relative:+d}"] = f"{segment[run_index]:02x}"
    return features


def target_context_setup(
    slots: Path,
    manifest: Path,
    base_fixtures: Path,
    min_run_length: int,
) -> tuple[tuple[str, str, str], list[token_review.PairContext], list[str]]:
    slot_rows = read_csv(slots)
    unknown_rows = token_review.unknown_source_rows(slot_rows)
    target_key_value, target_members = token_review.target_group(unknown_rows)
    target_offsets = sorted({int_value(row, "source_actual_offset", -1) for row in target_members})
    target_offsets = [offset for offset in target_offsets if offset >= 0]
    target_pair_start = min(target_offsets) if target_offsets else -1
    target_pair_len = len(target_offsets)
    contexts, issues = token_review.load_pair_contexts(
        manifest_rows=read_csv(manifest),
        base_rows=read_csv(base_fixtures),
        target_key_value=target_key_value,
        target_pair_start=target_pair_start,
        target_pair_len=target_pair_len,
        min_run_length=min_run_length,
    )
    return target_key_value, contexts, issues


def candidate_verdict(known_exact: int, known_false: int, target_full: int) -> str:
    if target_full <= 0:
        return "missing_target_full_match"
    if known_false:
        return "rejected_known_false"
    if known_exact >= 2:
        return "guarded_token_support"
    if known_exact == 1:
        return "weak_guarded_token_support"
    return "target_only_guard"


def evaluate_guard_splits(contexts: list[token_review.PairContext]) -> tuple[int, list[dict[str, str]]]:
    target_contexts = [context for context in contexts if context.is_target]
    if not target_contexts:
        return 0, []
    target_features = context_features(target_contexts[0])
    feature_by_context = {id(context): context_features(context) for context in contexts}
    rows: list[dict[str, str]] = []
    target_full_selector_rows = 0

    for spec in token_review.selector_specs():
        target_outputs = [token_review.selector_output(context, spec) for context in target_contexts]
        if any(output is None for output in target_outputs):
            continue
        if any(output != token_review.pair_bytes(context) for output, context in zip(target_outputs, target_contexts)):
            continue
        target_full_selector_rows += 1
        target_expected_hex = ";".join(token_review.pair_bytes(context).hex() for context in target_contexts)
        target_output_hex = ";".join(output.hex() for output in target_outputs if output is not None)

        for guard_feature, guard_value in target_features.items():
            selected_rows = 0
            output_rows = 0
            target_full = 0
            known_exact = 0
            known_false = 0
            known_miss = 0
            unknown_full = 0
            target_samples: list[str] = []
            exact_samples: list[str] = []
            false_samples: list[str] = []
            unknown_samples: list[str] = []

            for context in contexts:
                if feature_by_context[id(context)].get(guard_feature) != guard_value:
                    continue
                selected_rows += 1
                output = token_review.selector_output(context, spec)
                if output is None:
                    if token_review.pair_known(context):
                        known_miss += 1
                    continue
                output_rows += 1
                full = output == token_review.pair_bytes(context)
                if context.is_target:
                    if full:
                        target_full += 1
                        if len(target_samples) < 8:
                            target_samples.append(context_id(context))
                    continue
                if token_review.pair_known(context):
                    if full and token_review.pair_exact(context):
                        known_exact += 1
                        if len(exact_samples) < 8:
                            exact_samples.append(context_id(context))
                    else:
                        known_false += 1
                        if len(false_samples) < 8:
                            false_samples.append(context_id(context))
                elif full:
                    unknown_full += 1
                    if len(unknown_samples) < 8:
                        unknown_samples.append(context_id(context))

            verdict = candidate_verdict(known_exact, known_false, target_full)
            rows.append(
                {
                    "rank": "",
                    "selector": spec.label(),
                    "family": spec.family,
                    "source_pool": spec.source_pool,
                    "source_ref": str(spec.source_ref),
                    "transform": spec.transform,
                    "guard_feature": guard_feature,
                    "guard_value": guard_value,
                    "target_output_hex": target_output_hex,
                    "target_expected_hex": target_expected_hex,
                    "target_full_rows": str(target_full),
                    "known_exact_rows": str(known_exact),
                    "known_false_rows": str(known_false),
                    "known_miss_rows": str(known_miss),
                    "unknown_full_rows": str(unknown_full),
                    "selected_rows": str(selected_rows),
                    "output_rows": str(output_rows),
                    "verdict": verdict,
                    "target_samples": ";".join(target_samples),
                    "known_exact_samples": ";".join(exact_samples),
                    "known_false_samples": ";".join(false_samples),
                    "unknown_full_samples": ";".join(unknown_samples),
                }
            )

    rows.sort(
        key=lambda row: (
            row.get("verdict") != "guarded_token_support",
            row.get("verdict") != "weak_guarded_token_support",
            row.get("verdict") != "target_only_guard",
            int_value(row, "known_false_rows"),
            -int_value(row, "known_exact_rows"),
            -int_value(row, "target_full_rows"),
            feature_priority(row.get("guard_feature", "")),
            int_value(row, "selected_rows"),
            row.get("selector", ""),
        )
    )
    for rank, row in enumerate(rows, start=1):
        row["rank"] = str(rank)
    return target_full_selector_rows, rows


def best_candidate(rows: list[dict[str, str]]) -> dict[str, str]:
    return rows[0] if rows else {}


def build_target_rows(delta_targets: list[dict[str, str]], best: dict[str, str]) -> list[dict[str, str]]:
    promotion_ready = "1" if best.get("verdict") == "guarded_token_support" else "0"
    issue = "" if promotion_ready == "1" else (best.get("verdict") or "missing_guarded_compact_token_support")
    rows: list[dict[str, str]] = []
    for target in delta_targets:
        rows.append(
            {
                "rank": target.get("rank", str(len(rows) + 1)),
                "slot_rank": target.get("slot_rank", ""),
                "archive": target.get("archive", ""),
                "archive_tag": target.get("archive_tag", ""),
                "pcx_name": target.get("pcx_name", ""),
                "frontier_id": target.get("frontier_id", ""),
                "target_offset": target.get("target_offset", ""),
                "source_offset": target.get("source_offset", ""),
                "expected_byte": target.get("expected_byte", ""),
                "predicted_byte": target.get("expected_byte", ""),
                "best_selector": best.get("selector", ""),
                "best_guard_feature": best.get("guard_feature", ""),
                "best_guard_value": best.get("guard_value", ""),
                "best_formula": "guarded_compact_control_token_selector",
                "best_guard_family": best.get("family", ""),
                "best_guard_key": f"{best.get('guard_feature', '')}={best.get('guard_value', '')}",
                "promotion_ready": promotion_ready,
                "issues": issue,
            }
        )
    return rows


def build_summary(
    *,
    target_key_value: tuple[str, str, str],
    contexts: list[token_review.PairContext],
    target_full_selector_rows: int,
    candidates: list[dict[str, str]],
    targets: list[dict[str, str]],
    issue_rows: int,
) -> dict[str, str]:
    target_context = next((context for context in contexts if context.is_target), None)
    best = best_candidate(candidates)
    strong = [row for row in candidates if row.get("verdict") == "guarded_token_support"]
    weak = [row for row in candidates if row.get("verdict") == "weak_guarded_token_support"]
    target_only = [row for row in candidates if row.get("verdict") == "target_only_guard"]
    rejected = [row for row in candidates if row.get("verdict") == "rejected_known_false"]
    zero_false = [row for row in candidates if int_value(row, "known_false_rows") == 0]
    ready = sum(1 for row in targets if row.get("promotion_ready") == "1")

    if ready:
        verdict = "frontier80_tail_compact_token_guard_support_ready"
        next_probe = "promote guarded compact-control token selector for frontier80 offsets 16-17"
    elif weak:
        verdict = "frontier80_tail_compact_token_guard_weak_support"
        next_probe = (
            "seek second independent compact-control guard support for "
            f"{best.get('selector', 'frontier80 selector')}"
        )
    elif target_only:
        verdict = "frontier80_tail_compact_token_guard_target_only"
        next_probe = "expand guarded compact-control token evidence beyond target-only matches"
    else:
        verdict = "frontier80_tail_compact_token_guard_rejected"
        next_probe = "derive bit-level compact-control token selectors beyond simple guards"

    target_delta = token_review.pair_delta(target_context) if target_context else None
    return {
        "scope": "total",
        "candidate_mode": "old_clean_byte_union_frontier80_tail_compact_token_guard_split_review",
        "target_key": "|".join(target_key_value),
        "target_pair_offset": str(target_context.pair_start) if target_context else "",
        "target_pair_hex": token_review.pair_bytes(target_context).hex() if target_context else "",
        "target_run_value": f"{target_context.run_value:02x}" if target_context else "",
        "target_delta": "" if target_delta is None else str(target_delta),
        "selector_rows": str(len(token_review.selector_specs())),
        "target_full_selector_rows": str(target_full_selector_rows),
        "guard_candidate_rows": str(len(candidates)),
        "zero_false_guard_rows": str(len(zero_false)),
        "strong_guard_rows": str(len(strong)),
        "weak_guard_rows": str(len(weak)),
        "target_only_guard_rows": str(len(target_only)),
        "rejected_guard_rows": str(len(rejected)),
        "best_selector": best.get("selector", ""),
        "best_family": best.get("family", ""),
        "best_guard_feature": best.get("guard_feature", ""),
        "best_guard_value": best.get("guard_value", ""),
        "best_target_output_hex": best.get("target_output_hex", ""),
        "best_known_exact_rows": best.get("known_exact_rows", "0"),
        "best_known_false_rows": best.get("known_false_rows", "0"),
        "best_known_miss_rows": best.get("known_miss_rows", "0"),
        "best_target_full_rows": best.get("target_full_rows", "0"),
        "best_unknown_full_rows": best.get("unknown_full_rows", "0"),
        "best_selected_rows": best.get("selected_rows", "0"),
        "best_known_exact_samples": best.get("known_exact_samples", ""),
        "best_known_false_samples": best.get("known_false_samples", ""),
        "review_verdict": verdict,
        "next_probe": next_probe,
        "promotion_candidate_bytes": str(len(targets)),
        "promotion_ready_bytes": str(ready),
        "issue_rows": str(issue_rows),
    }


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 160) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    candidates: list[dict[str, str]],
    targets: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "candidates": candidates, "targets": targets}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
            ("targets.csv", output_dir / "targets.csv"),
        )
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 24px; background: #f6f7f8; color: #202529; }}
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; margin: 18px 0; }}
    .stat {{ background: white; border: 1px solid #d5dbe0; padding: 10px; }}
    .label {{ color: #68737d; font-size: 12px; }}
    .value {{ font-size: 20px; font-weight: 750; overflow-wrap: anywhere; }}
    table {{ border-collapse: collapse; width: 100%; background: white; margin: 18px 0; }}
    th, td {{ border: 1px solid #d5dbe0; padding: 6px 8px; font-size: 13px; text-align: left; vertical-align: top; }}
    th {{ background: #e9edf0; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <p>{links}</p>
  <div class="stats">
    <div class="stat"><div class="label">Verdict</div><div class="value">{html.escape(summary['review_verdict'])}</div></div>
    <div class="stat"><div class="label">Best selector</div><div class="value">{html.escape(summary['best_selector'])}</div></div>
    <div class="stat"><div class="label">Best guard</div><div class="value">{html.escape(summary['best_guard_feature'])}={html.escape(summary['best_guard_value'])}</div></div>
    <div class="stat"><div class="label">Known exact/false</div><div class="value">{html.escape(summary['best_known_exact_rows'])}/{html.escape(summary['best_known_false_rows'])}</div></div>
  </div>
  <h2>Targets</h2>
  {render_table(targets, TARGET_FIELDNAMES)}
  <h2>Guarded Selectors</h2>
  {render_table(candidates, CANDIDATE_FIELDNAMES)}
  <script type="application/json" id="payload">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("--base-fixtures", type=Path, default=DEFAULT_BASE_FIXTURES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--delta-targets", type=Path, default=DEFAULT_DELTA_TARGETS)
    parser.add_argument("--min-run-length", type=int, default=4)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Frontier80 Tail Compact Token Guard Split Review")
    args = parser.parse_args()

    target_key_value, contexts, issues = target_context_setup(
        args.slots,
        args.manifest,
        args.base_fixtures,
        args.min_run_length,
    )
    target_full_selector_rows, candidates = evaluate_guard_splits(contexts)
    targets = build_target_rows(read_csv(args.delta_targets), best_candidate(candidates))
    summary = build_summary(
        target_key_value=target_key_value,
        contexts=contexts,
        target_full_selector_rows=target_full_selector_rows,
        candidates=candidates,
        targets=targets,
        issue_rows=len(issues),
    )

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, targets)
    (args.output / "index.html").write_text(
        build_html(summary, candidates, targets, args.output, args.title),
        encoding="utf-8",
    )

    print(
        "Frontier80 compact token guard split review: "
        f"verdict={summary['review_verdict']} "
        f"best={summary['best_selector']} "
        f"guard={summary['best_guard_feature']}={summary['best_guard_value']} "
        f"known={summary['best_known_exact_rows']}/{summary['best_known_false_rows']} "
        f"promotion_ready={summary['promotion_ready_bytes']}"
    )
    print(f"HTML: {args.output / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
