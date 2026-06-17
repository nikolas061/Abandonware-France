#!/usr/bin/env python3
"""Inspect local atom switches inside the target-carrying five-byte family."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
from collections import Counter
from pathlib import Path

from lolg_tex_gap_opcode_probe import relative_href, write_csv


DEFAULT_CARRIER_SPLIT_SUMMARY = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_split/summary.csv"
)
DEFAULT_NON_TAIL_CANDIDATES = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_non_tail_support/candidates.csv"
)
DEFAULT_OUTPUT = Path(
    "output/tex_gradient_sequence_high_safe_low_exception_external_terminal_spatial_bridge_five_byte_target_carrier_local_switch"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "target_spans",
    "target_bytes",
    "carrier_shape",
    "target_carrier",
    "switch_position",
    "carrier_candidate_rows",
    "carrier_target_rows",
    "carrier_non_target_rows",
    "carrier_switch_atom_rows",
    "carrier_switch_atoms",
    "target_switch_atom_rows",
    "non_target_switch_atom_rows",
    "shared_target_non_target_atom_rows",
    "target_only_switch_atom_rows",
    "non_target_only_switch_atom_rows",
    "best_target_atom",
    "best_non_target_atom",
    "best_target_template",
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
    "switch_atom",
    "target_rows",
    "non_target_rows",
    "target_frontiers",
    "non_target_frontiers",
    "target_sample_rows",
    "non_target_sample_rows",
    "sample_starts",
    "sample_matches",
    "carrier_verdict",
]

SAMPLE_FIELDNAMES = [
    "rank",
    "variant_rank",
    "template_key",
    "switch_atom",
    "frontier_id",
    "sample_class",
    "span_start",
    "span_end",
    "sample_hex",
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


def template_body(template_key: str) -> list[str]:
    parts = [part for part in template_key.split("|") if part]
    return parts[1:] if len(parts) > 1 else parts


def template_shape(template_key: str) -> str:
    return "|".join(atom[:1] for atom in template_body(template_key))


def split_values(text: str) -> set[str]:
    return {part for part in text.replace(";", ",").split(",") if part}


def switch_atom(template_key: str, position: int) -> str:
    body = template_body(template_key)
    if 1 <= position <= len(body):
        return body[position - 1]
    return ""


def parse_samples(row: dict[str, str], switch_atom_value: str) -> list[dict[str, str]]:
    target_frontiers = split_values(row.get("target_frontiers", ""))
    samples: list[dict[str, str]] = []
    for match in SAMPLE_RE.finditer(row.get("sample_matches", "")):
        frontier = match.group("frontier")
        samples.append(
            {
                "rank": "",
                "variant_rank": row.get("variant_rank", ""),
                "template_key": row.get("template_key", ""),
                "switch_atom": switch_atom_value,
                "frontier_id": frontier,
                "sample_class": "target" if frontier in target_frontiers else "non_target",
                "span_start": match.group("start"),
                "span_end": match.group("end"),
                "sample_hex": match.group("hex"),
            }
        )
    return samples


def candidate_verdict(target_sample_rows: int, non_target_sample_rows: int) -> str:
    if target_sample_rows > 0 and non_target_sample_rows == 0:
        return "target_only_carrier_atom"
    if target_sample_rows > 0 and non_target_sample_rows > 0:
        return "shared_target_non_target_carrier_atom"
    if non_target_sample_rows > 0:
        return "non_target_only_carrier_atom"
    return "unsampled_carrier_atom"


def build(
    carrier_summary_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]]]:
    carrier_summary = carrier_summary_rows[0] if carrier_summary_rows else {}
    shape = carrier_summary.get("best_carrier_shape", "")
    target_carriers = [carrier for carrier in carrier_summary.get("best_target_carriers", "").split(";") if carrier]
    target_carrier = target_carriers[0] if target_carriers else ""
    switch_position = int_value(carrier_summary, "switch_position")
    issues: list[str] = []
    if not shape:
        issues.append("missing_carrier_shape")
    if not target_carrier:
        issues.append("missing_target_carrier")
    if switch_position <= 0:
        issues.append("missing_switch_position")

    scoped_candidates = [
        row
        for row in candidate_rows
        if template_shape(row.get("template_key", "")) == shape
        and row.get("non_target_frontiers", "") == target_carrier
    ]
    output_candidates: list[dict[str, str]] = []
    sample_rows: list[dict[str, str]] = []
    atom_targets: dict[str, Counter[str]] = {}
    for row in scoped_candidates:
        atom = switch_atom(row.get("template_key", ""), switch_position)
        samples = parse_samples(row, atom)
        target_samples = [sample for sample in samples if sample.get("sample_class") == "target"]
        non_target_samples = [sample for sample in samples if sample.get("sample_class") != "target"]
        starts = sorted({int_value(sample, "span_start") for sample in samples})
        atom_targets.setdefault(atom, Counter())
        atom_targets[atom]["target"] += len(target_samples)
        atom_targets[atom]["non_target"] += len(non_target_samples)
        output_candidates.append(
            {
                "rank": "",
                "variant_rank": row.get("variant_rank", ""),
                "template_key": row.get("template_key", ""),
                "switch_atom": atom,
                "target_rows": row.get("target_rows", "0"),
                "non_target_rows": row.get("non_target_rows", "0"),
                "target_frontiers": row.get("target_frontiers", ""),
                "non_target_frontiers": row.get("non_target_frontiers", ""),
                "target_sample_rows": str(len(target_samples)),
                "non_target_sample_rows": str(len(non_target_samples)),
                "sample_starts": ",".join(str(start) for start in starts),
                "sample_matches": row.get("sample_matches", ""),
                "carrier_verdict": candidate_verdict(len(target_samples), len(non_target_samples)),
            }
        )
        sample_rows.extend(samples)

    output_candidates.sort(
        key=lambda row: (
            row.get("carrier_verdict") != "target_only_carrier_atom",
            row.get("carrier_verdict") != "shared_target_non_target_carrier_atom",
            -int_value(row, "target_sample_rows"),
            int_value(row, "variant_rank"),
        )
    )
    for index, row in enumerate(output_candidates, start=1):
        row["rank"] = str(index)
    sample_rows.sort(
        key=lambda row: (
            row.get("sample_class") != "target",
            int_value(row, "span_start"),
            int_value(row, "variant_rank"),
        )
    )
    for index, row in enumerate(sample_rows, start=1):
        row["rank"] = str(index)

    target_atoms = {atom for atom, counts in atom_targets.items() if counts["target"] > 0}
    non_target_atoms = {atom for atom, counts in atom_targets.items() if counts["non_target"] > 0}
    shared_atoms = target_atoms & non_target_atoms
    target_only_atoms = target_atoms - non_target_atoms
    non_target_only_atoms = non_target_atoms - target_atoms
    best_target = max(target_atoms, key=lambda atom: atom_targets[atom]["target"], default="")
    best_non_target = max(non_target_atoms, key=lambda atom: atom_targets[atom]["non_target"], default="")
    best_target_row = next((row for row in output_candidates if row.get("switch_atom") == best_target), {})
    if issues:
        verdict = "carrier_local_switch_has_issues"
        next_probe = "fix carrier-local compact-control switch issues"
    elif target_only_atoms:
        verdict = "carrier_local_target_only_atom_found"
        next_probe = "review carrier-local target-only atom for promotion"
    elif shared_atoms:
        verdict = "carrier_local_switch_shared_with_non_target"
        next_probe = "derive carrier-local context split for target family 29"
    elif target_atoms:
        verdict = "carrier_local_target_atoms_without_non_target_samples"
        next_probe = "expand carrier-local non-target validation for target family 29"
    else:
        verdict = "no_carrier_local_target_switch"
        next_probe = "derive alternate carrier-local atom features for target family 29"
    summary = {
        "scope": "total",
        "candidate_mode": "external_terminal_spatial_bridge_five_byte_target_carrier_local_switch",
        "target_spans": carrier_summary.get("target_spans", "0"),
        "target_bytes": carrier_summary.get("target_bytes", "0"),
        "carrier_shape": shape,
        "target_carrier": target_carrier,
        "switch_position": str(switch_position),
        "carrier_candidate_rows": str(len(output_candidates)),
        "carrier_target_rows": str(sum(int_value(row, "target_rows") for row in output_candidates)),
        "carrier_non_target_rows": str(sum(int_value(row, "non_target_rows") for row in output_candidates)),
        "carrier_switch_atom_rows": str(len(atom_targets)),
        "carrier_switch_atoms": ";".join(sorted(atom_targets)),
        "target_switch_atom_rows": str(len(target_atoms)),
        "non_target_switch_atom_rows": str(len(non_target_atoms)),
        "shared_target_non_target_atom_rows": str(len(shared_atoms)),
        "target_only_switch_atom_rows": str(len(target_only_atoms)),
        "non_target_only_switch_atom_rows": str(len(non_target_only_atoms)),
        "best_target_atom": best_target,
        "best_non_target_atom": best_non_target,
        "best_target_template": best_target_row.get("template_key", ""),
        "review_verdict": verdict,
        "next_probe": next_probe,
        "promotion_candidate_bytes": "0",
        "promotion_ready_bytes": "0",
        "issue_rows": str(len(issues)),
    }
    return summary, output_candidates, sample_rows


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
    samples: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "candidates": candidates, "samples": samples}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("candidates.csv", output_dir / "candidates.csv"),
            ("samples.csv", output_dir / "samples.csv"),
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
    <div class="muted">Profiles target and non-target samples for the target-carrying family 29.</div>
  </header>
  <section class="stats">
    <div class="stat"><div class="muted">Carrier candidates</div><div class="value">{summary['carrier_candidate_rows']}</div></div>
    <div class="stat"><div class="muted">Switch atoms</div><div class="value">{summary['carrier_switch_atom_rows']}</div></div>
    <div class="stat"><div class="muted">Shared atoms</div><div class="value">{summary['shared_target_non_target_atom_rows']}</div></div>
    <div class="stat"><div class="muted">Target-only atoms</div><div class="value warn">{summary['target_only_switch_atom_rows']}</div></div>
    <div class="stat"><div class="muted">Promotion-ready</div><div class="value warn">{summary['promotion_ready_bytes']}</div></div>
  </section>
  <section class="panel"><h2>Files</h2>{links}</section>
  <section class="panel">
    <h2>Verdict</h2>
    <p><code>{html.escape(summary['review_verdict'])}</code></p>
    <p class="muted">Next: <code>{html.escape(summary['next_probe'])}</code>.</p>
  </section>
  <section class="panel"><h2>Candidates</h2>{render_table(candidates, CANDIDATE_FIELDNAMES)}</section>
  <section class="panel"><h2>Samples</h2>{render_table(samples, SAMPLE_FIELDNAMES)}</section>
  <script type="application/json" id="external-terminal-spatial-bridge-five-byte-target-carrier-local-switch-data">{html.escape(data_json)}</script>
</main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect target-carrier local atom switches.")
    parser.add_argument("--carrier-split-summary", type=Path, default=DEFAULT_CARRIER_SPLIT_SUMMARY)
    parser.add_argument("--non-tail-candidates", type=Path, default=DEFAULT_NON_TAIL_CANDIDATES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex External Terminal Spatial Bridge Five-Byte Target Carrier Local Switch Probe",
    )
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    summary, candidates, samples = build(
        read_rows(args.carrier_split_summary),
        read_rows(args.non_tail_candidates),
    )
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "candidates.csv", CANDIDATE_FIELDNAMES, candidates)
    write_csv(args.output / "samples.csv", SAMPLE_FIELDNAMES, samples)
    (args.output / "index.html").write_text(
        build_html(summary, candidates, samples, args.output, args.title),
        encoding="utf-8",
    )
    print(
        "External terminal spatial bridge five-byte target carrier local switch probe: "
        f"candidates={summary['carrier_candidate_rows']} "
        f"switch_atoms={summary['carrier_switch_atom_rows']} "
        f"shared={summary['shared_target_non_target_atom_rows']} "
        f"target_only={summary['target_only_switch_atom_rows']} "
        f"promotion_ready={summary['promotion_ready_bytes']} "
        f"issues={summary['issue_rows']}"
    )
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
