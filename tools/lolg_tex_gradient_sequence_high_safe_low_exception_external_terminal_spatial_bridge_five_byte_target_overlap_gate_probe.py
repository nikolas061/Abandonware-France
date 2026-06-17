#!/usr/bin/env python3
"""Gate the single-axis atom switch against target-overlap five-byte bridges."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv


DEFAULT_ATOM_RESOLVER_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_atom_resolver/summary.csv"
)
DEFAULT_FAMILY_BRIDGES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_family_bridge/bridges.csv"
)
DEFAULT_NON_TAIL_CANDIDATES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_non_tail_support/candidates.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_overlap_gate"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_spans",
    "target_bytes",
    "switch_position",
    "switch_map",
    "target_overlap_shape_rows",
    "switch_applicable_shape_rows",
    "exact_switch_shape_rows",
    "loose_switch_shape_rows",
    "target_direct_switch_rows",
    "target_indirect_switch_rows",
    "shape_mismatch_rows",
    "best_switch_shape",
    "best_switch_shape_verdict",
    "review_verdict",
    "next_probe",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

GATE_FIELDNAMES = [
    "rank",
    "shape_key",
    "families",
    "candidate_rows",
    "target_rows",
    "switch_position",
    "switch_shape_atom",
    "switch_map",
    "switch_family_rows",
    "exact_switch_family_rows",
    "partial_switch_family_rows",
    "target_switch_family_rows",
    "target_direct_switch_rows",
    "target_carrier_families",
    "best_samples",
    "gate_verdict",
]

FAMILY_FIELDNAMES = [
    "rank",
    "shape_key",
    "family_key",
    "candidate_rows",
    "target_rows",
    "switch_position",
    "switch_expected_atom",
    "switch_atom_set",
    "switch_atom_rows",
    "best_template",
    "best_samples",
    "family_gate_verdict",
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


def shape_atom(shape_key: str, position: int) -> str:
    parts = [part for part in shape_key.split("|") if part]
    if 1 <= position <= len(parts):
        return parts[position - 1]
    return ""


def parse_switch_map(text: str) -> dict[str, str]:
    switch: dict[str, str] = {}
    for part in text.split(";"):
        if not part or ":" not in part:
            continue
        family, atom = part.split(":", 1)
        if family and atom:
            switch[family] = atom
    return switch


def atom_set_text(values: set[str]) -> str:
    return ",".join(sorted(values))


def group_candidates(candidate_rows: list[dict[str, str]]) -> dict[tuple[str, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for candidate in candidate_rows:
        grouped[(template_shape(candidate.get("template_key", "")), candidate.get("non_target_frontiers", ""))].append(
            candidate
        )
    return grouped


def family_gate_verdict(
    *,
    expected_atom: str,
    atom_set: set[str],
    target_rows: int,
) -> str:
    if not expected_atom:
        return "not_switch_family"
    if atom_set == {expected_atom}:
        if target_rows > 0:
            return "target_direct_exact_switch_family"
        return "exact_switch_family"
    if expected_atom in atom_set:
        if target_rows > 0:
            return "target_direct_loose_switch_family"
        return "loose_switch_family"
    if target_rows > 0:
        return "target_family_switch_mismatch"
    return "switch_atom_absent"


def build_family_rows(
    bridge_rows: list[dict[str, str]],
    grouped: dict[tuple[str, str], list[dict[str, str]]],
    *,
    switch_position: int,
    switch: dict[str, str],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for bridge in bridge_rows:
        if bridge.get("bridge_verdict") != "target_overlap_shape_bridge_candidate":
            continue
        shape = bridge.get("shape_key", "")
        for family in family_parts(bridge.get("families", "")):
            candidates = grouped.get((shape, family), [])
            target_rows = sum(int_value(row, "target_rows") for row in candidates)
            atoms = {
                body[switch_position - 1]
                for row in candidates
                for body in [template_body(row.get("template_key", ""))]
                if len(body) >= switch_position
            }
            expected = switch.get(family, "")
            best = min(candidates, key=lambda row: int_value(row, "variant_rank")) if candidates else {}
            rows.append(
                {
                    "rank": "",
                    "shape_key": shape,
                    "family_key": family,
                    "candidate_rows": str(len(candidates)),
                    "target_rows": str(target_rows),
                    "switch_position": str(switch_position),
                    "switch_expected_atom": expected,
                    "switch_atom_set": atom_set_text(atoms),
                    "switch_atom_rows": ";".join(
                        f"{atom}:{count}"
                        for atom, count in Counter(
                            body[switch_position - 1]
                            for row in candidates
                            for body in [template_body(row.get("template_key", ""))]
                            if len(body) >= switch_position
                        ).most_common(8)
                    ),
                    "best_template": best.get("template_key", ""),
                    "best_samples": best.get("sample_matches", ""),
                    "family_gate_verdict": family_gate_verdict(
                        expected_atom=expected,
                        atom_set=atoms,
                        target_rows=target_rows,
                    ),
                }
            )
    rows.sort(
        key=lambda row: (
            row.get("shape_key", ""),
            row.get("family_key", ""),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = str(index)
    return rows


def gate_verdict(
    *,
    switch_shape_atom: str,
    switch_family_rows: int,
    exact_switch_family_rows: int,
    partial_switch_family_rows: int,
    target_switch_family_rows: int,
    target_direct_switch_rows: int,
    target_rows: int,
) -> str:
    if switch_shape_atom != "s":
        return "switch_position_shape_mismatch"
    if switch_family_rows == 0:
        return "switch_families_missing"
    if target_direct_switch_rows > 0:
        return "target_overlap_direct_switch_candidate"
    if target_rows > 0 and target_switch_family_rows == 0 and (exact_switch_family_rows or partial_switch_family_rows):
        return "target_overlap_switch_indirect_only"
    if exact_switch_family_rows == switch_family_rows and switch_family_rows > 0:
        return "target_overlap_exact_switch_no_target_carrier"
    if exact_switch_family_rows or partial_switch_family_rows:
        return "target_overlap_loose_switch_no_target_carrier"
    return "target_overlap_switch_reject"


def build_gate_rows(
    bridge_rows: list[dict[str, str]],
    family_rows: list[dict[str, str]],
    *,
    switch_position: int,
    switch: dict[str, str],
) -> list[dict[str, str]]:
    by_shape: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in family_rows:
        by_shape[row.get("shape_key", "")].append(row)
    rows: list[dict[str, str]] = []
    for bridge in bridge_rows:
        if bridge.get("bridge_verdict") != "target_overlap_shape_bridge_candidate":
            continue
        shape = bridge.get("shape_key", "")
        family_gate_rows = by_shape.get(shape, [])
        switch_family_rows = [row for row in family_gate_rows if row.get("switch_expected_atom", "")]
        exact_rows = [row for row in switch_family_rows if row.get("family_gate_verdict") == "exact_switch_family"]
        partial_rows = [row for row in switch_family_rows if row.get("family_gate_verdict") == "loose_switch_family"]
        target_switch_rows = [
            row
            for row in switch_family_rows
            if int_value(row, "target_rows") > 0
        ]
        target_direct_rows = [
            row
            for row in switch_family_rows
            if row.get("family_gate_verdict")
            in {"target_direct_exact_switch_family", "target_direct_loose_switch_family"}
        ]
        target_carriers = [
            row.get("family_key", "")
            for row in family_gate_rows
            if int_value(row, "target_rows") > 0
        ]
        verdict = gate_verdict(
            switch_shape_atom=shape_atom(shape, switch_position),
            switch_family_rows=len(switch_family_rows),
            exact_switch_family_rows=len(exact_rows),
            partial_switch_family_rows=len(partial_rows),
            target_switch_family_rows=len(target_switch_rows),
            target_direct_switch_rows=len(target_direct_rows),
            target_rows=int_value(bridge, "target_rows"),
        )
        rows.append(
            {
                "rank": "",
                "shape_key": shape,
                "families": bridge.get("families", ""),
                "candidate_rows": bridge.get("candidate_rows", "0"),
                "target_rows": bridge.get("target_rows", "0"),
                "switch_position": str(switch_position),
                "switch_shape_atom": shape_atom(shape, switch_position),
                "switch_map": ";".join(f"{family}:{atom}" for family, atom in switch.items()),
                "switch_family_rows": str(len(switch_family_rows)),
                "exact_switch_family_rows": str(len(exact_rows)),
                "partial_switch_family_rows": str(len(partial_rows)),
                "target_switch_family_rows": str(len(target_switch_rows)),
                "target_direct_switch_rows": str(len(target_direct_rows)),
                "target_carrier_families": ";".join(target_carriers),
                "best_samples": bridge.get("best_samples", ""),
                "gate_verdict": verdict,
            }
        )
    rows.sort(
        key=lambda row: (
            row.get("gate_verdict") != "target_overlap_direct_switch_candidate",
            row.get("gate_verdict") != "target_overlap_switch_indirect_only",
            row.get("gate_verdict") != "target_overlap_loose_switch_no_target_carrier",
            -int_value(row, "candidate_rows"),
            row.get("shape_key", ""),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = str(index)
    return rows


def build(
    atom_summary_rows: list[dict[str, str]],
    bridge_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    atom_summary = atom_summary_rows[0] if atom_summary_rows else {}
    switch_position = int_value(atom_summary, "best_single_axis_position")
    switch = parse_switch_map(atom_summary.get("best_single_axis_switch", ""))
    issues: list[str] = []
    if switch_position <= 0:
        issues.append("missing_switch_position")
    if not switch:
        issues.append("missing_switch_map")
    grouped = group_candidates(candidate_rows)
    family_rows = build_family_rows(
        bridge_rows,
        grouped,
        switch_position=switch_position,
        switch=switch,
    )
    gate_rows = build_gate_rows(
        bridge_rows,
        family_rows,
        switch_position=switch_position,
        switch=switch,
    )
    target_overlap_rows = [
        row for row in bridge_rows if row.get("bridge_verdict") == "target_overlap_shape_bridge_candidate"
    ]
    switch_applicable = [row for row in gate_rows if row.get("switch_shape_atom") == "s"]
    exact_switch = [
        row
        for row in gate_rows
        if int_value(row, "exact_switch_family_rows") == int_value(row, "switch_family_rows")
        and int_value(row, "switch_family_rows") > 0
    ]
    loose_switch = [
        row
        for row in gate_rows
        if int_value(row, "exact_switch_family_rows") > 0 or int_value(row, "partial_switch_family_rows") > 0
    ]
    target_direct = [row for row in gate_rows if int_value(row, "target_direct_switch_rows") > 0]
    target_indirect = [row for row in gate_rows if row.get("gate_verdict") == "target_overlap_switch_indirect_only"]
    shape_mismatch = [row for row in gate_rows if row.get("gate_verdict") == "switch_position_shape_mismatch"]
    best = target_direct[0] if target_direct else (target_indirect[0] if target_indirect else (loose_switch[0] if loose_switch else {}))
    if issues:
        verdict = "target_overlap_gate_has_issues"
        next_probe = "fix compact-control switch target-overlap gate issues"
    elif target_direct:
        verdict = "target_overlap_direct_switch_candidate_found"
        next_probe = "review direct target-overlap compact-control atom switch for promotion"
    elif target_indirect:
        verdict = "target_overlap_switch_indirect_only"
        next_probe = "split target-overlap compact-control switch by carrier family"
    elif loose_switch:
        verdict = "target_overlap_loose_switch_no_target_carrier"
        next_probe = "expand target-overlap compact-control switch carrier search"
    else:
        verdict = "target_overlap_switch_rejected"
        next_probe = "derive alternate target-overlap compact-control atom switch"
    summary = {
        "scope": "total",
        "candidate_mode": "external_terminal_spatial_bridge_five_byte_target_overlap_gate",
        "target_spans": atom_summary.get("target_spans", "0"),
        "target_bytes": atom_summary.get("target_bytes", "0"),
        "switch_position": str(switch_position),
        "switch_map": ";".join(f"{family}:{atom}" for family, atom in switch.items()),
        "target_overlap_shape_rows": str(len(target_overlap_rows)),
        "switch_applicable_shape_rows": str(len(switch_applicable)),
        "exact_switch_shape_rows": str(len(exact_switch)),
        "loose_switch_shape_rows": str(len(loose_switch)),
        "target_direct_switch_rows": str(len(target_direct)),
        "target_indirect_switch_rows": str(len(target_indirect)),
        "shape_mismatch_rows": str(len(shape_mismatch)),
        "best_switch_shape": best.get("shape_key", ""),
        "best_switch_shape_verdict": best.get("gate_verdict", ""),
        "review_verdict": verdict,
        "next_probe": next_probe,
        "promotion_candidate_bytes": "0",
        "promotion_ready_bytes": "0",
        "issue_rows": str(len(issues)),
    }
    return summary, gate_rows, family_rows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 260) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    gates: list[dict[str, str]],
    families: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "gates": gates, "families": families}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("gates.csv", output_dir / "gates.csv"),
            ("families.csv", output_dir / "families.csv"),
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
table {{ width: 100%; min-width: 1500px; border-collapse: collapse; }}
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
    <div class="muted">Checks whether the single-axis atom switch is directly supported by target-overlap bridges.</div>
  </header>
  <section class="stats">
    <div class="stat"><div class="muted">Target-overlap shapes</div><div class="value">{summary['target_overlap_shape_rows']}</div></div>
    <div class="stat"><div class="muted">Switch-applicable</div><div class="value">{summary['switch_applicable_shape_rows']}</div></div>
    <div class="stat"><div class="muted">Direct target switch</div><div class="value warn">{summary['target_direct_switch_rows']}</div></div>
    <div class="stat"><div class="muted">Indirect switch</div><div class="value">{summary['target_indirect_switch_rows']}</div></div>
    <div class="stat"><div class="muted">Promotion-ready</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2>{links}</section>
  <section class="panel">
    <h2>Verdict</h2>
    <p><code>{html.escape(summary['review_verdict'])}</code></p>
    <p class="muted">Next: <code>{html.escape(summary['next_probe'])}</code>.</p>
  </section>
  <section class="panel"><h2>Gates</h2>{render_table(gates, GATE_FIELDNAMES)}</section>
  <section class="panel"><h2>Families</h2>{render_table(families, FAMILY_FIELDNAMES)}</section>
  <script type="application/json" id="external-terminal-spatial-bridge-five-byte-target-overlap-gate-data">{html.escape(data_json)}</script>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Gate a five-byte atom switch against target-overlap bridges.")
    parser.add_argument("--atom-resolver-summary", type=Path, default=DEFAULT_ATOM_RESOLVER_SUMMARY)
    parser.add_argument("--family-bridges", type=Path, default=DEFAULT_FAMILY_BRIDGES)
    parser.add_argument("--non-tail-candidates", type=Path, default=DEFAULT_NON_TAIL_CANDIDATES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex External Terminal Spatial Bridge Five-Byte Target-Overlap Gate Probe",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, gates, families = build(
        read_rows(args.atom_resolver_summary),
        read_rows(args.family_bridges),
        read_rows(args.non_tail_candidates),
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "gates.csv", GATE_FIELDNAMES, gates)
    write_csv(args.output / "families.csv", FAMILY_FIELDNAMES, families)
    (args.output / "index.html").write_text(
        build_html(summary, gates, families, args.output, args.title),
        encoding="utf-8",
    )
    print(
        "External terminal spatial bridge five-byte target-overlap gate probe: "
        f"target_overlap={summary['target_overlap_shape_rows']} "
        f"applicable={summary['switch_applicable_shape_rows']} "
        f"direct={summary['target_direct_switch_rows']} "
        f"indirect={summary['target_indirect_switch_rows']} "
        f"promotion_ready={summary['promotion_ready_bytes']} "
        f"issues={summary['issue_rows']}"
    )
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
