#!/usr/bin/env python3
"""Review the residual high-safe source dependency core after promoted replays."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_gradient_sequence_high_safe_low_exception_source_chain_probe import (
    build_chains,
    build_terminals,
)
from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value, write_csv


DEFAULT_SLOTS = Path("output/tex_gradient_sequence_high_safe_low_exception_source_dependency_second_promoted_replay/slots.csv")
DEFAULT_EDGES = Path("output/tex_gradient_sequence_high_safe_low_exception_source_dependency_second_promoted_replay/edges.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_high_safe_low_exception_source_dependency_residual_core")

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "slots",
    "unknown_highsafe_slots",
    "unknown_outside_slots",
    "dependency_edges",
    "unknown_dependency_edges",
    "top_unknown_edge",
    "top_unknown_edge_unknown_slots",
    "terminal_slots",
    "terminal_known_slots",
    "terminal_unknown_outside_slots",
    "terminal_other_slots",
    "terminal_known_chains",
    "terminal_unknown_outside_chains",
    "terminal_other_chains",
    "terminal_known_edge_roots",
    "terminal_unknown_edge_roots",
    "dominant_blocker",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

EDGE_FIELDNAMES = [
    "rank",
    "edge_key",
    "target_frontier_id",
    "target_start",
    "source_frontier_id",
    "source_start",
    "slots",
    "exception_slots",
    "source_known_slots",
    "source_unknown_slots",
    "terminal_known_chains",
    "terminal_unknown_outside_chains",
    "terminal_other_chains",
    "terminal_slots",
    "top_terminal_slot_rank",
    "top_terminal_roots",
    "low_delta_histogram",
    "next_probe",
]

TERMINAL_FIELDNAMES = [
    "rank",
    "terminal_slot_rank",
    "terminal_frontier_id",
    "terminal_start",
    "terminal_target_offset",
    "terminal_target_low",
    "terminal_low_bucket",
    "root_chains",
    "terminal_source_availability",
    "terminal_source_location",
    "terminal_source_expected_byte",
    "terminal_source_decoded_byte",
    "terminal_dependency_verdict",
    "incoming_edges",
    "next_probe",
]

ROOT_FIELDNAMES = [
    "rank",
    "root_slot_rank",
    "edge_key",
    "root_frontier_id",
    "root_start",
    "root_target_offset",
    "root_target_low",
    "root_low_bucket",
    "source_slot_rank",
    "source_frontier_id",
    "source_start",
    "source_expected_byte",
    "source_decoded_byte",
    "chain_length",
    "terminal_slot_rank",
    "terminal_frontier_id",
    "terminal_target_offset",
    "terminal_target_low",
    "terminal_source_availability",
    "terminal_source_location",
    "path",
    "next_probe",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def edge_key(row: dict[str, str]) -> str:
    return (
        f"{row.get('frontier_id', '')}|{row.get('start', '')}->"
        f"{row.get('source_slot_frontier_id', '')}|{row.get('source_slot_start', '')}"
    )


def is_unknown_highsafe(row: dict[str, str]) -> bool:
    return (
        row.get("source_availability") == "unknown_source"
        and row.get("source_location") == "in_highsafe"
        and bool(row.get("source_slot_rank", ""))
    )


def terminal_state(row: dict[str, object]) -> str:
    availability = str(row.get("terminal_source_availability", ""))
    location = str(row.get("terminal_source_location", ""))
    if availability == "known_source":
        return "known_terminal_source"
    if availability == "unknown_source" and location == "outside_highsafe":
        return "external_unknown_terminal_source"
    return "other_terminal_source"


def next_probe_for_counts(known_chains: int, external_chains: int, other_chains: int) -> str:
    if external_chains > 0:
        return "resolve external terminal source bytes"
    if known_chains > 0:
        return "derive a stronger terminal transform from known-source chains"
    if other_chains > 0:
        return "inspect non-terminal high-safe chain tail"
    return "no residual high-safe roots"


def build_root_rows(
    slot_rows: list[dict[str, str]],
    chain_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    slots_by_rank = {row["rank"]: row for row in slot_rows}
    chains_by_root = {str(row.get("root_slot_rank", "")): row for row in chain_rows}
    output: list[dict[str, object]] = []
    for slot in slot_rows:
        if not is_unknown_highsafe(slot):
            continue
        chain = chains_by_root.get(slot["rank"], {})
        terminal_rank = str(chain.get("terminal_slot_rank", ""))
        terminal = slots_by_rank.get(terminal_rank, {})
        output.append(
            {
                "rank": len(output) + 1,
                "root_slot_rank": slot.get("rank", ""),
                "edge_key": edge_key(slot),
                "root_frontier_id": slot.get("frontier_id", ""),
                "root_start": slot.get("start", ""),
                "root_target_offset": slot.get("target_offset", ""),
                "root_target_low": slot.get("target_low", ""),
                "root_low_bucket": slot.get("low_bucket", ""),
                "source_slot_rank": slot.get("source_slot_rank", ""),
                "source_frontier_id": slot.get("source_slot_frontier_id", ""),
                "source_start": slot.get("source_slot_start", ""),
                "source_expected_byte": slot.get("source_expected_byte", ""),
                "source_decoded_byte": slot.get("source_decoded_byte", ""),
                "chain_length": chain.get("chain_length", ""),
                "terminal_slot_rank": terminal_rank,
                "terminal_frontier_id": terminal.get("frontier_id", ""),
                "terminal_target_offset": terminal.get("target_offset", ""),
                "terminal_target_low": terminal.get("target_low", ""),
                "terminal_source_availability": chain.get("terminal_source_availability", ""),
                "terminal_source_location": chain.get("terminal_source_location", ""),
                "path": chain.get("path", ""),
                "next_probe": next_probe_for_counts(
                    1 if terminal_state(chain) == "known_terminal_source" else 0,
                    1 if terminal_state(chain) == "external_unknown_terminal_source" else 0,
                    1 if terminal_state(chain) == "other_terminal_source" else 0,
                ),
            }
        )
    return output


def build_edge_rows(
    edge_rows: list[dict[str, str]],
    root_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    roots_by_edge: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in root_rows:
        roots_by_edge[str(row.get("edge_key", ""))].append(row)

    output: list[dict[str, object]] = []
    for edge in edge_rows:
        key = edge.get("edge_key", "")
        roots = roots_by_edge.get(key, [])
        terminal_counts = Counter(str(row.get("terminal_slot_rank", "")) for row in roots)
        state_counts = Counter(
            (
                "known_terminal_source"
                if row.get("terminal_source_availability") == "known_source"
                else "external_unknown_terminal_source"
                if row.get("terminal_source_availability") == "unknown_source"
                and row.get("terminal_source_location") == "outside_highsafe"
                else "other_terminal_source"
            )
            for row in roots
        )
        top_terminal = terminal_counts.most_common(1)[0] if terminal_counts else ("", 0)
        output.append(
            {
                "rank": edge.get("rank", ""),
                "edge_key": key,
                "target_frontier_id": edge.get("target_frontier_id", ""),
                "target_start": edge.get("target_start", ""),
                "source_frontier_id": edge.get("source_frontier_id", ""),
                "source_start": edge.get("source_start", ""),
                "slots": edge.get("slots", "0"),
                "exception_slots": edge.get("exception_slots", "0"),
                "source_known_slots": edge.get("source_known_slots", "0"),
                "source_unknown_slots": edge.get("source_unknown_slots", "0"),
                "terminal_known_chains": state_counts.get("known_terminal_source", 0),
                "terminal_unknown_outside_chains": state_counts.get("external_unknown_terminal_source", 0),
                "terminal_other_chains": state_counts.get("other_terminal_source", 0),
                "terminal_slots": len(terminal_counts),
                "top_terminal_slot_rank": top_terminal[0],
                "top_terminal_roots": top_terminal[1],
                "low_delta_histogram": edge.get("low_delta_histogram", ""),
                "next_probe": next_probe_for_counts(
                    state_counts.get("known_terminal_source", 0),
                    state_counts.get("external_unknown_terminal_source", 0),
                    state_counts.get("other_terminal_source", 0),
                ),
            }
        )
    output.sort(
        key=lambda row: (
            -int_value(row, "source_unknown_slots"),
            -int_value(row, "terminal_unknown_outside_chains"),
            int_value(row, "rank"),
        )
    )
    for index, row in enumerate(output, start=1):
        row["rank"] = index
    return output


def build_terminal_rows(
    terminal_rows: list[dict[str, object]],
    root_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    edges_by_terminal: dict[str, set[str]] = defaultdict(set)
    for row in root_rows:
        terminal_rank = str(row.get("terminal_slot_rank", ""))
        if terminal_rank:
            edges_by_terminal[terminal_rank].add(str(row.get("edge_key", "")))

    output: list[dict[str, object]] = []
    for row in terminal_rows:
        state = terminal_state(row)
        output.append(
            {
                "rank": row.get("rank", ""),
                "terminal_slot_rank": row.get("terminal_slot_rank", ""),
                "terminal_frontier_id": row.get("terminal_frontier_id", ""),
                "terminal_start": row.get("terminal_start", ""),
                "terminal_target_offset": row.get("terminal_target_offset", ""),
                "terminal_target_low": row.get("terminal_target_low", ""),
                "terminal_low_bucket": row.get("terminal_low_bucket", ""),
                "root_chains": row.get("root_chains", ""),
                "terminal_source_availability": row.get("terminal_source_availability", ""),
                "terminal_source_location": row.get("terminal_source_location", ""),
                "terminal_source_expected_byte": row.get("terminal_source_expected_byte", ""),
                "terminal_source_decoded_byte": row.get("terminal_source_decoded_byte", ""),
                "terminal_dependency_verdict": row.get("terminal_dependency_verdict", ""),
                "incoming_edges": "|".join(sorted(edges_by_terminal[str(row.get("terminal_slot_rank", ""))])),
                "next_probe": next_probe_for_counts(
                    int_value(row, "root_chains") if state == "known_terminal_source" else 0,
                    int_value(row, "root_chains") if state == "external_unknown_terminal_source" else 0,
                    int_value(row, "root_chains") if state == "other_terminal_source" else 0,
                ),
            }
        )
    return output


def build_summary(
    slot_rows: list[dict[str, str]],
    edge_rows: list[dict[str, object]],
    terminal_rows: list[dict[str, object]],
    root_rows: list[dict[str, object]],
) -> dict[str, object]:
    terminal_state_counts = Counter(terminal_state(row) for row in terminal_rows)
    chain_state_counts = Counter(
        (
            "known_terminal_source"
            if row.get("terminal_source_availability") == "known_source"
            else "external_unknown_terminal_source"
            if row.get("terminal_source_availability") == "unknown_source"
            and row.get("terminal_source_location") == "outside_highsafe"
            else "other_terminal_source"
        )
        for row in root_rows
    )
    top_edge = edge_rows[0] if edge_rows else {}
    dominant = next_probe_for_counts(
        chain_state_counts.get("known_terminal_source", 0),
        chain_state_counts.get("external_unknown_terminal_source", 0),
        chain_state_counts.get("other_terminal_source", 0),
    )
    return {
        "scope": "total",
        "candidate_mode": "high_safe_low_exception_source_dependency_residual_core",
        "slots": len(slot_rows),
        "unknown_highsafe_slots": sum(1 for row in slot_rows if is_unknown_highsafe(row)),
        "unknown_outside_slots": sum(
            1
            for row in slot_rows
            if row.get("source_availability") == "unknown_source"
            and row.get("source_location") == "outside_highsafe"
        ),
        "dependency_edges": len(edge_rows),
        "unknown_dependency_edges": sum(1 for row in edge_rows if int_value(row, "source_unknown_slots") > 0),
        "top_unknown_edge": top_edge.get("edge_key", ""),
        "top_unknown_edge_unknown_slots": top_edge.get("source_unknown_slots", 0),
        "terminal_slots": len(terminal_rows),
        "terminal_known_slots": terminal_state_counts.get("known_terminal_source", 0),
        "terminal_unknown_outside_slots": terminal_state_counts.get("external_unknown_terminal_source", 0),
        "terminal_other_slots": terminal_state_counts.get("other_terminal_source", 0),
        "terminal_known_chains": chain_state_counts.get("known_terminal_source", 0),
        "terminal_unknown_outside_chains": chain_state_counts.get("external_unknown_terminal_source", 0),
        "terminal_other_chains": chain_state_counts.get("other_terminal_source", 0),
        "terminal_known_edge_roots": sum(int_value(row, "terminal_known_chains") for row in edge_rows),
        "terminal_unknown_edge_roots": sum(
            int_value(row, "terminal_unknown_outside_chains") for row in edge_rows
        ),
        "dominant_blocker": dominant,
        "promotion_candidate_bytes": 0,
        "promotion_ready_bytes": 0,
        "issue_rows": 0,
    }


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    edge_rows: list[dict[str, object]],
    terminal_rows: list[dict[str, object]],
    root_rows: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {
            "summary": summary,
            "edges": edge_rows,
            "terminals": terminal_rows,
            "roots": root_rows,
        },
        indent=2,
        sort_keys=True,
    )
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ margin: 2rem; background: #101214; color: #edf5f4; font: 14px/1.45 system-ui, sans-serif; }}
table {{ border-collapse: collapse; width: 100%; min-width: 2200px; }}
th, td {{ border: 1px solid #31424a; padding: .45rem .55rem; vertical-align: top; }}
th {{ color: #9dafb5; background: #172023; text-align: left; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: .75rem; margin: 1rem 0; }}
.box {{ border: 1px solid #31424a; background: #172023; padding: .75rem; }}
.num {{ font-size: 1.35rem; font-weight: 750; }}
.muted {{ color: #9dafb5; }}
.panel {{ overflow-x: auto; margin-top: 1rem; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="grid">
  <div class="box"><div class="num">{summary['unknown_highsafe_slots']}</div><div class="muted">unknown high-safe slots</div></div>
  <div class="box"><div class="num">{summary['dependency_edges']}</div><div class="muted">dependency edges</div></div>
  <div class="box"><div class="num">{summary['terminal_known_chains']}</div><div class="muted">known terminal chains</div></div>
  <div class="box"><div class="num">{summary['terminal_unknown_outside_chains']}</div><div class="muted">external terminal chains</div></div>
  <div class="box"><div class="num">{summary['top_unknown_edge']}</div><div class="muted">top unknown edge</div></div>
  <div class="box"><div class="num">{summary['dominant_blocker']}</div><div class="muted">dominant blocker</div></div>
</div>
<div class="panel"><h2>Edges</h2>{render_table(edge_rows, EDGE_FIELDNAMES)}</div>
<div class="panel"><h2>Terminals</h2>{render_table(terminal_rows, TERMINAL_FIELDNAMES)}</div>
<div class="panel"><h2>Roots</h2>{render_table(root_rows, ROOT_FIELDNAMES)}</div>
<script type="application/json" id="gradient-sequence-high-safe-low-exception-source-dependency-residual-core-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("--edges", type=Path, default=DEFAULT_EDGES)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Gradient Source Dependency Residual Core Review",
    )
    args = parser.parse_args()

    slot_rows = read_csv(args.slots)
    edge_rows = read_csv(args.edges)
    chains = build_chains(slot_rows)
    terminals = build_terminals(slot_rows, chains)
    root_rows = build_root_rows(slot_rows, chains)
    reviewed_edges = build_edge_rows(edge_rows, root_rows)
    reviewed_terminals = build_terminal_rows(terminals, root_rows)
    summary = build_summary(slot_rows, reviewed_edges, reviewed_terminals, root_rows)

    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "edges.csv", EDGE_FIELDNAMES, reviewed_edges)
    write_csv(args.output / "terminals.csv", TERMINAL_FIELDNAMES, reviewed_terminals)
    write_csv(args.output / "roots.csv", ROOT_FIELDNAMES, root_rows)
    html_path = args.output / "index.html"
    html_path.write_text(
        build_html(summary, reviewed_edges, reviewed_terminals, root_rows, args.title),
        encoding="utf-8",
    )

    print(f"Unknown high-safe slots: {summary['unknown_highsafe_slots']}")
    print(f"Dependency edges: {summary['dependency_edges']}")
    print(f"Known terminal chains: {summary['terminal_known_chains']}")
    print(f"External terminal chains: {summary['terminal_unknown_outside_chains']}")
    print(f"Top unknown edge: {summary['top_unknown_edge']} ({summary['top_unknown_edge_unknown_slots']} slots)")
    print(f"Dominant blocker: {summary['dominant_blocker']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
