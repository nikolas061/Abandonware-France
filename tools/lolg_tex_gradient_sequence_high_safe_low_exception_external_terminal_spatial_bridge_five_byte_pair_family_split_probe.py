#!/usr/bin/env python3
"""Split non-tail compact-control five-byte support by frontier-pair family."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv


DEFAULT_NON_TAIL_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_non_tail_support/summary.csv"
)
DEFAULT_NON_TAIL_CANDIDATES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_non_tail_support/candidates.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_pair_family_split"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_spans",
    "target_bytes",
    "non_tail_support_rows",
    "family_rows",
    "partial_family_rows",
    "target_overlap_family_rows",
    "local_family_rows",
    "all_non_target_family_rows",
    "required_non_target_frontiers",
    "dominant_family",
    "dominant_family_rows",
    "dominant_family_missing_frontiers",
    "weak_pair_families",
    "exact_template_overlap_rows",
    "shape_overlap_rows",
    "cross_family_exact_all_non_target_rows",
    "best_exact_overlap_template",
    "best_exact_overlap_families",
    "best_exact_overlap_frontiers",
    "review_verdict",
    "next_probe",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

FAMILY_FIELDNAMES = [
    "rank",
    "family_key",
    "candidate_classes",
    "variant_rows",
    "target_rows",
    "non_target_rows",
    "sample_non_tail_rows",
    "sample_local_rows",
    "sample_tail_rows",
    "template_rows",
    "shape_rows",
    "top_atom_prefixes",
    "top_atoms",
    "best_variant_rank",
    "best_template",
    "best_samples",
    "family_verdict",
]

OVERLAP_FIELDNAMES = [
    "rank",
    "overlap_type",
    "key",
    "family_count",
    "families",
    "union_non_target_frontiers",
    "candidate_rows",
    "target_rows",
    "sample_local_rows",
    "best_variant_rank",
    "best_samples",
    "overlap_verdict",
]

ATOM_FIELDNAMES = [
    "rank",
    "family_key",
    "atom_position",
    "atom",
    "atom_rows",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def int_value(row: dict[str, str], field: str, default: int = 0) -> int:
    try:
        return int(row.get(field, ""))
    except (TypeError, ValueError):
        return default


def frontier_set(text: str) -> set[str]:
    return {value for value in text.split(",") if value}


def sort_frontiers(values: set[str]) -> list[str]:
    return sorted(values, key=lambda value: int(value) if value.isdigit() else value)


def template_body(template_key: str) -> str:
    parts = template_key.split("|")
    return "|".join(parts[1:]) if len(parts) > 1 else template_key


def template_shape(template_key: str) -> str:
    body = template_body(template_key)
    return "|".join(atom[:1] for atom in body.split("|") if atom)


def family_verdict(row_count: int, family: set[str], required: set[str], classes: set[str]) -> str:
    if required and required.issubset(family) and "partial_non_target_non_tail" in classes:
        return "all_non_target_family_candidate"
    if "partial_non_target_non_tail" in classes and row_count >= 100:
        return "dominant_partial_family"
    if "partial_non_target_non_tail" in classes and "target_overlap_non_tail" in classes:
        return "weak_partial_target_overlap_family"
    if "partial_non_target_non_tail" in classes:
        return "weak_partial_family"
    if "local_nonzero_target_pair" in classes:
        return "local_target_pair_family"
    if "target_overlap_non_tail" in classes:
        return "target_overlap_family"
    return "weak_partial_family"


def overlap_verdict(frontiers: set[str], required: set[str], has_target: bool) -> str:
    if required and required.issubset(frontiers):
        return "all_non_target_overlap_candidate"
    if has_target:
        return "target_overlap_bridge"
    if len(frontiers) >= 2:
        return "partial_frontier_overlap"
    return "single_frontier_overlap"


def build_family_rows(candidate_rows: list[dict[str, str]], required: set[str]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in candidate_rows:
        grouped[row.get("non_target_frontiers", "")].append(row)
    family_rows: list[dict[str, str]] = []
    atom_rows: list[dict[str, str]] = []
    for family_key, rows in grouped.items():
        classes = {row.get("candidate_class", "") for row in rows}
        family = frontier_set(family_key)
        templates = {row.get("template_key", "") for row in rows}
        shapes = {template_shape(row.get("template_key", "")) for row in rows}
        atom_prefixes: Counter[str] = Counter()
        atom_counts: dict[int, Counter[str]] = defaultdict(Counter)
        atom_total: Counter[str] = Counter()
        for row in rows:
            atoms = [atom for atom in template_body(row.get("template_key", "")).split("|") if atom]
            for index, atom in enumerate(atoms, start=1):
                atom_prefixes[atom[:1]] += 1
                atom_counts[index][atom] += 1
                atom_total[atom] += 1
        for position, counts in atom_counts.items():
            for atom, count in counts.most_common(8):
                atom_rows.append(
                    {
                        "rank": "",
                        "family_key": family_key,
                        "atom_position": str(position),
                        "atom": atom,
                        "atom_rows": str(count),
                    }
                )
        best = min(rows, key=lambda row: int_value(row, "variant_rank"))
        family_rows.append(
            {
                "rank": "",
                "family_key": family_key,
                "candidate_classes": ",".join(sorted(classes)),
                "variant_rows": str(len(rows)),
                "target_rows": str(sum(int_value(row, "target_rows") for row in rows)),
                "non_target_rows": str(sum(int_value(row, "non_target_rows") for row in rows)),
                "sample_non_tail_rows": str(sum(int_value(row, "sample_non_tail_rows") for row in rows)),
                "sample_local_rows": str(sum(int_value(row, "sample_local_rows") for row in rows)),
                "sample_tail_rows": str(sum(int_value(row, "sample_tail_rows") for row in rows)),
                "template_rows": str(len(templates)),
                "shape_rows": str(len(shapes)),
                "top_atom_prefixes": ";".join(f"{key}:{value}" for key, value in atom_prefixes.most_common()),
                "top_atoms": ";".join(f"{key}:{value}" for key, value in atom_total.most_common(8)),
                "best_variant_rank": best.get("variant_rank", ""),
                "best_template": best.get("template_key", ""),
                "best_samples": best.get("sample_matches", ""),
                "family_verdict": family_verdict(len(rows), family, required, classes),
            }
        )
    family_rows.sort(
        key=lambda row: (
            row.get("family_verdict") != "all_non_target_family_candidate",
            row.get("family_verdict") != "dominant_partial_family",
            row.get("family_verdict") != "local_target_pair_family",
            -int_value(row, "variant_rows"),
            row.get("family_key", ""),
        )
    )
    for index, row in enumerate(family_rows, start=1):
        row["rank"] = str(index)
    atom_rows.sort(key=lambda row: (row.get("family_key", ""), int_value(row, "atom_position"), -int_value(row, "atom_rows")))
    for index, row in enumerate(atom_rows, start=1):
        row["rank"] = str(index)
    return family_rows, atom_rows


def build_overlap_rows(candidate_rows: list[dict[str, str]], required: set[str]) -> list[dict[str, str]]:
    overlap_rows: list[dict[str, str]] = []
    for overlap_type, key_func in (
        ("exact_template", lambda row: template_body(row.get("template_key", ""))),
        ("atom_shape", lambda row: template_shape(row.get("template_key", ""))),
    ):
        grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
        for row in candidate_rows:
            grouped[key_func(row)].append(row)
        for key, rows in grouped.items():
            families = {row.get("non_target_frontiers", "") for row in rows}
            if len(families) < 2:
                continue
            union_frontiers: set[str] = set()
            for family in families:
                union_frontiers.update(frontier_set(family))
            best = min(rows, key=lambda row: int_value(row, "variant_rank"))
            has_target = any(int_value(row, "target_rows") > 0 for row in rows)
            overlap_rows.append(
                {
                    "rank": "",
                    "overlap_type": overlap_type,
                    "key": key,
                    "family_count": str(len(families)),
                    "families": ";".join(sorted(families)),
                    "union_non_target_frontiers": ",".join(sort_frontiers(union_frontiers)),
                    "candidate_rows": str(len(rows)),
                    "target_rows": str(sum(int_value(row, "target_rows") for row in rows)),
                    "sample_local_rows": str(sum(int_value(row, "sample_local_rows") for row in rows)),
                    "best_variant_rank": best.get("variant_rank", ""),
                    "best_samples": best.get("sample_matches", ""),
                    "overlap_verdict": overlap_verdict(union_frontiers, required, has_target),
                }
            )
    overlap_rows.sort(
        key=lambda row: (
            row.get("overlap_verdict") != "all_non_target_overlap_candidate",
            row.get("overlap_type") != "exact_template",
            -int_value(row, "family_count"),
            int_value(row, "best_variant_rank"),
            row.get("key", ""),
        )
    )
    for index, row in enumerate(overlap_rows, start=1):
        row["rank"] = str(index)
    return overlap_rows


def build(
    non_tail_summary_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    non_tail_summary = non_tail_summary_rows[0] if non_tail_summary_rows else {}
    required: set[str] = set()
    for row in candidate_rows:
        required.update(frontier_set(row.get("non_target_frontiers", "")))
    family_rows, atom_rows = build_family_rows(candidate_rows, required)
    overlap_rows = build_overlap_rows(candidate_rows, required)
    all_non_target_families = [
        row for row in family_rows if row.get("family_verdict") == "all_non_target_family_candidate"
    ]
    dominant_families = [row for row in family_rows if row.get("family_verdict") == "dominant_partial_family"]
    weak_pair_families = [
        row
        for row in family_rows
        if "partial_non_target_non_tail" in row.get("candidate_classes", "")
        and int_value(row, "variant_rows") < 100
        and len(frontier_set(row.get("family_key", ""))) >= 2
    ]
    exact_overlaps = [row for row in overlap_rows if row.get("overlap_type") == "exact_template"]
    shape_overlaps = [row for row in overlap_rows if row.get("overlap_type") == "atom_shape"]
    exact_all_non_target = [
        row for row in exact_overlaps if row.get("overlap_verdict") == "all_non_target_overlap_candidate"
    ]
    best_exact = exact_overlaps[0] if exact_overlaps else {}
    dominant = dominant_families[0] if dominant_families else (family_rows[0] if family_rows else {})
    dominant_missing = required - frontier_set(dominant.get("family_key", ""))
    if all_non_target_families:
        verdict = "all_non_target_family_candidate_found"
        next_probe = "review all-non-target compact-control five-byte pair family for promotion"
    elif exact_all_non_target:
        verdict = "cross_family_exact_all_non_target_candidate_found"
        next_probe = "review exact cross-family compact-control five-byte bridge candidate"
    elif dominant_families and weak_pair_families:
        verdict = "split_pair_family_bridge_required"
        next_probe = "derive bridge from dominant compact-control five-byte pair family to missing frontier"
    elif dominant_families:
        verdict = "dominant_pair_family_only"
        next_probe = "seek weak-pair support for missing compact-control five-byte frontiers"
    elif exact_overlaps:
        verdict = "exact_overlap_partial_bridge_only"
        next_probe = "expand exact-overlap compact-control five-byte bridge beyond partial frontiers"
    else:
        verdict = "frontier_pair_families_fragmented"
        next_probe = "derive new atoms for fragmented compact-control five-byte pair families"
    summary = {
        "scope": "total",
        "candidate_mode": "external_terminal_spatial_bridge_five_byte_pair_family_split",
        "target_spans": non_tail_summary.get("target_spans", "0"),
        "target_bytes": non_tail_summary.get("target_bytes", "0"),
        "non_tail_support_rows": non_tail_summary.get("non_tail_support_rows", str(len(candidate_rows))),
        "family_rows": str(len(family_rows)),
        "partial_family_rows": str(
            sum(1 for row in family_rows if "partial_non_target_non_tail" in row.get("candidate_classes", ""))
        ),
        "target_overlap_family_rows": str(
            sum(1 for row in family_rows if row.get("family_verdict") == "target_overlap_family")
        ),
        "local_family_rows": str(sum(1 for row in family_rows if row.get("family_verdict") == "local_target_pair_family")),
        "all_non_target_family_rows": str(len(all_non_target_families)),
        "required_non_target_frontiers": ",".join(sort_frontiers(required)),
        "dominant_family": dominant.get("family_key", ""),
        "dominant_family_rows": dominant.get("variant_rows", "0"),
        "dominant_family_missing_frontiers": ",".join(sort_frontiers(dominant_missing)),
        "weak_pair_families": ";".join(row.get("family_key", "") for row in weak_pair_families),
        "exact_template_overlap_rows": str(len(exact_overlaps)),
        "shape_overlap_rows": str(len(shape_overlaps)),
        "cross_family_exact_all_non_target_rows": str(len(exact_all_non_target)),
        "best_exact_overlap_template": best_exact.get("key", ""),
        "best_exact_overlap_families": best_exact.get("families", ""),
        "best_exact_overlap_frontiers": best_exact.get("union_non_target_frontiers", ""),
        "review_verdict": verdict,
        "next_probe": next_probe,
        "promotion_candidate_bytes": "0",
        "promotion_ready_bytes": "0",
        "issue_rows": "0",
    }
    return summary, family_rows, overlap_rows, atom_rows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 260) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    families: list[dict[str, str]],
    overlaps: list[dict[str, str]],
    atoms: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "families": families, "overlaps": overlaps, "atoms": atoms}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("families.csv", output_dir / "families.csv"),
            ("overlaps.csv", output_dir / "overlaps.csv"),
            ("atoms.csv", output_dir / "atoms.csv"),
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
    <div class="muted">Splits non-tail five-byte formula support into frontier-pair families and cross-family overlaps.</div>
  </header>
  <section class="stats">
    <div class="stat"><div class="muted">Families</div><div class="value">{summary['family_rows']}</div></div>
    <div class="stat"><div class="muted">Dominant family</div><div class="value">{html.escape(summary['dominant_family'])}</div></div>
    <div class="stat"><div class="muted">Exact overlaps</div><div class="value">{summary['exact_template_overlap_rows']}</div></div>
    <div class="stat"><div class="muted">All non-target families</div><div class="value warn">{summary['all_non_target_family_rows']}</div></div>
    <div class="stat"><div class="muted">Promotion-ready</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2>{links}</section>
  <section class="panel">
    <h2>Verdict</h2>
    <p><code>{html.escape(summary['review_verdict'])}</code></p>
    <p class="muted">Next: <code>{html.escape(summary['next_probe'])}</code>.</p>
  </section>
  <section class="panel"><h2>Families</h2>{render_table(families, FAMILY_FIELDNAMES)}</section>
  <section class="panel"><h2>Overlaps</h2>{render_table(overlaps, OVERLAP_FIELDNAMES)}</section>
  <section class="panel"><h2>Atoms</h2>{render_table(atoms, ATOM_FIELDNAMES)}</section>
  <script type="application/json" id="external-terminal-spatial-bridge-five-byte-pair-family-split-data">{html.escape(data_json)}</script>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Split compact-control five-byte support by frontier-pair family.")
    parser.add_argument("--non-tail-summary", type=Path, default=DEFAULT_NON_TAIL_SUMMARY)
    parser.add_argument("--non-tail-candidates", type=Path, default=DEFAULT_NON_TAIL_CANDIDATES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex External Terminal Spatial Bridge Five-Byte Pair Family Split Probe",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, families, overlaps, atoms = build(
        read_rows(args.non_tail_summary),
        read_rows(args.non_tail_candidates),
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "families.csv", FAMILY_FIELDNAMES, families)
    write_csv(args.output / "overlaps.csv", OVERLAP_FIELDNAMES, overlaps)
    write_csv(args.output / "atoms.csv", ATOM_FIELDNAMES, atoms)
    (args.output / "index.html").write_text(
        build_html(summary, families, overlaps, atoms, args.output, args.title),
        encoding="utf-8",
    )
    print(
        "External terminal spatial bridge five-byte pair family split probe: "
        f"families={summary['family_rows']} "
        f"dominant={summary['dominant_family']} "
        f"exact_overlaps={summary['exact_template_overlap_rows']} "
        f"all_non_target={summary['all_non_target_family_rows']} "
        f"promotion_ready={summary['promotion_ready_bytes']} "
        f"issues={summary['issue_rows']}"
    )
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
