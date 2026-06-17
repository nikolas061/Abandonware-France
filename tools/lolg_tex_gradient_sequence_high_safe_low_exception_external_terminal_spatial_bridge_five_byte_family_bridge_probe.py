#!/usr/bin/env python3
"""Review shape-level bridges across compact-control five-byte pair families."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv


DEFAULT_PAIR_FAMILY_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_pair_family_split/summary.csv"
)
DEFAULT_PAIR_FAMILY_OVERLAPS = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_pair_family_split/overlaps.csv"
)
DEFAULT_NON_TAIL_CANDIDATES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_non_tail_support/candidates.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_family_bridge"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_spans",
    "target_bytes",
    "required_non_target_frontiers",
    "dominant_family",
    "dominant_family_missing_frontiers",
    "shape_bridge_rows",
    "target_free_shape_bridge_rows",
    "target_overlap_shape_bridge_rows",
    "exact_bridge_rows",
    "dominant_to_missing_shape_rows",
    "dominant_to_missing_target_free_rows",
    "best_shape_bridge",
    "best_shape_bridge_families",
    "best_shape_bridge_candidate_rows",
    "best_shape_bridge_samples",
    "best_exact_overlap_template",
    "best_exact_overlap_frontiers",
    "review_verdict",
    "next_probe",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

BRIDGE_FIELDNAMES = [
    "rank",
    "shape_key",
    "families",
    "union_non_target_frontiers",
    "candidate_rows",
    "target_rows",
    "sample_local_rows",
    "dominant_family_present",
    "missing_frontier_present",
    "target_free",
    "best_variant_rank",
    "best_samples",
    "bridge_verdict",
]

EXAMPLE_FIELDNAMES = [
    "rank",
    "shape_key",
    "family_key",
    "candidate_rows",
    "target_rows",
    "sample_local_rows",
    "best_variant_rank",
    "best_template",
    "best_samples",
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
    return {value for value in text.replace(";", ",").split(",") if value}


def sort_frontiers(values: set[str]) -> list[str]:
    return sorted(values, key=lambda value: int(value) if value.isdigit() else value)


def template_shape(template_key: str) -> str:
    parts = template_key.split("|")[1:]
    return "|".join(atom[:1] for atom in parts if atom)


def bridge_verdict(
    *,
    target_free: bool,
    dominant_present: bool,
    missing_present: bool,
    exact_bridge: bool,
) -> str:
    if exact_bridge and target_free:
        return "target_free_exact_bridge_candidate"
    if target_free and dominant_present and missing_present:
        return "target_free_shape_bridge_candidate"
    if dominant_present and missing_present:
        return "target_overlap_shape_bridge_candidate"
    return "partial_shape_bridge"


def build_bridge_rows(
    pair_summary: dict[str, str],
    overlap_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    required = frontier_set(pair_summary.get("required_non_target_frontiers", ""))
    dominant = pair_summary.get("dominant_family", "")
    missing = frontier_set(pair_summary.get("dominant_family_missing_frontiers", ""))
    rows: list[dict[str, str]] = []
    for overlap in overlap_rows:
        if overlap.get("overlap_type") != "atom_shape":
            continue
        union_frontiers = frontier_set(overlap.get("union_non_target_frontiers", ""))
        if not required.issubset(union_frontiers):
            continue
        families = overlap.get("families", "")
        family_parts = [part for part in families.split(";") if part]
        family_frontiers = [frontier_set(part) for part in family_parts]
        dominant_present = dominant in family_parts
        missing_present = any(missing & values for values in family_frontiers)
        target_free = int_value(overlap, "target_rows") == 0
        rows.append(
            {
                "rank": "",
                "shape_key": overlap.get("key", ""),
                "families": families,
                "union_non_target_frontiers": overlap.get("union_non_target_frontiers", ""),
                "candidate_rows": overlap.get("candidate_rows", "0"),
                "target_rows": overlap.get("target_rows", "0"),
                "sample_local_rows": overlap.get("sample_local_rows", "0"),
                "dominant_family_present": "1" if dominant_present else "0",
                "missing_frontier_present": "1" if missing_present else "0",
                "target_free": "1" if target_free else "0",
                "best_variant_rank": overlap.get("best_variant_rank", ""),
                "best_samples": overlap.get("best_samples", ""),
                "bridge_verdict": bridge_verdict(
                    target_free=target_free,
                    dominant_present=dominant_present,
                    missing_present=missing_present,
                    exact_bridge=False,
                ),
            }
        )
    rows.sort(
        key=lambda row: (
            row.get("bridge_verdict") != "target_free_shape_bridge_candidate",
            -int_value(row, "candidate_rows"),
            int_value(row, "target_rows"),
            int_value(row, "best_variant_rank"),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = str(index)
    return rows


def build_example_rows(
    bridge_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    bridge_shapes = {row.get("shape_key", "") for row in bridge_rows}
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for candidate in candidate_rows:
        shape = template_shape(candidate.get("template_key", ""))
        if shape not in bridge_shapes:
            continue
        grouped[(shape, candidate.get("non_target_frontiers", ""))].append(candidate)
    rows: list[dict[str, str]] = []
    for (shape, family), candidates in grouped.items():
        best = min(candidates, key=lambda row: int_value(row, "variant_rank"))
        rows.append(
            {
                "rank": "",
                "shape_key": shape,
                "family_key": family,
                "candidate_rows": str(len(candidates)),
                "target_rows": str(sum(int_value(row, "target_rows") for row in candidates)),
                "sample_local_rows": str(sum(int_value(row, "sample_local_rows") for row in candidates)),
                "best_variant_rank": best.get("variant_rank", ""),
                "best_template": best.get("template_key", ""),
                "best_samples": best.get("sample_matches", ""),
            }
        )
    rows.sort(
        key=lambda row: (
            row.get("shape_key", ""),
            row.get("family_key", ""),
            int_value(row, "best_variant_rank"),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = str(index)
    return rows


def build(
    pair_summary_rows: list[dict[str, str]],
    overlap_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    pair_summary = pair_summary_rows[0] if pair_summary_rows else {}
    bridge_rows = build_bridge_rows(pair_summary, overlap_rows)
    example_rows = build_example_rows(bridge_rows, candidate_rows)
    target_free = [row for row in bridge_rows if row.get("bridge_verdict") == "target_free_shape_bridge_candidate"]
    target_overlap = [row for row in bridge_rows if row.get("bridge_verdict") == "target_overlap_shape_bridge_candidate"]
    dominant_to_missing = [
        row
        for row in bridge_rows
        if row.get("dominant_family_present") == "1" and row.get("missing_frontier_present") == "1"
    ]
    dominant_to_missing_target_free = [row for row in dominant_to_missing if row.get("target_free") == "1"]
    exact_overlap_template = pair_summary.get("best_exact_overlap_template", "")
    exact_overlap_frontiers = pair_summary.get("best_exact_overlap_frontiers", "")
    best = target_free[0] if target_free else (bridge_rows[0] if bridge_rows else {})
    if target_free:
        verdict = "target_free_shape_bridge_candidates_found"
        next_probe = "derive atom resolver for target-free compact-control five-byte shape bridges"
    elif target_overlap:
        verdict = "target_overlap_shape_bridge_only"
        next_probe = "gate target-overlap compact-control five-byte shape bridges"
    elif exact_overlap_template:
        verdict = "exact_overlap_partial_bridge_only"
        next_probe = "expand exact-overlap compact-control five-byte bridge beyond partial frontiers"
    else:
        verdict = "no_family_bridge_candidate"
        next_probe = "expand compact-control five-byte bridge shapes beyond current pair families"
    summary = {
        "scope": "total",
        "candidate_mode": "external_terminal_spatial_bridge_five_byte_family_bridge",
        "target_spans": pair_summary.get("target_spans", "0"),
        "target_bytes": pair_summary.get("target_bytes", "0"),
        "required_non_target_frontiers": pair_summary.get("required_non_target_frontiers", ""),
        "dominant_family": pair_summary.get("dominant_family", ""),
        "dominant_family_missing_frontiers": pair_summary.get("dominant_family_missing_frontiers", ""),
        "shape_bridge_rows": str(len(bridge_rows)),
        "target_free_shape_bridge_rows": str(len(target_free)),
        "target_overlap_shape_bridge_rows": str(len(target_overlap)),
        "exact_bridge_rows": "0",
        "dominant_to_missing_shape_rows": str(len(dominant_to_missing)),
        "dominant_to_missing_target_free_rows": str(len(dominant_to_missing_target_free)),
        "best_shape_bridge": best.get("shape_key", ""),
        "best_shape_bridge_families": best.get("families", ""),
        "best_shape_bridge_candidate_rows": best.get("candidate_rows", "0"),
        "best_shape_bridge_samples": best.get("best_samples", ""),
        "best_exact_overlap_template": exact_overlap_template,
        "best_exact_overlap_frontiers": exact_overlap_frontiers,
        "review_verdict": verdict,
        "next_probe": next_probe,
        "promotion_candidate_bytes": "0",
        "promotion_ready_bytes": "0",
        "issue_rows": "0",
    }
    return summary, bridge_rows, example_rows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 260) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    bridges: list[dict[str, str]],
    examples: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "bridges": bridges, "examples": examples}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("bridges.csv", output_dir / "bridges.csv"),
            ("examples.csv", output_dir / "examples.csv"),
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
    <div class="muted">Reviews shape-level bridges from the dominant pair family to the missing frontier.</div>
  </header>
  <section class="stats">
    <div class="stat"><div class="muted">Shape bridges</div><div class="value">{summary['shape_bridge_rows']}</div></div>
    <div class="stat"><div class="muted">Target-free bridges</div><div class="value">{summary['target_free_shape_bridge_rows']}</div></div>
    <div class="stat"><div class="muted">Best bridge</div><div class="value">{html.escape(summary['best_shape_bridge'])}</div></div>
    <div class="stat"><div class="muted">Exact bridges</div><div class="value warn">{summary['exact_bridge_rows']}</div></div>
    <div class="stat"><div class="muted">Promotion-ready</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2>{links}</section>
  <section class="panel">
    <h2>Verdict</h2>
    <p><code>{html.escape(summary['review_verdict'])}</code></p>
    <p class="muted">Next: <code>{html.escape(summary['next_probe'])}</code>.</p>
  </section>
  <section class="panel"><h2>Bridges</h2>{render_table(bridges, BRIDGE_FIELDNAMES)}</section>
  <section class="panel"><h2>Examples</h2>{render_table(examples, EXAMPLE_FIELDNAMES)}</section>
  <script type="application/json" id="external-terminal-spatial-bridge-five-byte-family-bridge-data">{html.escape(data_json)}</script>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Review compact-control five-byte shape bridges across pair families.")
    parser.add_argument("--pair-family-summary", type=Path, default=DEFAULT_PAIR_FAMILY_SUMMARY)
    parser.add_argument("--pair-family-overlaps", type=Path, default=DEFAULT_PAIR_FAMILY_OVERLAPS)
    parser.add_argument("--non-tail-candidates", type=Path, default=DEFAULT_NON_TAIL_CANDIDATES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex External Terminal Spatial Bridge Five-Byte Family Bridge Probe",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, bridges, examples = build(
        read_rows(args.pair_family_summary),
        read_rows(args.pair_family_overlaps),
        read_rows(args.non_tail_candidates),
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "bridges.csv", BRIDGE_FIELDNAMES, bridges)
    write_csv(args.output / "examples.csv", EXAMPLE_FIELDNAMES, examples)
    (args.output / "index.html").write_text(
        build_html(summary, bridges, examples, args.output, args.title),
        encoding="utf-8",
    )
    print(
        "External terminal spatial bridge five-byte family bridge probe: "
        f"shape_bridges={summary['shape_bridge_rows']} "
        f"target_free={summary['target_free_shape_bridge_rows']} "
        f"exact={summary['exact_bridge_rows']} "
        f"promotion_ready={summary['promotion_ready_bytes']} "
        f"issues={summary['issue_rows']}"
    )
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
