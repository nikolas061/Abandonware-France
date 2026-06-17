#!/usr/bin/env python3
"""Resolve atom-level differences inside target-free five-byte shape bridges."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv


DEFAULT_FAMILY_BRIDGE_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_family_bridge/summary.csv"
)
DEFAULT_FAMILY_BRIDGES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_family_bridge/bridges.csv"
)
DEFAULT_NON_TAIL_CANDIDATES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_non_tail_support/candidates.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_atom_resolver"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_spans",
    "target_bytes",
    "target_free_shape_bridge_rows",
    "shape_resolver_rows",
    "exact_family_resolver_rows",
    "single_axis_resolver_rows",
    "shared_ambiguity_single_axis_rows",
    "broad_ambiguous_shape_rows",
    "family_atom_rows",
    "resolved_family_atom_rows",
    "ambiguous_family_atom_rows",
    "position_delta_rows",
    "shared_position_rows",
    "divergent_exact_position_rows",
    "divergent_ambiguous_position_rows",
    "best_exact_shape",
    "best_single_axis_shape",
    "best_single_axis_position",
    "best_single_axis_switch",
    "review_verdict",
    "next_probe",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

SHAPE_FIELDNAMES = [
    "rank",
    "shape_key",
    "families",
    "candidate_rows",
    "target_rows",
    "family_rows",
    "exact_family_rows",
    "family_template_counts",
    "shared_positions",
    "divergent_exact_positions",
    "divergent_ambiguous_positions",
    "unresolved_positions",
    "single_axis_position",
    "single_axis_switch",
    "best_templates",
    "resolver_verdict",
]

ATOM_FIELDNAMES = [
    "rank",
    "shape_key",
    "family_key",
    "atom_position",
    "shape_atom",
    "candidate_rows",
    "target_rows",
    "unique_atom_count",
    "resolved_atom",
    "top_atoms",
    "atom_verdict",
]

POSITION_FIELDNAMES = [
    "rank",
    "shape_key",
    "atom_position",
    "shape_atom",
    "families",
    "atom_sets",
    "position_verdict",
]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def int_value(row: dict[str, str], field: str, default: int = 0) -> int:
    try:
        return int(row.get(field, ""))
    except (TypeError, ValueError):
        return default


def template_body(template_key: str) -> list[str]:
    parts = [part for part in template_key.split("|") if part]
    return parts[1:] if len(parts) > 1 else parts


def template_shape(template_key: str) -> str:
    return "|".join(atom[:1] for atom in template_body(template_key))


def family_parts(text: str) -> list[str]:
    return [part for part in text.split(";") if part]


def position_key(position: int, shape_key: str) -> str:
    shape_atoms = [part for part in shape_key.split("|") if part]
    if 1 <= position <= len(shape_atoms):
        return shape_atoms[position - 1]
    return ""


def atom_set_text(values: set[str]) -> str:
    return ",".join(sorted(values))


def counter_text(counter: Counter[str], limit: int = 8) -> str:
    return ";".join(f"{atom}:{count}" for atom, count in counter.most_common(limit))


def group_candidates_by_shape_family(
    bridge_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
) -> dict[tuple[str, str], list[dict[str, str]]]:
    wanted: set[tuple[str, str]] = set()
    for bridge in bridge_rows:
        if bridge.get("bridge_verdict") != "target_free_shape_bridge_candidate":
            continue
        for family in family_parts(bridge.get("families", "")):
            wanted.add((bridge.get("shape_key", ""), family))

    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for candidate in candidate_rows:
        shape = template_shape(candidate.get("template_key", ""))
        family = candidate.get("non_target_frontiers", "")
        if (shape, family) not in wanted:
            continue
        grouped[(shape, family)].append(candidate)
    return grouped


def build_atom_rows(
    grouped: dict[tuple[str, str], list[dict[str, str]]],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for (shape, family), candidates in grouped.items():
        target_rows = sum(int_value(row, "target_rows") for row in candidates)
        for position in range(1, 6):
            counts: Counter[str] = Counter()
            for candidate in candidates:
                body = template_body(candidate.get("template_key", ""))
                if len(body) >= position:
                    counts[body[position - 1]] += 1
            if not counts:
                resolved = ""
                verdict = "missing_atom"
            elif len(counts) == 1:
                resolved = next(iter(counts))
                verdict = "family_atom_resolved"
            else:
                resolved = ""
                verdict = "family_atom_ambiguous"
            rows.append(
                {
                    "rank": "",
                    "shape_key": shape,
                    "family_key": family,
                    "atom_position": str(position),
                    "shape_atom": position_key(position, shape),
                    "candidate_rows": str(len(candidates)),
                    "target_rows": str(target_rows),
                    "unique_atom_count": str(len(counts)),
                    "resolved_atom": resolved,
                    "top_atoms": counter_text(counts),
                    "atom_verdict": verdict,
                }
            )
    rows.sort(
        key=lambda row: (
            row.get("shape_key", ""),
            row.get("family_key", ""),
            int_value(row, "atom_position"),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = str(index)
    return rows


def position_verdict(atom_sets: list[set[str]]) -> str:
    if not atom_sets or any(not values for values in atom_sets):
        return "unresolved_position"
    frozen = {frozenset(values) for values in atom_sets}
    if len(frozen) == 1:
        return "shared_position"
    if all(len(values) == 1 for values in atom_sets):
        return "divergent_exact_position"
    return "divergent_ambiguous_position"


def build_shape_rows(
    bridge_rows: list[dict[str, str]],
    grouped: dict[tuple[str, str], list[dict[str, str]]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    shape_rows: list[dict[str, str]] = []
    position_rows: list[dict[str, str]] = []
    target_free_bridges = [
        row for row in bridge_rows if row.get("bridge_verdict") == "target_free_shape_bridge_candidate"
    ]
    for bridge in target_free_bridges:
        shape = bridge.get("shape_key", "")
        families = family_parts(bridge.get("families", ""))
        family_template_counts: list[str] = []
        best_templates: list[str] = []
        exact_family_rows = 0
        candidate_total = 0
        target_total = 0
        atom_sets_by_position: dict[int, list[set[str]]] = defaultdict(list)
        family_atoms_by_position: dict[int, list[tuple[str, set[str]]]] = defaultdict(list)

        for family in families:
            candidates = grouped.get((shape, family), [])
            candidate_total += len(candidates)
            family_target_rows = sum(int_value(row, "target_rows") for row in candidates)
            target_total += family_target_rows
            template_counts = Counter(row.get("template_key", "") for row in candidates)
            family_template_counts.append(f"{family}:{len(template_counts)}")
            if template_counts and len(template_counts) == 1 and family_target_rows == 0:
                exact_family_rows += 1
            if candidates:
                best = min(candidates, key=lambda row: int_value(row, "variant_rank"))
                best_templates.append(f"{family}:{best.get('template_key', '')}")
            for position in range(1, 6):
                values = {
                    body[position - 1]
                    for row in candidates
                    for body in [template_body(row.get("template_key", ""))]
                    if len(body) >= position
                }
                atom_sets_by_position[position].append(values)
                family_atoms_by_position[position].append((family, values))

        shared_positions: list[str] = []
        divergent_exact_positions: list[str] = []
        divergent_ambiguous_positions: list[str] = []
        unresolved_positions: list[str] = []
        for position in range(1, 6):
            family_values = family_atoms_by_position[position]
            verdict = position_verdict([values for _family, values in family_values])
            if verdict == "shared_position":
                shared_positions.append(str(position))
            elif verdict == "divergent_exact_position":
                divergent_exact_positions.append(str(position))
            elif verdict == "divergent_ambiguous_position":
                divergent_ambiguous_positions.append(str(position))
            else:
                unresolved_positions.append(str(position))
            position_rows.append(
                {
                    "rank": "",
                    "shape_key": shape,
                    "atom_position": str(position),
                    "shape_atom": position_key(position, shape),
                    "families": ";".join(families),
                    "atom_sets": ";".join(f"{family}:{atom_set_text(values)}" for family, values in family_values),
                    "position_verdict": verdict,
                }
            )

        single_axis = (
            len(divergent_exact_positions) == 1
            and not divergent_ambiguous_positions
            and not unresolved_positions
        )
        single_axis_position = divergent_exact_positions[0] if single_axis else ""
        single_axis_switch = ""
        if single_axis_position:
            position = int(single_axis_position)
            single_axis_switch = ";".join(
                f"{family}:{atom_set_text(values)}" for family, values in family_atoms_by_position[position]
            )
        all_families_exact = exact_family_rows == len(families) and bool(families)
        if all_families_exact and single_axis:
            verdict = "exact_single_axis_atom_resolver"
        elif single_axis:
            verdict = "shared_ambiguity_single_axis_atom_resolver"
        elif divergent_exact_positions or divergent_ambiguous_positions:
            verdict = "broad_ambiguous_atom_bridge"
        else:
            verdict = "shared_atom_shape_only"

        shape_rows.append(
            {
                "rank": "",
                "shape_key": shape,
                "families": ";".join(families),
                "candidate_rows": str(candidate_total),
                "target_rows": str(target_total),
                "family_rows": str(len(families)),
                "exact_family_rows": str(exact_family_rows),
                "family_template_counts": ";".join(family_template_counts),
                "shared_positions": ",".join(shared_positions),
                "divergent_exact_positions": ",".join(divergent_exact_positions),
                "divergent_ambiguous_positions": ",".join(divergent_ambiguous_positions),
                "unresolved_positions": ",".join(unresolved_positions),
                "single_axis_position": single_axis_position,
                "single_axis_switch": single_axis_switch,
                "best_templates": ";".join(best_templates),
                "resolver_verdict": verdict,
            }
        )

    shape_rows.sort(
        key=lambda row: (
            row.get("resolver_verdict") != "exact_single_axis_atom_resolver",
            row.get("resolver_verdict") != "shared_ambiguity_single_axis_atom_resolver",
            -int_value(row, "candidate_rows"),
            row.get("shape_key", ""),
        )
    )
    for index, row in enumerate(shape_rows, start=1):
        row["rank"] = str(index)
    position_rows.sort(
        key=lambda row: (
            row.get("shape_key", ""),
            int_value(row, "atom_position"),
        )
    )
    for index, row in enumerate(position_rows, start=1):
        row["rank"] = str(index)
    return shape_rows, position_rows


def build(
    family_bridge_summary_rows: list[dict[str, str]],
    bridge_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    family_bridge_summary = family_bridge_summary_rows[0] if family_bridge_summary_rows else {}
    grouped = group_candidates_by_shape_family(bridge_rows, candidate_rows)
    atom_rows = build_atom_rows(grouped)
    shape_rows, position_rows = build_shape_rows(bridge_rows, grouped)
    exact_shapes = [row for row in shape_rows if row.get("resolver_verdict") == "exact_single_axis_atom_resolver"]
    shared_ambiguity_shapes = [
        row for row in shape_rows if row.get("resolver_verdict") == "shared_ambiguity_single_axis_atom_resolver"
    ]
    single_axis_shapes = exact_shapes + shared_ambiguity_shapes
    broad_ambiguous_shapes = [
        row for row in shape_rows if row.get("resolver_verdict") == "broad_ambiguous_atom_bridge"
    ]
    resolved_atoms = [row for row in atom_rows if row.get("atom_verdict") == "family_atom_resolved"]
    ambiguous_atoms = [row for row in atom_rows if row.get("atom_verdict") == "family_atom_ambiguous"]
    shared_positions = [row for row in position_rows if row.get("position_verdict") == "shared_position"]
    divergent_exact_positions = [
        row for row in position_rows if row.get("position_verdict") == "divergent_exact_position"
    ]
    divergent_ambiguous_positions = [
        row for row in position_rows if row.get("position_verdict") == "divergent_ambiguous_position"
    ]
    best_exact = exact_shapes[0] if exact_shapes else {}
    best_single_axis = single_axis_shapes[0] if single_axis_shapes else {}
    if exact_shapes:
        verdict = "exact_single_axis_atom_resolver_found"
        next_probe = "gate single-axis compact-control atom resolver against target-overlap templates"
    elif single_axis_shapes:
        verdict = "shared_ambiguity_single_axis_atom_resolver_found"
        next_probe = "resolve shared ambiguous compact-control atoms inside single-axis bridges"
    elif broad_ambiguous_shapes:
        verdict = "broad_ambiguous_atom_bridges_only"
        next_probe = "split broad ambiguous compact-control atom bridges by context"
    else:
        verdict = "no_atom_resolver_candidate"
        next_probe = "expand compact-control five-byte atom resolver features"

    summary = {
        "scope": "total",
        "candidate_mode": "external_terminal_spatial_bridge_five_byte_atom_resolver",
        "target_spans": family_bridge_summary.get("target_spans", "0"),
        "target_bytes": family_bridge_summary.get("target_bytes", "0"),
        "target_free_shape_bridge_rows": family_bridge_summary.get("target_free_shape_bridge_rows", "0"),
        "shape_resolver_rows": str(len(shape_rows)),
        "exact_family_resolver_rows": str(len(exact_shapes)),
        "single_axis_resolver_rows": str(len(single_axis_shapes)),
        "shared_ambiguity_single_axis_rows": str(len(shared_ambiguity_shapes)),
        "broad_ambiguous_shape_rows": str(len(broad_ambiguous_shapes)),
        "family_atom_rows": str(len(atom_rows)),
        "resolved_family_atom_rows": str(len(resolved_atoms)),
        "ambiguous_family_atom_rows": str(len(ambiguous_atoms)),
        "position_delta_rows": str(len(position_rows)),
        "shared_position_rows": str(len(shared_positions)),
        "divergent_exact_position_rows": str(len(divergent_exact_positions)),
        "divergent_ambiguous_position_rows": str(len(divergent_ambiguous_positions)),
        "best_exact_shape": best_exact.get("shape_key", ""),
        "best_single_axis_shape": best_single_axis.get("shape_key", ""),
        "best_single_axis_position": best_single_axis.get("single_axis_position", ""),
        "best_single_axis_switch": best_single_axis.get("single_axis_switch", ""),
        "review_verdict": verdict,
        "next_probe": next_probe,
        "promotion_candidate_bytes": "0",
        "promotion_ready_bytes": "0",
        "issue_rows": "0",
    }
    return summary, shape_rows, atom_rows, position_rows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 260) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    shapes: list[dict[str, str]],
    atoms: list[dict[str, str]],
    positions: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "shapes": shapes, "atoms": atoms, "positions": positions}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("shapes.csv", output_dir / "shapes.csv"),
            ("atoms.csv", output_dir / "atoms.csv"),
            ("positions.csv", output_dir / "positions.csv"),
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
table {{ width: 100%; min-width: 1520px; border-collapse: collapse; }}
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
    <div class="muted">Classifies atom-level resolver candidates inside target-free five-byte shape bridges.</div>
  </header>
  <section class="stats">
    <div class="stat"><div class="muted">Shape resolvers</div><div class="value">{summary['shape_resolver_rows']}</div></div>
    <div class="stat"><div class="muted">Exact single-axis</div><div class="value">{summary['exact_family_resolver_rows']}</div></div>
    <div class="stat"><div class="muted">Single-axis total</div><div class="value">{summary['single_axis_resolver_rows']}</div></div>
    <div class="stat"><div class="muted">Best switch</div><div class="value">{html.escape(summary['best_single_axis_switch'])}</div></div>
    <div class="stat"><div class="muted">Promotion-ready</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2>{links}</section>
  <section class="panel">
    <h2>Verdict</h2>
    <p><code>{html.escape(summary['review_verdict'])}</code></p>
    <p class="muted">Next: <code>{html.escape(summary['next_probe'])}</code>.</p>
  </section>
  <section class="panel"><h2>Shapes</h2>{render_table(shapes, SHAPE_FIELDNAMES)}</section>
  <section class="panel"><h2>Positions</h2>{render_table(positions, POSITION_FIELDNAMES)}</section>
  <section class="panel"><h2>Atoms</h2>{render_table(atoms, ATOM_FIELDNAMES)}</section>
  <script type="application/json" id="external-terminal-spatial-bridge-five-byte-atom-resolver-data">{html.escape(data_json)}</script>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolve atom-level differences in five-byte shape bridges.")
    parser.add_argument("--family-bridge-summary", type=Path, default=DEFAULT_FAMILY_BRIDGE_SUMMARY)
    parser.add_argument("--family-bridges", type=Path, default=DEFAULT_FAMILY_BRIDGES)
    parser.add_argument("--non-tail-candidates", type=Path, default=DEFAULT_NON_TAIL_CANDIDATES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex External Terminal Spatial Bridge Five-Byte Atom Resolver Probe",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, shapes, atoms, positions = build(
        read_rows(args.family_bridge_summary),
        read_rows(args.family_bridges),
        read_rows(args.non_tail_candidates),
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "shapes.csv", SHAPE_FIELDNAMES, shapes)
    write_csv(args.output / "atoms.csv", ATOM_FIELDNAMES, atoms)
    write_csv(args.output / "positions.csv", POSITION_FIELDNAMES, positions)
    (args.output / "index.html").write_text(
        build_html(summary, shapes, atoms, positions, args.output, args.title),
        encoding="utf-8",
    )
    print(
        "External terminal spatial bridge five-byte atom resolver probe: "
        f"shapes={summary['shape_resolver_rows']} "
        f"exact_single_axis={summary['exact_family_resolver_rows']} "
        f"single_axis={summary['single_axis_resolver_rows']} "
        f"promotion_ready={summary['promotion_ready_bytes']} "
        f"issues={summary['issue_rows']}"
    )
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
