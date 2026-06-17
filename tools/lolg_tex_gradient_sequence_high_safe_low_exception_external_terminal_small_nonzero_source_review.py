#!/usr/bin/env python3
"""Review source support for final small nonzero external terminal blockers."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv
from lolg_tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector_probe import (
    asset_key,
    byte_exact,
    fixed_outputs,
    int_value,
    load_bytes,
)


DEFAULT_TARGETS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector/targets.csv"
)
DEFAULT_SOURCE_CANDIDATES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector/source_candidates.csv"
)
DEFAULT_SMALL_GAPS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_selector/small_gaps.csv"
)
DEFAULT_FIXTURES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_source_terminal_replay_union_guard_cover_second_promoted_replay/fixtures.csv"
)
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures/manifest.csv")
DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_small_nonzero_source_review"
)

SELECTOR_RE = re.compile(
    r"^(?P<pool>[a-z_]+)@(?P<offset>\d+):(?P<transform>[a-z_]+)(?:=(?P<parameter>[0-9a-f]{2}))?$"
)

STRICT_CONTEXT_FEATURES = ("gap_role", "length", "prev_op_length", "next_op_length", "control_ref_mod64")
CONTEXT_FAMILIES = [
    ("gap_role", "length", "prev_op_length", "next_op_length"),
    ("gap_role", "length", "control_ref_mod64"),
    STRICT_CONTEXT_FEATURES,
    ("gap_role", "length"),
    ("frontier_type", "strategy", "length"),
    ("pcx_name", "gap_role", "length"),
]
STRUCTURAL_ISSUES = {"invalid_selector"}
STRUCTURAL_ISSUE_PREFIXES = ("unsupported_pool:", "missing_", "read_")

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_spans",
    "target_bytes",
    "source_candidate_rows",
    "full_source_candidate_rows",
    "known_eval_rows",
    "known_exact_rows",
    "known_false_rows",
    "best_target_span",
    "best_selector",
    "best_review_verdict",
    "best_known_eval_rows",
    "best_known_exact_rows",
    "best_known_false_rows",
    "best_same_context_eval_rows",
    "best_same_context_exact_rows",
    "best_same_context_false_rows",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "next_probe",
    "issue_rows",
]

TARGET_FIELDNAMES = [
    "rank",
    "span_key",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "span_start",
    "span_end",
    "span_length",
    "expected_hex",
    "best_selector",
    "best_review_verdict",
    "best_known_eval_rows",
    "best_known_exact_rows",
    "best_known_false_rows",
    "best_same_context_eval_rows",
    "best_same_context_exact_rows",
    "best_same_context_false_rows",
    "promotion_ready",
    "issues",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "target_span",
    "selector",
    "pool",
    "offset",
    "transform",
    "parameter",
    "target_full_match",
    "target_exact_bytes",
    "target_output_hex",
    "target_expected_hex",
    "known_eval_rows",
    "known_exact_rows",
    "known_false_rows",
    "same_context_eval_rows",
    "same_context_exact_rows",
    "same_context_false_rows",
    "strict_context_key",
    "review_verdict",
    "promotion_ready",
    "issues",
]

EVALUATION_FIELDNAMES = [
    "rank",
    "candidate_rank",
    "target_span",
    "selector",
    "span_key",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "known_in_replay",
    "same_strict_context",
    "source_available",
    "expected_hex",
    "source_hex",
    "output_hex",
    "formula_exact",
    "features",
    "issues",
]

CONTEXT_FIELDNAMES = [
    "rank",
    "candidate_rank",
    "target_span",
    "selector",
    "context_family",
    "context_key",
    "known_eval_rows",
    "known_exact_rows",
    "known_false_rows",
    "verdict",
    "sample_spans",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def selector_parts(selector: str) -> dict[str, str]:
    match = SELECTOR_RE.match(selector)
    if not match:
        return {}
    return match.groupdict(default="")


def apply_transform(source: bytes, transform: str, parameter: str) -> bytes:
    for candidate_transform, candidate_parameter, output in fixed_outputs(source):
        if candidate_transform == transform and candidate_parameter == parameter:
            return output
    return b""


def source_pool(
    row: dict[str, str],
    pool: str,
    fixtures_by_key: dict[tuple[str, str, str], dict[str, str]],
    manifest_by_key: dict[tuple[str, str, str], dict[str, str]],
    issues: list[str],
) -> tuple[bytes, bytes]:
    key = asset_key(row)
    manifest = manifest_by_key.get(key, {})
    fixture = fixtures_by_key.get(key, {})
    if pool == "segment_gap":
        return load_bytes(manifest.get("segment_gap_path", ""), issues, "segment_gap"), b""
    if pool == "control_prefix":
        return load_bytes(manifest.get("control_prefix_path", ""), issues, "control_prefix"), b""
    if pool == "fragment":
        return load_bytes(manifest.get("fragment_path", ""), issues, "fragment"), b""
    if pool == "known_decoded":
        return (
            load_bytes(fixture.get("decoded_path", ""), issues, "decoded"),
            load_bytes(fixture.get("known_mask_path", ""), issues, "known_mask"),
        )
    issues.append(f"unsupported_pool:{pool}")
    return b"", b""


def evaluate_selector(
    selector: str,
    row: dict[str, str],
    fixtures_by_key: dict[tuple[str, str, str], dict[str, str]],
    manifest_by_key: dict[tuple[str, str, str], dict[str, str]],
) -> dict[str, str]:
    parts = selector_parts(selector)
    issues: list[str] = []
    if not parts:
        return {
            "source_available": "0",
            "source_hex": "",
            "output_hex": "",
            "formula_exact": "0",
            "issues": "invalid_selector",
        }

    expected = bytes.fromhex(row.get("expected_hex", ""))
    length = len(expected)
    offset = int(parts["offset"])
    source_data, known_mask = source_pool(row, parts["pool"], fixtures_by_key, manifest_by_key, issues)
    if length <= 0:
        issues.append("empty_expected")
    if offset < 0 or offset + length > len(source_data):
        issues.append("source_out_of_range")
        source = b""
    else:
        source = source_data[offset : offset + length]
    if parts["pool"] == "known_decoded":
        if offset + length > len(known_mask):
            issues.append("known_mask_out_of_range")
        elif not all(known_mask[offset : offset + length]):
            issues.append("known_decoded_source_unknown")
    output = apply_transform(source, parts["transform"], parts["parameter"]) if source and not issues else b""
    return {
        "source_available": "1" if source and not issues else "0",
        "source_hex": source.hex(),
        "output_hex": output.hex(),
        "formula_exact": "1" if output and output == expected else "0",
        "issues": ";".join(issues),
    }


def context_key(row: dict[str, str], fields: tuple[str, ...]) -> str:
    return "|".join(f"{field}={row.get(field, '')}" for field in fields)


def sample_spans(rows: list[dict[str, str]], limit: int = 8) -> str:
    return ",".join(row.get("span_key", "") for row in rows[:limit])


def context_metrics(
    evaluations: list[dict[str, str]],
    target: dict[str, str],
    fields: tuple[str, ...],
) -> dict[str, str]:
    key = context_key(target, fields)
    rows = [
        row
        for row in evaluations
        if row.get("known_in_replay") == "1"
        and row.get("source_available") == "1"
        and row.get("features") == key
    ]
    exact = sum(1 for row in rows if row.get("formula_exact") == "1")
    false = len(rows) - exact
    if exact > 0 and false == 0:
        verdict = "known_context_support_ready"
    elif exact > 0 and false > 0:
        verdict = "known_context_conflicted"
    elif false > 0:
        verdict = "known_context_false_without_support"
    else:
        verdict = "target_only_context"
    return {
        "context_family": "+".join(fields),
        "context_key": key,
        "known_eval_rows": str(len(rows)),
        "known_exact_rows": str(exact),
        "known_false_rows": str(false),
        "verdict": verdict,
        "sample_spans": sample_spans(rows),
    }


def review_verdict(full_match: bool, known_eval: int, known_exact: int, known_false: int, strict_eval: int) -> str:
    if not full_match:
        return "target_not_full_match"
    if known_exact > 0 and known_false == 0:
        return "known_support_ready"
    if known_exact > 0 and known_false > 0:
        return "known_conflicted_block_promotion"
    if known_false > 0:
        return "known_false_without_support"
    if known_eval == 0 or strict_eval == 0:
        return "target_only_no_known_support"
    return "unresolved_no_known_support"


def is_structural_issue(issue: str) -> bool:
    return issue in STRUCTURAL_ISSUES or any(issue.startswith(prefix) for prefix in STRUCTURAL_ISSUE_PREFIXES)


def candidate_sort_key(row: dict[str, str]) -> tuple[object, ...]:
    verdict = row.get("review_verdict", "")
    verdict_rank = {
        "known_support_ready": 0,
        "known_conflicted_block_promotion": 1,
        "known_false_without_support": 2,
        "target_only_no_known_support": 3,
        "unresolved_no_known_support": 4,
        "target_not_full_match": 5,
    }.get(verdict, 6)
    return (
        verdict_rank,
        row.get("target_full_match") != "1",
        -int_value(row, "known_exact_rows"),
        -int_value(row, "known_eval_rows"),
        int_value(row, "known_false_rows"),
        int_value(row, "rank"),
        row.get("selector", ""),
    )


def build(
    target_rows: list[dict[str, str]],
    source_candidates: list[dict[str, str]],
    small_gap_rows: list[dict[str, str]],
    fixture_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    fixtures_by_key = {asset_key(row): row for row in fixture_rows}
    manifest_by_key = {asset_key(row): row for row in manifest_rows}
    targets_by_span = {row.get("span_key", ""): row for row in target_rows}
    full_candidates = [row for row in source_candidates if row.get("full_match") == "1"]
    known_rows_by_length: dict[str, list[dict[str, str]]] = {}
    for row in small_gap_rows:
        if row.get("known_in_replay") != "1":
            continue
        known_rows_by_length.setdefault(row.get("length", ""), []).append(row)

    reviewed_candidates: list[dict[str, str]] = []
    evaluation_rows: list[dict[str, str]] = []
    context_rows: list[dict[str, str]] = []
    issue_rows = 0

    for candidate in full_candidates:
        target = targets_by_span.get(candidate.get("target_span", ""), {})
        if not target:
            issue_rows += 1
            continue
        target_length = target.get("span_length", candidate.get("exact_bytes", ""))
        candidate_evaluations: list[dict[str, str]] = []
        for gap in known_rows_by_length.get(target_length, []):
            evaluated = evaluate_selector(candidate.get("selector", ""), gap, fixtures_by_key, manifest_by_key)
            strict_key = context_key(target, STRICT_CONTEXT_FEATURES)
            strict_gap_key = context_key(gap, STRICT_CONTEXT_FEATURES)
            row = {
                "rank": "",
                "candidate_rank": candidate.get("rank", ""),
                "target_span": candidate.get("target_span", ""),
                "selector": candidate.get("selector", ""),
                "span_key": gap.get("span_key", ""),
                "archive_tag": gap.get("archive_tag", ""),
                "pcx_name": gap.get("pcx_name", ""),
                "frontier_id": gap.get("frontier_id", ""),
                "known_in_replay": gap.get("known_in_replay", ""),
                "same_strict_context": "1" if strict_gap_key == strict_key else "0",
                "expected_hex": gap.get("expected_hex", ""),
                "features": strict_gap_key,
                **evaluated,
            }
            candidate_evaluations.append(row)
            evaluation_rows.append(row)

        evaluable = [row for row in candidate_evaluations if row.get("source_available") == "1"]
        known_exact = sum(1 for row in evaluable if row.get("formula_exact") == "1")
        known_false = len(evaluable) - known_exact
        same_context = [row for row in evaluable if row.get("same_strict_context") == "1"]
        same_exact = sum(1 for row in same_context if row.get("formula_exact") == "1")
        same_false = len(same_context) - same_exact
        verdict = review_verdict(
            candidate.get("full_match") == "1",
            len(evaluable),
            known_exact,
            known_false,
            len(same_context),
        )
        promotion_ready = (
            int_value(target, "span_length")
            if verdict == "known_support_ready" and candidate.get("full_match") == "1"
            else 0
        )
        issues = sorted(
            {
                issue
                for row in candidate_evaluations
                for issue in row.get("issues", "").split(";")
                if issue and is_structural_issue(issue)
            }
        )
        reviewed_candidates.append(
            {
                "rank": candidate.get("rank", ""),
                "target_span": candidate.get("target_span", ""),
                "selector": candidate.get("selector", ""),
                "pool": candidate.get("pool", ""),
                "offset": candidate.get("offset", ""),
                "transform": candidate.get("transform", ""),
                "parameter": candidate.get("parameter", ""),
                "target_full_match": candidate.get("full_match", "0"),
                "target_exact_bytes": candidate.get("exact_bytes", "0"),
                "target_output_hex": candidate.get("output_hex", ""),
                "target_expected_hex": candidate.get("expected_hex", ""),
                "known_eval_rows": str(len(evaluable)),
                "known_exact_rows": str(known_exact),
                "known_false_rows": str(known_false),
                "same_context_eval_rows": str(len(same_context)),
                "same_context_exact_rows": str(same_exact),
                "same_context_false_rows": str(same_false),
                "strict_context_key": context_key(target, STRICT_CONTEXT_FEATURES),
                "review_verdict": verdict,
                "promotion_ready": str(promotion_ready),
                "issues": ";".join(issues),
            }
        )
        if issues:
            issue_rows += 1

        for fields in CONTEXT_FAMILIES:
            metric = context_metrics(
                [
                    {**row, "features": context_key(gap_by_span(small_gap_rows, row.get("span_key", "")), fields)}
                    for row in candidate_evaluations
                ],
                target,
                fields,
            )
            context_rows.append(
                {
                    "rank": "",
                    "candidate_rank": candidate.get("rank", ""),
                    "target_span": candidate.get("target_span", ""),
                    "selector": candidate.get("selector", ""),
                    **metric,
                }
            )

    reviewed_candidates.sort(key=candidate_sort_key)
    for index, row in enumerate(reviewed_candidates, start=1):
        row["rank"] = str(index)
    for index, row in enumerate(evaluation_rows, start=1):
        row["rank"] = str(index)
    for index, row in enumerate(context_rows, start=1):
        row["rank"] = str(index)

    candidates_by_target: dict[str, list[dict[str, str]]] = {}
    for row in reviewed_candidates:
        candidates_by_target.setdefault(row.get("target_span", ""), []).append(row)

    reviewed_targets: list[dict[str, str]] = []
    for index, target in enumerate(target_rows, start=1):
        target_candidates = candidates_by_target.get(target.get("span_key", ""), [])
        best = target_candidates[0] if target_candidates else {}
        promotion_ready = int_value(best, "promotion_ready")
        target_issues = []
        if not best:
            target_issues.append("missing_full_source_candidate")
        elif promotion_ready == 0:
            target_issues.append(best.get("review_verdict", "not_promotion_ready"))
        reviewed_targets.append(
            {
                "rank": str(index),
                "span_key": target.get("span_key", ""),
                "archive": target.get("archive", ""),
                "archive_tag": target.get("archive_tag", ""),
                "pcx_name": target.get("pcx_name", ""),
                "frontier_id": target.get("frontier_id", ""),
                "span_start": target.get("span_start", ""),
                "span_end": target.get("span_end", ""),
                "span_length": target.get("span_length", ""),
                "expected_hex": target.get("expected_hex", ""),
                "best_selector": best.get("selector", ""),
                "best_review_verdict": best.get("review_verdict", ""),
                "best_known_eval_rows": best.get("known_eval_rows", "0"),
                "best_known_exact_rows": best.get("known_exact_rows", "0"),
                "best_known_false_rows": best.get("known_false_rows", "0"),
                "best_same_context_eval_rows": best.get("same_context_eval_rows", "0"),
                "best_same_context_exact_rows": best.get("same_context_exact_rows", "0"),
                "best_same_context_false_rows": best.get("same_context_false_rows", "0"),
                "promotion_ready": str(promotion_ready),
                "issues": ";".join(target_issues),
            }
        )

    best_candidate = reviewed_candidates[0] if reviewed_candidates else {}
    promotion_ready_bytes = sum(int_value(row, "promotion_ready") for row in reviewed_targets)
    known_eval_rows = max((int_value(row, "known_eval_rows") for row in reviewed_candidates), default=0)
    known_exact_rows = max((int_value(row, "known_exact_rows") for row in reviewed_candidates), default=0)
    known_false_rows = min((int_value(row, "known_false_rows") for row in reviewed_candidates), default=0)
    if promotion_ready_bytes > 0:
        next_probe = "promote final independently supported small-nonzero external terminal source byte"
    elif reviewed_candidates:
        next_probe = "derive broader evidence for final small-nonzero external terminal source"
    else:
        next_probe = "derive final small-nonzero external terminal source candidate"
    summary = {
        "scope": "total",
        "candidate_mode": "external_terminal_small_nonzero_source_review",
        "target_spans": str(len(target_rows)),
        "target_bytes": str(sum(int_value(row, "span_length") for row in target_rows)),
        "source_candidate_rows": str(len(source_candidates)),
        "full_source_candidate_rows": str(len(full_candidates)),
        "known_eval_rows": str(known_eval_rows),
        "known_exact_rows": str(known_exact_rows),
        "known_false_rows": str(known_false_rows),
        "best_target_span": best_candidate.get("target_span", ""),
        "best_selector": best_candidate.get("selector", ""),
        "best_review_verdict": best_candidate.get("review_verdict", ""),
        "best_known_eval_rows": best_candidate.get("known_eval_rows", "0"),
        "best_known_exact_rows": best_candidate.get("known_exact_rows", "0"),
        "best_known_false_rows": best_candidate.get("known_false_rows", "0"),
        "best_same_context_eval_rows": best_candidate.get("same_context_eval_rows", "0"),
        "best_same_context_exact_rows": best_candidate.get("same_context_exact_rows", "0"),
        "best_same_context_false_rows": best_candidate.get("same_context_false_rows", "0"),
        "promotion_candidate_bytes": "0",
        "promotion_ready_bytes": str(promotion_ready_bytes),
        "next_probe": next_probe,
        "issue_rows": str(issue_rows),
    }
    return summary, reviewed_targets, reviewed_candidates, evaluation_rows, context_rows


def gap_by_span(rows: list[dict[str, str]], span_key: str) -> dict[str, str]:
    for row in rows:
        if row.get("span_key", "") == span_key:
            return row
    return {}


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    target_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    evaluation_rows: list[dict[str, str]],
    context_rows: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {
        "summary": summary,
        "targets": target_rows,
        "candidates": candidate_rows,
        "evaluations": evaluation_rows,
        "contexts": context_rows,
    }
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("targets.csv", output_dir / "targets.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
            ("evaluations.csv", output_dir / "evaluations.csv"),
            ("contexts.csv", output_dir / "contexts.csv"),
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
  --bg: #101417;
  --panel: #171f22;
  --line: #31424a;
  --text: #edf5f4;
  --muted: #9dafb5;
  --accent: #77d3b1;
  --warn: #f0b36c;
}}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, sans-serif; }}
main {{ width: min(1680px, calc(100vw - 28px)); margin: 0 auto; padding: 22px 0 32px; display: grid; gap: 16px; }}
h1 {{ margin: 0; font-size: 22px; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.muted {{ color: var(--muted); }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.value {{ font-size: 22px; font-weight: 760; color: var(--accent); }}
.warn {{ color: var(--warn); }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; min-width: 1350px; border-collapse: collapse; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
code {{ color: var(--accent); }}
</style>
</head>
<body>
<main>
  <header>
    <h1>{html.escape(title)}</h1>
    <div class="muted">Reviews whether final target-only source selectors have known replay support before promotion.</div>
  </header>
  <section class="stats">
    <div class="stat"><div class="muted">Target bytes</div><div class="value">{summary['target_bytes']}</div></div>
    <div class="stat"><div class="muted">Full source candidates</div><div class="value">{summary['full_source_candidate_rows']}</div></div>
    <div class="stat"><div class="muted">Best known exact</div><div class="value warn">{summary['best_known_exact_rows']}</div></div>
    <div class="stat"><div class="muted">Best known false</div><div class="value warn">{summary['best_known_false_rows']}</div></div>
    <div class="stat"><div class="muted">Promotion-ready</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2>{links}</section>
  <section class="panel">
    <h2>Verdict</h2>
    <p><code>{html.escape(summary['best_review_verdict'])}</code></p>
    <p class="muted">Best selector: <code>{html.escape(summary['best_selector'])}</code>. Next: <code>{html.escape(summary['next_probe'])}</code>.</p>
  </section>
  <section class="panel"><h2>Targets</h2>{render_table(target_rows, TARGET_FIELDNAMES)}</section>
  <section class="panel"><h2>Candidates</h2>{render_table(candidate_rows, CANDIDATE_FIELDNAMES)}</section>
  <section class="panel"><h2>Contexts</h2>{render_table(context_rows, CONTEXT_FIELDNAMES)}</section>
  <section class="panel"><h2>Known Evaluations</h2>{render_table(evaluation_rows, EVALUATION_FIELDNAMES)}</section>
  <script type="application/json" id="external-terminal-small-nonzero-source-review-data">{html.escape(data_json)}</script>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Review final small nonzero external terminal source candidates before guarded promotion."
    )
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--source-candidates", type=Path, default=DEFAULT_SOURCE_CANDIDATES)
    parser.add_argument("--small-gaps", type=Path, default=DEFAULT_SMALL_GAPS)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex External Terminal Small Nonzero Source Review",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, target_rows, candidate_rows, evaluation_rows, context_rows = build(
        read_csv(args.targets),
        read_csv(args.source_candidates),
        read_csv(args.small_gaps),
        read_csv(args.fixtures),
        read_csv(args.manifest),
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "targets.csv", TARGET_FIELDNAMES, target_rows)
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidate_rows)
    write_csv(args.output / "evaluations.csv", EVALUATION_FIELDNAMES, evaluation_rows)
    write_csv(args.output / "contexts.csv", CONTEXT_FIELDNAMES, context_rows)
    html_path = args.output / "index.html"
    html_path.write_text(
        build_html(summary, target_rows, candidate_rows, evaluation_rows, context_rows, args.output, args.title),
        encoding="utf-8",
    )

    print(
        "Small-nonzero source review: "
        f"targets={summary['target_spans']} "
        f"full_candidates={summary['full_source_candidate_rows']} "
        f"best={summary['best_selector']} "
        f"verdict={summary['best_review_verdict']} "
        f"promotion_ready={summary['promotion_ready_bytes']} "
        f"issues={summary['issue_rows']}"
    )
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
