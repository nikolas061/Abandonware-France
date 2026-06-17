#!/usr/bin/env python3
"""Split target-overlap atom-switch gates by their target-carrying families."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv


DEFAULT_TARGET_GATE_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_overlap_gate/summary.csv"
)
DEFAULT_TARGET_GATE_GATES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_overlap_gate/gates.csv"
)
DEFAULT_TARGET_GATE_FAMILIES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_overlap_gate/families.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_split"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_spans",
    "target_bytes",
    "switch_position",
    "switch_map",
    "target_overlap_shape_rows",
    "carrier_split_rows",
    "target_carrier_family_rows",
    "switch_support_family_rows",
    "direct_carrier_switch_rows",
    "indirect_carrier_split_rows",
    "carrier_shape_mismatch_rows",
    "target_switch_mismatch_family_rows",
    "best_carrier_shape",
    "best_target_carriers",
    "best_carrier_atom_sets",
    "best_switch_support",
    "review_verdict",
    "next_probe",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

SPLIT_FIELDNAMES = [
    "rank",
    "shape_key",
    "gate_verdict",
    "switch_position",
    "switch_shape_atom",
    "target_rows",
    "candidate_rows",
    "target_carrier_families",
    "target_carrier_atom_sets",
    "target_carrier_templates",
    "switch_support_families",
    "switch_support_atom_sets",
    "switch_support_templates",
    "target_switch_mismatch_families",
    "carrier_split_verdict",
]

CARRIER_FIELDNAMES = [
    "rank",
    "shape_key",
    "family_key",
    "carrier_role",
    "candidate_rows",
    "target_rows",
    "switch_position",
    "switch_expected_atom",
    "switch_atom_set",
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


def family_role(row: dict[str, str]) -> str:
    if row.get("family_gate_verdict") in {"exact_switch_family", "loose_switch_family"}:
        return "switch_support_family"
    if row.get("family_gate_verdict") in {
        "target_direct_exact_switch_family",
        "target_direct_loose_switch_family",
    }:
        return "direct_target_switch_family"
    if row.get("family_gate_verdict") == "target_family_switch_mismatch":
        return "target_switch_mismatch_family"
    if int_value(row, "target_rows") > 0:
        return "target_carrier_family"
    return "context_family"


def row_label(row: dict[str, str], field: str) -> str:
    return f"{row.get('family_key', '')}:{row.get(field, '')}"


def split_verdict(
    *,
    gate_verdict_value: str,
    switch_shape_atom: str,
    direct_rows: list[dict[str, str]],
    carriers: list[dict[str, str]],
    switch_support: list[dict[str, str]],
    mismatches: list[dict[str, str]],
) -> str:
    if direct_rows:
        return "direct_carrier_switch_candidate"
    if switch_shape_atom != "s":
        if mismatches:
            return "carrier_shape_mismatch_with_switch_family_target"
        return "carrier_shape_mismatch"
    if carriers and switch_support and gate_verdict_value == "target_overlap_switch_indirect_only":
        return "indirect_switch_carrier_split"
    if carriers and switch_support:
        return "carrier_has_switch_support_no_direct_target"
    if carriers:
        return "carrier_without_switch_support"
    return "no_target_carrier"


def build_carrier_rows(family_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in family_rows:
        role = family_role(row)
        if role == "context_family":
            continue
        rows.append(
            {
                "rank": "",
                "shape_key": row.get("shape_key", ""),
                "family_key": row.get("family_key", ""),
                "carrier_role": role,
                "candidate_rows": row.get("candidate_rows", "0"),
                "target_rows": row.get("target_rows", "0"),
                "switch_position": row.get("switch_position", ""),
                "switch_expected_atom": row.get("switch_expected_atom", ""),
                "switch_atom_set": row.get("switch_atom_set", ""),
                "best_template": row.get("best_template", ""),
                "best_samples": row.get("best_samples", ""),
                "family_gate_verdict": row.get("family_gate_verdict", ""),
            }
        )
    rows.sort(
        key=lambda row: (
            row.get("shape_key", ""),
            row.get("carrier_role") != "direct_target_switch_family",
            row.get("carrier_role") != "target_carrier_family",
            row.get("family_key", ""),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = str(index)
    return rows


def build_split_rows(
    gate_rows: list[dict[str, str]],
    carrier_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    by_shape: dict[str, list[dict[str, str]]] = {}
    for row in carrier_rows:
        by_shape.setdefault(row.get("shape_key", ""), []).append(row)
    rows: list[dict[str, str]] = []
    for gate in gate_rows:
        shape = gate.get("shape_key", "")
        families = by_shape.get(shape, [])
        direct = [row for row in families if row.get("carrier_role") == "direct_target_switch_family"]
        carriers = [row for row in families if row.get("carrier_role") == "target_carrier_family"]
        support = [row for row in families if row.get("carrier_role") == "switch_support_family"]
        mismatches = [row for row in families if row.get("carrier_role") == "target_switch_mismatch_family"]
        rows.append(
            {
                "rank": "",
                "shape_key": shape,
                "gate_verdict": gate.get("gate_verdict", ""),
                "switch_position": gate.get("switch_position", ""),
                "switch_shape_atom": gate.get("switch_shape_atom", ""),
                "target_rows": gate.get("target_rows", "0"),
                "candidate_rows": gate.get("candidate_rows", "0"),
                "target_carrier_families": ";".join(row.get("family_key", "") for row in carriers + direct),
                "target_carrier_atom_sets": ";".join(row_label(row, "switch_atom_set") for row in carriers + direct),
                "target_carrier_templates": ";".join(row_label(row, "best_template") for row in carriers + direct),
                "switch_support_families": ";".join(row.get("family_key", "") for row in support),
                "switch_support_atom_sets": ";".join(row_label(row, "switch_atom_set") for row in support),
                "switch_support_templates": ";".join(row_label(row, "best_template") for row in support),
                "target_switch_mismatch_families": ";".join(row.get("family_key", "") for row in mismatches),
                "carrier_split_verdict": split_verdict(
                    gate_verdict_value=gate.get("gate_verdict", ""),
                    switch_shape_atom=gate.get("switch_shape_atom", ""),
                    direct_rows=direct,
                    carriers=carriers,
                    switch_support=support,
                    mismatches=mismatches,
                ),
            }
        )
    rows.sort(
        key=lambda row: (
            row.get("carrier_split_verdict") != "direct_carrier_switch_candidate",
            row.get("carrier_split_verdict") != "indirect_switch_carrier_split",
            row.get("carrier_split_verdict") != "carrier_shape_mismatch_with_switch_family_target",
            -int_value(row, "target_rows"),
            row.get("shape_key", ""),
        )
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = str(index)
    return rows


def build(
    gate_summary_rows: list[dict[str, str]],
    gate_rows: list[dict[str, str]],
    family_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    gate_summary = gate_summary_rows[0] if gate_summary_rows else {}
    carrier_rows = build_carrier_rows(family_rows)
    split_rows = build_split_rows(gate_rows, carrier_rows)
    direct = [row for row in split_rows if row.get("carrier_split_verdict") == "direct_carrier_switch_candidate"]
    indirect = [row for row in split_rows if row.get("carrier_split_verdict") == "indirect_switch_carrier_split"]
    shape_mismatch = [row for row in split_rows if row.get("carrier_split_verdict").startswith("carrier_shape_mismatch")]
    target_carriers = [
        row
        for row in carrier_rows
        if row.get("carrier_role") in {"target_carrier_family", "direct_target_switch_family"}
    ]
    switch_support = [row for row in carrier_rows if row.get("carrier_role") == "switch_support_family"]
    target_switch_mismatches = [
        row for row in carrier_rows if row.get("carrier_role") == "target_switch_mismatch_family"
    ]
    best = direct[0] if direct else (indirect[0] if indirect else (split_rows[0] if split_rows else {}))
    if direct:
        verdict = "direct_target_carrier_switch_candidate_found"
        next_probe = "review direct target-carrier compact-control switch for promotion"
    elif indirect:
        verdict = "indirect_target_carrier_split_found"
        next_probe = "derive carrier-local compact-control atom switch for target family 29"
    elif target_switch_mismatches:
        verdict = "target_switch_family_mismatch_only"
        next_probe = "derive alternate atom switch for target-carrying switch families"
    elif shape_mismatch:
        verdict = "target_carrier_shape_mismatch_only"
        next_probe = "derive shape-local target carrier switch outside position 2"
    else:
        verdict = "no_target_carrier_switch_support"
        next_probe = "expand target carrier search beyond current switch families"
    summary = {
        "scope": "total",
        "candidate_mode": "external_terminal_spatial_bridge_five_byte_target_carrier_split",
        "target_spans": gate_summary.get("target_spans", "0"),
        "target_bytes": gate_summary.get("target_bytes", "0"),
        "switch_position": gate_summary.get("switch_position", ""),
        "switch_map": gate_summary.get("switch_map", ""),
        "target_overlap_shape_rows": gate_summary.get("target_overlap_shape_rows", str(len(gate_rows))),
        "carrier_split_rows": str(len(split_rows)),
        "target_carrier_family_rows": str(len(target_carriers)),
        "switch_support_family_rows": str(len(switch_support)),
        "direct_carrier_switch_rows": str(len(direct)),
        "indirect_carrier_split_rows": str(len(indirect)),
        "carrier_shape_mismatch_rows": str(len(shape_mismatch)),
        "target_switch_mismatch_family_rows": str(len(target_switch_mismatches)),
        "best_carrier_shape": best.get("shape_key", ""),
        "best_target_carriers": best.get("target_carrier_families", ""),
        "best_carrier_atom_sets": best.get("target_carrier_atom_sets", ""),
        "best_switch_support": best.get("switch_support_families", ""),
        "review_verdict": verdict,
        "next_probe": next_probe,
        "promotion_candidate_bytes": "0",
        "promotion_ready_bytes": "0",
        "issue_rows": "0",
    }
    return summary, split_rows, carrier_rows


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 260) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    splits: list[dict[str, str]],
    carriers: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "splits": splits, "carriers": carriers}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("splits.csv", output_dir / "splits.csv"),
            ("carriers.csv", output_dir / "carriers.csv"),
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
    <div class="muted">Separates target carriers from switch-support families in target-overlap gates.</div>
  </header>
  <section class="stats">
    <div class="stat"><div class="muted">Carrier splits</div><div class="value">{summary['carrier_split_rows']}</div></div>
    <div class="stat"><div class="muted">Target carriers</div><div class="value">{summary['target_carrier_family_rows']}</div></div>
    <div class="stat"><div class="muted">Indirect carrier split</div><div class="value">{summary['indirect_carrier_split_rows']}</div></div>
    <div class="stat"><div class="muted">Direct carrier switch</div><div class="value warn">{summary['direct_carrier_switch_rows']}</div></div>
    <div class="stat"><div class="muted">Promotion-ready</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2>{links}</section>
  <section class="panel">
    <h2>Verdict</h2>
    <p><code>{html.escape(summary['review_verdict'])}</code></p>
    <p class="muted">Next: <code>{html.escape(summary['next_probe'])}</code>.</p>
  </section>
  <section class="panel"><h2>Splits</h2>{render_table(splits, SPLIT_FIELDNAMES)}</section>
  <section class="panel"><h2>Carriers</h2>{render_table(carriers, CARRIER_FIELDNAMES)}</section>
  <script type="application/json" id="external-terminal-spatial-bridge-five-byte-target-carrier-split-data">{html.escape(data_json)}</script>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Split target-overlap atom-switch gates by carrier family.")
    parser.add_argument("--target-gate-summary", type=Path, default=DEFAULT_TARGET_GATE_SUMMARY)
    parser.add_argument("--target-gate-gates", type=Path, default=DEFAULT_TARGET_GATE_GATES)
    parser.add_argument("--target-gate-families", type=Path, default=DEFAULT_TARGET_GATE_FAMILIES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex External Terminal Spatial Bridge Five-Byte Target Carrier Split Probe",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, splits, carriers = build(
        read_rows(args.target_gate_summary),
        read_rows(args.target_gate_gates),
        read_rows(args.target_gate_families),
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "splits.csv", SPLIT_FIELDNAMES, splits)
    write_csv(args.output / "carriers.csv", CARRIER_FIELDNAMES, carriers)
    (args.output / "index.html").write_text(
        build_html(summary, splits, carriers, args.output, args.title),
        encoding="utf-8",
    )
    print(
        "External terminal spatial bridge five-byte target carrier split probe: "
        f"splits={summary['carrier_split_rows']} "
        f"carriers={summary['target_carrier_family_rows']} "
        f"indirect={summary['indirect_carrier_split_rows']} "
        f"direct={summary['direct_carrier_switch_rows']} "
        f"promotion_ready={summary['promotion_ready_bytes']} "
        f"issues={summary['issue_rows']}"
    )
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
