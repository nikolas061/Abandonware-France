#!/usr/bin/env python3
"""Summarize non-tail support for compact-control five-byte formula variants."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
from collections import Counter
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv


DEFAULT_FORMULA_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_formula_variant/summary.csv"
)
DEFAULT_FORMULA_VARIANTS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_formula_variant/variants.csv"
)
DEFAULT_REFINED_HITS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_refined_support/hits.csv"
)
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures_expanded/manifest.csv")
DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_non_tail_support"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_spans",
    "target_bytes",
    "formula_variant_rows",
    "non_tail_support_rows",
    "non_tail_all_non_target_rows",
    "non_tail_partial_non_target_rows",
    "non_tail_target_and_non_target_rows",
    "local_nonzero_rows",
    "dominant_partial_group",
    "dominant_partial_rows",
    "best_local_template",
    "best_local_frontiers",
    "best_local_samples",
    "best_partial_template",
    "best_partial_frontiers",
    "best_partial_samples",
    "review_verdict",
    "next_probe",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "variant_rank",
    "window_scope",
    "verdict",
    "template_key",
    "target_frontiers",
    "non_target_frontiers",
    "target_rows",
    "non_target_rows",
    "zero_heavy_rows",
    "min_start",
    "max_start",
    "sample_non_tail_rows",
    "sample_local_rows",
    "sample_tail_rows",
    "sample_matches",
    "candidate_class",
]

GROUP_FIELDNAMES = [
    "rank",
    "candidate_class",
    "frontier_group",
    "variant_rows",
    "best_variant_rank",
    "best_template",
    "best_samples",
]

SAMPLE_RE = re.compile(r"(?P<frontier>\d+):(?P<start>\d+)-(?P<end>\d+):(?P<hex>[0-9a-f]+)")


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def int_value(row: dict[str, str], field: str, default: int = 0) -> int:
    try:
        return int(row.get(field, ""))
    except (TypeError, ValueError):
        return default


def row_identity(row: dict[str, str]) -> tuple[str, str, str, str]:
    return row.get("archive", ""), row.get("archive_tag", ""), row.get("pcx_name", ""), row.get("frontier_id", "")


def load_expected_lengths(
    hit_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
) -> tuple[dict[str, tuple[int, int]], list[str]]:
    manifest_by_key = {row_identity(row): row for row in manifest_rows}
    lengths: dict[str, tuple[int, int]] = {}
    issues: list[str] = []
    for hit in hit_rows:
        frontier_id = hit.get("frontier_id", "")
        manifest = manifest_by_key.get(row_identity(hit))
        if manifest is None:
            issues.append(f"{'|'.join(row_identity(hit))}:missing_manifest")
            continue
        path_text = manifest.get("expected_gap_path", "")
        if not path_text:
            issues.append(f"{frontier_id}:missing_expected_path")
            continue
        try:
            gap_len = len(Path(path_text).read_bytes())
        except OSError as exc:
            issues.append(f"{frontier_id}:read_expected_failed:{exc}")
            continue
        lengths[frontier_id] = (gap_len, int_value(hit, "ref_offset", -1))
    return lengths, issues


def sample_context_counts(
    row: dict[str, str],
    lengths: dict[str, tuple[int, int]],
    *,
    tail_limit: int,
    local_start_limit: int,
    local_ref_radius: int,
    issues: list[str],
) -> tuple[int, int, int]:
    non_tail = 0
    local = 0
    tail = 0
    for match in SAMPLE_RE.finditer(row.get("sample_matches", "")):
        frontier_id = match.group("frontier")
        fixture = lengths.get(frontier_id)
        if fixture is None:
            issues.append(f"variant_{row.get('rank', '')}:missing_fixture:{frontier_id}")
            continue
        gap_len, ref = fixture
        start = int(match.group("start"))
        end = int(match.group("end"))
        tail_after = gap_len - end
        ref_distance = start - ref
        if 0 <= tail_after <= tail_limit:
            tail += 1
        else:
            non_tail += 1
        if start <= local_start_limit or abs(ref_distance) <= local_ref_radius:
            local += 1
    return non_tail, local, tail


def candidate_class(row: dict[str, str]) -> str:
    verdict = row.get("verdict", "")
    if verdict == "all_non_target_variant":
        return "all_non_target_non_tail"
    if row.get("window_scope") == "local" and verdict == "target_and_non_target_variant":
        return "local_nonzero_target_pair"
    if verdict == "target_and_non_target_variant":
        return "target_overlap_non_tail"
    if verdict == "partial_non_target_variant":
        return "partial_non_target_non_tail"
    return "other_non_tail"


def build_groups(candidates: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in candidates:
        key = row.get("candidate_class", ""), row.get("non_target_frontiers", "")
        grouped.setdefault(key, []).append(row)
    group_rows: list[dict[str, str]] = []
    for (klass, frontiers), rows in grouped.items():
        best = min(rows, key=lambda row: int_value(row, "variant_rank"))
        group_rows.append(
            {
                "rank": "",
                "candidate_class": klass,
                "frontier_group": frontiers,
                "variant_rows": str(len(rows)),
                "best_variant_rank": best.get("variant_rank", ""),
                "best_template": best.get("template_key", ""),
                "best_samples": best.get("sample_matches", ""),
            }
        )
    group_rows.sort(
        key=lambda row: (
            row.get("candidate_class") != "all_non_target_non_tail",
            row.get("candidate_class") != "local_nonzero_target_pair",
            row.get("candidate_class") != "target_overlap_non_tail",
            -int_value(row, "variant_rows"),
            row.get("frontier_group", ""),
        )
    )
    for index, row in enumerate(group_rows, start=1):
        row["rank"] = str(index)
    return group_rows


def build(
    formula_summary_rows: list[dict[str, str]],
    formula_variant_rows: list[dict[str, str]],
    refined_hit_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
    *,
    tail_limit: int,
    local_start_limit: int,
    local_ref_radius: int,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    formula_summary = formula_summary_rows[0] if formula_summary_rows else {}
    lengths, issues = load_expected_lengths(refined_hit_rows, manifest_rows)
    candidates: list[dict[str, str]] = []
    for row in formula_variant_rows:
        if int_value(row, "zero_heavy_rows") > 0:
            continue
        non_tail_rows, local_rows, tail_rows = sample_context_counts(
            row,
            lengths,
            tail_limit=tail_limit,
            local_start_limit=local_start_limit,
            local_ref_radius=local_ref_radius,
            issues=issues,
        )
        if non_tail_rows <= 0:
            continue
        klass = candidate_class(row)
        if klass == "other_non_tail":
            continue
        candidates.append(
            {
                "rank": "",
                "variant_rank": row.get("rank", ""),
                "window_scope": row.get("window_scope", ""),
                "verdict": row.get("verdict", ""),
                "template_key": row.get("template_key", ""),
                "target_frontiers": row.get("target_frontiers", ""),
                "non_target_frontiers": row.get("non_target_frontiers", ""),
                "target_rows": row.get("target_rows", ""),
                "non_target_rows": row.get("non_target_rows", ""),
                "zero_heavy_rows": row.get("zero_heavy_rows", ""),
                "min_start": row.get("min_start", ""),
                "max_start": row.get("max_start", ""),
                "sample_non_tail_rows": str(non_tail_rows),
                "sample_local_rows": str(local_rows),
                "sample_tail_rows": str(tail_rows),
                "sample_matches": row.get("sample_matches", ""),
                "candidate_class": klass,
            }
        )
    candidates.sort(
        key=lambda row: (
            row.get("candidate_class") != "all_non_target_non_tail",
            row.get("candidate_class") != "local_nonzero_target_pair",
            row.get("candidate_class") != "target_overlap_non_tail",
            -int_value(row, "sample_local_rows"),
            -int_value(row, "non_target_rows"),
            int_value(row, "variant_rank"),
        )
    )
    for index, row in enumerate(candidates, start=1):
        row["rank"] = str(index)
    group_rows = build_groups(candidates)
    class_counts = Counter(row.get("candidate_class", "") for row in candidates)
    partial_groups = [
        row for row in group_rows if row.get("candidate_class") == "partial_non_target_non_tail"
    ]
    dominant_partial = partial_groups[0] if partial_groups else {}
    local_rows = [row for row in candidates if row.get("candidate_class") == "local_nonzero_target_pair"]
    partial_rows = [row for row in candidates if row.get("candidate_class") == "partial_non_target_non_tail"]
    best_local = local_rows[0] if local_rows else {}
    best_partial = (
        next(
            (row for row in partial_rows if row.get("variant_rank") == dominant_partial.get("best_variant_rank")),
            partial_rows[0],
        )
        if partial_rows
        else {}
    )
    if issues:
        verdict = "non_tail_support_has_issues"
        next_probe = "fix compact-control five-byte non-tail support issues"
    elif class_counts["all_non_target_non_tail"] > 0:
        verdict = "non_tail_all_non_target_candidate_found"
        next_probe = "review non-tail all-non-target compact-control five-byte formula candidates"
    elif partial_rows:
        verdict = "pair_family_non_tail_support_only"
        next_probe = "split non-tail compact-control five-byte support by frontier pair family"
    elif local_rows:
        verdict = "local_target_pair_support_only"
        next_probe = "expand local non-tail compact-control five-byte support beyond target pair"
    else:
        verdict = "no_non_tail_formula_support"
        next_probe = "expand compact-control five-byte formula atoms beyond current non-tail search"
    summary = {
        "scope": "total",
        "candidate_mode": "external_terminal_spatial_bridge_five_byte_non_tail_support",
        "target_spans": formula_summary.get("target_spans", "0"),
        "target_bytes": formula_summary.get("target_bytes", "0"),
        "formula_variant_rows": str(len(formula_variant_rows)),
        "non_tail_support_rows": str(len(candidates)),
        "non_tail_all_non_target_rows": str(class_counts["all_non_target_non_tail"]),
        "non_tail_partial_non_target_rows": str(class_counts["partial_non_target_non_tail"]),
        "non_tail_target_and_non_target_rows": str(
            class_counts["target_overlap_non_tail"] + class_counts["local_nonzero_target_pair"]
        ),
        "local_nonzero_rows": str(len(local_rows)),
        "dominant_partial_group": dominant_partial.get("frontier_group", ""),
        "dominant_partial_rows": dominant_partial.get("variant_rows", "0"),
        "best_local_template": best_local.get("template_key", ""),
        "best_local_frontiers": best_local.get("non_target_frontiers", ""),
        "best_local_samples": best_local.get("sample_matches", ""),
        "best_partial_template": best_partial.get("template_key", ""),
        "best_partial_frontiers": best_partial.get("non_target_frontiers", ""),
        "best_partial_samples": best_partial.get("sample_matches", ""),
        "review_verdict": verdict,
        "next_probe": next_probe,
        "promotion_candidate_bytes": "0",
        "promotion_ready_bytes": "0",
        "issue_rows": str(len(issues)),
    }
    return summary, candidates, group_rows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 260) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    candidates: list[dict[str, str]],
    groups: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "candidates": candidates, "groups": groups}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
            ("groups.csv", output_dir / "groups.csv"),
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
  --panel: #182023;
  --line: #314247;
  --text: #edf4f2;
  --muted: #a4b2b5;
  --accent: #7bd5b4;
  --warn: #eebb70;
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
table {{ width: 100%; min-width: 1420px; border-collapse: collapse; }}
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
    <div class="muted">Filters formula variants to non-zero, non-tail compact-control support.</div>
  </header>
  <section class="stats">
    <div class="stat"><div class="muted">Non-tail support</div><div class="value">{summary['non_tail_support_rows']}</div></div>
    <div class="stat"><div class="muted">All non-target</div><div class="value warn">{summary['non_tail_all_non_target_rows']}</div></div>
    <div class="stat"><div class="muted">Partial non-target</div><div class="value">{summary['non_tail_partial_non_target_rows']}</div></div>
    <div class="stat"><div class="muted">Target overlap</div><div class="value">{summary['non_tail_target_and_non_target_rows']}</div></div>
    <div class="stat"><div class="muted">Promotion-ready</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2>{links}</section>
  <section class="panel">
    <h2>Verdict</h2>
    <p><code>{html.escape(summary['review_verdict'])}</code></p>
    <p class="muted">Next: <code>{html.escape(summary['next_probe'])}</code>.</p>
  </section>
  <section class="panel"><h2>Groups</h2>{render_table(groups, GROUP_FIELDNAMES)}</section>
  <section class="panel"><h2>Candidates</h2>{render_table(candidates, CANDIDATE_FIELDNAMES)}</section>
  <script type="application/json" id="external-terminal-spatial-bridge-five-byte-non-tail-support-data">{html.escape(data_json)}</script>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize non-tail compact-control five-byte formula support.")
    parser.add_argument("--formula-summary", type=Path, default=DEFAULT_FORMULA_SUMMARY)
    parser.add_argument("--formula-variants", type=Path, default=DEFAULT_FORMULA_VARIANTS)
    parser.add_argument("--refined-hits", type=Path, default=DEFAULT_REFINED_HITS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--tail-limit", type=int, default=32)
    parser.add_argument("--local-start-limit", type=int, default=20)
    parser.add_argument("--local-ref-radius", type=int, default=32)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex External Terminal Spatial Bridge Five-Byte Non-Tail Support Probe",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, candidates, groups = build(
        read_rows(args.formula_summary),
        read_rows(args.formula_variants),
        read_rows(args.refined_hits),
        read_rows(args.manifest),
        tail_limit=args.tail_limit,
        local_start_limit=args.local_start_limit,
        local_ref_radius=args.local_ref_radius,
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(args.output / "groups.csv", GROUP_FIELDNAMES, groups)
    (args.output / "index.html").write_text(
        build_html(summary, candidates, groups, args.output, args.title),
        encoding="utf-8",
    )
    print(
        "External terminal spatial bridge five-byte non-tail support probe: "
        f"non_tail={summary['non_tail_support_rows']} "
        f"all_non_target={summary['non_tail_all_non_target_rows']} "
        f"partial={summary['non_tail_partial_non_target_rows']} "
        f"target_overlap={summary['non_tail_target_and_non_target_rows']} "
        f"promotion_ready={summary['promotion_ready_bytes']} "
        f"issues={summary['issue_rows']}"
    )
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
