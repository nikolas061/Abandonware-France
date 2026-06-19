#!/usr/bin/env python3
"""Probe header-derived starts for the shifted 0x2a30 branch target."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path

from analyze_te_pcx_payloads import bounded_payload, load_rows
from lolg_tex_large_shifted_2a30_branch_bounded_family_probe import float_text
from lolg_tex_large_shifted_2a30_branch_singleton_header_probe import (
    int_text,
    key_for,
    read_csv,
    relative_href,
    render_table,
    write_csv,
)
from probe_te_span_decode import decode_span
from score_te_raw_layouts import row_score


DEFAULT_OUTPUT = Path("output/tex_large_shifted_2a30_branch_header_start_probe")
DEFAULT_HEADER_RECORDS = Path("output/tex_large_shifted_2a30_branch_singleton_header_probe/records.csv")
DEFAULT_HEADER_SUMMARY = Path("output/tex_large_shifted_2a30_branch_singleton_header_probe/summary.csv")
DEFAULT_SELECTOR_SUMMARY = Path("output/tex_large_shifted_2a30_branch_selector_probe/summary.csv")
DEFAULT_CATALOG = Path("reports/te_resources.tsv")
DEFAULT_FEATURES = Path("reports/te_decoder_features.tsv")

SUMMARY_FIELDNAMES = [
    "scope",
    "source_signature_rows",
    "selector_renderer_candidate_rows",
    "selector_target_best_score",
    "formula_candidate_rows",
    "formula_best_rows",
    "target_formula_rows",
    "target_best_formula",
    "target_best_marker_extra",
    "target_best_start",
    "target_best_mode",
    "target_best_score",
    "target_best_delta_vs_selector",
    "target_tail0",
    "target_tail0_half_marker_extra",
    "target_tail0_half_score",
    "target_tail0_half_mode",
    "target_tail0_half_rank",
    "target_constant64_score",
    "target_xy_sum_minus4_marker_extra",
    "target_xy_sum_minus4_score",
    "tail0_half_same_tail0_cross_rows",
    "tail0_half_same_tail0_cross_pcx_support",
    "tail0_half_same_tail0_rank1_cross_rows",
    "tail0_half_same_tail0_near_cross_rows",
    "issue_rows",
    "visual_status",
    "next_action",
]

CANDIDATE_FIELDNAMES = [
    "archive_tag",
    "pcx_name",
    "marker_pos",
    "marker",
    "is_target",
    "formula",
    "start",
    "marker_extra",
    "mode",
    "width",
    "height",
    "score",
    "filled_ratio",
    "unique_colors",
    "final_x",
    "final_y",
    "tail0",
    "target_tail0_match",
    "prologue_start_valid",
]

FORMULA_BEST_FIELDNAMES = CANDIDATE_FIELDNAMES + [
    "formula_rank",
    "score_delta_vs_record_best",
]

GROUP_FIELDNAMES = [
    "formula",
    "records",
    "target_rows",
    "rank1_rows",
    "near_delta_0_25_rows",
    "target_tail0_cross_rows",
    "target_tail0_rank1_cross_rows",
    "target_best_score",
    "target_best_marker_extra",
    "target_best_mode",
    "examples",
]


def formula_priority(formula: str) -> int:
    order = {
        "tail0_half": 0,
        "xy_sum_minus4": 1,
        "sig_after8_end": 2,
        "tail0_quarter": 3,
        "prologue_start": 4,
        "constant64": 5,
    }
    return order.get(formula, 99)


def catalog_payloads(catalog: Path) -> dict[tuple[str, str], bytes]:
    payloads: dict[tuple[str, str], bytes] = {}
    for row in load_rows(catalog):
        if row.get("ext") != ".pcx" or row.get("name", "").lower() == "palette.pcx":
            continue
        payloads[key_for(row["source_path"].parent.name, row.get("name", ""))] = bounded_payload(row)
    return payloads


def feature_lookup(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    rows: dict[tuple[str, str], dict[str, str]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            rows[key_for(row.get("level", ""), row.get("name", ""))] = row
    return rows


def tail0(row: dict[str, str]) -> int:
    parts = row.get("tail4_hex", "").split()
    return int(parts[0], 16) if parts else 0


def formula_starts(row: dict[str, str]) -> list[tuple[str, int, int, bool]]:
    marker = int_text(row.get("marker_pos"), -1)
    sig_rel = int_text(row.get("sig_rel"))
    x = int_text(row.get("rect_x"))
    y = int_text(row.get("rect_y"))
    t0 = tail0(row)
    prologue_start = int_text(row.get("prologue_start"), -1)
    prologue_extra = int_text(row.get("prologue_start_minus_marker"), -1)
    prologue_valid = prologue_start >= 0 and prologue_extra >= 0 and prologue_start - prologue_extra == marker
    starts = [
        ("sig_after8_end", marker + sig_rel + 11, sig_rel + 11, False),
        ("tail0_half", marker + t0 // 2, t0 // 2, False),
        ("tail0_quarter", marker + t0 // 4, t0 // 4, False),
        ("xy_sum_minus4", marker + x + y - 4, x + y - 4, False),
        ("constant64", marker + 64, 64, False),
    ]
    if prologue_valid:
        starts.append(("prologue_start", prologue_start, prologue_extra, True))
    return starts


def candidate_modes(row: dict[str, str]) -> list[str]:
    modes = [
        row.get("known_mode", ""),
        row.get("prologue_mode", ""),
        "filter",
        "cmd20_sig_skip4_markerknown",
        "cmd20_skip4_markerknown",
        "op4_skip2",
        "op4_skip1",
    ]
    output = []
    for mode in modes:
        if mode and mode not in output:
            output.append(mode)
    return output


def score_pixels(pixels: bytes, width: int, height: int) -> tuple[float, float]:
    score = row_score(pixels, width, height)
    filled = sum(1 for value in pixels if value) / max(1, len(pixels))
    return (999999.0 if score is None else float(score), filled)


def build_candidates(
    records: list[dict[str, str]],
    payloads: dict[tuple[str, str], bytes],
    features: dict[tuple[str, str], dict[str, str]],
    target_tail0: int,
    height: int,
    low: int,
    high: int,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for record in records:
        key = key_for(record.get("archive_tag", ""), record.get("pcx_name", ""))
        payload = payloads.get(key, b"")
        if not payload:
            continue
        feature = features.get(key, {})
        width = int_text(feature.get("width") or record.get("known_width"), 48)
        for formula, start, marker_extra, prologue_valid in formula_starts(record):
            if not (0 <= start < len(payload)):
                continue
            for mode in candidate_modes(record):
                pixels, stats = decode_span(
                    payload[start:],
                    width,
                    height,
                    mode,
                    low,
                    high,
                    return_stats=True,
                )
                score, filled = score_pixels(pixels, width, height)
                rows.append(
                    {
                        "archive_tag": record.get("archive_tag", ""),
                        "pcx_name": record.get("pcx_name", ""),
                        "marker_pos": record.get("marker_pos", ""),
                        "marker": record.get("marker", ""),
                        "is_target": record.get("is_target", ""),
                        "formula": formula,
                        "start": str(start),
                        "marker_extra": str(marker_extra),
                        "mode": mode,
                        "width": str(width),
                        "height": str(height),
                        "score": f"{score:.4f}",
                        "filled_ratio": f"{filled:.4f}",
                        "unique_colors": str(len(set(pixels))),
                        "final_x": str(stats.get("final_x", "")),
                        "final_y": str(stats.get("final_y", "")),
                        "tail0": str(tail0(record)),
                        "target_tail0_match": "yes" if tail0(record) == target_tail0 else "no",
                        "prologue_start_valid": "yes" if prologue_valid else "no",
                    }
                )
    return rows


def record_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        row.get("archive_tag", ""),
        row.get("pcx_name", "").lower(),
        row.get("marker_pos", ""),
        row.get("marker", ""),
    )


def best_formula_rows(candidates: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: defaultdict[tuple[tuple[str, str, str, str], str], list[dict[str, str]]] = defaultdict(list)
    for row in candidates:
        grouped[(record_key(row), row.get("formula", ""))].append(row)
    bests: list[dict[str, str]] = []
    for (_key, _formula), rows in grouped.items():
        bests.append(
            min(
                rows,
                key=lambda row: (
                    float_text(row.get("score"), 999999.0),
                    -float_text(row.get("filled_ratio")),
                    int_text(row.get("start")),
                    row.get("mode", ""),
                ),
            ).copy()
        )
    by_record: defaultdict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in bests:
        by_record[record_key(row)].append(row)
    output = []
    for rows in by_record.values():
        ranked = sorted(
            rows,
            key=lambda row: (
                float_text(row.get("score"), 999999.0),
                -float_text(row.get("filled_ratio")),
                formula_priority(row.get("formula", "")),
                row.get("formula", ""),
            ),
        )
        record_best = float_text(ranked[0].get("score"), 999999.0) if ranked else 0.0
        for rank, row in enumerate(ranked, start=1):
            row = row.copy()
            row["formula_rank"] = str(rank)
            row["score_delta_vs_record_best"] = f"{float_text(row.get('score'), 999999.0) - record_best:.4f}"
            output.append(row)
    output.sort(
        key=lambda row: (
            row.get("is_target") != "yes",
            row.get("archive_tag", ""),
            row.get("pcx_name", ""),
            int_text(row.get("marker_pos")),
            int_text(row.get("formula_rank")),
            row.get("formula", ""),
        )
    )
    return output


def best_row(rows: list[dict[str, str]]) -> dict[str, str]:
    return min(
        rows,
        key=lambda row: (
            float_text(row.get("score"), 999999.0),
            int_text(row.get("formula_rank")),
            formula_priority(row.get("formula", "")),
            row.get("formula", ""),
        ),
        default={},
    )


def example_text(rows: list[dict[str, str]], limit: int = 6) -> str:
    examples = []
    seen = set()
    for row in rows:
        item = (
            f"{row.get('archive_tag', '')}/{row.get('pcx_name', '')}@"
            f"{row.get('marker_pos', '')}:{row.get('marker_extra', '')}"
        )
        if item in seen:
            continue
        seen.add(item)
        examples.append(item)
        if len(examples) >= limit:
            break
    return "|".join(examples)


def cross_pcx_support(rows: list[dict[str, str]]) -> int:
    return len({(row.get("archive_tag", ""), row.get("pcx_name", "").lower()) for row in rows})


def build_groups(formula_bests: list[dict[str, str]], target_tail0: str) -> list[dict[str, str]]:
    grouped: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    for row in formula_bests:
        grouped[row.get("formula", "")].append(row)
    output = []
    for formula, rows in sorted(grouped.items()):
        target_rows = [row for row in rows if row.get("is_target") == "yes"]
        target_best = best_row(target_rows)
        target_tail0_cross = [
            row for row in rows if row.get("is_target") != "yes" and row.get("tail0") == target_tail0
        ]
        output.append(
            {
                "formula": formula,
                "records": str(len(rows)),
                "target_rows": str(len(target_rows)),
                "rank1_rows": str(sum(1 for row in rows if row.get("formula_rank") == "1")),
                "near_delta_0_25_rows": str(
                    sum(1 for row in rows if float_text(row.get("score_delta_vs_record_best")) <= 0.25)
                ),
                "target_tail0_cross_rows": str(len(target_tail0_cross)),
                "target_tail0_rank1_cross_rows": str(
                    sum(1 for row in target_tail0_cross if row.get("formula_rank") == "1")
                ),
                "target_best_score": target_best.get("score", ""),
                "target_best_marker_extra": target_best.get("marker_extra", ""),
                "target_best_mode": target_best.get("mode", ""),
                "examples": example_text(rows),
            }
        )
    return output


def formula_row(rows: list[dict[str, str]], formula: str, is_target: bool = True) -> dict[str, str]:
    candidates = [
        row
        for row in rows
        if row.get("formula") == formula and (row.get("is_target") == "yes") == is_target
    ]
    return best_row(candidates)


def build_summary(
    header_summary: dict[str, str],
    selector_summary: dict[str, str],
    candidates: list[dict[str, str]],
    formula_bests: list[dict[str, str]],
    groups: list[dict[str, str]],
    target_tail0: int,
    issues: list[str],
) -> dict[str, str]:
    target_rows = [row for row in formula_bests if row.get("is_target") == "yes"]
    target_best = best_row(target_rows)
    target_tail0_half = formula_row(formula_bests, "tail0_half")
    target_constant64 = formula_row(formula_bests, "constant64")
    target_xy = formula_row(formula_bests, "xy_sum_minus4")
    tail0_half_cross = [
        row
        for row in formula_bests
        if row.get("formula") == "tail0_half"
        and row.get("is_target") != "yes"
        and row.get("tail0") == str(target_tail0)
    ]
    target_score = float_text(target_best.get("score"), 999999.0)
    selector_score = float_text(selector_summary.get("target_best_score"), 999999.0)
    target_delta = target_score - selector_score
    if issues:
        visual_status = "blocked_header_start_probe_issues"
        next_action = "fix shifted 0x2a30 header start probe inputs"
    elif target_best.get("formula") == "tail0_half" and abs(target_delta) <= 0.001:
        visual_status = "blocked_header_tail0_half_start_supported_renderer_noisy"
        next_action = (
            "promote header-derived tail0/2 start guard for shifted 0x2a30 branch before renderer grammar; "
            f"target recovers selector extra{target_best.get('marker_extra', '')} with "
            f"{cross_pcx_support(tail0_half_cross)} same-tail0 cross-PCX support, but renderer remains noisy"
        )
    else:
        visual_status = "blocked_header_start_formula_not_resolved"
        next_action = "derive stronger shifted 0x2a30 header start formula before renderer promotion"
    tail0_half_group = next((row for row in groups if row.get("formula") == "tail0_half"), {})
    return {
        "scope": "total",
        "source_signature_rows": header_summary.get("signature_rows", ""),
        "selector_renderer_candidate_rows": selector_summary.get("renderer_candidate_rows", ""),
        "selector_target_best_score": selector_summary.get("target_best_score", ""),
        "formula_candidate_rows": str(len(candidates)),
        "formula_best_rows": str(len(formula_bests)),
        "target_formula_rows": str(len(target_rows)),
        "target_best_formula": target_best.get("formula", ""),
        "target_best_marker_extra": target_best.get("marker_extra", ""),
        "target_best_start": target_best.get("start", ""),
        "target_best_mode": target_best.get("mode", ""),
        "target_best_score": target_best.get("score", ""),
        "target_best_delta_vs_selector": f"{target_delta:.4f}",
        "target_tail0": str(target_tail0),
        "target_tail0_half_marker_extra": target_tail0_half.get("marker_extra", ""),
        "target_tail0_half_score": target_tail0_half.get("score", ""),
        "target_tail0_half_mode": target_tail0_half.get("mode", ""),
        "target_tail0_half_rank": target_tail0_half.get("formula_rank", ""),
        "target_constant64_score": target_constant64.get("score", ""),
        "target_xy_sum_minus4_marker_extra": target_xy.get("marker_extra", ""),
        "target_xy_sum_minus4_score": target_xy.get("score", ""),
        "tail0_half_same_tail0_cross_rows": str(len(tail0_half_cross)),
        "tail0_half_same_tail0_cross_pcx_support": str(cross_pcx_support(tail0_half_cross)),
        "tail0_half_same_tail0_rank1_cross_rows": str(
            sum(1 for row in tail0_half_cross if row.get("formula_rank") == "1")
        ),
        "tail0_half_same_tail0_near_cross_rows": tail0_half_group.get("near_delta_0_25_rows", ""),
        "issue_rows": str(len(issues)),
        "visual_status": visual_status,
        "next_action": next_action,
    }


def build_html(
    summary: dict[str, str],
    groups: list[dict[str, str]],
    formula_bests: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "groups": groups, "formula_bests": formula_bests}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("formula_candidates.csv", output_dir / "formula_candidates.csv"),
            ("formula_bests.csv", output_dir / "formula_bests.csv"),
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
:root {{ color-scheme: dark; --bg: #101214; --panel: #171b1f; --line: #2b3339; --text: #edf2f4; --muted: #aab5ba; --accent: #7cc7ff; }}
body {{ margin: 0; background: var(--bg); color: var(--text); font: 14px/1.45 system-ui, -apple-system, Segoe UI, sans-serif; }}
main {{ max-width: 1500px; margin: 0 auto; padding: 28px; }}
h1 {{ font-size: 24px; margin: 0 0 8px; }}
h2 {{ font-size: 18px; margin: 26px 0 10px; }}
.muted {{ color: var(--muted); }}
a {{ color: var(--accent); text-decoration: none; margin-right: 10px; }}
table {{ width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--line); margin-top: 10px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; font-size: 12px; }}
th {{ color: var(--muted); background: #20262b; }}
td {{ max-width: 520px; overflow-wrap: anywhere; }}
</style>
</head>
<body>
<main>
<h1>{html.escape(title)}</h1>
<p class="muted">Header-derived start formulas for marker-local 04a900 records. No renderer is promoted here.</p>
<p>{links}</p>
<h2>Summary</h2>
{render_table([summary], SUMMARY_FIELDNAMES)}
<h2>Formula Groups</h2>
{render_table(groups, GROUP_FIELDNAMES)}
<h2>Formula Bests</h2>
{render_table(formula_bests, FORMULA_BEST_FIELDNAMES)}
</main>
<script>const TEX_LARGE_SHIFTED_2A30_BRANCH_HEADER_START_PROBE = {data_json};</script>
</body>
</html>
"""


def write_report(args: argparse.Namespace) -> tuple[dict[str, str], list[str]]:
    args.output.mkdir(parents=True, exist_ok=True)
    issues: list[str] = []
    records = read_csv(args.header_records)
    header_summary = (read_csv(args.header_summary) or [{}])[0]
    selector_summary = (read_csv(args.selector_summary) or [{}])[0]
    if not records:
        issues.append("missing_header_records")
    if not header_summary:
        issues.append("missing_header_summary")
    if not selector_summary:
        issues.append("missing_selector_summary")
    target = next((row for row in records if row.get("is_target") == "yes"), {})
    if not target:
        issues.append("missing_target_header_record")
    target_tail0 = tail0(target) if target else 0
    payloads = catalog_payloads(args.catalog)
    features = feature_lookup(args.features)
    candidates = build_candidates(records, payloads, features, target_tail0, args.height, args.low, args.high)
    formula_bests = best_formula_rows(candidates)
    groups = build_groups(formula_bests, str(target_tail0))
    summary = build_summary(header_summary, selector_summary, candidates, formula_bests, groups, target_tail0, issues)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "formula_candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(args.output / "formula_bests.csv", FORMULA_BEST_FIELDNAMES, formula_bests)
    write_csv(args.output / "groups.csv", GROUP_FIELDNAMES, groups)
    (args.output / "index.html").write_text(
        build_html(summary, groups, formula_bests, args.output, args.title),
        encoding="utf-8",
    )
    return summary, issues


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe header-derived starts for shifted 0x2a30 branch 04a900 records."
    )
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--header-records", type=Path, default=DEFAULT_HEADER_RECORDS)
    parser.add_argument("--header-summary", type=Path, default=DEFAULT_HEADER_SUMMARY)
    parser.add_argument("--selector-summary", type=Path, default=DEFAULT_SELECTOR_SUMMARY)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES)
    parser.add_argument("--height", type=int, default=128)
    parser.add_argument("--low", type=lambda value: int(value, 0), default=0x30)
    parser.add_argument("--high", type=lambda value: int(value, 0), default=0xBF)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Large Shifted 2a30 Branch Header Start Probe",
    )
    args = parser.parse_args()

    summary, issues = write_report(args)
    print(f"Formula candidates: {summary['formula_candidate_rows']}")
    print(f"Target best formula: {summary['target_best_formula']} extra {summary['target_best_marker_extra']}")
    print(f"Target best score: {summary['target_best_score']} delta {summary['target_best_delta_vs_selector']}")
    print(f"tail0/2 same-tail0 cross support: {summary['tail0_half_same_tail0_cross_pcx_support']}")
    print(f"Issue rows: {summary['issue_rows']}")
    print(f"Visual status: {summary['visual_status']}")
    print(f"Next action: {summary['next_action']}")
    print(f"HTML: {args.output / 'index.html'}")
    if issues:
        print("Issues: " + "; ".join(issues))


if __name__ == "__main__":
    main()
