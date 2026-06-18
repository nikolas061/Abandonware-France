#!/usr/bin/env python3
"""Review transfer guards for the frontier80 compact-token high2 selector."""

from __future__ import annotations

import argparse
import csv
import html
import itertools
import json
from dataclasses import dataclass
from pathlib import Path

import lolg_tex_old_clean_byte_union_frontier80_tail_compact_token_guard_split_review as guard_review
import lolg_tex_old_clean_byte_union_frontier80_tail_compact_token_independent_support_review as support_review
import lolg_tex_old_clean_byte_union_frontier80_tail_compact_token_review as token_review
from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value


DEFAULT_SLOTS = support_review.DEFAULT_SLOTS
DEFAULT_BASE_FIXTURES = support_review.DEFAULT_BASE_FIXTURES
DEFAULT_MANIFEST = support_review.DEFAULT_MANIFEST
DEFAULT_DELTA_TARGETS = support_review.DEFAULT_DELTA_TARGETS
DEFAULT_OUTPUT = Path("output/tex_old_clean_byte_union_frontier80_tail_compact_token_transfer_guard_review")

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_key",
    "target_pair_offset",
    "target_pair_hex",
    "target_run_value",
    "target_delta",
    "selector",
    "candidate_rows",
    "ready_guard_rows",
    "zero_false_guard_rows",
    "best_guard_key",
    "best_guard_width",
    "best_target_full_rows",
    "best_known_exact_rows",
    "best_known_false_rows",
    "best_compact_exact_rows",
    "best_cross_rule_exact_rows",
    "best_unknown_full_rows",
    "best_selected_rows",
    "best_known_exact_samples",
    "best_known_false_samples",
    "review_verdict",
    "next_probe",
    "transfer_candidate_bytes",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "guard_width",
    "guard_key",
    "guard_features",
    "guard_values",
    "target_full_rows",
    "known_exact_rows",
    "known_false_rows",
    "compact_exact_rows",
    "cross_rule_exact_rows",
    "unknown_full_rows",
    "selected_rows",
    "output_rows",
    "verdict",
    "target_samples",
    "compact_exact_samples",
    "cross_rule_exact_samples",
    "known_exact_samples",
    "known_false_samples",
    "unknown_full_samples",
]

SELECTED_FIELDNAMES = [
    "rank",
    "sample_class",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "rule_type",
    "guard_key",
    "control_prefix_bytes",
    "fragment_bytes",
    "segment_gap_bytes",
    "pair_offset",
    "pair_hex",
    "run_start",
    "run_end",
    "run_length",
    "run_value",
    "source_index",
    "source_byte",
    "source_high2",
    "source_low2",
    "predicted_pair_hex",
    "full_match",
    "pair_known",
    "known_pair_bits",
    "decoded_pair_hex",
    "known_exact",
    "known_false",
    "is_target",
    "issues",
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
    "best_formula",
    "best_guard_family",
    "best_guard_key",
    "transfer_ready",
    "promotion_ready",
    "issues",
]


@dataclass(frozen=True)
class PairEvaluation:
    context: token_review.PairContext
    manifest: dict[str, str]
    features: dict[str, str]
    source_index: int
    source_byte: int
    predicted_pair: bytes
    full_match: bool
    pair_known: bool
    known_exact: bool
    known_false: bool


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        return list(csv.DictReader(handle))


def fixture_key(context: token_review.PairContext) -> tuple[str, str, str]:
    return token_review.fixture_key(context.row)


def selector_label() -> str:
    return "run_value+high2(segment[pair_offset-8])"


def guard_key(atoms: tuple[tuple[str, str], ...]) -> str:
    return ";".join(f"{feature}={value}" for feature, value in atoms)


def sample_id(pair: PairEvaluation) -> str:
    return token_review.context_id(pair.context)


def context_features(context: token_review.PairContext, source_index: int, source_byte: int) -> dict[str, str]:
    features = dict(guard_review.context_features(context))
    run_length = context.run_end - context.run_start
    features.update(
        {
            "pair_offset_bucket64": f"{context.pair_start // 64}",
            "pair_offset_lt64": "1" if context.pair_start < 64 else "0",
            "pair_offset_lt128": "1" if context.pair_start < 128 else "0",
            "source_index_mod2": str(source_index % 2),
            "source_index_mod4": str(source_index % 4),
            "source_index_mod8": str(source_index % 8),
            "source_index_mod16": str(source_index % 16),
            "source_byte": f"{source_byte:02x}",
            "source_high2": str(source_byte >> 6),
            "source_low2": str(source_byte & 0x03),
            "source_high_nibble": f"{source_byte >> 4:x}",
            "source_low_nibble": f"{source_byte & 0x0F:x}",
            "run_length_exact": str(run_length),
            "run_length_mod2": str(run_length % 2),
            "run_length_mod4": str(run_length % 4),
            "run_length_4_to_14": "1" if 4 <= run_length <= 14 else "0",
        }
    )
    for relative in range(-8, 9):
        index = source_index + relative
        if 0 <= index < len(context.segment):
            value = context.segment[index]
            features[f"src_{relative:+d}"] = f"{value:02x}"
            features[f"src_{relative:+d}_high2"] = str(value >> 6)
            features[f"src_{relative:+d}_low2"] = str(value & 0x03)
            features[f"src_{relative:+d}_high_nibble"] = f"{value >> 4:x}"
            features[f"src_{relative:+d}_low_nibble"] = f"{value & 0x0F:x}"
    return features


def evaluate_pairs(
    contexts: list[token_review.PairContext],
    manifests: dict[tuple[str, str, str], dict[str, str]],
) -> list[PairEvaluation]:
    pairs: list[PairEvaluation] = []
    for context in contexts:
        prediction = support_review.selector_prediction(context)
        if prediction is None:
            continue
        source_index, source_byte, predicted_pair = prediction
        pair = token_review.pair_bytes(context)
        full_match = predicted_pair == pair
        pair_known = token_review.pair_known(context)
        known_exact = pair_known and full_match and token_review.pair_exact(context)
        known_false = pair_known and not known_exact
        if not (context.is_target or full_match or pair_known):
            continue
        pairs.append(
            PairEvaluation(
                context=context,
                manifest=manifests.get(fixture_key(context), {}),
                features=context_features(context, source_index, source_byte),
                source_index=source_index,
                source_byte=source_byte,
                predicted_pair=predicted_pair,
                full_match=full_match,
                pair_known=pair_known,
                known_exact=known_exact,
                known_false=known_false,
            )
        )
    return pairs


def feature_priority(feature: str) -> int:
    if feature.startswith("source_"):
        return 45
    if feature.startswith("src_"):
        return 55
    if feature.startswith("pair_offset_"):
        return 58
    return guard_review.feature_priority(feature)


def verdict_for(
    *,
    target_full: int,
    known_false: int,
    compact_exact: int,
    cross_rule_exact: int,
    known_exact: int,
) -> str:
    if target_full <= 0:
        return "missing_target_full_match"
    if known_false:
        return "rejected_known_false"
    if compact_exact and cross_rule_exact:
        return "transfer_guard_support"
    if compact_exact:
        return "compact_only_guard"
    if cross_rule_exact:
        return "cross_rule_only_guard"
    if known_exact:
        return "known_exact_without_required_family"
    return "target_only_guard"


def sample_join(pairs: list[PairEvaluation], limit: int = 8) -> str:
    return ";".join(sample_id(pair) for pair in pairs[:limit])


def candidate_row(atoms: tuple[tuple[str, str], ...], pairs: list[PairEvaluation]) -> dict[str, str]:
    selected = [
        pair
        for pair in pairs
        if all(pair.features.get(feature) == value for feature, value in atoms)
    ]
    target_pairs = [pair for pair in selected if pair.context.is_target and pair.full_match]
    exact_pairs = [pair for pair in selected if pair.known_exact and not pair.context.is_target]
    false_pairs = [pair for pair in selected if pair.known_false]
    compact_exact = [
        pair for pair in exact_pairs if pair.manifest.get("rule_type") == "compact_control_stream"
    ]
    cross_rule_exact = [
        pair for pair in exact_pairs if pair.manifest.get("rule_type") != "compact_control_stream"
    ]
    unknown_full = [
        pair
        for pair in selected
        if pair.full_match and not pair.pair_known and not pair.context.is_target
    ]
    verdict = verdict_for(
        target_full=len(target_pairs),
        known_false=len(false_pairs),
        compact_exact=len(compact_exact),
        cross_rule_exact=len(cross_rule_exact),
        known_exact=len(exact_pairs),
    )
    return {
        "rank": "",
        "guard_width": str(len(atoms)),
        "guard_key": guard_key(atoms),
        "guard_features": ";".join(feature for feature, _value in atoms),
        "guard_values": ";".join(value for _feature, value in atoms),
        "target_full_rows": str(len(target_pairs)),
        "known_exact_rows": str(len(exact_pairs)),
        "known_false_rows": str(len(false_pairs)),
        "compact_exact_rows": str(len(compact_exact)),
        "cross_rule_exact_rows": str(len(cross_rule_exact)),
        "unknown_full_rows": str(len(unknown_full)),
        "selected_rows": str(len(selected)),
        "output_rows": str(len(selected)),
        "verdict": verdict,
        "target_samples": sample_join(target_pairs),
        "compact_exact_samples": sample_join(compact_exact),
        "cross_rule_exact_samples": sample_join(cross_rule_exact),
        "known_exact_samples": sample_join(exact_pairs),
        "known_false_samples": sample_join(false_pairs),
        "unknown_full_samples": sample_join(unknown_full),
    }


def candidate_sort_key(row: dict[str, str]) -> tuple[object, ...]:
    verdict_rank = {
        "transfer_guard_support": 0,
        "compact_only_guard": 1,
        "cross_rule_only_guard": 2,
        "known_exact_without_required_family": 3,
        "target_only_guard": 4,
        "rejected_known_false": 5,
        "missing_target_full_match": 6,
    }.get(row.get("verdict", ""), 9)
    features = row.get("guard_features", "").split(";") if row.get("guard_features") else []
    feature_score = sum(feature_priority(feature) for feature in features)
    return (
        verdict_rank,
        int_value(row, "known_false_rows"),
        -int_value(row, "known_exact_rows"),
        -int_value(row, "cross_rule_exact_rows"),
        -int_value(row, "compact_exact_rows"),
        int_value(row, "selected_rows"),
        int_value(row, "guard_width"),
        feature_score,
        row.get("guard_key", ""),
    )


def build_candidates(pairs: list[PairEvaluation], target: PairEvaluation, max_guard_width: int) -> list[dict[str, str]]:
    target_features = {
        feature: value
        for feature, value in target.features.items()
        if value != "" and not feature.startswith("seg_run_")
    }
    feature_names = sorted(target_features, key=lambda feature: (feature_priority(feature), feature))
    rows: list[dict[str, str]] = []
    for width in range(1, max_guard_width + 1):
        for features in itertools.combinations(feature_names, width):
            atoms = tuple((feature, target_features[feature]) for feature in features)
            row = candidate_row(atoms, pairs)
            if (
                int_value(row, "target_full_rows") > 0
                and (
                    int_value(row, "known_exact_rows") > 0
                    or int_value(row, "known_false_rows") > 0
                    or int_value(row, "unknown_full_rows") > 0
                )
            ):
                rows.append(row)
    rows.sort(key=candidate_sort_key)
    for rank, row in enumerate(rows, start=1):
        row["rank"] = str(rank)
    return rows


def selected_rows(best: dict[str, str], pairs: list[PairEvaluation]) -> list[dict[str, str]]:
    atoms = []
    for atom in best.get("guard_key", "").split(";"):
        if not atom or "=" not in atom:
            continue
        feature, value = atom.split("=", 1)
        atoms.append((feature, value))
    rows: list[dict[str, str]] = []
    for pair in pairs:
        if not all(pair.features.get(feature) == value for feature, value in atoms):
            continue
        context = pair.context
        rule_type = pair.manifest.get("rule_type", "")
        sample_class = "target"
        if not context.is_target:
            if pair.known_exact and rule_type == "compact_control_stream":
                sample_class = "compact_exact"
            elif pair.known_exact:
                sample_class = "cross_rule_exact"
            elif pair.known_false:
                sample_class = "known_false"
            elif pair.full_match:
                sample_class = "unknown_full"
            else:
                sample_class = "selected"
        rows.append(
            {
                "rank": "",
                "sample_class": sample_class,
                "archive": context.row.get("archive", ""),
                "archive_tag": context.row.get("archive_tag", ""),
                "pcx_name": context.row.get("pcx_name", ""),
                "frontier_id": context.row.get("frontier_id", ""),
                "rule_type": rule_type,
                "guard_key": best.get("guard_key", ""),
                "control_prefix_bytes": str(len(context.control_prefix)),
                "fragment_bytes": str(len(context.fragment)),
                "segment_gap_bytes": str(len(context.segment)),
                "pair_offset": str(context.pair_start),
                "pair_hex": token_review.pair_bytes(context).hex(),
                "run_start": str(context.run_start),
                "run_end": str(context.run_end),
                "run_length": str(context.run_end - context.run_start),
                "run_value": f"{context.run_value:02x}",
                "source_index": str(pair.source_index),
                "source_byte": f"{pair.source_byte:02x}",
                "source_high2": str(pair.source_byte >> 6),
                "source_low2": str(pair.source_byte & 0x03),
                "predicted_pair_hex": pair.predicted_pair.hex(),
                "full_match": "1" if pair.full_match else "0",
                "pair_known": "1" if pair.pair_known else "0",
                "known_pair_bits": token_review.mask_bits(
                    context.known_mask,
                    context.pair_start,
                    context.run_start,
                ),
                "decoded_pair_hex": context.decoded[context.pair_start : context.run_start].hex(),
                "known_exact": "1" if pair.known_exact else "0",
                "known_false": "1" if pair.known_false else "0",
                "is_target": "1" if context.is_target else "0",
                "issues": "",
            }
        )
    rows.sort(
        key=lambda row: (
            row.get("sample_class") != "target",
            row.get("sample_class") != "compact_exact",
            row.get("sample_class") != "cross_rule_exact",
            row.get("sample_class") != "unknown_full",
            int_value(row, "frontier_id"),
            int_value(row, "pair_offset"),
        )
    )
    for rank, row in enumerate(rows, start=1):
        row["rank"] = str(rank)
    return rows


def build_target_rows(
    delta_targets: list[dict[str, str]],
    summary: dict[str, str],
    target: PairEvaluation,
) -> list[dict[str, str]]:
    transfer_ready = "1" if summary.get("review_verdict") == "frontier80_tail_compact_token_transfer_guard_ready" else "0"
    issue = summary.get("next_probe", "") if summary.get("promotion_ready_bytes") == "0" else ""
    rows: list[dict[str, str]] = []
    for target_row in delta_targets:
        source_offset = int_value(target_row, "source_offset", target.context.pair_start)
        predicted_index = max(0, min(source_offset - target.context.pair_start, len(target.predicted_pair) - 1))
        rows.append(
            {
                "rank": target_row.get("rank", str(len(rows) + 1)),
                "slot_rank": target_row.get("slot_rank", ""),
                "archive": target_row.get("archive", ""),
                "archive_tag": target_row.get("archive_tag", ""),
                "pcx_name": target_row.get("pcx_name", ""),
                "frontier_id": target_row.get("frontier_id", ""),
                "target_offset": target_row.get("target_offset", ""),
                "source_offset": target_row.get("source_offset", ""),
                "expected_byte": target_row.get("expected_byte", ""),
                "predicted_byte": f"{target.predicted_pair[predicted_index]:02x}",
                "best_selector": selector_label(),
                "best_formula": "run_value+high2(segment[pair_offset-8])",
                "best_guard_family": "compact_token_transfer_guard",
                "best_guard_key": summary.get("best_guard_key", ""),
                "transfer_ready": transfer_ready,
                "promotion_ready": "0",
                "issues": issue,
            }
        )
    return rows


def build_summary(
    *,
    target_key_value: tuple[str, str, str],
    target: PairEvaluation,
    candidates: list[dict[str, str]],
    issue_rows: int,
) -> dict[str, str]:
    best = candidates[0] if candidates else {}
    ready = [row for row in candidates if row.get("verdict") == "transfer_guard_support"]
    zero_false = [row for row in candidates if int_value(row, "known_false_rows") == 0]
    if ready:
        verdict = "frontier80_tail_compact_token_transfer_guard_ready"
        next_probe = "validate guarded high2 selector with compact-control replay before promotion"
    elif any(row.get("verdict") == "compact_only_guard" for row in candidates):
        verdict = "frontier80_tail_compact_token_transfer_guard_compact_only"
        next_probe = "seek cross-rule transfer evidence that matches the compact-control guard"
    elif any(row.get("verdict") == "cross_rule_only_guard" for row in candidates):
        verdict = "frontier80_tail_compact_token_transfer_guard_cross_rule_only"
        next_probe = "seek compact-control support that matches the cross-rule transfer guard"
    else:
        verdict = "frontier80_tail_compact_token_transfer_guard_rejected"
        next_probe = "derive alternate compact-control token transfer beyond high2 local guards"
    target_delta = token_review.pair_delta(target.context)
    return {
        "scope": "total",
        "candidate_mode": "old_clean_byte_union_frontier80_tail_compact_token_transfer_guard_review",
        "target_key": "|".join(target_key_value),
        "target_pair_offset": str(target.context.pair_start),
        "target_pair_hex": token_review.pair_bytes(target.context).hex(),
        "target_run_value": f"{target.context.run_value:02x}",
        "target_delta": "" if target_delta is None else str(target_delta),
        "selector": selector_label(),
        "candidate_rows": str(len(candidates)),
        "ready_guard_rows": str(len(ready)),
        "zero_false_guard_rows": str(len(zero_false)),
        "best_guard_key": best.get("guard_key", ""),
        "best_guard_width": best.get("guard_width", "0"),
        "best_target_full_rows": best.get("target_full_rows", "0"),
        "best_known_exact_rows": best.get("known_exact_rows", "0"),
        "best_known_false_rows": best.get("known_false_rows", "0"),
        "best_compact_exact_rows": best.get("compact_exact_rows", "0"),
        "best_cross_rule_exact_rows": best.get("cross_rule_exact_rows", "0"),
        "best_unknown_full_rows": best.get("unknown_full_rows", "0"),
        "best_selected_rows": best.get("selected_rows", "0"),
        "best_known_exact_samples": best.get("known_exact_samples", ""),
        "best_known_false_samples": best.get("known_false_samples", ""),
        "review_verdict": verdict,
        "next_probe": next_probe,
        "transfer_candidate_bytes": str(target.context.pair_len if ready else 0),
        "promotion_candidate_bytes": str(target.context.pair_len),
        "promotion_ready_bytes": "0",
        "issue_rows": str(issue_rows),
    }


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 180) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    candidates: list[dict[str, str]],
    selected: list[dict[str, str]],
    targets: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "candidates": candidates, "selected": selected, "targets": targets}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
            ("selected_pairs.csv", output_dir / "selected_pairs.csv"),
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
    <div class="stat"><div class="label">Best guard</div><div class="value">{html.escape(summary['best_guard_key'])}</div></div>
    <div class="stat"><div class="label">Best exact/false</div><div class="value">{html.escape(summary['best_known_exact_rows'])}/{html.escape(summary['best_known_false_rows'])}</div></div>
    <div class="stat"><div class="label">Compact/Cross exact</div><div class="value">{html.escape(summary['best_compact_exact_rows'])}/{html.escape(summary['best_cross_rule_exact_rows'])}</div></div>
  </div>
  <h2>Targets</h2>
  {render_table(targets, TARGET_FIELDNAMES)}
  <h2>Best Selected Pairs</h2>
  {render_table(selected, SELECTED_FIELDNAMES)}
  <h2>Candidates</h2>
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
    parser.add_argument("--max-guard-width", type=int, default=2)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--title", default="Lands of Lore II .tex Frontier80 Tail Compact Token Transfer Guard Review")
    args = parser.parse_args()

    target_key_value, contexts, manifests, issues = support_review.target_setup(
        args.slots,
        args.manifest,
        args.base_fixtures,
        args.min_run_length,
    )
    pairs = evaluate_pairs(contexts, manifests)
    target = next((pair for pair in pairs if pair.context.is_target), None)
    if target is None:
        raise SystemExit("missing target pair evaluation")

    candidates = build_candidates(pairs, target, max(1, args.max_guard_width))
    summary = build_summary(
        target_key_value=target_key_value,
        target=target,
        candidates=candidates,
        issue_rows=len(issues),
    )
    selected = selected_rows(candidates[0] if candidates else {}, pairs)
    targets = build_target_rows(read_csv(args.delta_targets), summary, target)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(args.output / "selected_pairs.csv", SELECTED_FIELDNAMES, selected)
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, targets)
    (args.output / "index.html").write_text(
        build_html(summary, candidates, selected, targets, args.output, args.title),
        encoding="utf-8",
    )

    print(
        "Frontier80 compact token transfer guard review: "
        f"verdict={summary['review_verdict']} "
        f"best={summary['best_guard_key']} "
        f"known={summary['best_known_exact_rows']}/{summary['best_known_false_rows']} "
        f"compact_cross={summary['best_compact_exact_rows']}/{summary['best_cross_rule_exact_rows']} "
        f"promotion_ready={summary['promotion_ready_bytes']}"
    )
    print(f"HTML: {args.output / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
