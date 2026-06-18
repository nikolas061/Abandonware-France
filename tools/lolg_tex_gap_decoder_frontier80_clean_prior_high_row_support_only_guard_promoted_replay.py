#!/usr/bin/env python3
"""Replay the high-row byte-local selector with a support-only guard."""

from __future__ import annotations

import argparse
import csv
import html
import json
from pathlib import Path

from lolg_tex_gap_opcode_probe import int_value, relative_href, write_csv


DEFAULT_OUTPUT = Path("output/tex_gap_decoder_frontier80_clean_prior_high_row_support_only_guard_promoted_replay")
DEFAULT_OBSERVATIONS = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_byte_local_start_non_oracle_guard_probe/"
    "byte_observations.csv"
)
DEFAULT_OPERATIONS = Path(
    "output/tex_gap_decoder_frontier80_clean_prior_high_row_byte_local_start_non_oracle_guard_probe/"
    "guard_operations.csv"
)

SUMMARY_FIELDNAMES = [
    "scope",
    "selector_name",
    "total_bytes",
    "outlier_bytes",
    "switch_candidate_rows",
    "applied_switch_rows",
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
    "operation_available",
    "allow_switch",
    "decision_reason",
    "selected_start",
    "chosen_start",
    "selected_delta",
    "chosen_delta",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def ratio(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.6f}" if denominator else "0.000000"


def row_key(row: dict[str, str]) -> tuple[str, str, str]:
    return row.get("pair_id", ""), row.get("source_id", ""), row.get("byte_index", "")


def build_replay(
    observation_rows: list[dict[str, str]],
    operation_rows: list[dict[str, str]],
) -> tuple[dict[str, str], list[dict[str, str]], list[dict[str, str]], list[str]]:
    issues: list[str] = []
    operations_by_key = {row_key(row): row for row in operation_rows}
    selector_names = sorted({row.get("selector_name", "") for row in operation_rows if row.get("selector_name", "")})
    selector_name = selector_names[0] if selector_names else ""
    if len(selector_names) > 1:
        issues.append(f"multiple_selector_names:{';'.join(selector_names)}")

    operations: list[dict[str, str]] = []
    decisions: list[dict[str, str]] = []
    total = len(observation_rows)
    outlier_count = sum(1 for row in observation_rows if row.get("selected_outlier") == "1")
    applied = 0
    resolved = 0
    unresolved = 0
    false_switches = 0
    false_delta = 0
    total_le2 = 0

    for observation in observation_rows:
        key = row_key(observation)
        operation = operations_by_key.get(key)
        selected_outlier = observation.get("selected_outlier") == "1"
        selected_start = observation.get("selected_start", "")
        selected_support = observation.get("selected_support_value_hex", "")
        source_value = observation.get("source_value_hex", "")
        selected_delta = int_value(observation, "selected_delta")
        chosen_start = selected_start
        chosen_support = selected_support
        chosen_delta = selected_delta
        guard_reason = "selected"
        allow_switch = False

        if operation:
            allow_switch = True
            applied += 1
            chosen_start = operation.get("chosen_start", selected_start)
            chosen_support = operation.get("chosen_support_value_hex", selected_support)
            chosen_delta = int_value(operation, "chosen_delta")
            guard_reason = "support_only_guard"
        elif selected_outlier:
            issues.append(f"{key[0]}:{key[2]}:missing_support_only_operation_for_outlier")

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

        decisions.append(
            {
                "pair_id": observation.get("pair_id", ""),
                "source_id": observation.get("source_id", ""),
                "byte_index": observation.get("byte_index", ""),
                "selected_outlier": "1" if selected_outlier else "0",
                "operation_available": "1" if operation else "0",
                "allow_switch": "1" if allow_switch else "0",
                "decision_reason": guard_reason,
                "selected_start": selected_start,
                "chosen_start": str(chosen_start),
                "selected_delta": str(selected_delta),
                "chosen_delta": str(chosen_delta),
            }
        )
        if did_switch or selected_outlier:
            operations.append(
                {
                    "selector_name": selector_name,
                    "pair_id": observation.get("pair_id", ""),
                    "source_id": observation.get("source_id", ""),
                    "byte_index": observation.get("byte_index", ""),
                    "selector_key": operation.get("selector_key", "") if operation else "",
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

    clean = (
        resolved == outlier_count
        and unresolved == 0
        and false_switches == 0
        and false_delta == 0
        and total_le2 == total
        and not issues
    )
    verdict = (
        "frontier80_prior_high_row_support_only_guard_promoted_replay_ready"
        if clean
        else "frontier80_prior_high_row_support_only_guard_promoted_replay_weak"
    )
    next_probe = (
        "integrate support-only guard into high-row replay promotion"
        if clean
        else "review support-only guard replay misses before promotion"
    )
    summary = {
        "scope": "total",
        "selector_name": selector_name,
        "total_bytes": str(total),
        "outlier_bytes": str(outlier_count),
        "switch_candidate_rows": str(len(operation_rows)),
        "applied_switch_rows": str(applied),
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
    <div class="sub">Replays support-only byte-local high-row guard operations without source-dependent inputs.</div>
  </div>
</header>
<main class="wrap">
  <section class="stats">
    <div class="stat"><div class="label">Resolved</div><div class="value">{html.escape(summary['resolved_outliers'])}/{html.escape(summary['outlier_bytes'])}</div></div>
    <div class="stat"><div class="label">False switches</div><div class="value">{html.escape(summary['false_switch_bytes'])}</div></div>
    <div class="stat"><div class="label">Total &lt;=2</div><div class="value">{html.escape(summary['total_le2_bytes'])}/{html.escape(summary['total_bytes'])}</div></div>
    <div class="stat"><div class="label">Applied switches</div><div class="value">{html.escape(summary['applied_switch_rows'])}</div></div>
  </section>
  <section class="panel"><div>{links}</div><div class="sub">{html.escape(summary['review_verdict'])}: {html.escape(summary['next_probe'])}</div></section>
  <section class="panel"><h2>Operations</h2>{render_table(operations, OPERATION_FIELDNAMES)}</section>
  <section class="panel"><h2>Guard decisions</h2>{render_table(decisions, DECISION_FIELDNAMES)}</section>
</main>
<script type="application/json" id="support-only-guard-replay-data">{data_json}</script>
</body>
</html>
"""


def write_report(
    output_dir: Path,
    observations_path: Path,
    operations_path: Path,
    *,
    title: str,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary, operations, decisions, issues = build_replay(
        read_csv(observations_path),
        read_csv(operations_path),
    )
    write_csv(output_dir / "summary.csv", SUMMARY_FIELDNAMES, [summary])
    write_csv(output_dir / "operations.csv", OPERATION_FIELDNAMES, operations)
    write_csv(output_dir / "guard_decisions.csv", DECISION_FIELDNAMES, decisions)
    (output_dir / "issues.txt").write_text("\n".join(issues) + ("\n" if issues else ""))
    (output_dir / "index.html").write_text(build_html(summary, operations, decisions, output_dir, title))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay high-row byte-local selector with a support-only guard.")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--observations", type=Path, default=DEFAULT_OBSERVATIONS)
    parser.add_argument("--operations", type=Path, default=DEFAULT_OPERATIONS)
    parser.add_argument(
        "--title",
        default="Lands of Lore II .tex Frontier80 Prior High Row Support-Only Guard Promoted Replay",
    )
    args = parser.parse_args()

    summary = write_report(
        args.output,
        args.observations,
        args.operations,
        title=args.title,
    )
    print(f"Resolved outliers: {summary['resolved_outliers']}/{summary['outlier_bytes']}")
    print(f"False switches: {summary['false_switch_bytes']}")
    print(f"Total <=2: {summary['total_le2_bytes']}/{summary['total_bytes']}")
    print(f"Verdict: {summary['review_verdict']}")
    print(f"HTML: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
