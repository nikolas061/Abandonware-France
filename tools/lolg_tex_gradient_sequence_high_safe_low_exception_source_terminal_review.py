#!/usr/bin/env python3
"""Review false-free terminal contexts against high-safe source chains."""

from __future__ import annotations

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path

from lolg_tex_micro_mixed_value_payload_state_opcode_probe import int_value, ratio, write_csv


DEFAULT_TERMINALS = Path("output/tex_gradient_sequence_high_safe_low_exception_source_terminal/terminals.csv")
DEFAULT_CHAINS = Path("output/tex_gradient_sequence_high_safe_low_exception_source_chain/chains.csv")
DEFAULT_SLOTS = Path("output/tex_gradient_sequence_high_safe_low_exception_source_dependency/slots.csv")
DEFAULT_OUTPUT = Path("output/tex_gradient_sequence_high_safe_low_exception_source_terminal_review")

SUMMARY_FIELDNAMES = [
    "scope",
    "candidate_mode",
    "terminal_slots",
    "predicted_terminal_slots",
    "terminal_correct_slots",
    "terminal_false_slots",
    "terminal_unknown_slots",
    "covered_chains",
    "covered_root_slots",
    "covered_contexts",
    "covered_chain_length2",
    "covered_chain_length3",
    "oracle_delta_root_exact",
    "oracle_delta_root_false",
    "oracle_delta_root_unknown",
    "oracle_delta_root_precision",
    "promotion_candidate_bytes",
    "promotion_ready_bytes",
    "issue_rows",
]

TERMINAL_FIELDNAMES = [
    "rank",
    "terminal_slot_rank",
    "frontier_id",
    "start",
    "target_offset",
    "target_low",
    "low_bucket",
    "root_chains",
    "covered_chains",
    "terminal_context",
    "terminal_prediction",
    "terminal_verdict",
    "source_availability",
    "source_location",
    "source_decoded_byte",
    "source_expected_byte",
    "review_verdict",
]

CHAIN_FIELDNAMES = [
    "rank",
    "root_slot_rank",
    "root_frontier_id",
    "root_target_offset",
    "root_target_low",
    "root_low_bucket",
    "chain_length",
    "terminal_slot_rank",
    "terminal_frontier_id",
    "terminal_target_offset",
    "terminal_target_low",
    "terminal_context",
    "terminal_prediction",
    "terminal_verdict",
    "delta_path",
    "oracle_delta_root_low",
    "oracle_delta_root_verdict",
    "path",
]

GROUP_FIELDNAMES = [
    "rank",
    "terminal_context",
    "terminal_prediction",
    "terminal_slots",
    "covered_chains",
    "root_lows",
    "oracle_delta_root_exact",
    "oracle_delta_root_false",
    "verdict",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def low_add(low: str, delta: int) -> str:
    if not low:
        return ""
    return f"{(int(low, 16) + delta) & 0x0F:x}"


def path_deltas(path: str, slots_by_rank: dict[str, dict[str, str]]) -> list[int]:
    ranks = [rank for rank in path.split("->") if rank]
    deltas: list[int] = []
    for rank in ranks[:-1]:
        row = slots_by_rank.get(rank, {})
        value = row.get("source_low_delta", "")
        if value == "":
            return []
        deltas.append(int_value(row, "source_low_delta") & 0x0F)
    return deltas


def build_chain_rows(
    terminal_rows: list[dict[str, str]],
    chain_rows: list[dict[str, str]],
    slot_rows: list[dict[str, str]],
) -> list[dict[str, object]]:
    terminals_by_rank = {row["terminal_slot_rank"]: row for row in terminal_rows}
    slots_by_rank = {row["rank"]: row for row in slot_rows}
    output: list[dict[str, object]] = []
    for chain in chain_rows:
        terminal = terminals_by_rank.get(chain.get("terminal_slot_rank", ""), {})
        prediction = terminal.get("terminal_prediction", "")
        if not prediction:
            continue
        deltas = path_deltas(chain.get("path", ""), slots_by_rank)
        predicted_root_low = low_add(prediction, sum(deltas)) if deltas else ""
        if not predicted_root_low:
            oracle_verdict = "unknown"
        elif predicted_root_low == chain.get("root_target_low", ""):
            oracle_verdict = "exact"
        else:
            oracle_verdict = "false"
        output.append(
            {
                "rank": len(output) + 1,
                "root_slot_rank": chain.get("root_slot_rank", ""),
                "root_frontier_id": chain.get("root_frontier_id", ""),
                "root_target_offset": chain.get("root_target_offset", ""),
                "root_target_low": chain.get("root_target_low", ""),
                "root_low_bucket": chain.get("root_low_bucket", ""),
                "chain_length": chain.get("chain_length", ""),
                "terminal_slot_rank": chain.get("terminal_slot_rank", ""),
                "terminal_frontier_id": chain.get("terminal_frontier_id", ""),
                "terminal_target_offset": chain.get("terminal_target_offset", ""),
                "terminal_target_low": chain.get("terminal_target_low", ""),
                "terminal_context": terminal.get("terminal_context", ""),
                "terminal_prediction": prediction,
                "terminal_verdict": terminal.get("terminal_verdict", ""),
                "delta_path": "+".join(str(delta) for delta in deltas),
                "oracle_delta_root_low": predicted_root_low,
                "oracle_delta_root_verdict": oracle_verdict,
                "path": chain.get("path", ""),
            }
        )
    return output


def build_terminal_rows(
    terminal_rows: list[dict[str, str]],
    covered_chains: list[dict[str, object]],
) -> list[dict[str, object]]:
    covered_counts = Counter(str(row.get("terminal_slot_rank", "")) for row in covered_chains)
    output: list[dict[str, object]] = []
    for row in terminal_rows:
        prediction = row.get("terminal_prediction", "")
        if prediction:
            review_verdict = "covered" if covered_counts[row["terminal_slot_rank"]] else "predicted_terminal_only"
        else:
            review_verdict = "not_predicted"
        output.append(
            {
                "rank": row.get("rank", ""),
                "terminal_slot_rank": row.get("terminal_slot_rank", ""),
                "frontier_id": row.get("frontier_id", ""),
                "start": row.get("start", ""),
                "target_offset": row.get("target_offset", ""),
                "target_low": row.get("target_low", ""),
                "low_bucket": row.get("low_bucket", ""),
                "root_chains": row.get("root_chains", ""),
                "covered_chains": covered_counts[row.get("terminal_slot_rank", "")],
                "terminal_context": row.get("terminal_context", ""),
                "terminal_prediction": prediction,
                "terminal_verdict": row.get("terminal_verdict", ""),
                "source_availability": row.get("source_availability", ""),
                "source_location": row.get("source_location", ""),
                "source_decoded_byte": row.get("source_decoded_byte", ""),
                "source_expected_byte": row.get("source_expected_byte", ""),
                "review_verdict": review_verdict,
            }
        )
    return output


def build_group_rows(chain_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in chain_rows:
        grouped[(str(row.get("terminal_context", "")), str(row.get("terminal_prediction", "")))].append(row)

    output: list[dict[str, object]] = []
    for (context, prediction), members in grouped.items():
        verdicts = Counter(str(row.get("oracle_delta_root_verdict", "")) for row in members)
        root_lows = Counter(str(row.get("root_target_low", "")) for row in members)
        if verdicts["false"]:
            verdict = "oracle_delta_conflict"
        elif verdicts["exact"]:
            verdict = "oracle_delta_exact_review"
        else:
            verdict = "oracle_delta_unknown"
        output.append(
            {
                "rank": 0,
                "terminal_context": context,
                "terminal_prediction": prediction,
                "terminal_slots": len({str(row.get("terminal_slot_rank", "")) for row in members}),
                "covered_chains": len(members),
                "root_lows": "|".join(f"{low}:{count}" for low, count in sorted(root_lows.items())),
                "oracle_delta_root_exact": verdicts["exact"],
                "oracle_delta_root_false": verdicts["false"],
                "verdict": verdict,
            }
        )
    output.sort(
        key=lambda row: (
            -int_value(row, "oracle_delta_root_exact"),
            int_value(row, "oracle_delta_root_false"),
            str(row.get("terminal_context", "")),
        )
    )
    for index, row in enumerate(output, start=1):
        row["rank"] = index
    return output


def build(
    terminal_rows: list[dict[str, str]],
    chain_rows: list[dict[str, str]],
    slot_rows: list[dict[str, str]],
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    covered_chains = build_chain_rows(terminal_rows, chain_rows, slot_rows)
    terminals = build_terminal_rows(terminal_rows, covered_chains)
    groups = build_group_rows(covered_chains)
    terminal_verdicts = Counter(row.get("terminal_verdict", "") for row in terminal_rows)
    chain_verdicts = Counter(str(row.get("oracle_delta_root_verdict", "")) for row in covered_chains)
    covered_root_slots = {str(row.get("root_slot_rank", "")) for row in covered_chains}
    covered_contexts = {str(row.get("terminal_context", "")) for row in covered_chains}
    predicted = sum(1 for row in terminal_rows if row.get("terminal_prediction", ""))
    summary = {
        "scope": "total",
        "candidate_mode": "high_safe_low_exception_source_terminal_review",
        "terminal_slots": len(terminal_rows),
        "predicted_terminal_slots": predicted,
        "terminal_correct_slots": terminal_verdicts["correct"],
        "terminal_false_slots": terminal_verdicts["false"],
        "terminal_unknown_slots": terminal_verdicts["unknown"],
        "covered_chains": len(covered_chains),
        "covered_root_slots": len(covered_root_slots),
        "covered_contexts": len(covered_contexts),
        "covered_chain_length2": sum(1 for row in covered_chains if int_value(row, "chain_length") == 2),
        "covered_chain_length3": sum(1 for row in covered_chains if int_value(row, "chain_length") == 3),
        "oracle_delta_root_exact": chain_verdicts["exact"],
        "oracle_delta_root_false": chain_verdicts["false"],
        "oracle_delta_root_unknown": chain_verdicts["unknown"],
        "oracle_delta_root_precision": ratio(chain_verdicts["exact"], chain_verdicts["exact"] + chain_verdicts["false"]),
        "promotion_candidate_bytes": len(covered_chains),
        "promotion_ready_bytes": 0,
        "issue_rows": 0,
    }
    return summary, terminals, covered_chains, groups


def render_table(rows: list[dict[str, object]], fields: list[str], limit: int = 220) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(row.get(field, '')))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, object],
    terminals: list[dict[str, object]],
    chains: list[dict[str, object]],
    groups: list[dict[str, object]],
    title: str,
) -> str:
    data_json = json.dumps(
        {"summary": summary, "terminals": terminals, "chains": chains, "groups": groups},
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
table {{ border-collapse: collapse; width: 100%; min-width: 1900px; }}
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
  <div class="box"><div class="num">{summary['predicted_terminal_slots']}</div><div class="muted">predicted terminals</div></div>
  <div class="box"><div class="num">{summary['covered_chains']}</div><div class="muted">covered chains</div></div>
  <div class="box"><div class="num">{summary['oracle_delta_root_exact']}/{summary['oracle_delta_root_false']}</div><div class="muted">oracle delta exact/false</div></div>
  <div class="box"><div class="num">{summary['covered_contexts']}</div><div class="muted">covered contexts</div></div>
  <div class="box"><div class="num">{summary['promotion_ready_bytes']}</div><div class="muted">promotion-ready bytes</div></div>
</div>
<div class="panel"><h2>Terminal context groups</h2>{render_table(groups, GROUP_FIELDNAMES)}</div>
<div class="panel"><h2>Covered chains</h2>{render_table(chains, CHAIN_FIELDNAMES)}</div>
<div class="panel"><h2>Terminals</h2>{render_table(terminals, TERMINAL_FIELDNAMES)}</div>
<script type="application/json" id="gradient-sequence-high-safe-low-exception-source-terminal-review-data">{html.escape(data_json)}</script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Review false-free source-terminal context candidates.")
    parser.add_argument("--terminals", type=Path, default=DEFAULT_TERMINALS)
    parser.add_argument("--chains", type=Path, default=DEFAULT_CHAINS)
    parser.add_argument("--slots", type=Path, default=DEFAULT_SLOTS)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Gradient Sequence High-Safe Low Exception Source-Terminal Review",
    )
    args = parser.parse_args()

    summary, terminals, chains, groups = build(read_csv(args.terminals), read_csv(args.chains), read_csv(args.slots))
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(args.output / "terminals.csv", TERMINAL_FIELDNAMES, terminals)
    write_csv(args.output / "chains.csv", CHAIN_FIELDNAMES, chains)
    write_csv(args.output / "groups.csv", GROUP_FIELDNAMES, groups)
    html_path = args.output / "index.html"
    html_path.write_text(build_html(summary, terminals, chains, groups, args.title))

    print(f"Predicted terminals: {summary['predicted_terminal_slots']} / {summary['terminal_slots']}")
    print(f"Covered chains: {summary['covered_chains']}")
    print(
        "Oracle delta replay: "
        f"{summary['oracle_delta_root_exact']} exact / {summary['oracle_delta_root_false']} false"
    )
    print(f"Promotion-ready bytes: {summary['promotion_ready_bytes']}")
    print(f"HTML: {html_path}")


if __name__ == "__main__":
    main()
