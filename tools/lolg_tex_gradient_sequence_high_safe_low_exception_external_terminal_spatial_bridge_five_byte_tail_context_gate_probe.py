#!/usr/bin/env python3
"""Gate full-window compact-control five-byte variants by local/tail context."""

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
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_tail_context_gate"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_spans",
    "target_bytes",
    "formula_variant_rows",
    "full_all_non_target_rows",
    "gated_candidate_rows",
    "tail_only_candidate_rows",
    "non_tail_candidate_rows",
    "local_context_candidate_rows",
    "target_overlap_candidate_rows",
    "unique_tail_distance_groups",
    "best_tail_template",
    "best_tail_distances",
    "best_ref_distances",
    "best_samples",
    "review_verdict",
    "next_probe",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

CANDIDATE_FIELDNAMES = [
    "rank",
    "variant_rank",
    "template_key",
    "frontier_count",
    "target_rows",
    "non_target_rows",
    "min_start",
    "max_start",
    "tail_only",
    "non_tail_rows",
    "local_context_rows",
    "target_overlap",
    "tail_distances",
    "ref_distances",
    "sample_matches",
    "gate_verdict",
]

CONTEXT_FIELDNAMES = [
    "rank",
    "variant_rank",
    "template_key",
    "frontier_id",
    "ref_offset",
    "gap_len",
    "span_start",
    "span_end",
    "tail_after",
    "ref_distance",
    "local_context",
    "tail_context",
    "expected_hex",
    "expected_context_hex",
    "segment_ref_hex",
    "is_target_asset",
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


def load_bytes(path_text: str, issues: list[str], label: str) -> bytes:
    if not path_text:
        issues.append(f"missing_{label}_path")
        return b""
    try:
        return Path(path_text).read_bytes()
    except OSError as exc:
        issues.append(f"read_{label}_failed:{exc}")
        return b""


def parse_samples(sample_text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for match in SAMPLE_RE.finditer(sample_text):
        rows.append(
            {
                "frontier_id": match.group("frontier"),
                "span_start": match.group("start"),
                "span_end": match.group("end"),
                "expected_hex": match.group("hex"),
            }
        )
    return rows


def context_hex(data: bytes, start: int, end: int, radius: int = 4) -> str:
    context_start = max(0, start - radius)
    context_end = min(len(data), end + radius)
    return data[context_start:context_end].hex()


def segment_ref_hex(segment: bytes, ref: int, radius: int = 4) -> str:
    start = max(0, ref - radius)
    end = min(len(segment), ref + radius + 4)
    return segment[start:end].hex()


def fixture_rows(
    hit_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
) -> tuple[dict[str, dict[str, object]], list[str]]:
    manifest_by_key = {row_identity(row): row for row in manifest_rows}
    fixtures: dict[str, dict[str, object]] = {}
    issues: list[str] = []
    for hit in hit_rows:
        manifest = manifest_by_key.get(row_identity(hit))
        if manifest is None:
            issues.append(f"{'|'.join(row_identity(hit))}:missing_manifest")
            continue
        expected = load_bytes(manifest.get("expected_gap_path", ""), issues, "expected")
        segment = load_bytes(manifest.get("segment_gap_path", ""), issues, "segment")
        if not expected or not segment:
            continue
        fixtures[hit.get("frontier_id", "")] = {
            "hit": hit,
            "expected": expected,
            "segment": segment,
            "ref": int_value(hit, "ref_offset", -1),
        }
    return fixtures, issues


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
    fixtures, issues = fixture_rows(refined_hit_rows, manifest_rows)
    candidates = [
        row
        for row in formula_variant_rows
        if row.get("window_scope") == "full" and row.get("verdict") == "all_non_target_variant"
    ]
    candidate_rows: list[dict[str, str]] = []
    context_rows: list[dict[str, str]] = []
    tail_distance_groups: Counter[str] = Counter()
    for variant in candidates:
        samples = parse_samples(variant.get("sample_matches", ""))
        if int_value(variant, "match_rows") != len(samples):
            issues.append(f"variant_{variant.get('rank', '')}:truncated_sample_matches")
        contexts: list[dict[str, str]] = []
        for sample in samples:
            frontier_id = sample.get("frontier_id", "")
            fixture = fixtures.get(frontier_id)
            if fixture is None:
                issues.append(f"variant_{variant.get('rank', '')}:missing_fixture:{frontier_id}")
                continue
            expected = fixture["expected"]
            segment = fixture["segment"]
            hit = fixture["hit"]
            ref = fixture["ref"]
            assert isinstance(expected, bytes)
            assert isinstance(segment, bytes)
            assert isinstance(hit, dict)
            assert isinstance(ref, int)
            start = int_value(sample, "span_start")
            end = int_value(sample, "span_end")
            tail_after = len(expected) - end
            ref_distance = start - ref
            tail_context = 0 <= tail_after <= tail_limit
            local_context = start <= local_start_limit or abs(ref_distance) <= local_ref_radius
            contexts.append(
                {
                    "rank": "",
                    "variant_rank": variant.get("rank", ""),
                    "template_key": variant.get("template_key", ""),
                    "frontier_id": frontier_id,
                    "ref_offset": str(ref),
                    "gap_len": str(len(expected)),
                    "span_start": str(start),
                    "span_end": str(end),
                    "tail_after": str(tail_after),
                    "ref_distance": str(ref_distance),
                    "local_context": "1" if local_context else "0",
                    "tail_context": "1" if tail_context else "0",
                    "expected_hex": sample.get("expected_hex", ""),
                    "expected_context_hex": context_hex(expected, start, end),
                    "segment_ref_hex": segment_ref_hex(segment, ref),
                    "is_target_asset": hit.get("is_target_asset", ""),
                }
            )
        if not contexts:
            continue
        tail_only = all(row.get("tail_context") == "1" for row in contexts) and all(
            row.get("local_context") == "0" for row in contexts
        )
        non_tail_rows = [row for row in contexts if row.get("tail_context") != "1"]
        local_context_rows = [row for row in contexts if row.get("local_context") == "1"]
        target_overlap = int_value(variant, "target_rows") > 0
        if target_overlap and local_context_rows:
            gate_verdict = "target_local_overlap_candidate"
        elif local_context_rows:
            gate_verdict = "local_context_candidate"
        elif non_tail_rows:
            gate_verdict = "non_tail_full_candidate"
        elif tail_only:
            gate_verdict = "tail_only_blocked"
        else:
            gate_verdict = "mixed_context_blocked"
        tail_distances = ",".join(row.get("tail_after", "") for row in contexts)
        ref_distances = ",".join(row.get("ref_distance", "") for row in contexts)
        tail_distance_groups[tail_distances] += 1
        candidate_rows.append(
            {
                "rank": "",
                "variant_rank": variant.get("rank", ""),
                "template_key": variant.get("template_key", ""),
                "frontier_count": variant.get("frontier_count", ""),
                "target_rows": variant.get("target_rows", ""),
                "non_target_rows": variant.get("non_target_rows", ""),
                "min_start": variant.get("min_start", ""),
                "max_start": variant.get("max_start", ""),
                "tail_only": "1" if tail_only else "0",
                "non_tail_rows": str(len(non_tail_rows)),
                "local_context_rows": str(len(local_context_rows)),
                "target_overlap": "1" if target_overlap else "0",
                "tail_distances": tail_distances,
                "ref_distances": ref_distances,
                "sample_matches": variant.get("sample_matches", ""),
                "gate_verdict": gate_verdict,
            }
        )
        context_rows.extend(contexts)
    candidate_rows.sort(
        key=lambda row: (
            row.get("gate_verdict") == "tail_only_blocked",
            int_value(row, "local_context_rows") == 0,
            int_value(row, "non_tail_rows") == 0,
            int_value(row, "variant_rank"),
        )
    )
    for index, row in enumerate(candidate_rows, start=1):
        row["rank"] = str(index)
    for index, row in enumerate(context_rows, start=1):
        row["rank"] = str(index)
    tail_only_rows = [row for row in candidate_rows if row.get("gate_verdict") == "tail_only_blocked"]
    non_tail_rows = [row for row in candidate_rows if int_value(row, "non_tail_rows") > 0]
    local_context_candidates = [row for row in candidate_rows if int_value(row, "local_context_rows") > 0]
    target_overlap_candidates = [row for row in candidate_rows if row.get("target_overlap") == "1"]
    best_tail = tail_only_rows[0] if tail_only_rows else (candidate_rows[0] if candidate_rows else {})
    if issues:
        verdict = "tail_context_gate_has_issues"
        next_probe = "fix compact-control five-byte tail-context gate issues"
    elif local_context_candidates:
        verdict = "local_context_candidate_found"
        next_probe = "review local-context compact-control five-byte tail gate candidates"
    elif non_tail_rows:
        verdict = "non_tail_full_candidate_found"
        next_probe = "review non-tail compact-control five-byte full-window candidates"
    elif tail_only_rows and len(tail_only_rows) == len(candidate_rows):
        verdict = "tail_only_candidates_blocked"
        next_probe = "derive non-tail compact-control five-byte formula support beyond tail candidates"
    else:
        verdict = "mixed_full_candidate_context_blocked"
        next_probe = "split compact-control five-byte full-window candidates by context"
    summary = {
        "scope": "total",
        "candidate_mode": "external_terminal_spatial_bridge_five_byte_tail_context_gate",
        "target_spans": formula_summary.get("target_spans", "0"),
        "target_bytes": formula_summary.get("target_bytes", "0"),
        "formula_variant_rows": formula_summary.get("full_variant_rows", "0"),
        "full_all_non_target_rows": formula_summary.get("full_all_non_target_rows", str(len(candidates))),
        "gated_candidate_rows": str(len(candidate_rows)),
        "tail_only_candidate_rows": str(len(tail_only_rows)),
        "non_tail_candidate_rows": str(len(non_tail_rows)),
        "local_context_candidate_rows": str(len(local_context_candidates)),
        "target_overlap_candidate_rows": str(len(target_overlap_candidates)),
        "unique_tail_distance_groups": str(len(tail_distance_groups)),
        "best_tail_template": best_tail.get("template_key", ""),
        "best_tail_distances": best_tail.get("tail_distances", ""),
        "best_ref_distances": best_tail.get("ref_distances", ""),
        "best_samples": best_tail.get("sample_matches", ""),
        "review_verdict": verdict,
        "next_probe": next_probe,
        "promotion_candidate_bytes": "0",
        "promotion_ready_bytes": "0",
        "issue_rows": str(len(issues)),
    }
    return summary, candidate_rows, context_rows


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
    contexts: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "candidates": candidates, "contexts": contexts}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
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
    <div class="muted">Gates all-non-target full-window formula variants by tail and local context.</div>
  </header>
  <section class="stats">
    <div class="stat"><div class="muted">Gated candidates</div><div class="value">{summary['gated_candidate_rows']}</div></div>
    <div class="stat"><div class="muted">Tail-only blocked</div><div class="value warn">{summary['tail_only_candidate_rows']}</div></div>
    <div class="stat"><div class="muted">Non-tail candidates</div><div class="value">{summary['non_tail_candidate_rows']}</div></div>
    <div class="stat"><div class="muted">Local-context candidates</div><div class="value">{summary['local_context_candidate_rows']}</div></div>
    <div class="stat"><div class="muted">Promotion-ready</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2>{links}</section>
  <section class="panel">
    <h2>Verdict</h2>
    <p><code>{html.escape(summary['review_verdict'])}</code></p>
    <p class="muted">Next: <code>{html.escape(summary['next_probe'])}</code>.</p>
  </section>
  <section class="panel"><h2>Candidates</h2>{render_table(candidates, CANDIDATE_FIELDNAMES)}</section>
  <section class="panel"><h2>Contexts</h2>{render_table(contexts, CONTEXT_FIELDNAMES)}</section>
  <script type="application/json" id="external-terminal-spatial-bridge-five-byte-tail-context-gate-data">{html.escape(data_json)}</script>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Gate compact-control five-byte formula variants by tail context.")
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
        default="Lands of Lore II .tex External Terminal Spatial Bridge Five-Byte Tail Context Gate Probe",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, candidates, contexts = build(
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
    write_csv(args.output / "contexts.csv", CONTEXT_FIELDNAMES, contexts)
    (args.output / "index.html").write_text(
        build_html(summary, candidates, contexts, args.output, args.title),
        encoding="utf-8",
    )
    print(
        "External terminal spatial bridge five-byte tail context gate probe: "
        f"gated={summary['gated_candidate_rows']} "
        f"tail_only={summary['tail_only_candidate_rows']} "
        f"non_tail={summary['non_tail_candidate_rows']} "
        f"local_context={summary['local_context_candidate_rows']} "
        f"promotion_ready={summary['promotion_ready_bytes']} "
        f"issues={summary['issue_rows']}"
    )
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
