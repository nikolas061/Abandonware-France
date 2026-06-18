#!/usr/bin/env python3
"""Review independent support for the frontier80 compact-token high2 selector."""

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
DEFAULT_OUTPUT = Path("output/tex_old_clean_byte_union_frontier80_tail_compact_token_independent_support_review")

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_key",
    "target_pair_offset",
    "target_pair_hex",
    "target_run_value",
    "target_delta",
    "selector",
    "pair_rows",
    "full_rows",
    "known_pair_rows",
    "known_exact_rows",
    "known_false_rows",
    "compact_pair_rows",
    "compact_known_exact_rows",
    "compact_known_false_rows",
    "target_guard_pair_rows",
    "target_guard_full_rows",
    "target_guard_known_exact_rows",
    "target_guard_known_false_rows",
    "cross_rule_known_exact_rows",
    "cross_rule_known_false_rows",
    "cross_rule_rule_types",
    "best_independent_support",
    "best_compact_support",
    "review_verdict",
    "next_probe",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

PAIR_FIELDNAMES = [
    "rank",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "rule_type",
    "control_prefix_bytes",
    "fragment_bytes",
    "segment_gap_bytes",
    "pair_offset",
    "pair_hex",
    "run_start",
    "run_end",
    "run_length",
    "run_value",
    "delta",
    "source_index",
    "source_byte",
    "source_high2",
    "predicted_pair_hex",
    "full_match",
    "known_pair_bits",
    "decoded_pair_hex",
    "known_exact",
    "known_false",
    "target_guard_match",
    "is_target",
    "support_class",
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
    "promotion_ready",
    "issues",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        return list(csv.DictReader(handle))


def load_contexts_all_rules(
    *,
    manifest_rows: list[dict[str, str]],
    base_rows: list[dict[str, str]],
    target_key_value: tuple[str, str, str],
    target_pair_start: int,
    target_pair_len: int,
    min_run_length: int,
) -> tuple[list[token_review.PairContext], dict[tuple[str, str, str], dict[str, str]], list[str]]:
    manifests = {token_review.fixture_key(row): row for row in manifest_rows}
    contexts: list[token_review.PairContext] = []
    issues: list[str] = []
    for base_row in base_rows:
        key = token_review.fixture_key(base_row)
        manifest = manifests.get(key, {})
        local_issues: list[str] = []
        expected = token_review.load_bytes(manifest.get("expected_gap_path", ""), local_issues, "expected")
        decoded = token_review.load_bytes(base_row.get("decoded_path", ""), local_issues, "decoded")
        known_mask = token_review.load_bytes(base_row.get("known_mask_path", ""), local_issues, "known_mask")
        segment = token_review.load_bytes(manifest.get("segment_gap_path", ""), local_issues, "segment")
        control_prefix = token_review.load_bytes(manifest.get("control_prefix_path", ""), local_issues, "control_prefix")
        fragment = token_review.load_bytes(manifest.get("fragment_path", ""), local_issues, "fragment")
        if local_issues:
            issues.extend(f"{'|'.join(key)}:{issue}" for issue in local_issues)
        if not expected or not decoded or not known_mask or not segment:
            continue
        for run_start, run_end, run_value in token_review.byte_runs(expected):
            run_length = run_end - run_start
            if run_length < min_run_length or run_start < target_pair_len:
                continue
            pair_start = run_start - target_pair_len
            pair = expected[pair_start:run_start]
            if len(pair) != target_pair_len or len(set(pair)) != 1:
                continue
            contexts.append(
                token_review.PairContext(
                    row=base_row,
                    expected=expected,
                    decoded=decoded,
                    known_mask=known_mask,
                    segment=segment,
                    control_prefix=control_prefix,
                    fragment=fragment,
                    pair_start=pair_start,
                    pair_len=target_pair_len,
                    run_start=run_start,
                    run_end=run_end,
                    run_value=run_value,
                    is_target=key == target_key_value and pair_start == target_pair_start,
                    issues=tuple(local_issues),
                )
            )
    return contexts, manifests, issues


def target_setup(
    slots: Path,
    manifest: Path,
    base_fixtures: Path,
    min_run_length: int,
) -> tuple[tuple[str, str, str], list[token_review.PairContext], dict[tuple[str, str, str], dict[str, str]], list[str]]:
    slot_rows = read_csv(slots)
    unknown_rows = token_review.unknown_source_rows(slot_rows)
    target_key_value, target_members = token_review.target_group(unknown_rows)
    target_offsets = sorted({int_value(row, "source_actual_offset", -1) for row in target_members})
    target_offsets = [offset for offset in target_offsets if offset >= 0]
    target_pair_start = min(target_offsets) if target_offsets else -1
    target_pair_len = len(target_offsets)
    contexts, manifests, issues = load_contexts_all_rules(
        manifest_rows=read_csv(manifest),
        base_rows=read_csv(base_fixtures),
        target_key_value=target_key_value,
        target_pair_start=target_pair_start,
        target_pair_len=target_pair_len,
        min_run_length=min_run_length,
    )
    return target_key_value, contexts, manifests, issues


def selector_prediction(context: token_review.PairContext) -> tuple[int, int, bytes] | None:
    source_index = context.pair_start - 8
    if source_index < 0 or source_index >= len(context.segment):
        return None
    source_byte = context.segment[source_index]
    predicted = (context.run_value + (source_byte >> 6)) & 0xFF
    return source_index, source_byte, bytes([predicted] * context.pair_len)


def target_guard(context: token_review.PairContext, target: token_review.PairContext) -> bool:
    return (
        len(context.control_prefix) == len(target.control_prefix)
        and len(context.fragment) == len(target.fragment)
        and len(context.segment) == len(target.segment)
    )


def support_class(
    *,
    context: token_review.PairContext,
    manifest: dict[str, str],
    target: token_review.PairContext,
    full_match: bool,
    known_exact: bool,
    known_false: bool,
) -> str:
    if context.is_target:
        return "target"
    if known_exact and manifest.get("rule_type") == "compact_control_stream" and target_guard(context, target):
        return "compact_target_guard_known_exact"
    if known_exact and manifest.get("rule_type") == "compact_control_stream":
        return "compact_known_exact"
    if known_exact:
        return "cross_rule_known_exact"
    if known_false and manifest.get("rule_type") == "compact_control_stream":
        return "compact_known_false"
    if known_false:
        return "cross_rule_known_false"
    if full_match and target_guard(context, target):
        return "target_guard_unknown_full"
    if full_match:
        return "unknown_full"
    return "candidate"


def build_pair_rows(
    contexts: list[token_review.PairContext],
    manifests: dict[tuple[str, str, str], dict[str, str]],
    target: token_review.PairContext,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for context in contexts:
        prediction = selector_prediction(context)
        if prediction is None:
            continue
        source_index, source_byte, predicted_pair = prediction
        pair = token_review.pair_bytes(context)
        full_match = predicted_pair == pair
        known = token_review.pair_known(context)
        exact = known and full_match and token_review.pair_exact(context)
        false = known and not full_match
        if not (full_match or known):
            continue
        manifest = manifests.get(token_review.fixture_key(context.row), {})
        delta = token_review.pair_delta(context)
        rows.append(
            {
                "rank": "",
                "archive": context.row.get("archive", ""),
                "archive_tag": context.row.get("archive_tag", ""),
                "pcx_name": context.row.get("pcx_name", ""),
                "frontier_id": context.row.get("frontier_id", ""),
                "rule_type": manifest.get("rule_type", ""),
                "control_prefix_bytes": str(len(context.control_prefix)),
                "fragment_bytes": str(len(context.fragment)),
                "segment_gap_bytes": str(len(context.segment)),
                "pair_offset": str(context.pair_start),
                "pair_hex": pair.hex(),
                "run_start": str(context.run_start),
                "run_end": str(context.run_end),
                "run_length": str(context.run_end - context.run_start),
                "run_value": f"{context.run_value:02x}",
                "delta": "" if delta is None else str(delta),
                "source_index": str(source_index),
                "source_byte": f"{source_byte:02x}",
                "source_high2": str(source_byte >> 6),
                "predicted_pair_hex": predicted_pair.hex(),
                "full_match": "1" if full_match else "0",
                "known_pair_bits": token_review.mask_bits(context.known_mask, context.pair_start, context.run_start),
                "decoded_pair_hex": context.decoded[context.pair_start : context.run_start].hex(),
                "known_exact": "1" if exact else "0",
                "known_false": "1" if false else "0",
                "target_guard_match": "1" if target_guard(context, target) else "0",
                "is_target": "1" if context.is_target else "0",
                "support_class": support_class(
                    context=context,
                    manifest=manifest,
                    target=target,
                    full_match=full_match,
                    known_exact=exact,
                    known_false=false,
                ),
                "issues": "",
            }
        )
    rows.sort(
        key=lambda row: (
            row.get("is_target") != "1",
            row.get("known_exact") != "1",
            row.get("target_guard_match") != "1",
            row.get("support_class", ""),
            row.get("rule_type", ""),
            row.get("pcx_name", ""),
            int_value(row, "frontier_id"),
            int_value(row, "pair_offset"),
        )
    )
    for rank, row in enumerate(rows, start=1):
        row["rank"] = str(rank)
    return rows


def join_rule_types(rows: list[dict[str, str]]) -> str:
    return ";".join(sorted({row.get("rule_type", "") for row in rows if row.get("rule_type", "")}))


def first_sample(rows: list[dict[str, str]]) -> str:
    if not rows:
        return ""
    row = rows[0]
    return f"{row.get('pcx_name', '')}:{row.get('frontier_id', '')}:{row.get('pair_offset', '')}"


def build_target_rows(delta_targets: list[dict[str, str]], summary_seed: dict[str, str]) -> list[dict[str, str]]:
    promotion_ready = "1" if summary_seed.get("promotion_ready_bytes") not in {"", "0"} else "0"
    issue = "" if promotion_ready == "1" else summary_seed.get("review_verdict", "missing_independent_compact_support")
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
                "best_selector": summary_seed.get("selector", ""),
                "best_formula": "run_value+high2(segment[pair_offset-8])",
                "best_guard_family": "compact_token_independent_support",
                "best_guard_key": summary_seed.get("review_verdict", ""),
                "promotion_ready": promotion_ready,
                "issues": issue,
            }
        )
    return rows


def build_summary(
    *,
    target_key_value: tuple[str, str, str],
    target: token_review.PairContext,
    pair_rows: list[dict[str, str]],
    issue_rows: int,
) -> dict[str, str]:
    exact_rows = [row for row in pair_rows if row.get("known_exact") == "1"]
    false_rows = [row for row in pair_rows if row.get("known_false") == "1"]
    compact_rows = [row for row in pair_rows if row.get("rule_type") == "compact_control_stream"]
    compact_exact = [row for row in compact_rows if row.get("known_exact") == "1"]
    compact_false = [row for row in compact_rows if row.get("known_false") == "1"]
    target_guard_rows = [row for row in pair_rows if row.get("target_guard_match") == "1"]
    target_guard_exact = [row for row in target_guard_rows if row.get("known_exact") == "1"]
    target_guard_false = [row for row in target_guard_rows if row.get("known_false") == "1"]
    cross_rule_exact = [
        row
        for row in exact_rows
        if row.get("rule_type") != "compact_control_stream" and row.get("is_target") != "1"
    ]
    cross_rule_false = [
        row
        for row in false_rows
        if row.get("rule_type") != "compact_control_stream" and row.get("is_target") != "1"
    ]
    target_delta = token_review.pair_delta(target)
    ready = 0
    if len(target_guard_exact) >= 2 and not target_guard_false:
        review_verdict = "frontier80_tail_compact_token_independent_support_ready"
        next_probe = "promote high2 compact-control token selector for frontier80 offsets 16-17"
        ready = target.pair_len
    elif cross_rule_exact and target_guard_exact and not target_guard_false:
        review_verdict = "frontier80_tail_compact_token_cross_rule_support_only"
        next_probe = "derive compact-control-specific guard for cross-rule high2 selector transfer"
    elif target_guard_exact and not target_guard_false:
        review_verdict = "frontier80_tail_compact_token_single_compact_support_only"
        next_probe = "seek second compact-control high2 selector support row"
    else:
        review_verdict = "frontier80_tail_compact_token_independent_support_rejected"
        next_probe = "derive alternate compact-control token support beyond high2 selector"
    return {
        "scope": "total",
        "candidate_mode": "old_clean_byte_union_frontier80_tail_compact_token_independent_support_review",
        "target_key": "|".join(target_key_value),
        "target_pair_offset": str(target.pair_start),
        "target_pair_hex": token_review.pair_bytes(target).hex(),
        "target_run_value": f"{target.run_value:02x}",
        "target_delta": "" if target_delta is None else str(target_delta),
        "selector": "run_value+high2(segment[pair_offset-8])",
        "pair_rows": str(len(pair_rows)),
        "full_rows": str(sum(1 for row in pair_rows if row.get("full_match") == "1")),
        "known_pair_rows": str(sum(1 for row in pair_rows if "1" in row.get("known_pair_bits", ""))),
        "known_exact_rows": str(len(exact_rows)),
        "known_false_rows": str(len(false_rows)),
        "compact_pair_rows": str(len(compact_rows)),
        "compact_known_exact_rows": str(len(compact_exact)),
        "compact_known_false_rows": str(len(compact_false)),
        "target_guard_pair_rows": str(len(target_guard_rows)),
        "target_guard_full_rows": str(sum(1 for row in target_guard_rows if row.get("full_match") == "1")),
        "target_guard_known_exact_rows": str(len(target_guard_exact)),
        "target_guard_known_false_rows": str(len(target_guard_false)),
        "cross_rule_known_exact_rows": str(len(cross_rule_exact)),
        "cross_rule_known_false_rows": str(len(cross_rule_false)),
        "cross_rule_rule_types": join_rule_types(cross_rule_exact),
        "best_independent_support": first_sample(cross_rule_exact),
        "best_compact_support": first_sample(target_guard_exact or compact_exact),
        "review_verdict": review_verdict,
        "next_probe": next_probe,
        "promotion_candidate_bytes": str(target.pair_len),
        "promotion_ready_bytes": str(ready),
        "issue_rows": str(issue_rows),
    }


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 200) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    pairs: list[dict[str, str]],
    targets: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "pairs": pairs, "targets": targets}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("pairs.csv", output_dir / "pairs.csv"),
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
    <div class="stat"><div class="label">Known exact/false</div><div class="value">{html.escape(summary['known_exact_rows'])}/{html.escape(summary['known_false_rows'])}</div></div>
    <div class="stat"><div class="label">Target guard exact/false</div><div class="value">{html.escape(summary['target_guard_known_exact_rows'])}/{html.escape(summary['target_guard_known_false_rows'])}</div></div>
    <div class="stat"><div class="label">Cross-rule exact</div><div class="value">{html.escape(summary['cross_rule_known_exact_rows'])}</div></div>
  </div>
  <h2>Targets</h2>
  {render_table(targets, TARGET_FIELDNAMES)}
  <h2>Pairs</h2>
  {render_table(pairs, PAIR_FIELDNAMES)}
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
    parser.add_argument("--title", default="Lands of Lore II .tex Frontier80 Tail Compact Token Independent Support Review")
    args = parser.parse_args()

    target_key_value, contexts, manifests, issues = target_setup(
        args.slots,
        args.manifest,
        args.base_fixtures,
        args.min_run_length,
    )
    target = next((context for context in contexts if context.is_target), None)
    if target is None:
        raise SystemExit("missing target context")
    pairs = build_pair_rows(contexts, manifests, target)
    summary = build_summary(
        target_key_value=target_key_value,
        target=target,
        pair_rows=pairs,
        issue_rows=len(issues),
    )
    targets = build_target_rows(read_csv(args.delta_targets), summary)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "pairs.csv", PAIR_FIELDNAMES, pairs)
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, targets)
    (args.output / "index.html").write_text(
        build_html(summary, pairs, targets, args.output, args.title),
        encoding="utf-8",
    )

    print(
        "Frontier80 compact token independent support review: "
        f"verdict={summary['review_verdict']} "
        f"known={summary['known_exact_rows']}/{summary['known_false_rows']} "
        f"target_guard={summary['target_guard_known_exact_rows']}/{summary['target_guard_known_false_rows']} "
        f"cross_rule={summary['cross_rule_known_exact_rows']} "
        f"promotion_ready={summary['promotion_ready_bytes']}"
    )
    print(f"HTML: {args.output / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
