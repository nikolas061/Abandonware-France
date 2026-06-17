#!/usr/bin/env python3
"""Search compact-control five-byte formula variants for refined support rows."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from itertools import product
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv


DEFAULT_REFINED_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_refined_support/summary.csv"
)
DEFAULT_REFINED_HITS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_refined_support/hits.csv"
)
DEFAULT_MANIFEST = Path("output/tex_gap_rule_fixtures_expanded/manifest.csv")
DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_formula_variant"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_spans",
    "target_bytes",
    "refined_pair_rows",
    "refined_non_target_rows",
    "local_variant_rows",
    "local_multi_frontier_rows",
    "local_all_non_target_rows",
    "local_target_rows",
    "full_variant_rows",
    "full_all_non_target_rows",
    "full_target_rows",
    "best_local_template",
    "best_local_frontiers",
    "best_local_samples",
    "best_full_template",
    "best_full_frontiers",
    "best_full_samples",
    "review_verdict",
    "next_probe",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

VARIANT_FIELDNAMES = [
    "rank",
    "window_scope",
    "template_key",
    "frontier_count",
    "match_rows",
    "target_frontiers",
    "non_target_frontiers",
    "target_rows",
    "non_target_rows",
    "zero_heavy_rows",
    "min_start",
    "max_start",
    "sample_matches",
    "verdict",
]

MATCH_FIELDNAMES = [
    "rank",
    "window_scope",
    "template_key",
    "archive",
    "archive_tag",
    "pcx_name",
    "frontier_id",
    "ref_offset",
    "span_start",
    "span_end",
    "anchor_rel",
    "expected_hex",
    "is_target_asset",
    "zero_heavy",
]


SEGMENT_OFFSETS = (-4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 6)
CONSTANTS = (0, 0x53, 0x54, 0x55, 0x56, 0x57, 0x6A, 0x6B, 0xA7, 0xA8, 0xA9)
ANCHOR_RELS = (-6, -5, -4, -3, -2, -1, 0, 1, 2)


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


def candidate_atoms_for_byte(
    value: int,
    anchor: int,
    segment: bytes,
    ref: int,
    *,
    per_position_limit: int,
) -> list[str]:
    candidates: list[tuple[int, str]] = []
    for delta in (-3, -2, -1, 0, 1, 2, 3):
        if ((anchor + delta) & 0xFF) == value:
            candidates.append((abs(delta), f"a{delta:+d}"))
    for segment_rel in SEGMENT_OFFSETS:
        index = ref + segment_rel
        if index < 0 or index >= len(segment):
            continue
        for delta in (-2, -1, 0, 1, 2):
            if ((segment[index] + delta) & 0xFF) == value:
                preference = 1 if segment_rel in (2, 3, 1, 4) else 2
                candidates.append((preference * 10 + abs(delta), f"s{segment_rel:+d}{delta:+d}"))
    for constant in CONSTANTS:
        if constant == value:
            candidates.append((50, f"c{constant:02x}"))
    return [name for _score, name in sorted(set(candidates))[:per_position_limit]]


def zero_heavy(expected: bytes) -> bool:
    return expected.count(0) >= 2


def load_refined_rows(
    hit_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
) -> tuple[list[dict[str, object]], list[str]]:
    manifest_by_key = {row_identity(row): row for row in manifest_rows}
    rows: list[dict[str, object]] = []
    issues: list[str] = []
    for hit in hit_rows:
        manifest = manifest_by_key.get(row_identity(hit))
        if manifest is None:
            issues.append(f"{'|'.join(row_identity(hit))}:missing_manifest")
            continue
        segment = load_bytes(manifest.get("segment_gap_path", ""), issues, "segment")
        expected = load_bytes(manifest.get("expected_gap_path", ""), issues, "expected")
        if not segment or not expected:
            continue
        rows.append({"hit": hit, "segment": segment, "expected": expected, "ref": int_value(hit, "ref_offset", -1)})
    return rows, issues


def add_template_match(
    templates: dict[str, dict[str, object]],
    *,
    window_scope: str,
    template_key: str,
    hit: dict[str, str],
    start: int,
    anchor_rel: int,
    expected: bytes,
) -> None:
    data = templates.setdefault(
        f"{window_scope}|{template_key}",
        {
            "window_scope": window_scope,
            "template_key": template_key,
            "matches": [],
            "frontiers": set(),
            "target_frontiers": set(),
            "non_target_frontiers": set(),
        },
    )
    match = {
        "window_scope": window_scope,
        "template_key": template_key,
        "archive": hit.get("archive", ""),
        "archive_tag": hit.get("archive_tag", ""),
        "pcx_name": hit.get("pcx_name", ""),
        "frontier_id": hit.get("frontier_id", ""),
        "ref_offset": hit.get("ref_offset", ""),
        "span_start": str(start),
        "span_end": str(start + 5),
        "anchor_rel": str(anchor_rel),
        "expected_hex": expected.hex(),
        "is_target_asset": hit.get("is_target_asset", ""),
        "zero_heavy": "1" if zero_heavy(expected) else "0",
    }
    data["matches"].append(match)
    data["frontiers"].add(hit.get("frontier_id", ""))
    if hit.get("is_target_asset") == "1":
        data["target_frontiers"].add(hit.get("frontier_id", ""))
    else:
        data["non_target_frontiers"].add(hit.get("frontier_id", ""))


def search_variants(
    refined_rows: list[dict[str, object]],
    *,
    window_scope: str,
    local_start_limit: int | None,
    per_position_limit: int,
    max_combinations: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    templates: dict[str, dict[str, object]] = {}
    for refined in refined_rows:
        hit = refined["hit"]
        segment = refined["segment"]
        expected = refined["expected"]
        ref = refined["ref"]
        assert isinstance(hit, dict)
        assert isinstance(segment, bytes)
        assert isinstance(expected, bytes)
        assert isinstance(ref, int)
        end_limit = len(expected) - 4
        if local_start_limit is not None:
            end_limit = min(end_limit, local_start_limit)
        for start in range(2, end_limit):
            expected_window = expected[start : start + 5]
            for anchor_rel in ANCHOR_RELS:
                anchor_index = start + anchor_rel
                if anchor_index < 0 or anchor_index >= len(expected):
                    continue
                anchor = expected[anchor_index]
                candidates = [
                    candidate_atoms_for_byte(
                        value,
                        anchor,
                        segment,
                        ref,
                        per_position_limit=per_position_limit,
                    )
                    for value in expected_window
                ]
                if not all(candidates):
                    continue
                combinations = 1
                for values in candidates:
                    combinations *= len(values)
                if combinations > max_combinations:
                    candidates = [values[: max(1, per_position_limit // 2)] for values in candidates]
                for template in product(*candidates):
                    if not any(atom.startswith("s") for atom in template):
                        continue
                    add_template_match(
                        templates,
                        window_scope=window_scope,
                        template_key=f"ar{anchor_rel:+d}|" + "|".join(template),
                        hit=hit,
                        start=start,
                        anchor_rel=anchor_rel,
                        expected=expected_window,
                    )
    variant_rows: list[dict[str, str]] = []
    match_rows: list[dict[str, str]] = []
    for data in templates.values():
        matches = data["matches"]
        frontiers = data["frontiers"]
        if len(frontiers) < 2:
            continue
        target_frontiers = data["target_frontiers"]
        non_target_frontiers = data["non_target_frontiers"]
        target_rows = [row for row in matches if row.get("is_target_asset") == "1"]
        non_target_rows = [row for row in matches if row.get("is_target_asset") != "1"]
        zero_rows = [row for row in matches if row.get("zero_heavy") == "1"]
        starts = [int_value(row, "span_start") for row in matches]
        if target_frontiers and non_target_frontiers:
            verdict = "target_and_non_target_variant"
        elif len(non_target_frontiers) >= 3:
            verdict = "all_non_target_variant"
        elif len(non_target_frontiers) >= 2 and len(zero_rows) == len(matches):
            verdict = "zero_tail_non_target_variant"
        elif len(non_target_frontiers) >= 2:
            verdict = "partial_non_target_variant"
        else:
            verdict = "target_only_variant"
        sample_matches = ";".join(
            f"{row.get('frontier_id')}:{row.get('span_start')}-{row.get('span_end')}:{row.get('expected_hex')}"
            for row in matches[:6]
        )
        variant_rows.append(
            {
                "rank": "",
                "window_scope": str(data["window_scope"]),
                "template_key": str(data["template_key"]),
                "frontier_count": str(len(frontiers)),
                "match_rows": str(len(matches)),
                "target_frontiers": ",".join(sorted(target_frontiers, key=lambda value: int(value or 0))),
                "non_target_frontiers": ",".join(sorted(non_target_frontiers, key=lambda value: int(value or 0))),
                "target_rows": str(len(target_rows)),
                "non_target_rows": str(len(non_target_rows)),
                "zero_heavy_rows": str(len(zero_rows)),
                "min_start": str(min(starts)),
                "max_start": str(max(starts)),
                "sample_matches": sample_matches,
                "verdict": verdict,
            }
        )
        match_rows.extend(matches[:6])
    variant_rows.sort(
        key=lambda row: (
            row.get("window_scope") != "local",
            row.get("verdict") == "zero_tail_non_target_variant",
            -int_value(row, "frontier_count"),
            -int_value(row, "non_target_rows"),
            int_value(row, "target_rows") == 0,
            int_value(row, "min_start"),
            row.get("template_key", ""),
        )
    )
    for index, row in enumerate(variant_rows, start=1):
        row["rank"] = str(index)
    for index, row in enumerate(match_rows, start=1):
        row["rank"] = str(index)
    return variant_rows, match_rows


def best_row(rows: list[dict[str, str]], scope: str) -> dict[str, str]:
    scoped = [row for row in rows if row.get("window_scope") == scope]
    return scoped[0] if scoped else {}


def build(
    refined_summary_rows: list[dict[str, str]],
    refined_hit_rows: list[dict[str, str]],
    manifest_rows: list[dict[str, str]],
    *,
    local_start_limit: int,
    per_position_limit: int,
    max_combinations: int,
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    refined_summary = refined_summary_rows[0] if refined_summary_rows else {}
    refined_rows, issues = load_refined_rows(refined_hit_rows, manifest_rows)
    local_variants, local_matches = search_variants(
        refined_rows,
        window_scope="local",
        local_start_limit=local_start_limit,
        per_position_limit=per_position_limit,
        max_combinations=max_combinations,
    )
    full_variants, full_matches = search_variants(
        refined_rows,
        window_scope="full",
        local_start_limit=None,
        per_position_limit=per_position_limit,
        max_combinations=max_combinations,
    )
    variants = local_variants + full_variants
    variants.sort(
        key=lambda row: (
            row.get("window_scope") != "local",
            row.get("verdict") == "zero_tail_non_target_variant",
            -int_value(row, "frontier_count"),
            -int_value(row, "non_target_rows"),
            int_value(row, "min_start"),
            row.get("template_key", ""),
        )
    )
    for index, row in enumerate(variants, start=1):
        row["rank"] = str(index)
    matches = local_matches + full_matches
    for index, row in enumerate(matches, start=1):
        row["rank"] = str(index)
    local_all_non_target = [
        row for row in variants if row.get("window_scope") == "local" and row.get("verdict") == "all_non_target_variant"
    ]
    local_target = [row for row in variants if row.get("window_scope") == "local" and int_value(row, "target_rows") > 0]
    full_all_non_target = [
        row for row in variants if row.get("window_scope") == "full" and row.get("verdict") == "all_non_target_variant"
    ]
    full_target = [row for row in variants if row.get("window_scope") == "full" and int_value(row, "target_rows") > 0]
    best_local = best_row(variants, "local")
    best_full = best_row(variants, "full")
    if local_all_non_target:
        verdict = "local_all_non_target_variant_candidate"
        next_probe = "review local compact-control five-byte formula variants against target context"
    elif full_all_non_target:
        verdict = "full_tail_variant_only"
        next_probe = "gate compact-control formula variants by local/tail context before promotion"
    elif best_local:
        verdict = "local_zero_tail_or_partial_variant_only"
        next_probe = "derive non-tail local compact-control five-byte variant"
    else:
        verdict = "no_shared_compact_control_variant"
        next_probe = "expand compact-control five-byte formula atoms beyond current anchor/segment family"
    summary = {
        "scope": "total",
        "candidate_mode": "external_terminal_spatial_bridge_five_byte_formula_variant",
        "target_spans": refined_summary.get("target_spans", "0"),
        "target_bytes": refined_summary.get("target_bytes", "0"),
        "refined_pair_rows": refined_summary.get("refined_pair_any_rows", str(len(refined_hit_rows))),
        "refined_non_target_rows": refined_summary.get("refined_pair_any_non_target_rows", "0"),
        "local_variant_rows": str(sum(1 for row in variants if row.get("window_scope") == "local")),
        "local_multi_frontier_rows": str(
            sum(1 for row in variants if row.get("window_scope") == "local" and int_value(row, "frontier_count") >= 2)
        ),
        "local_all_non_target_rows": str(len(local_all_non_target)),
        "local_target_rows": str(len(local_target)),
        "full_variant_rows": str(sum(1 for row in variants if row.get("window_scope") == "full")),
        "full_all_non_target_rows": str(len(full_all_non_target)),
        "full_target_rows": str(len(full_target)),
        "best_local_template": best_local.get("template_key", ""),
        "best_local_frontiers": best_local.get("non_target_frontiers", ""),
        "best_local_samples": best_local.get("sample_matches", ""),
        "best_full_template": best_full.get("template_key", ""),
        "best_full_frontiers": best_full.get("non_target_frontiers", ""),
        "best_full_samples": best_full.get("sample_matches", ""),
        "review_verdict": verdict,
        "next_probe": next_probe,
        "promotion_candidate_bytes": "0",
        "promotion_ready_bytes": "0",
        "issue_rows": str(len(issues)),
    }
    return summary, variants, matches


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 260) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    variants: list[dict[str, str]],
    matches: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "variants": variants, "matches": matches}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("variants.csv", output_dir / "variants.csv"),
            ("matches.csv", output_dir / "matches.csv"),
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
    <div class="muted">Separates local compact-control formula variants from full-gap/tail candidates.</div>
  </header>
  <section class="stats">
    <div class="stat"><div class="muted">Local variants</div><div class="value">{summary['local_variant_rows']}</div></div>
    <div class="stat"><div class="muted">Local all non-target</div><div class="value warn">{summary['local_all_non_target_rows']}</div></div>
    <div class="stat"><div class="muted">Full all non-target</div><div class="value">{summary['full_all_non_target_rows']}</div></div>
    <div class="stat"><div class="muted">Target variants</div><div class="value warn">{summary['local_target_rows']}/{summary['full_target_rows']}</div></div>
    <div class="stat"><div class="muted">Promotion-ready</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2>{links}</section>
  <section class="panel">
    <h2>Verdict</h2>
    <p><code>{html.escape(summary['review_verdict'])}</code></p>
    <p class="muted">Next: <code>{html.escape(summary['next_probe'])}</code>.</p>
  </section>
  <section class="panel"><h2>Variants</h2>{render_table(variants, VARIANT_FIELDNAMES)}</section>
  <section class="panel"><h2>Matches</h2>{render_table(matches, MATCH_FIELDNAMES)}</section>
  <script type="application/json" id="external-terminal-spatial-bridge-five-byte-formula-variant-data">{html.escape(data_json)}</script>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Search compact-control formula variants for the five-byte guard.")
    parser.add_argument("--refined-summary", type=Path, default=DEFAULT_REFINED_SUMMARY)
    parser.add_argument("--refined-hits", type=Path, default=DEFAULT_REFINED_HITS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--local-start-limit", type=int, default=20)
    parser.add_argument("--per-position-limit", type=int, default=8)
    parser.add_argument("--max-combinations", type=int, default=50000)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex External Terminal Spatial Bridge Five-Byte Formula Variant Probe",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, variants, matches = build(
        read_rows(args.refined_summary),
        read_rows(args.refined_hits),
        read_rows(args.manifest),
        local_start_limit=args.local_start_limit,
        per_position_limit=args.per_position_limit,
        max_combinations=args.max_combinations,
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "variants.csv", VARIANT_FIELDNAMES, variants)
    write_csv(args.output / "matches.csv", MATCH_FIELDNAMES, matches)
    (args.output / "index.html").write_text(
        build_html(summary, variants, matches, args.output, args.title),
        encoding="utf-8",
    )
    print(
        "External terminal spatial bridge five-byte formula variant probe: "
        f"local_variants={summary['local_variant_rows']} "
        f"local_all_non_target={summary['local_all_non_target_rows']} "
        f"full_all_non_target={summary['full_all_non_target_rows']} "
        f"promotion_ready={summary['promotion_ready_bytes']} "
        f"issues={summary['issue_rows']}"
    )
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
