#!/usr/bin/env python3
"""Replay the high-row byte-local selector with the threshold source guard."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_clean_prior_high_row_threshold_source_guard_promoted_replay")
DEFAULT_OBSERVATIONS = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_byte_local_start_non_oracle_guard_probe/"
    "byte_observations.csv"
)
DEFAULT_SWITCHES = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_byte_local_start_source_split_probe/"
    "source_split_switch_rows.csv"
)
DEFAULT_GUARD_PREDICTIONS = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_threshold_source_guard_probe/guard_predictions.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "total_bytes",
    "outlier_bytes",
    "switch_candidate_rows",
    "allowed_switch_rows",
    "blocked_false_switch_rows",
    "resolved_outliers",
    "unresolved_outliers",
    "false_switch_bytes",
    "false_delta_bytes",
    "total_le2_bytes",
    "total_le2_ratio",
    "issue_rows",
    "review_verdict",
    "next_probe",
]

OPERATION_FIELDNAMES = [
    "selector_name",
    "pair_id",
    "source_id",
    "byte_index",
    "selector_key",
    "selected_start",
    "selected_support_value_hex",
    "source_value_hex",
    "selected_delta",
    "chosen_start",
    "chosen_support_value_hex",
    "chosen_delta",
    "selected_outlier",
    "resolved_outlier",
    "false_switch",
    "guard_reason",
]

DECISION_FIELDNAMES = [
    "pair_id",
    "source_id",
    "byte_index",
    "selected_outlier",
    "false_switch_candidate",
    "source_known",
    "selected_delta_abs_gt2",
    "guard_predicted_abs_gt2",
    "allow_switch",
    "decision_reason",
    "selected_start",
    "chosen_start",
    "selected_delta",
    "chosen_delta",
]

SELECTOR_NAME = "threshold_source_guard/byte_index_selected_support_value"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def ratio(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.6f}" if denominator else "0.000000"


def row_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("pair_id", ""), row.get("source_id", ""), row.get("byte_index", "")


def allow_switch(row: dict[str, str], predictions: dict[tuple[str, str, str], dict[str, str]]) -> tuple[bool, str]:
    if row.get("selected_outlier") != "1":
        return False, "block_non_outlier"
    if row.get("source_known") == "1":
        if row.get("selected_delta_abs_gt2") == "1":
            return True, "known_source_delta_abs_gt2"
        return False, "known_source_delta_le2"
    prediction = predictions.get(row_key(row), {})
    if prediction.get("predicted_abs_gt2") == "1":
        return True, "threshold_source_guard_high_marker"
    return False, "threshold_source_guard_reject"


def build_replay(
    observation_rows: list[dict[str, str]],
    switch_rows: list[dict[str, str]],
    guard_predictions: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[str]]:
    issues: list[str] = []
    switches_by_key = {row_key(row): row for row in switch_rows}
    predictions_by_key = {row_key(row): row for row in guard_predictions}
    operations: list[dict[str, str]] = []
    decisions: list[dict[str, str]] = []
    total = len(observation_rows)
    outlier_count = sum(1 for row in observation_rows if row.get("selected_outlier") == "1")
    resolved = 0
    unresolved = 0
    false_switches = 0
    false_delta = 0
    total_le2 = 0
    allowed = 0
    blocked_false = 0

    for observation in observation_rows:
        key = row_key(observation)
        switch = switches_by_key.get(key)
        selected_outlier = observation.get("selected_outlier") == "1"
        selected_start = observation.get("selected_start", "")
        selected_delta = int_value(observation, "selected_delta")
        selected_support = observation.get("selected_support_value_hex", "")
        source_value = observation.get("source_value_hex", "")
        chosen_start = selected_start
        chosen_support = selected_support
        chosen_delta = selected_delta
        guard_reason = "selected"
        allowed_switch = False

        if switch:
            allowed_switch, guard_reason = allow_switch(switch, predictions_by_key)
            if allowed_switch:
                allowed += 1
                chosen_start = switch.get("chosen_start", selected_start)
                chosen_support = switch.get("chosen_support_value_hex", selected_support)
                chosen_delta = int_value(switch, "chosen_delta")
            elif switch.get("false_switch") == "1":
                blocked_false += 1
            decisions.append(
                {
                    "pair_id": observation.get("pair_id", ""),
                    "source_id": observation.get("source_id", ""),
                    "byte_index": observation.get("byte_index", ""),
                    "selected_outlier": observation.get("selected_outlier", ""),
                    "false_switch_candidate": switch.get("false_switch", ""),
                    "source_known": switch.get("source_known", ""),
                    "selected_delta_abs_gt2": switch.get("selected_delta_abs_gt2", ""),
                    "guard_predicted_abs_gt2": predictions_by_key.get(key, {}).get("predicted_abs_gt2", ""),
                    "allow_switch": "1" if allowed_switch else "0",
                    "decision_reason": guard_reason,
                    "selected_start": selected_start,
                    "chosen_start": str(chosen_start),
                    "selected_delta": str(selected_delta),
                    "chosen_delta": str(chosen_delta),
                }
            )
        elif selected_outlier:
            issues.append(f"{key[0]}:{key[2]}:missing_switch_for_outlier")

        did_switch = str(chosen_start) != selected_start
        if did_switch and not selected_outlier:
            false_switches += 1
            if abs(chosen_delta) > 2:
                false_delta += 1
        if abs(chosen_delta) <= 2:
            total_le2 += 1
            if selected_outlier:
                resolved += 1
        elif selected_outlier:
            unresolved += 1
        if did_switch or selected_outlier:
            operations.append(
                {
                    "selector_name": SELECTOR_NAME,
                    "pair_id": observation.get("pair_id", ""),
                    "source_id": observation.get("source_id", ""),
                    "byte_index": observation.get("byte_index", ""),
                    "selector_key": observation.get("byte_index", ""),
                    "selected_start": selected_start,
                    "selected_support_value_hex": selected_support,
                    "source_value_hex": source_value,
                    "selected_delta": str(selected_delta),
                    "chosen_start": str(chosen_start),
                    "chosen_support_value_hex": str(chosen_support),
                    "chosen_delta": str(chosen_delta),
                    "selected_outlier": "1" if selected_outlier else "0",
                    "resolved_outlier": "1" if selected_outlier and abs(chosen_delta) <= 2 else "0",
                    "false_switch": "1" if did_switch and not selected_outlier else "0",
                    "guard_reason": guard_reason,
                }
            )

    clean = resolved == outlier_count and unresolved == 0 and false_switches == 0 and false_delta == 0 and total_le2 == total
    verdict = (
        "frontier80_prior_high_row_threshold_source_guard_promoted_replay_ready"
        if clean
        else "frontier80_prior_high_row_threshold_source_guard_promoted_replay_weak"
    )
    next_probe = (
        "integrate threshold source guard into high-row replay promotion"
        if clean
        else "review threshold source guard replay misses before promotion"
    )
    summary = {
        "scope": "total",
        "total_bytes": str(total),
        "outlier_bytes": str(outlier_count),
        "switch_candidate_rows": str(len(switch_rows)),
        "allowed_switch_rows": str(allowed),
        "blocked_false_switch_rows": str(blocked_false),
        "resolved_outliers": str(resolved),
        "unresolved_outliers": str(unresolved),
        "false_switch_bytes": str(false_switches),
        "false_delta_bytes": str(false_delta),
        "total_le2_bytes": str(total_le2),
        "total_le2_ratio": ratio(total_le2, total),
        "issue_rows": str(len(issues)),
        "review_verdict": verdict,
        "next_probe": next_probe,
    }
    return summary, operations, decisions, issues


def render_table(rows: list[dict[str, str]], fields: list[str], limit: int = 240) -> str:
    header = "".join(f"<th>{html.escape(field)}</th>" for field in fields)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(row.get(field, ''))}</td>" for field in fields) + "</tr>"
        for row in rows[:limit]
    )
    return f"<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>"


def build_html(
    summary: dict[str, str],
    operations: list[dict[str, str]],
    decisions: list[dict[str, str]],
    output_dir: Path,
    title: str,
) -> str:
    payload = {"summary": summary, "operations": operations, "decisions": decisions}
    data_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    links = " ".join(
        f'<a href="{html.escape(relative_href(path, output_dir))}">{html.escape(label)}</a>'
        for label, path in (
            ("summary.csv", output_dir / "summary.csv"),
            ("operations.csv", output_dir / "operations.csv"),
            ("guard_decisions.csv", output_dir / "guard_decisions.csv"),
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
  --bg: #101417;
  --panel: #171f22;
  --line: #31424a;
  --text: #edf5f4;
  --muted: #9dafb5;
  --accent: #77d3b1;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.wrap {{ width: min(1680px, calc(100vw - 28px)); margin: 0 auto; }}
header {{ border-bottom: 1px solid var(--line); background: #12191b; padding: 18px 0 14px; }}
h1 {{ margin: 0; font-size: 21px; font-weight: 720; letter-spacing: 0; }}
h2 {{ margin: 0 0 10px; font-size: 16px; }}
.sub {{ color: var(--muted); margin-top: 4px; }}
main {{ padding: 16px 0 28px; display: grid; gap: 16px; }}
.stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 10px; }}
.stat, .panel {{ border: 1px solid var(--line); border-radius: 8px; background: var(--panel); padding: 10px; }}
.label, .muted {{ color: var(--muted); }}
.value {{ font-size: 22px; font-weight: 760; line-height: 1.05; margin-top: 4px; }}
.panel {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; min-width: 1180px; }}
th, td {{ border-top: 1px solid var(--line); padding: 7px 8px; text-align: left; vertical-align: top; }}
th {{ color: var(--muted); font-weight: 600; }}
a {{ color: var(--accent); text-decoration: none; margin-right: 8px; }}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <h1>{html.escape(title)}</h1>
    <div class="sub">Replays high-row byte-local switches gated by the threshold source guard.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Resolved</div><div class="value">{html.escape(summary['resolved_outliers'])}/{html.escape(summary['outlier_bytes'])}</div></div>
    <div class="stat"><div class="label">False switches</div><div class="value">{html.escape(summary['false_switch_bytes'])}</div></div>
    <div class="stat"><div class="label">Total <=2</div><div class="value">{html.escape(summary['total_le2_bytes'])}/{html.escape(summary['total_bytes'])}</div></div>
    <div class="stat"><div class="label">Blocked false</div><div class="value">{html.escape(summary['blocked_false_switch_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="sub">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</div></section>
  <section class="panel"><h2>Operations</h2>{render_table(operations, OPERATION_FIELDNAMES)}</section>
  <section class="panel"><h2>Guard decisions</h2>{render_table(decisions, DECISION_FIELDNAMES)}</section>
</main>
<script type="application/json" id="threshold-source-guard-replay-data">{data_json}</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    observations_path: Path,
    switches_path: Path,
    guard_predictions_path: Path,
    *,
    title: str,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary, operations, decisions, issues = build_replay(
        read_csv(observations_path),
        read_csv(switches_path),
        read_csv(guard_predictions_path),
    )
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "operations.csv", OPERATION_FIELDNAMES, operations)
    write_csv(output_dir / "guard_decisions.csv", DECISION_FIELDNAMES, decisions)
    (output_dir / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output_dir / "index.html").write_text(build_html(summary, operations, decisions, output_dir, title))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay high-row byte-local selector with threshold source guard.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--observations", type=Path, default=DEFAULT_OBSERVATIONS)
    parser.add_argument("--switches", type=Path, default=DEFAULT_SWITCHES)
    parser.add_argument("--guard-predictions", type=Path, default=DEFAULT_GUARD_PREDICTIONS)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Prior High Row Threshold Source Guard Promoted Replay",
    )
    args = parser.parse_args()

    summary = write_report(
        args.output,
        args.observations,
        args.switches,
        args.guard_predictions,
        title=args.title,
    )
    print(f"Resolved outliers: {summary['resolved_outliers']}/{summary['outlier_bytes']}")
    print(f"False switches: {summary['false_switch_bytes']}")
    print(f"Total <=2: {summary['total_le2_bytes']}/{summary['total_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
